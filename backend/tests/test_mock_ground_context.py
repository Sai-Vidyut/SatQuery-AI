"""Tests for deterministic mock ground context."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app
from app.schemas.domain import AnalysisResult
from app.services.mock_ground_context import (
    build_ground_context,
    polygon_centroid_wgs84,
    resolve_scene_category,
)
from app.services.region_interpretation import _find_region
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


async def _submit_bi_temporal(
    client: AsyncClient,
    upload_root,
    *,
    scenario: str = "vegetation_loss",
) -> tuple[str, str]:
    earlier_path = upload_root / "bt_before.tif"
    later_path = upload_root / "bt_after.tif"
    write_bi_temporal_scene(earlier_path, role="earlier", scenario=scenario)
    write_bi_temporal_scene(later_path, role="later", scenario=scenario)

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
async def test_ground_context_valid_region(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/ground-context")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["session_id"] == session_id
    assert body["region_id"] == region_id
    assert body["provenance"]["provider"] == "mock_ground_context"
    assert body["provenance"]["source_type"] == "mock"
    assert body["provenance"]["status"] == "demonstration_data"
    assert body["provenance"]["real_world_imagery"] is False
    assert "demonstration data" in body["provenance"]["disclosure"].lower()
    assert body["image"]["url"].startswith("/")
    assert body["scene"]["features"]


@pytest.mark.asyncio
async def test_ground_context_deterministic(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    first = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/ground-context")
    second = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/ground-context")
    assert first.json()["data"] == second.json()["data"]


@pytest.mark.asyncio
async def test_ground_context_centroid_matches_region(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    result = await client.get(f"/api/v1/query/{session_id}/result")
    result = AnalysisResult.model_validate(result.json()["data"])
    region = _find_region(result, region_id)
    expected_lon, expected_lat = polygon_centroid_wgs84(region.geometry.model_dump())
    context = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/ground-context")
    location = context.json()["data"]["location"]
    assert location["longitude"] == pytest.approx(expected_lon)
    assert location["latitude"] == pytest.approx(expected_lat)


@pytest.mark.asyncio
async def test_ground_context_unknown_session(client):
    res = await client.get(
        "/api/v1/query/00000000-0000-0000-0000-000000000000/regions/change-region-01/ground-context",
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "session_not_found"


@pytest.mark.asyncio
async def test_ground_context_unknown_region(client, upload_root):
    session_id, _ = await _submit_bi_temporal(client, upload_root)
    res = await client.get(f"/api/v1/query/{session_id}/regions/missing-region/ground-context")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "region_not_found"


@pytest.mark.asyncio
async def test_ground_context_not_bi_temporal(client, upload_root):
    path = upload_root / "single.tif"
    write_bi_temporal_scene(path, role="earlier", scenario="uniform")
    with path.open("rb") as handle:
        upload = await client.post(
            "/api/v1/imagery/upload",
            files={"file": (path.name, handle, "image/tiff")},
            data={"modality": "optical"},
        )
    image_id = upload.json()["data"]["image"]["id"]
    query = await client.post(
        "/api/v1/query/submit",
        json={"query": "What land-cover types are visible?", "image_id": image_id},
    )
    session_id = query.json()["data"]["session_id"]
    res = await client.get(f"/api/v1/query/{session_id}/regions/change-region-01/ground-context")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "not_bi_temporal_session"


@pytest.mark.asyncio
async def test_ground_context_does_not_mutate_session(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root)
    before = await client.get(f"/api/v1/query/{session_id}/result")
    evidence_before = before.json()["data"]["evidence"]
    trace_before = before.json()["data"]["trace"]
    await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/ground-context")
    after = await client.get(f"/api/v1/query/{session_id}/result")
    assert after.json()["data"]["evidence"] == evidence_before
    assert after.json()["data"]["trace"] == trace_before


@pytest.mark.parametrize(
    ("hint", "expected"),
    [
        ("vegetation_loss", "vegetation_loss"),
        ("built_up_increase", "built_up_increase"),
        ("water_contraction", "water_shrinkage"),
        ("water_expansion", "flood"),
        ("unknown_hint", "generic_change"),
        (None, "generic_change"),
    ],
)
def test_resolve_scene_category(hint, expected):
    assert resolve_scene_category(hint) == expected


@pytest.mark.asyncio
async def test_ground_context_vegetation_mapping(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root, scenario="vegetation_loss")
    res = await client.get(f"/api/v1/query/{session_id}/regions/{region_id}/ground-context")
    assert res.json()["data"]["scene"]["category"] == "vegetation_loss"


@pytest.mark.asyncio
async def test_ground_context_flood_mapping(client, upload_root):
    session_id, region_id = await _submit_bi_temporal(client, upload_root, scenario="flood")
    result_res = await client.get(f"/api/v1/query/{session_id}/result")
    result = AnalysisResult.model_validate(result_res.json()["data"])
    region = _find_region(result, region_id)
    region.metadata["change_direction_hint"] = "water_expansion"
    context = build_ground_context(session_id=session_id, region=region, result=result)
    assert context.scene.category == "flood"
