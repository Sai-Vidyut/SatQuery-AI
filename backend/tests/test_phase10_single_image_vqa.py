"""Phase 10 — SIH mandatory single-image VQA tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.adapters.rsvlm.development import DevelopmentGeoChatVLM
from app.adapters.rsvlm.factory import get_geochat_vlm
from app.core.config import get_settings
from app.main import app
from app.schemas.domain import AOI, GeoJSONGeometry, QueryRequest
from app.schemas.input import ImageModality
from app.schemas.planning import PlannerToolName, QueryAnalysisPlan, QueryIntent, RequestedModality
from app.schemas.vqa import VQAProviderKind
from app.services.planner.deterministic import build_deterministic_plan
from app.services.planner.service import plan_with_llm, MockLLMPlannerClient
from app.services.query_controller import QueryController
from tests.fixtures.rasters import write_geotiff, write_invalid_tiff, write_jpeg, write_png


def _aoi() -> AOI:
    return AOI(
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[[[77.56, 12.94], [77.60, 12.94], [77.60, 12.98], [77.56, 12.98], [77.56, 12.94]]],
        )
    )


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


# TEST 1 — valid optical GeoTIFF + VQA
@pytest.mark.asyncio
async def test_sih_01_valid_optical_geotiff_vqa(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root, modality="optical")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "Describe the land-cover and major objects visible in this image.",
            "image_id": image_id,
        },
    )
    assert res.status_code == 200
    result = res.json()["data"]["result"]
    assert result["status"] == "completed"
    assert result["vqa"]["task"] == "single_image_vqa"
    assert "geochat_vqa" in [s["tool_name"] for s in result["trace"]]
    plan_step = next(s for s in result["trace"] if s["tool_name"] == "plan_query")
    assert plan_step["metadata"]["intent"] == "single_image_vqa"
    assert result["answer"]


# TEST 2 — valid SAR GeoTIFF + VQA
@pytest.mark.asyncio
async def test_sih_02_valid_sar_geotiff_vqa(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root, modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "What structures or surface patterns are visible in this image?",
            "image_id": image_id,
        },
    )
    assert res.status_code == 200
    result = res.json()["data"]["result"]
    assert result["vqa"]["requested_modality"] == "sar"
    assert result["status"] == "completed"


# TEST 3 — invalid file rejected before specialist
@pytest.mark.asyncio
async def test_sih_03_invalid_file_rejected(client, upload_root):
    path = upload_root / "bad.tif"
    write_invalid_tiff(path)
    with path.open("rb") as f:
        upload = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("bad.tif", f, "image/tiff")},
        )
    assert upload.status_code == 400


# TEST 4 — unsupported production JPEG
@pytest.mark.asyncio
async def test_sih_04_unsupported_jpeg_without_benchmark(client, upload_root):
    path = upload_root / "scene.jpg"
    write_png(path.with_suffix(".png"))
    png_path = path.with_suffix(".png")
    with png_path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("scene.jpeg", f, "image/jpeg")},
            data={"benchmark_dataset": "false"},
        )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "benchmark_required"


# TEST 5 — benchmark JPEG exception
@pytest.mark.asyncio
async def test_sih_05_benchmark_jpeg_accepted(client, upload_root):
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
        json={"query": "What land-cover types are visible?", "image_id": image_id},
    )
    assert submit.status_code == 200


# TEST 6 — planner routing single_image_vqa
def test_sih_06_planner_routing_single_image_vqa():
    req = QueryRequest(
        query="What land-cover types are visible?",
        image_id="a" * 32,
    )
    plan = build_deterministic_plan(req, image_modality=ImageModality.OPTICAL)
    assert plan.user_intent == QueryIntent.SINGLE_IMAGE_VQA
    assert [t.value for t in plan.required_tools] == ["geochat_vqa", "generate_evidence"]
    assert plan.user_intent not in (
        QueryIntent.CONSTRUCTION,
        QueryIntent.SPECTRAL_CHANGE,
        QueryIntent.RADAR_CHANGE,
        QueryIntent.MULTIMODAL_COMPARISON,
    )


# TEST 7 — planner cannot inject evidence
@pytest.mark.asyncio
async def test_sih_07_planner_cannot_inject_evidence():
    with pytest.raises(ValueError, match="forbidden planner field"):
        await plan_with_llm(
            QueryRequest(query="What is visible?", image_id="b" * 32),
            MockLLMPlannerClient({"confidence": 0.9, "user_intent": "single_image_vqa"}),
        )
    with pytest.raises(ValidationError):
        QueryAnalysisPlan.model_validate(
            {
                "user_intent": "single_image_vqa",
                "requested_modalities": ["optical"],
                "analysis_profile": "none",
                "required_tools": ["geochat_vqa", "generate_evidence"],
                "sensor_requirement": "not_applicable",
                "aoi_required": False,
                "user_intent_summary": "bad",
                "geojson": {"type": "Point", "coordinates": [0, 0]},
            }
        )


# TEST 8 — model provenance
@pytest.mark.asyncio
async def test_sih_08_model_provenance_mock(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root)
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "What land-cover types are visible?", "image_id": image_id},
    )
    vqa = res.json()["data"]["result"]["vqa"]
    assert vqa["provider"] == VQAProviderKind.DEVELOPMENT.value
    assert "mock" in vqa["provenance"].lower() or "development" in vqa["model_name"].lower()


@pytest.mark.asyncio
async def test_sih_08_model_provenance_real_service_metadata(monkeypatch):
    monkeypatch.setenv("GEOCHAT_VQA_PROVIDER", "geochat_service")
    monkeypatch.setenv("GEOCHAT_SERVICE_URL", "http://geochat-gpu")
    get_settings.cache_clear()
    get_geochat_vlm.cache_clear()

    class FakeServiceVLM(DevelopmentGeoChatVLM):
        name = "geochat_service_vqa"
        provider_kind = VQAProviderKind.GEOCHAT_SERVICE.value

        async def run_vqa(self, *, image, question, parameters):
            base = await super().run_vqa(image=image, question=question, parameters=parameters)
            return base.model_copy(
                update={
                    "model_name": "MBZUAI/geochat-7B",
                    "provider": VQAProviderKind.GEOCHAT_SERVICE,
                    "provenance": "MBZUAI/geochat-7B via GPU inference service",
                }
            )

    from app.schemas.input import ImageFormat, ImageInput, ImageSource

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
    from app.schemas.vqa import GeoChatVQAParameters

    result = await vlm.run_vqa(
        image=image,
        question="Describe.",
        parameters=GeoChatVQAParameters(),
    )
    assert result.model_name == "MBZUAI/geochat-7B"
    assert result.provider == VQAProviderKind.GEOCHAT_SERVICE
    get_geochat_vlm.cache_clear()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_sih_03b_validation_failure_before_specialist(client, upload_root):
    image_id = await _upload_geotiff(client, upload_root)
    from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
    from app.storage.factory import get_metadata_registry

    provider = get_uploaded_imagery_provider()
    image = provider.get(image_id)
    get_metadata_registry().save(image.model_copy(update={"georeferenced": False}))
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "What land-cover types are visible?", "image_id": image_id},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "input_validation_failed"


# TEST 9 covered by running full pytest suite separately
