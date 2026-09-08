"""Tests for session-scoped conversational chat (catalog/upload/cross-modal)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_region_chat import upload_root  # noqa: F401


@pytest.fixture
async def client(upload_root):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _submit_catalog(client: AsyncClient) -> tuple[str, str, str]:
    query = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "Show me significant new construction.",
            "aoi": {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [77.591, 12.991],
                            [77.593, 12.991],
                            [77.593, 12.993],
                            [77.591, 12.993],
                            [77.591, 12.991],
                        ]
                    ],
                },
                "area_km2": 4.8,
            },
            "earlier_date": "2024-12-01",
            "later_date": "2025-03-01",
            "demo_mode": True,
        },
    )
    assert query.status_code == 200
    payload = query.json()["data"]
    session_id = payload["session_id"]
    analysis_answer = payload["result"]["answer"]
    region_id = payload["result"]["evidence"][0]["id"]
    return session_id, region_id, analysis_answer


async def _session_chat(client: AsyncClient, session_id: str, message: str, region_id: str | None = None):
    body = {"message": message}
    if region_id:
        body["region_id"] = region_id
    return await client.post(f"/api/v1/query/{session_id}/chat", json=body)


@pytest.mark.asyncio
async def test_hello_does_not_return_analysis_template(client, upload_root):
    session_id, _, analysis_answer = await _submit_catalog(client)
    res = await _session_chat(client, session_id, "hello")
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["answer"] != analysis_answer
    assert "Found 3 significant spectral change regions" not in chat["answer"]
    assert chat["route"] == "general"
    assert chat["provider"] == "groq"


@pytest.mark.asyncio
async def test_conversational_development_mock_responds(client, upload_root):
    session_id, region_id, _ = await _submit_catalog(client)
    res = await _session_chat(
        client,
        session_id,
        "Why do you think this is vegetation loss?",
        region_id=region_id,
    )
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["provider"] == "development"
    assert "region" in chat["answer"].lower()
    assert "Found 3 significant spectral change regions" not in chat["answer"]


@pytest.mark.asyncio
async def test_first_turn_creates_conversation(client, upload_root):
    session_id, _, _ = await _submit_catalog(client)
    res = await _session_chat(client, session_id, "hello")
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["turn_index"] == 0
    assert chat["conversation_id"]
    assert len(chat["conversation"]["turns"]) == 1
    assert res.json()["data"]["trace_step"]["tool_name"] == "session_chat"


@pytest.mark.asyncio
async def test_second_turn_preserves_history(client, upload_root):
    session_id, _, _ = await _submit_catalog(client)
    first = await _session_chat(client, session_id, "hello")
    second = await _session_chat(client, session_id, "What is the strongest change signal?")
    assert first.status_code == 200
    assert second.status_code == 200
    chat = second.json()["data"]["chat"]
    assert chat["turn_index"] == 1
    assert chat["conversation_id"] == first.json()["data"]["chat"]["conversation_id"]
    assert len(chat["conversation"]["turns"]) == 2
    assert chat["conversation"]["turns"][0]["user_message"] == "hello"
    assert chat["answer"] != first.json()["data"]["chat"]["answer"]


@pytest.mark.asyncio
async def test_chat_does_not_mutate_analysis_result(client, upload_root):
    session_id, _, _ = await _submit_catalog(client)
    before = await client.get(f"/api/v1/query/{session_id}/result")
    assert before.status_code == 200
    original_answer = before.json()["data"]["answer"]

    res = await _session_chat(client, session_id, "on what basis are you publishing these findings")
    assert res.status_code == 200
    assert "Found 3 significant spectral change regions matching your query" not in res.json()["data"]["chat"]["answer"]

    after = await client.get(f"/api/v1/query/{session_id}/result")
    assert after.json()["data"]["answer"] == original_answer


@pytest.mark.asyncio
async def test_bi_temporal_session_rejects_session_chat(client, upload_root):
    from tests.test_region_chat import _submit_bi_temporal

    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await _session_chat(client, session_id, "hello", region_id=region_id)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "use_region_chat"
