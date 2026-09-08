"""Tests for evidence-grounded GeoChat region interpretation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.rsvlm.development import DevelopmentGeoChatVLM
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.main import app
from app.schemas.vqa import SingleImageVQAResult, VQAProviderKind, VQATask
from app.services.region_interpretation import (
    build_evidence_prompt,
    format_preview_bbox,
    padded_bbox_from_geometry,
)
from tests.fixtures.rasters import write_bi_temporal_scene


@pytest.fixture
def upload_root(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(root))
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "8")
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "development")
    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "bi_temporal")
    get_settings.cache_clear()
    from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
    from app.adapters.rsvlm.factory import get_geochat_vlm
    from app.storage.factory import get_image_storage, get_metadata_registry

    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    get_uploaded_imagery_provider.cache_clear()
    get_geochat_vlm.cache_clear()
    yield root
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


@pytest.mark.asyncio
async def test_interpret_region_valid_session(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    before = await client.get(f"/api/v1/query/{session_id}/result")
    evidence_before = before.json()["data"]["evidence"]

    res = await client.post(
        f"/api/v1/query/{session_id}/regions/{region_id}/interpret",
        json={"question": "What visible change occurred in this detected region between the two dates?"},
    )
    assert res.status_code == 200
    body = res.json()["data"]
    interpretation = body["interpretation"]
    assert interpretation["task"] == "bi_temporal_region_interpretation"
    assert interpretation["region_id"] == region_id
    assert interpretation["session_id"] == session_id
    assert interpretation["detector"] == "uploaded_bi_temporal"
    assert interpretation["provider"] == "development"
    assert interpretation["evidence_inputs"] == "before_after_composite_crop"
    assert interpretation["preview_bbox_wgs84"]
    assert "[development mock" in interpretation["answer"]
    assert body["trace_step"]["tool_name"] == "geochat_region_interpretation"
    assert body["trace_step"]["metadata"]["region_id"] == region_id
    assert body["trace_step"]["metadata"]["evidence_inputs"] == "before_after_composite_crop"

    after = await client.get(f"/api/v1/query/{session_id}/result")
    assert after.json()["data"]["evidence"] == evidence_before


@pytest.mark.asyncio
async def test_interpret_region_unknown_session(client):
    res = await client.post(
        "/api/v1/query/00000000-0000-0000-0000-000000000000/regions/change-region-01/interpret",
        json={"question": "What changed here?"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "session_not_found"


@pytest.mark.asyncio
async def test_interpret_region_unknown_region(client, upload_root):
    session_id, _region_id = await _submit_bi_temporal(client, upload_root)
    res = await client.post(
        f"/api/v1/query/{session_id}/regions/missing-region/interpret",
        json={"question": "What changed here?"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "region_not_found"


@pytest.mark.asyncio
async def test_interpret_region_non_bi_temporal_session(client, upload_root):
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
    res = await client.post(
        f"/api/v1/query/{session_id}/regions/change-region-01/interpret",
        json={"question": "What changed here?"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "not_bi_temporal_session"


@pytest.mark.asyncio
async def test_interpret_region_preview_failure(client, upload_root, monkeypatch):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    monkeypatch.setattr(
        "app.services.region_interpretation.render_before_after_composite",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SatQueryError("preview_render_failed", "Could not render crop.", status_code=422)
        ),
    )
    res = await client.post(
        f"/api/v1/query/{session_id}/regions/{region_id}/interpret",
        json={"question": "What changed here?"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "preview_render_failed"


@pytest.mark.asyncio
async def test_interpret_region_geochat_service_unavailable(client, upload_root, monkeypatch):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)

    async def fail_composite(self, **kwargs):
        raise SatQueryError("geochat_service_error", "Service down.", status_code=502)

    monkeypatch.setattr(DevelopmentGeoChatVLM, "run_composite_vqa", fail_composite)
    from app.adapters.rsvlm.factory import get_geochat_vlm

    get_geochat_vlm.cache_clear()

    res = await client.post(
        f"/api/v1/query/{session_id}/regions/{region_id}/interpret",
        json={"question": "What changed here?"},
    )
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "geochat_service_error"


@pytest.mark.asyncio
async def test_interpret_region_geochat_timeout(client, upload_root, monkeypatch):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)

    async def timeout_composite(self, **kwargs):
        raise SatQueryError("geochat_service_timeout", "Timed out.", status_code=504)

    monkeypatch.setattr(DevelopmentGeoChatVLM, "run_composite_vqa", timeout_composite)
    from app.adapters.rsvlm.factory import get_geochat_vlm

    get_geochat_vlm.cache_clear()

    res = await client.post(
        f"/api/v1/query/{session_id}/regions/{region_id}/interpret",
        json={"question": "What changed here?"},
    )
    assert res.status_code == 504
    assert res.json()["error"]["code"] == "geochat_service_timeout"


@pytest.mark.asyncio
async def test_interpret_region_passes_composite_bytes_not_paths(client, upload_root, monkeypatch):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    captured: dict = {}

    async def capture_composite(self, **kwargs):
        captured.update(kwargs)
        return SingleImageVQAResult(
            task=VQATask.SINGLE_IMAGE_VQA,
            answer="Composite interpretation.",
            model_name="test-model",
            model_version="1.0.0",
            provider=VQAProviderKind.DEVELOPMENT,
            provenance="test",
            input_image_id=kwargs["composite_image_id"],
            requested_modality="optical",
        )

    monkeypatch.setattr(DevelopmentGeoChatVLM, "run_composite_vqa", capture_composite)
    from app.adapters.rsvlm.factory import get_geochat_vlm

    get_geochat_vlm.cache_clear()

    res = await client.post(
        f"/api/v1/query/{session_id}/regions/{region_id}/interpret",
        json={"question": "What changed here?"},
    )
    assert res.status_code == 200
    assert isinstance(captured.get("composite_png"), bytes)
    assert captured["composite_png"][:8] == b"\x89PNG\r\n\x1a\n"
    assert "path" not in captured


def test_build_evidence_prompt_contains_context():
    from app.schemas.bi_temporal_change import BiTemporalChangeProviderKind, BiTemporalChangeResult
    from app.schemas.domain import AnalysisResult, AnalysisStatus, DataMode, EvidenceRegion, GeoJSONGeometry

    region = EvidenceRegion(
        id="change-region-01",
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[[[77.591, 12.991], [77.593, 12.991], [77.593, 12.993], [77.591, 12.993], [77.591, 12.991]]],
        ),
        confidence=0.47,
        source="uploaded_bi_temporal",
        metadata={"change_direction_hint": "vegetation_loss", "evidence_modality": "optical"},
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
            earlier_acquisition=datetime(2023, 1, 1, tzinfo=timezone.utc),
            later_acquisition=datetime(2024, 1, 1, tzinfo=timezone.utc),
            earlier_date=datetime(2023, 1, 1).date(),
            later_date=datetime(2024, 1, 1).date(),
        ),
    )
    prompt = build_evidence_prompt(
        region=region,
        result=result,
        question="What visible change occurred here?",
    )
    assert "Region ID: change-region-01" in prompt
    assert "uploaded_bi_temporal" in prompt
    assert "Do NOT decide whether change exists" in prompt
    assert "LEFT panel = BEFORE" in prompt


def test_padded_bbox_matches_preview_convention():
    geometry = {
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
    }
    bbox = padded_bbox_from_geometry(geometry)
    assert format_preview_bbox(bbox) == "77.590500,12.990500,77.593500,12.993500"
