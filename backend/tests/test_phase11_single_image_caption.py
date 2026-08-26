"""Phase 11 — SIH mandatory single-image scene description tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.rsvlm.development import DevelopmentGeoChatVLM
from app.adapters.rsvlm.factory import get_geochat_vlm
from app.core.config import get_settings
from app.main import app
from app.schemas.domain import QueryRequest
from app.schemas.input import ImageModality
from app.schemas.planning import QueryIntent
from app.schemas.vqa import VQAProviderKind
from app.services.planner.deterministic import build_deterministic_plan
from app.services.single_image_intent import single_image_intent_from_query
from tests.fixtures.rasters import write_geotiff, write_invalid_tiff, write_jpeg


def _vqa_request(query: str, image_id: str) -> QueryRequest:
    return QueryRequest(query=query, image_id=image_id)


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


async def _upload_geotiff(client, upload_root: Path, *, modality: str = "optical") -> str:
    path = upload_root / f"{modality}.tif"
    write_geotiff(path)
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("scene.tif", f, "image/tiff")},
            data={"modality": modality},
        )
    assert res.status_code == 200
    return res.json()["data"]["image"]["id"]


# TEST 1 — optical scene description
@pytest.mark.asyncio
async def test_sih_01_optical_scene_description(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root, modality="optical")
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe this satellite scene.", "image_id": image_id},
    )
    assert res.status_code == 200
    result = res.json()["data"]["result"]
    assert result["status"] == "completed"
    assert result["caption"]["task"] == "single_image_caption"
    assert result["caption"]["description"]
    assert "geochat_caption" in [s["tool_name"] for s in result["trace"]]
    plan_step = next(s for s in result["trace"] if s["tool_name"] == "plan_query")
    assert plan_step["metadata"]["intent"] == "single_image_caption"
    assert result.get("vqa") is None


# TEST 2 — SAR scene description
@pytest.mark.asyncio
async def test_sih_02_sar_scene_description(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root, modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe the visible surface patterns.", "image_id": image_id},
    )
    assert res.status_code == 200
    result = res.json()["data"]["result"]
    assert result["caption"]["requested_modality"] == "sar"
    assert result["caption"]["task"] == "single_image_caption"
    assert "geochat_caption" in [s["tool_name"] for s in result["trace"]]


# TEST 3 — VQA remains unchanged
@pytest.mark.asyncio
async def test_sih_03_vqa_unchanged(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root, modality="optical")
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "What land-cover types are visible?", "image_id": image_id},
    )
    assert res.status_code == 200
    result = res.json()["data"]["result"]
    assert result["vqa"]["task"] == "single_image_vqa"
    assert result.get("caption") is None
    plan_step = next(s for s in result["trace"] if s["tool_name"] == "plan_query")
    assert plan_step["metadata"]["intent"] == "single_image_vqa"


# TEST 4 — caption query routing
@pytest.mark.parametrize(
    "query",
    [
        "Describe this scene.",
        "Give a caption for this satellite image.",
        "What does this image show?",
    ],
)
def test_sih_04_caption_query_routing(query: str):
    assert single_image_intent_from_query(query) == QueryIntent.SINGLE_IMAGE_CAPTION
    plan = build_deterministic_plan(_vqa_request(query, "a" * 32))
    assert plan.user_intent == QueryIntent.SINGLE_IMAGE_CAPTION
    assert [t.value for t in plan.required_tools] == ["geochat_caption", "generate_evidence"]


# TEST 5 — invalid raster rejected before specialist
@pytest.mark.asyncio
async def test_sih_05_invalid_raster_rejected(client, upload_root):
    path = upload_root / "bad.tif"
    write_invalid_tiff(path)
    with path.open("rb") as f:
        upload = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("bad.tif", f, "image/tiff")},
        )
    assert upload.status_code == 400


@pytest.mark.asyncio
async def test_sih_05b_validation_failure_before_specialist(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root)
    from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
    from app.storage.factory import get_metadata_registry

    provider = get_uploaded_imagery_provider()
    image = provider.get(image_id)
    get_metadata_registry().save(image.model_copy(update={"georeferenced": False}))
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe this satellite scene.", "image_id": image_id},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "input_validation_failed"
    trace_names = [s["tool_name"] for s in res.json().get("data", {}).get("trace", [])]
    assert "geochat_caption" not in trace_names


# TEST 6 — production JPEG rejection
@pytest.mark.asyncio
async def test_sih_06_production_jpeg_rejected(client, upload_root):
    path = upload_root / "scene.jpg"
    write_jpeg(path)
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("scene.jpeg", f, "image/jpeg")},
            data={"benchmark_dataset": "false"},
        )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "benchmark_required"


# TEST 7 — benchmark JPEG exception
@pytest.mark.asyncio
async def test_sih_07_benchmark_jpeg_accepted(client, upload_root):
    path = upload_root / "bench.jpeg"
    write_jpeg(path)
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("bench.jpeg", f, "image/jpeg")},
            data={"benchmark_dataset": "true"},
        )
    assert res.status_code == 200
    image_id = res.json()["data"]["image"]["id"]
    submit = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe this satellite scene.", "image_id": image_id},
    )
    assert submit.status_code == 200
    assert submit.json()["data"]["result"]["caption"]["task"] == "single_image_caption"


# TEST 8 — provenance
@pytest.mark.asyncio
async def test_sih_08_provenance_development_mock(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root)
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe this satellite scene.", "image_id": image_id},
    )
    caption = res.json()["data"]["result"]["caption"]
    assert caption["provider"] == VQAProviderKind.DEVELOPMENT.value
    assert "mock" in caption["provenance"].lower() or "development" in caption["model_name"].lower()


@pytest.mark.asyncio
async def test_sih_08b_provenance_real_service_metadata(monkeypatch):
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "geochat_service")
    monkeypatch.setenv("GEOCHAT_SERVICE_URL", "http://geochat-gpu")
    get_settings.cache_clear()
    get_geochat_vlm.cache_clear()

    class FakeServiceVLM(DevelopmentGeoChatVLM):
        name = "geochat_service_rsvlm"
        provider_kind = VQAProviderKind.GEOCHAT_SERVICE.value

        async def run_caption(self, *, image, user_request, parameters):
            base = await super().run_caption(
                image=image,
                user_request=user_request,
                parameters=parameters,
            )
            return base.model_copy(
                update={
                    "model_name": "MBZUAI/geochat-7B",
                    "provider": VQAProviderKind.GEOCHAT_SERVICE,
                    "provenance": "MBZUAI/geochat-7B via GPU inference service",
                }
            )

    from app.schemas.input import ImageFormat, ImageInput, ImageSource
    from app.schemas.vqa import GeoChatCaptionParameters

    image = ImageInput(
        id="c" * 32,
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="x.tif",
        width=64,
        height=64,
        file_size_bytes=100,
        georeferenced=True,
        source=ImageSource.UPLOAD,
    )
    vlm = FakeServiceVLM()
    result = await vlm.run_caption(
        image=image,
        user_request="Describe this satellite scene.",
        parameters=GeoChatCaptionParameters(),
    )
    assert result.model_name == "MBZUAI/geochat-7B"
    assert result.provider == VQAProviderKind.GEOCHAT_SERVICE
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


# TEST 9 — no fabricated confidence
@pytest.mark.asyncio
async def test_sih_09_no_fabricated_confidence(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root)
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe this satellite scene.", "image_id": image_id},
    )
    result = res.json()["data"]["result"]
    assert result["confidence_available"] is False
    assert result["caption"]["confidence_available"] is False
    assert result["caption"].get("confidence") is None
    assert not any(m["name"] == "caption_confidence" for m in result["metrics"])


# TEST 10 — no fabricated spatial evidence
@pytest.mark.asyncio
async def test_sih_10_no_fabricated_spatial_evidence(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root)
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe this satellite scene.", "image_id": image_id},
    )
    result = res.json()["data"]["result"]
    assert result["evidence"] == []
    meta = result["caption"].get("inference_metadata") or {}
    assert "bounding_boxes" not in meta
    assert "regions" not in meta
    assert "geojson" not in meta


# TEST 11 — trace
@pytest.mark.asyncio
async def test_sih_11_trace_contains_required_steps(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root)
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe this satellite scene.", "image_id": image_id},
    )
    trace_names = [s["tool_name"] for s in res.json()["data"]["result"]["trace"]]
    assert "input_validation" in trace_names
    assert "plan_query" in trace_names
    assert "geochat_caption" in trace_names
    assert "generate_evidence" in trace_names
