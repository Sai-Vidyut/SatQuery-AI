"""Tests for bi-temporal region evidence export."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.main import app
from app.services.region_evidence_export import (
    build_export_metadata,
    build_region_geojson_feature,
    serialize_conversation,
)
from app.services.session_store import ConversationTurn, session_store
from tests.fixtures.rasters import write_bi_temporal_scene


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
    from app.adapters.rsvlm.factory import get_geochat_vlm
    from app.storage.factory import get_image_storage, get_metadata_registry

    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    get_uploaded_imagery_provider.cache_clear()
    get_geochat_vlm.cache_clear()
    session_store._conversations.clear()
    session_store._interpretations.clear()
    yield root
    session_store._conversations.clear()
    session_store._interpretations.clear()
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


def _read_zip(content: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


@pytest.mark.asyncio
async def test_export_success_for_valid_bi_temporal_session(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/evidence")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert "attachment" in res.headers["content-disposition"]
    assert session_id[:8] in res.headers["content-disposition"]
    assert region_id in res.headers["content-disposition"]


@pytest.mark.asyncio
async def test_export_zip_contains_expected_files(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/evidence")
    files = _read_zip(res.content)
    assert set(files) >= {"metadata.json", "region.geojson", "before.png", "after.png", "trace.json"}
    assert "interpretation.json" not in files
    assert "chat.json" not in files


@pytest.mark.asyncio
async def test_export_pngs_are_valid(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/evidence")
    files = _read_zip(res.content)
    for name in ("before.png", "after.png"):
        image = Image.open(io.BytesIO(files[name]))
        assert image.format == "PNG"
        assert image.width > 0 and image.height > 0


@pytest.mark.asyncio
async def test_export_geojson_matches_selected_region(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    result = (await client.get(f"/api/v1/query/{session_id}/result")).json()["data"]
    region = next(item for item in result["evidence"] if item["id"] == region_id)

    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/evidence")
    feature = json.loads(_read_zip(res.content)["region.geojson"])
    assert feature["type"] == "Feature"
    assert feature["geometry"] == region["geometry"]
    assert feature["properties"]["id"] == region_id
    assert feature["properties"]["confidence"] == region["confidence"]
    assert feature["properties"]["source"] == region["source"]
    assert feature["properties"]["metadata"] == region["metadata"]


@pytest.mark.asyncio
async def test_export_metadata_uses_authoritative_detector_values(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    result = (await client.get(f"/api/v1/query/{session_id}/result")).json()["data"]
    region = next(item for item in result["evidence"] if item["id"] == region_id)
    bt = result["bi_temporal_change"]

    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/evidence")
    metadata = json.loads(_read_zip(res.content)["metadata.json"])
    assert metadata["session_id"] == session_id
    assert metadata["region_id"] == region_id
    assert metadata["workflow_type"] == "bi_temporal_change_vqa"
    assert metadata["detector"] == bt["detector"] == "uploaded_bi_temporal"
    assert metadata["region_confidence"] == region["confidence"]
    assert metadata["confidence_kind"] == "histogram_separability"
    assert metadata["source_image_ids"]["earlier_image_id"] == bt["earlier_image_id"]
    assert metadata["source_image_ids"]["later_image_id"] == bt["later_image_id"]
    assert metadata["preview_bbox_wgs84"]
    assert metadata["exported_at"]


@pytest.mark.asyncio
async def test_export_includes_latest_interpretation_when_available(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    interpret = await client.post(
        f"/api/v1/query/{session_id}/regions/{region_id}/interpret",
        json={"question": "What visible change occurred in this detected region between the two dates?"},
    )
    assert interpret.status_code == 200
    interpretation = interpret.json()["data"]["interpretation"]

    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/evidence")
    exported = json.loads(_read_zip(res.content)["interpretation.json"])
    assert exported["task"] == "bi_temporal_region_interpretation"
    assert exported["answer"] == interpretation["answer"]
    assert exported["region_id"] == region_id
    assert exported["provider"] == interpretation["provider"]


@pytest.mark.asyncio
async def test_export_includes_region_chat_when_available(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    chat = await client.post(
        f"/api/v1/query/{session_id}/regions/{region_id}/chat",
        json={"message": "Why do you think this is vegetation loss?"},
    )
    assert chat.status_code == 200
    conversation = chat.json()["data"]["chat"]["conversation"]

    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/evidence")
    exported = json.loads(_read_zip(res.content)["chat.json"])
    assert exported["conversation_id"] == conversation["conversation_id"]
    assert exported["region_id"] == region_id
    assert len(exported["turns"]) == 1
    assert exported["turns"][0]["user_message"].startswith("Why do you think")


@pytest.mark.asyncio
async def test_export_excludes_other_region_chat(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    await client.post(
        f"/api/v1/query/{session_id}/regions/{region_id}/chat",
        json={"message": "Region one question"},
    )

    other = session_store.get_or_create_conversation(session_id, "other-region")
    other.turns.append(
        ConversationTurn(
            turn_id="other-turn",
            turn_index=0,
            user_message="Other region chat",
            assistant_answer="Other answer",
            created_at=datetime.now(UTC),
        )
    )

    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/evidence")
    exported = json.loads(_read_zip(res.content)["chat.json"])
    assert exported["region_id"] == region_id
    assert all(turn["user_message"] != "Other region chat" for turn in exported["turns"])


@pytest.mark.asyncio
async def test_export_unknown_session(client):
    res = await client.get(
        "/api/v1/query/00000000-0000-0000-0000-000000000000/regions/change-region-01/evidence"
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "session_not_found"


@pytest.mark.asyncio
async def test_export_unknown_region(client, upload_root):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    res = await client.get(f"/api/v1/query/{session_id}/regions/missing-region/evidence")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "region_not_found"


@pytest.mark.asyncio
async def test_export_non_bi_temporal_session(client, upload_root):
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
    res = await client.get(f"/api/v1/query/{session_id}/regions/change-region-01/evidence")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "not_bi_temporal_session"


@pytest.mark.asyncio
async def test_export_preview_failure(client, upload_root, monkeypatch):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)

    def fail_render(*args, **kwargs):
        raise SatQueryError("preview_render_failed", "Could not render crop.", status_code=422)

    monkeypatch.setattr(
        "app.services.region_evidence_export.render_raster_preview_png",
        fail_render,
    )

    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/evidence")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "preview_render_failed"


@pytest.mark.asyncio
async def test_export_does_not_mutate_session_state(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    before = await client.get(f"/api/v1/query/{session_id}/result")
    trace_before = await client.get(f"/api/v1/query/{session_id}/trace")
    evidence_before = before.json()["data"]["evidence"]
    trace_payload_before = trace_before.json()["data"]

    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/evidence")
    assert res.status_code == 200

    after = await client.get(f"/api/v1/query/{session_id}/result")
    trace_after = await client.get(f"/api/v1/query/{session_id}/trace")
    assert after.json()["data"]["evidence"] == evidence_before
    assert trace_after.json()["data"] == trace_payload_before


def test_build_region_geojson_feature_preserves_metadata():
    from app.schemas.domain import EvidenceRegion, GeoJSONGeometry, Metric

    region = EvidenceRegion(
        id="change-region-01",
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[[[77.0, 12.0], [77.1, 12.0], [77.1, 12.1], [77.0, 12.1], [77.0, 12.0]]],
        ),
        type="spectral_change",
        confidence=0.9,
        source="uploaded_bi_temporal",
        metrics=[Metric(name="estimated_area", value=1200, unit="m²", source="uploaded_bi_temporal")],
        metadata={"evidence_type": "spectral_change", "confidence_kind": "histogram_separability"},
    )
    feature = build_region_geojson_feature(region)
    assert feature["properties"]["id"] == "change-region-01"
    assert feature["properties"]["metadata"]["confidence_kind"] == "histogram_separability"


def test_serialize_conversation_preserves_turn_order():
    from app.services.session_store import RegionConversation

    conversation = RegionConversation(
        conversation_id="conv-1",
        session_id="session-1",
        region_id="change-region-01",
        turns=[
            ConversationTurn(
                turn_id="t0",
                turn_index=0,
                user_message="First",
                assistant_answer="A1",
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
            ),
            ConversationTurn(
                turn_id="t1",
                turn_index=1,
                user_message="Second",
                assistant_answer="A2",
                created_at=datetime(2024, 1, 2, tzinfo=UTC),
            ),
        ],
    )
    payload = serialize_conversation(conversation)
    assert [turn["turn_index"] for turn in payload["turns"]] == [0, 1]
    assert payload["turns"][0]["user_message"] == "First"


def test_build_export_metadata_requires_bi_temporal():
    from app.schemas.domain import AnalysisResult, AnalysisStatus, EvidenceRegion, GeoJSONGeometry

    result = AnalysisResult(
        status=AnalysisStatus.COMPLETED,
        session_id="s1",
        answer="done",
        confidence=0.5,
        evidence=[
            EvidenceRegion(
                id="change-region-01",
                geometry=GeoJSONGeometry(type="Polygon", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]),
                confidence=0.5,
                source="uploaded_bi_temporal",
            )
        ],
    )
    region = result.evidence[0]
    with pytest.raises(SatQueryError) as exc:
        build_export_metadata(
            session_id="s1",
            region=region,
            result=result,
            preview_bbox_wgs84="0,0,1,1",
            exported_at=datetime.now(UTC),
        )
    assert exc.value.code == "not_bi_temporal_session"
