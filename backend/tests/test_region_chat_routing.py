"""Tests for Groq general assistant adapter and region chat routing integration."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.llm.groq_service import GroqApiAssistant, get_groq_assistant
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.main import app
from app.services.region_chat_router import classify_region_chat_message
from tests.test_region_chat import _chat, _submit_bi_temporal, upload_root  # noqa: F401


@pytest.fixture
async def client(upload_root):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_general_question_routes_to_groq_development(client, upload_root, monkeypatch):
    monkeypatch.setenv("GROQ_PROVIDER", "development")
    get_settings.cache_clear()
    get_groq_assistant.cache_clear()

    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await _chat(client, session_id, region_id, "What is a binary search tree?")
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["route"] == "general"
    assert chat["provider"] == "groq"
    assert chat["scope"] == "general_assistant"
    assert chat["evidence_inputs"] == "general_assistant_no_imagery"
    assert chat["scope_limited"] is False
    assert chat["inference_metadata"]["groq_called"] is False
    assert chat["inference_metadata"]["development_mock"] is True
    assert chat["inference_metadata"]["geochat_called"] is False
    assert "hi" in chat["answer"].lower() or "hello" in chat["answer"].lower() or "general assistant" in chat["answer"].lower()


@pytest.mark.asyncio
async def test_geo_question_still_routes_to_geochat(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await _chat(client, session_id, region_id, "Why do you think this is vegetation loss?")
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["route"] == "geo"
    assert chat["provider"] == "development"
    assert chat["scope"] == "selected_region"
    assert chat["evidence_inputs"] == "before_after_composite_crop"
    assert chat["inference_metadata"]["geochat_called"] is True


@pytest.mark.asyncio
async def test_out_of_scope_geo_not_routed_to_groq(client, upload_root, monkeypatch):
    monkeypatch.setenv("GROQ_PROVIDER", "development")
    get_settings.cache_clear()
    get_groq_assistant.cache_clear()

    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await _chat(client, session_id, region_id, "Find every changed area in the city.")
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["route"] == "geo"
    assert chat["scope_limited"] is True
    assert chat["inference_metadata"]["geochat_called"] is False
    assert chat["inference_metadata"].get("groq_called") is not True


@pytest.mark.asyncio
async def test_groq_not_configured_falls_back_to_development_demo(client, upload_root, monkeypatch):
    monkeypatch.setenv("GROQ_PROVIDER", "groq_api")
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    get_groq_assistant.cache_clear()

    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await _chat(client, session_id, region_id, "What does HTTP 404 mean?")
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["route"] == "general"
    assert chat["inference_metadata"]["development_mock"] is True
    assert chat["inference_metadata"]["groq_fallback"] is True
    assert chat["inference_metadata"]["groq_called"] is False


@pytest.mark.asyncio
async def test_groq_timeout_falls_back_to_development_demo(client, upload_root, monkeypatch):
    monkeypatch.setenv("GROQ_PROVIDER", "groq_api")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key")
    get_settings.cache_clear()
    get_groq_assistant.cache_clear()

    async def timeout_complete(self, *args, **kwargs):
        raise SatQueryError("groq_service_timeout", "Timed out.", status_code=504)

    monkeypatch.setattr(GroqApiAssistant, "complete", timeout_complete)

    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await _chat(client, session_id, region_id, "Tell me a joke.")
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["inference_metadata"]["development_mock"] is True
    assert chat["inference_metadata"]["groq_fallback"] is True


@pytest.mark.asyncio
async def test_geochat_service_failure_falls_back_to_development_mock(client, upload_root, monkeypatch):
    from app.adapters.rsvlm.factory import get_geochat_vlm

    monkeypatch.setenv("GROQ_PROVIDER", "development")
    get_settings.cache_clear()
    get_groq_assistant.cache_clear()

    class FailingServiceVLM:
        async def run_composite_vqa(self, **kwargs):
            raise SatQueryError("geochat_service_error", "Service down.", status_code=502)

    monkeypatch.setattr("app.services.region_chat.get_geochat_vlm", lambda: FailingServiceVLM())
    get_geochat_vlm.cache_clear()

    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await _chat(client, session_id, region_id, "Explain the detected change.")
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["provider"] == "development"
    assert chat["inference_metadata"]["geochat_fallback"] is True
    assert chat["inference_metadata"]["development_mock"] is True


def test_classifier_distinguishes_geo_from_general():
    geo = classify_region_chat_message(
        "What visible change occurred between the two dates?",
        region_id="change-region-01",
    )
    general = classify_region_chat_message(
        "What is a binary search tree?",
        region_id="change-region-01",
    )
    assert geo.route == "geo"
    assert general.route == "general"
