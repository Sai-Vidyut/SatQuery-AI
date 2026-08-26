"""Phase 14 — GeoChat real service integration tests."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.rsvlm.development import DevelopmentGeoChatVLM
from app.adapters.rsvlm.factory import get_geochat_vlm
from app.adapters.rsvlm.geochat_service import GeoChatServiceVLM
from app.core.config import get_settings
from app.main import app
from app.schemas.input import ImageFormat, ImageInput, ImageModality, ImageSource
from app.schemas.vqa import GeoChatVQAParameters, VQAProviderKind
from tests.fixtures.rasters import write_geotiff

REPO_ROOT = Path(__file__).resolve().parents[2]
GEOCHAT_SERVICE_ROOT = REPO_ROOT / "services" / "geochat"


@pytest.fixture
def upload_root(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(root))
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "8")
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "development")
    get_settings.cache_clear()
    from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
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
def sample_image() -> ImageInput:
    return ImageInput(
        id="b" * 32,
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="scene.tif",
        width=64,
        height=64,
        file_size_bytes=100,
        georeferenced=True,
        source=ImageSource.UPLOAD,
        crs="EPSG:4326",
        bounds=[77.59, 12.99, 77.5964, 12.9964],
    )


@pytest.fixture
def fake_geochat_service(monkeypatch):
    """Run the standalone GeoChat service with fake inference engine on a local port."""
    port = 19876
    env = {
        **os.environ,
        "GEOCHAT_SERVICE_FAKE_ENGINE": "true",
        "GEOCHAT_SERVICE_PORT": str(port),
        "GEOCHAT_EAGER_LOAD": "false",
        "PYTHONPATH": str(GEOCHAT_SERVICE_ROOT),
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "geochat_service.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(GEOCHAT_SERVICE_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            res = httpx.get(f"{url}/health", timeout=1.0)
            if res.status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        proc.terminate()
        pytest.fail("Fake GeoChat service did not become healthy in time.")
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "geochat_service")
    monkeypatch.setenv("GEOCHAT_SERVICE_URL", url)
    monkeypatch.setenv("GEOCHAT_SERVICE_TIMEOUT_S", "30")
    get_settings.cache_clear()
    get_geochat_vlm.cache_clear()
    yield url
    proc.terminate()
    proc.wait(timeout=5)
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


def _store_image(upload_root: Path, image: ImageInput) -> None:
    from app.storage.factory import get_image_storage

    path = upload_root / "scene.tif"
    write_geotiff(path)
    with path.open("rb") as handle:
        get_image_storage().save(image.id, ".tif", handle)


# 1 — service health (via fake HTTP service)
@pytest.mark.asyncio
async def test_01_service_health(fake_geochat_service):
    res = httpx.get(f"{fake_geochat_service}/health")
    body = res.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["model_loaded"] is True
    assert body["model_name"] == "MBZUAI/geochat-7B"
    assert body["provider"] == "geochat_service"


# 2 — valid VQA request through backend adapter
@pytest.mark.asyncio
async def test_02_valid_vqa_request(fake_geochat_service, upload_root, sample_image):
    _store_image(upload_root, sample_image)
    vlm = GeoChatServiceVLM(fake_geochat_service, "MBZUAI/geochat-7B")
    result = await vlm.run_vqa(
        image=sample_image,
        question="Describe the main land-cover types visible in this satellite image.",
        parameters=GeoChatVQAParameters(),
    )
    assert result.provider == VQAProviderKind.GEOCHAT_SERVICE
    assert result.model_name == "MBZUAI/geochat-7B"
    assert result.answer
    assert "development mock" not in result.answer.lower()


# 3 — malformed request rejected by service
def test_03_malformed_request(fake_geochat_service):
    res = httpx.post(f"{fake_geochat_service}/v1/vqa", json={"question": "only question"})
    assert res.status_code == 422


# 4 — missing image
def test_04_missing_image(fake_geochat_service):
    res = httpx.post(
        f"{fake_geochat_service}/v1/vqa",
        json={"question": "What is visible?", "image_metadata": {"image_id": "x", "modality": "optical", "width": 1, "height": 1}},
    )
    assert res.status_code == 422


# 5 — missing question
def test_05_missing_question(fake_geochat_service):
    raw = base64.b64encode(b"not-image").decode("ascii")
    res = httpx.post(
        f"{fake_geochat_service}/v1/vqa",
        json={
            "image": {"content_base64": raw, "format": "png", "filename": "x.png"},
            "image_metadata": {"image_id": "x", "modality": "optical", "width": 1, "height": 1},
        },
    )
    assert res.status_code == 422


# 6 — backend adapter contract (no filesystem path in payload)
@pytest.mark.asyncio
async def test_06_adapter_sends_bytes_not_paths(fake_geochat_service, upload_root, sample_image, monkeypatch):
    _store_image(upload_root, sample_image)
    captured: dict = {}

    async def capture_post(self, path, payload):
        captured.update(payload)
        return {
            "answer": "Urban and agricultural land cover are visible.",
            "model_name": "MBZUAI/geochat-7B",
            "provider": "geochat_service",
            "confidence_available": False,
            "runtime_ms": 12,
            "provenance": {
                "model_name": "MBZUAI/geochat-7B",
                "provider": "geochat_service",
                "service_version": "0.1.0",
                "runtime_ms": 12,
            },
        }

    monkeypatch.setattr(GeoChatServiceVLM, "_post", capture_post)
    vlm = GeoChatServiceVLM(fake_geochat_service, "MBZUAI/geochat-7B")
    await vlm.run_vqa(image=sample_image, question="Describe.", parameters=GeoChatVQAParameters())
    assert "image_path" not in captured
    assert "content_base64" in captured["image"]
    assert captured["image_metadata"]["image_id"] == sample_image.id


# 7 — timeout handling
@pytest.mark.asyncio
async def test_07_timeout_handling(upload_root, sample_image, monkeypatch):
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "geochat_service")
    monkeypatch.setenv("GEOCHAT_SERVICE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("GEOCHAT_SERVICE_TIMEOUT_S", "0.1")
    get_settings.cache_clear()
    get_geochat_vlm.cache_clear()
    _store_image(upload_root, sample_image)

    import httpx

    async def timeout_post(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", timeout_post)
    vlm = GeoChatServiceVLM("http://127.0.0.1:1", "MBZUAI/geochat-7B")
    from app.core.errors import SatQueryError

    with pytest.raises(SatQueryError) as exc:
        await vlm.run_vqa(image=sample_image, question="Describe.", parameters=GeoChatVQAParameters())
    assert exc.value.code == "geochat_service_timeout"
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


# 8 — service unavailable
@pytest.mark.asyncio
async def test_08_service_unavailable(upload_root, sample_image, monkeypatch):
    monkeypatch.setenv("GEOCHAT_SERVICE_TIMEOUT_S", "2")
    _store_image(upload_root, sample_image)
    vlm = GeoChatServiceVLM("http://127.0.0.1:1", "MBZUAI/geochat-7B")
    from app.core.errors import SatQueryError

    with pytest.raises(SatQueryError) as exc:
        await vlm.run_vqa(image=sample_image, question="Describe.", parameters=GeoChatVQAParameters())
    assert exc.value.code == "geochat_service_error"


# 9 — provenance
@pytest.mark.asyncio
async def test_09_provenance(fake_geochat_service, upload_root, sample_image):
    _store_image(upload_root, sample_image)
    vlm = GeoChatServiceVLM(fake_geochat_service, "MBZUAI/geochat-7B")
    result = await vlm.run_vqa(
        image=sample_image,
        question="Describe land cover.",
        parameters=GeoChatVQAParameters(),
    )
    assert "MBZUAI/geochat-7B" in result.provenance
    assert result.inference_metadata.get("service_url") == fake_geochat_service


# 10 — no fake confidence
@pytest.mark.asyncio
async def test_10_no_fake_confidence(fake_geochat_service, upload_root, sample_image):
    _store_image(upload_root, sample_image)
    vlm = GeoChatServiceVLM(fake_geochat_service, "MBZUAI/geochat-7B")
    result = await vlm.run_vqa(
        image=sample_image,
        question="Describe land cover.",
        parameters=GeoChatVQAParameters(),
    )
    assert result.confidence_available is False
    assert result.confidence is None


# 11 — development provider regression
def test_11_development_provider_regression(monkeypatch):
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "development")
    get_settings.cache_clear()
    get_geochat_vlm.cache_clear()
    vlm = get_geochat_vlm()
    assert vlm.name == "development_geochat_rsvlm"
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


# 12 — single-image VQA regression
@pytest.mark.asyncio
async def test_12_single_image_vqa_regression_api(upload_root):
    transport = ASGITransport(app=app)
    path = upload_root / "vqa.tif"
    write_geotiff(path)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with path.open("rb") as f:
            up = await client.post(
                "/api/v1/imagery/upload",
                files={"file": ("vqa.tif", f, "image/tiff")},
                data={"modality": "optical"},
            )
        image_id = up.json()["data"]["image"]["id"]
        res = await client.post(
            "/api/v1/query/submit",
            json={"query": "What land-cover types are visible?", "image_id": image_id},
        )
        assert res.status_code == 200
        assert res.json()["data"]["result"]["vqa"]["provider"] == "development"


# 13 — caption regression
@pytest.mark.asyncio
async def test_13_caption_regression(upload_root):
    transport = ASGITransport(app=app)
    path = upload_root / "caption.tif"
    write_geotiff(path)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with path.open("rb") as f:
            up = await client.post(
                "/api/v1/imagery/upload",
                files={"file": ("caption.tif", f, "image/tiff")},
                data={"modality": "optical"},
            )
        image_id = up.json()["data"]["image"]["id"]
        res = await client.post(
            "/api/v1/query/submit",
            json={"query": "Describe this satellite scene.", "image_id": image_id},
        )
        assert res.status_code == 200
        assert res.json()["data"]["result"]["caption"]["task"] == "single_image_caption"


# 14 — bi-temporal regression
@pytest.mark.asyncio
async def test_14_bi_temporal_regression(upload_root):
    transport = ASGITransport(app=app)
    before = upload_root / "before.tif"
    after = upload_root / "after.tif"
    write_geotiff(before)
    write_geotiff(after)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with before.open("rb") as f:
            earlier_up = await client.post(
                "/api/v1/imagery/upload",
                files={"file": ("before.tif", f, "image/tiff")},
                data={"modality": "optical", "acquisition_datetime": "2023-01-01T00:00:00+00:00"},
            )
        with after.open("rb") as f:
            later_up = await client.post(
                "/api/v1/imagery/upload",
                files={"file": ("after.tif", f, "image/tiff")},
                data={"modality": "optical", "acquisition_datetime": "2024-01-01T00:00:00+00:00"},
            )
        res = await client.post(
            "/api/v1/query/submit",
            json={
                "query": "What changed between these two dates?",
                "earlier_image_id": earlier_up.json()["data"]["image"]["id"],
                "later_image_id": later_up.json()["data"]["image"]["id"],
            },
        )
        assert res.status_code == 200


# 15 — cross-modal regression
@pytest.mark.asyncio
async def test_15_cross_modal_regression(upload_root):
    transport = ASGITransport(app=app)
    optical = upload_root / "optical.tif"
    sar = upload_root / "sar.tif"
    write_geotiff(optical)
    write_geotiff(sar)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with optical.open("rb") as f:
            optical_up = await client.post(
                "/api/v1/imagery/upload",
                files={"file": ("optical.tif", f, "image/tiff")},
                data={"modality": "optical"},
            )
        with sar.open("rb") as f:
            sar_up = await client.post(
                "/api/v1/imagery/upload",
                files={"file": ("sar.tif", f, "image/tiff")},
                data={"modality": "sar"},
            )
        res = await client.post(
            "/api/v1/query/submit",
            json={
                "query": "Use the optical and SAR images together to identify built-up and water-covered regions.",
                "optical_image_id": optical_up.json()["data"]["image"]["id"],
                "sar_image_id": sar_up.json()["data"]["image"]["id"],
            },
        )
        assert res.status_code == 200
        assert res.json()["data"]["result"]["cross_modal"]["task"] == "cross_modal_optical_sar"


# 16 — Earth Engine catalog regression (planner)
def test_16_catalog_planner_regression():
    from datetime import date

    from app.schemas.domain import AOI, GeoJSONGeometry, QueryRequest
    from app.services.planner.deterministic import build_deterministic_plan

    plan = build_deterministic_plan(
        QueryRequest(
            query="Show significant spectral change",
            aoi=AOI(
                geometry=GeoJSONGeometry(
                    type="Polygon",
                    coordinates=[[[0.0, 0.0], [0.01, 0.0], [0.01, 0.01], [0.0, 0.01], [0.0, 0.0]]],
                )
            ),
            earlier_date=date(2024, 1, 1),
            later_date=date(2024, 6, 1),
        )
    )
    assert plan.user_intent.value in {"spectral_change", "construction", "radar_change", "multimodal_comparison"}


# Real GPU integration — only when explicitly enabled
@pytest.mark.skipif(
    os.environ.get("GEOCHAT_REAL_SERVICE_TEST", "").lower() != "true",
    reason="Set GEOCHAT_REAL_SERVICE_TEST=true to run against a live GPU GeoChat service.",
)
@pytest.mark.asyncio
async def test_real_geochat_service_integration(upload_root, sample_image):
    service_url = os.environ.get("GEOCHAT_SERVICE_URL")
    if not service_url:
        pytest.skip("GEOCHAT_SERVICE_URL is required for real service integration test.")
    smoke_path = REPO_ROOT / "experiments" / "phase9b_geochat" / "assets" / "sentinel2_smoketest.png"
    if not smoke_path.exists():
        pytest.skip("Sentinel-2 smoke image not found.")
    from app.storage.factory import get_image_storage

    with smoke_path.open("rb") as handle:
        get_image_storage().save(sample_image.id, ".png", handle)
    sample_png = sample_image.model_copy(update={"format": ImageFormat.PNG, "filename": "sentinel2_smoketest.png", "width": 504, "height": 504})
    vlm = GeoChatServiceVLM(service_url, "MBZUAI/geochat-7B")
    result = await vlm.run_vqa(
        image=sample_png,
        question="Describe the main land-cover types visible in this satellite image.",
        parameters=GeoChatVQAParameters(),
    )
    assert result.provider == VQAProviderKind.GEOCHAT_SERVICE
    assert result.model_name == "MBZUAI/geochat-7B"
    assert "development mock" not in result.answer.lower()
    assert "[development mock" not in result.answer.lower()

    artifact_dir = GEOCHAT_SERVICE_ROOT / "validation_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / "real_gpu_vqa_result.json"
    artifact.write_text(result.model_dump_json(indent=2))
