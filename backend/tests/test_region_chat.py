"""Tests for evidence-scoped conversational GeoChat region chat."""

from __future__ import annotations

import os
import subprocess
import sys
import time

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.rsvlm.development import DevelopmentGeoChatVLM
from app.adapters.rsvlm.factory import get_geochat_vlm
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.main import app
from app.schemas.vqa import SingleImageVQAResult, VQAProviderKind, VQATask
from app.services.region_chat import (
    MAX_CONVERSATION_TURNS,
    build_region_chat_prompt,
    is_out_of_scope_message,
    region_chat_service,
)
from app.services.session_store import session_store
from tests.fixtures.rasters import write_bi_temporal_scene

from pathlib import Path

GEOCHAT_SERVICE_ROOT = Path(__file__).resolve().parents[2] / "services" / "geochat"


@pytest.fixture
def upload_root(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(root))
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "8")
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "development")
    monkeypatch.setenv("GEOCHAT_SERVICE_URL", "")
    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "bi_temporal")
    get_settings.cache_clear()
    from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
    from app.storage.factory import get_image_storage, get_metadata_registry

    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    get_uploaded_imagery_provider.cache_clear()
    get_geochat_vlm.cache_clear()
    session_store._conversations.clear()
    yield root
    session_store._conversations.clear()
    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    get_uploaded_imagery_provider.cache_clear()
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
async def client(upload_root):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _submit_bi_temporal(client: AsyncClient, upload_root) -> tuple[str, str]:
    earlier_path = upload_root / "bt_before.tif"
    later_path = upload_root / "bt_after.tif"
    write_bi_temporal_scene(earlier_path, role="earlier", scenario="vegetation_loss")
    write_bi_temporal_scene(later_path, role="later", scenario="vegetation_loss")

    async def upload(path, dt: str) -> str:
        with path.open("rb") as handle:
            res = await client.post(
                "/api/v1/imagery/upload",
                files={"file": (path.name, handle, "image/tiff")},
                data={"modality": "multispectral", "acquisition_datetime": dt},
            )
        assert res.status_code == 200
        return res.json()["data"]["image"]["id"]

    earlier_id = await upload(earlier_path, "2023-01-01T00:00:00Z")
    later_id = await upload(later_path, "2024-01-01T00:00:00Z")
    query = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "What changed between these two dates, and where did the change occur?",
            "earlier_image_id": earlier_id,
            "later_image_id": later_id,
        },
    )
    assert query.status_code == 200
    payload = query.json()["data"]
    return payload["session_id"], payload["result"]["evidence"][0]["id"]


async def _chat(client, session_id: str, region_id: str, message: str):
    return await client.post(
        f"/api/v1/query/{session_id}/regions/{region_id}/chat",
        json={"message": message},
    )


@pytest.mark.asyncio
async def test_first_chat_turn(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    before = await client.get(f"/api/v1/query/{session_id}/result")
    evidence_before = before.json()["data"]["evidence"]

    res = await _chat(client, session_id, region_id, "Why do you think this is vegetation loss?")
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["task"] == "bi_temporal_region_chat"
    assert chat["turn_index"] == 0
    assert chat["conversation_id"]
    assert chat["turn_id"]
    assert chat["detector"] == "uploaded_bi_temporal"
    assert chat["provider"] == "development"
    assert "[development mock" in chat["answer"]
    assert chat["conversation"]["turns"][0]["user_message"].startswith("Why do you think")
    assert res.json()["data"]["trace_step"]["tool_name"] == "geochat_region_chat"

    after = await client.get(f"/api/v1/query/{session_id}/result")
    assert after.json()["data"]["evidence"] == evidence_before


@pytest.mark.asyncio
async def test_follow_up_turn_includes_history(client, upload_root, monkeypatch):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    captured: dict = {}

    async def capture_composite(self, **kwargs):
        captured["question"] = kwargs["question"]
        return SingleImageVQAResult(
            task=VQATask.SINGLE_IMAGE_VQA,
            answer="Follow-up mock answer.",
            model_name="development-mock-geochat",
            model_version="0.0.0-dev",
            provider=VQAProviderKind.DEVELOPMENT,
            provenance="mock",
            input_image_id=kwargs["composite_image_id"],
            requested_modality="optical",
        )

    monkeypatch.setattr(DevelopmentGeoChatVLM, "run_composite_vqa", capture_composite)
    get_geochat_vlm.cache_clear()

    first = await _chat(client, session_id, region_id, "What changed here?")
    assert first.status_code == 200
    second = await _chat(client, session_id, region_id, "Can you explain the edges?")
    assert second.status_code == 200
    assert second.json()["data"]["chat"]["turn_index"] == 1
    assert len(second.json()["data"]["chat"]["conversation"]["turns"]) == 2
    assert "User: What changed here?" in captured.get("question", "")
    assert "Assistant:" in captured.get("question", "")


@pytest.mark.asyncio
async def test_different_regions_have_independent_conversations(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res1 = await _chat(client, session_id, region_id, "Region one question")
    assert res1.status_code == 200
    conv1 = res1.json()["data"]["chat"]["conversation_id"]

    res2 = await _chat(client, session_id, "missing-region", "Other region")
    assert res2.status_code == 404

    # Same region keeps conversation id
    res3 = await _chat(client, session_id, region_id, "Follow up")
    assert res3.status_code == 200
    assert res3.json()["data"]["chat"]["conversation_id"] == conv1


@pytest.mark.asyncio
async def test_different_sessions_have_independent_conversations(client, upload_root):
    session_a, region_a = await _submit_bi_temporal(client, upload_root)
    session_b, region_b = await _submit_bi_temporal(client, upload_root)
    res_a = await _chat(client, session_a, region_a, "Session A")
    res_b = await _chat(client, session_b, region_b, "Session B")
    assert res_a.json()["data"]["chat"]["conversation_id"] != res_b.json()["data"]["chat"]["conversation_id"]


@pytest.mark.asyncio
async def test_unknown_session(client):
    res = await _chat(client, "00000000-0000-0000-0000-000000000000", "change-region-01", "Hi")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "session_not_found"


@pytest.mark.asyncio
async def test_unknown_region(client, upload_root):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    res = await _chat(client, session_id, "missing-region", "Hi")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "region_not_found"


@pytest.mark.asyncio
async def test_non_bi_temporal_session(client, upload_root):
    path = upload_root / "single.tif"
    write_bi_temporal_scene(path, role="earlier", scenario="vegetation_loss")
    with path.open("rb") as handle:
        upload = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("single.tif", handle, "image/tiff")},
            data={"modality": "multispectral"},
        )
    image_id = upload.json()["data"]["image"]["id"]
    query = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe this scene.", "image_id": image_id},
    )
    session_id = query.json()["data"]["session_id"]
    res = await _chat(client, session_id, "change-region-01", "Hi")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "not_bi_temporal_session"


@pytest.mark.asyncio
async def test_invalid_empty_message(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await client.post(
        f"/api/v1/query/{session_id}/regions/{region_id}/chat",
        json={"message": "   "},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_history_limit_enforced(client, upload_root, monkeypatch):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    monkeypatch.setattr("app.services.region_chat.MAX_CONVERSATION_TURNS", 2)

    assert (await _chat(client, session_id, region_id, "Turn 0")).status_code == 200
    assert (await _chat(client, session_id, region_id, "Turn 1")).status_code == 200
    res = await _chat(client, session_id, region_id, "Turn 2")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "conversation_history_too_large"


@pytest.mark.asyncio
async def test_out_of_scope_message_is_scope_limited(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await _chat(client, session_id, region_id, "Find other changed areas in the whole city")
    assert res.status_code == 200
    chat = res.json()["data"]["chat"]
    assert chat["scope_limited"] is True
    assert chat["inference_metadata"]["geochat_called"] is False
    assert "new analysis" in chat["answer"].lower()


@pytest.mark.asyncio
async def test_geochat_service_unavailable(client, upload_root, monkeypatch):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)

    async def fail_composite(self, **kwargs):
        raise SatQueryError("geochat_service_error", "Service down.", status_code=502)

    monkeypatch.setattr(DevelopmentGeoChatVLM, "run_composite_vqa", fail_composite)
    get_geochat_vlm.cache_clear()

    res = await _chat(client, session_id, region_id, "Explain this change")
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "geochat_service_error"


@pytest.mark.asyncio
async def test_geochat_timeout(client, upload_root, monkeypatch):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)

    async def timeout_composite(self, **kwargs):
        raise SatQueryError("geochat_service_timeout", "Timed out.", status_code=504)

    monkeypatch.setattr(DevelopmentGeoChatVLM, "run_composite_vqa", timeout_composite)
    get_geochat_vlm.cache_clear()

    res = await _chat(client, session_id, region_id, "Explain this change")
    assert res.status_code == 504
    assert res.json()["error"]["code"] == "geochat_service_timeout"


@pytest.mark.asyncio
async def test_geochat_malformed_response(client, upload_root, monkeypatch):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)

    async def empty_composite(self, **kwargs):
        raise SatQueryError(
            "geochat_malformed_response",
            "GeoChat inference service returned an empty or missing answer.",
            status_code=502,
        )

    monkeypatch.setattr(DevelopmentGeoChatVLM, "run_composite_vqa", empty_composite)
    get_geochat_vlm.cache_clear()

    res = await _chat(client, session_id, region_id, "Explain this change")
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "geochat_malformed_response"


def test_factory_requires_service_url_no_silent_fallback(monkeypatch):
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "geochat_service")
    monkeypatch.setenv("GEOCHAT_SERVICE_URL", "")
    get_settings.cache_clear()
    get_geochat_vlm.cache_clear()
    with pytest.raises(SatQueryError) as exc:
        get_geochat_vlm()
    assert exc.value.code == "geochat_service_misconfigured"
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


def test_build_chat_prompt_contains_guardrails_and_history():
    from app.schemas.bi_temporal_change import BiTemporalChangeProviderKind, BiTemporalChangeResult
    from app.schemas.domain import AnalysisResult, AnalysisStatus, DataMode, EvidenceRegion, GeoJSONGeometry
    from app.services.session_store import ConversationTurn

    region = EvidenceRegion(
        id="change-region-01",
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[[[77.591, 12.991], [77.593, 12.991], [77.593, 12.993], [77.591, 12.993], [77.591, 12.991]]],
        ),
        confidence=0.47,
        source="uploaded_bi_temporal",
        metadata={"change_direction_hint": "vegetation_loss", "claim_type": "none"},
    )
    result = AnalysisResult(
        status=AnalysisStatus.COMPLETED,
        session_id="sess",
        answer="Detected change",
        confidence=0.47,
        confidence_available=True,
        evidence=[region],
        trace=[],
        mode=DataMode.DEVELOPMENT,
        bi_temporal_change=BiTemporalChangeResult(
            change_summary="Change detected",
            question="What changed?",
            changed_region_count=1,
            detector="uploaded_bi_temporal",
            provider=BiTemporalChangeProviderKind.UPLOADED_CVA,
            provenance="test",
            earlier_image_id="a" * 32,
            later_image_id="b" * 32,
            earlier_acquisition=__import__("datetime").datetime(2023, 1, 1, tzinfo=__import__("datetime").timezone.utc),
            later_acquisition=__import__("datetime").datetime(2024, 1, 1, tzinfo=__import__("datetime").timezone.utc),
            earlier_date=__import__("datetime").date(2023, 1, 1),
            later_date=__import__("datetime").date(2024, 1, 1),
        ),
    )
    prompt = build_region_chat_prompt(
        region=region,
        result=result,
        message="Why vegetation loss?",
        prior_turns=[
            ConversationTurn(
                turn_id="t0",
                turn_index=0,
                user_message="What changed?",
                assistant_answer="Vegetation decreased.",
            )
        ],
    )
    assert "Do NOT invent" in prompt
    assert "uploaded_bi_temporal" in prompt
    assert "Claim type" in prompt
    assert "User: What changed?" in prompt
    assert "Current user message: Why vegetation loss?" in prompt


def test_out_of_scope_detector():
    assert is_out_of_scope_message("Find other changed areas")
    assert not is_out_of_scope_message("Why is vegetation lower here?")


@pytest.mark.asyncio
async def test_real_provider_contract_with_fake_service(client, upload_root, monkeypatch):
    port = 19877
    env = {
        **os.environ,
        "GEOCHAT_SERVICE_FAKE_ENGINE": "true",
        "GEOCHAT_SERVICE_PORT": str(port),
        "GEOCHAT_EAGER_LOAD": "false",
        "PYTHONPATH": str(GEOCHAT_SERVICE_ROOT),
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "geochat_service.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(GEOCHAT_SERVICE_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                if httpx.get(f"{url}/health", timeout=1.0).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        else:
            pytest.skip("Fake GeoChat service did not start.")

        monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "geochat_service")
        monkeypatch.setenv("GEOCHAT_SERVICE_URL", url)
        get_settings.cache_clear()
        get_geochat_vlm.cache_clear()

        session_id, region_id = await _submit_bi_temporal(client, upload_root)
        res = await _chat(client, session_id, region_id, "Describe the visible change.")
        assert res.status_code == 200
        chat = res.json()["data"]["chat"]
        assert chat["provider"] == "geochat_service"
        assert chat["model_name"] == "MBZUAI/geochat-7B"
        assert "development mock" not in chat["answer"].lower()
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        get_geochat_vlm.cache_clear()
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_trace_metadata_contains_conversation_fields(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await _chat(client, session_id, region_id, "Trace metadata check")
    trace = res.json()["data"]["trace_step"]
    assert trace["tool_name"] == "geochat_region_chat"
    meta = trace["metadata"]
    assert meta["region_id"] == region_id
    assert meta["conversation_id"]
    assert meta["provider"] == "development"
    assert meta["evidence_inputs"] == "before_after_composite_crop"
