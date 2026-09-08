"""Backend tests for uploaded imagery preview crops."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.core.config import get_settings
from app.main import app
from app.adapters.change.uploaded_bitemporal import UploadedBiTemporalChangeDetector
from app.adapters.imagery.uploaded.bi_temporal_bridge import build_change_detection_input
from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
from app.services.imagery_preview import parse_bbox_wgs84, render_raster_preview_png
from tests.fixtures.rasters import write_bi_temporal_scene, write_geotiff, write_multispectral_geotiff


@pytest.fixture
def upload_root(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(root))
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
    get_settings.cache_clear()
    from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
    from app.storage.factory import get_image_storage, get_metadata_registry

    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    get_uploaded_imagery_provider.cache_clear()
    yield root
    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    get_uploaded_imagery_provider.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
async def client(upload_root):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _upload_geotiff(client, upload_root, path: Path, *, lon_offset: float = 0.0) -> str:
    write_geotiff(path, origin_lon=77.59 + lon_offset, origin_lat=12.99)
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("scene.tif", f, "image/tiff")},
            data={"modality": "optical", "acquisition_datetime": "2024-01-01T00:00:00Z"},
        )
    assert res.status_code == 200
    return res.json()["data"]["image"]["id"]


@pytest.mark.asyncio
async def test_imagery_preview_valid_crop(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root, upload_root / "preview.tif")
    bbox = "77.5910,12.9840,77.5960,12.9895"
    res = await client.get(f"/api/v1/imagery/{image_id}/preview", params={"bbox": bbox})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/png")
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_imagery_preview_invalid_image_id(client):
    res = await client.get(
        "/api/v1/imagery/not-a-valid-id/preview",
        params={"bbox": "77.59,12.99,77.60,13.00"},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "invalid_image_id"


@pytest.mark.asyncio
async def test_imagery_preview_nonexistent_image_id(client):
    res = await client.get(
        "/api/v1/imagery/00000000000000000000000000000000/preview",
        params={"bbox": "77.59,12.99,77.60,13.00"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "image_not_found"


@pytest.mark.asyncio
async def test_imagery_preview_bbox_outside_raster(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root, upload_root / "outside.tif")
    res = await client.get(
        f"/api/v1/imagery/{image_id}/preview",
        params={"bbox": "0,0,1,1"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "preview_bbox_no_intersection"


@pytest.mark.asyncio
async def test_imagery_preview_bbox_partially_outside_raster(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root, upload_root / "partial.tif")
    # Intersects upper-right corner of fixture while extending outside
    res = await client.get(
        f"/api/v1/imagery/{image_id}/preview",
        params={"bbox": "77.595,12.985,77.700,12.990"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/png")


@pytest.mark.asyncio
async def test_imagery_preview_respects_crs_geotransform(client, upload_root, tmp_path):
    import numpy as np

    path = tmp_path / "metric_crs.tif"
    array = np.ones((3, 32, 32), dtype=np.float32) * 0.4
    write_multispectral_geotiff(
        path,
        array,
        origin_lon=10.0,
        origin_lat=50.0,
        pixel_size=0.001,
        epsg=32632,
    )
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("metric.tif", f, "image/tiff")},
            data={"modality": "optical"},
        )
    assert res.status_code == 200
    image_id = res.json()["data"]["image"]["id"]

    # WGS84 bbox overlapping the UTM raster footprint (north-up origin at lat=50)
    res = await client.get(
        f"/api/v1/imagery/{image_id}/preview",
        params={"bbox": "10.000,49.960,10.020,50.000"},
    )
    assert res.status_code == 200
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_parse_bbox_wgs84_valid():
    assert parse_bbox_wgs84("1,2,3,4") == (1.0, 2.0, 3.0, 4.0)


def test_render_preview_direct_on_fixture(tmp_path):
    path = tmp_path / "direct.tif"
    write_geotiff(path)
    png = render_raster_preview_png(
        path,
        bbox_wgs84=(77.5910, 12.9840, 77.5960, 12.9895),
        max_size=256,
    )
    assert png.startswith(b"\x89PNG")


def _preview_non_black_ratio(png_bytes: bytes) -> float:
    arr = np.asarray(Image.open(io.BytesIO(png_bytes)).convert("RGB"))
    return float((arr > 10).any(axis=2).mean())


def _padded_bbox_from_region_geometry(geometry: dict) -> str:
    ring = geometry["coordinates"][0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    pad = 0.00005
    return (
        f"{min(lons) - pad:.6f},{min(lats) - pad:.6f},"
        f"{max(lons) + pad:.6f},{max(lats) + pad:.6f}"
    )


@pytest.mark.asyncio
async def test_real_bi_temporal_region_preview_has_signal(client, upload_root):
    """Preview crops for real uploaded_bi_temporal regions must contain meaningful pixels."""
    earlier_path = upload_root / "bt_before.tif"
    later_path = upload_root / "bt_after.tif"
    write_bi_temporal_scene(earlier_path, role="earlier", scenario="vegetation_loss")
    write_bi_temporal_scene(later_path, role="later", scenario="vegetation_loss")

    async def upload(path: Path, dt: str) -> str:
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

    provider = get_uploaded_imagery_provider()
    earlier = provider.get(earlier_id)
    later = provider.get(later_id)
    payload = build_change_detection_input(earlier, later, query_hint="vegetation loss")
    detections = await UploadedBiTemporalChangeDetector().detect(payload)
    assert detections.detector == "uploaded_bi_temporal"
    assert detections.regions

    bbox = _padded_bbox_from_region_geometry(detections.regions[0].geometry.model_dump())
    for image_id in (earlier_id, later_id):
        res = await client.get(f"/api/v1/imagery/{image_id}/preview", params={"bbox": bbox})
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("image/png")
        assert _preview_non_black_ratio(res.content) > 0.5
