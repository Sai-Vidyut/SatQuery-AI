from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app
from tests.fixtures.rasters import write_geotiff, write_invalid_tiff, write_png


@pytest.fixture
async def client(upload_root):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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


@pytest.mark.asyncio
async def test_upload_geotiff_success(client, upload_root):
    path = upload_root / "input.tif"
    write_geotiff(path)
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("scene.tif", f, "image/tiff")},
            data={"modality": "optical"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    image = body["data"]["image"]
    assert image["georeferenced"] is True
    assert image["format"] == "geotiff"
    assert len(image["id"]) == 32


@pytest.mark.asyncio
async def test_upload_invalid_extension(client):
    res = await client.post(
        "/api/v1/imagery/upload",
        files={"file": ("scene.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "unsupported_format"


@pytest.mark.asyncio
async def test_upload_invalid_raster(client, upload_root):
    path = upload_root / "bad.tif"
    write_invalid_tiff(path)
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("bad.tif", f, "image/tiff")},
        )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "invalid_raster"


@pytest.mark.asyncio
async def test_upload_png_requires_benchmark(client, upload_root):
    path = upload_root / "bench.png"
    write_png(path)
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("bench.png", f, "image/png")},
        )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "benchmark_required"


@pytest.mark.asyncio
async def test_get_uploaded_image(client, upload_root):
    path = upload_root / "input.tif"
    write_geotiff(path)
    with path.open("rb") as f:
        up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("scene.tif", f, "image/tiff")},
        )
    image_id = up.json()["data"]["image"]["id"]
    res = await client.get(f"/api/v1/imagery/{image_id}")
    assert res.status_code == 200
    assert res.json()["data"]["image"]["id"] == image_id


@pytest.mark.asyncio
async def test_validate_bi_temporal_pair(client, upload_root):
    a = upload_root / "a.tif"
    b = upload_root / "b.tif"
    write_geotiff(a)
    write_geotiff(b)
    with a.open("rb") as fa:
        up_a = await client.post("/api/v1/imagery/upload", files={"file": ("a.tif", fa, "image/tiff")})
    with b.open("rb") as fb:
        up_b = await client.post("/api/v1/imagery/upload", files={"file": ("b.tif", fb, "image/tiff")})
    earlier = up_a.json()["data"]["image"]
    later = up_b.json()["data"]["image"]
    res = await client.post(
        "/api/v1/imagery/validate-input",
        json={
            "input_type": "bi_temporal",
            "earlier": earlier,
            "later": later,
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["valid"] is True


@pytest.mark.asyncio
async def test_existing_ee_query_workflow_unchanged(client):
    from tests.test_api import SAMPLE_QUERY

    res = await client.post("/api/v1/query/submit", json=SAMPLE_QUERY.model_dump(mode="json"))
    assert res.status_code == 200
    assert res.json()["data"]["result"]["status"] == "completed"
