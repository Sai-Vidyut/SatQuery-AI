"""Phase 12 — SIH mandatory bi-temporal change analysis tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.imagery.uploaded.compatibility import validate_bi_temporal
from app.core.config import get_settings
from app.main import app
from app.schemas.domain import QueryRequest
from app.schemas.input import ImageFormat, ImageInput, ImageModality, ImageSource
from app.schemas.planning import QueryIntent
from app.services.bi_temporal_intent import is_bi_temporal_change_query
from app.services.planner.deterministic import build_deterministic_plan
from tests.fixtures.rasters import write_bi_temporal_scene, write_geotiff, write_invalid_tiff, write_jpeg


def _pair_request(query: str, earlier_id: str, later_id: str) -> QueryRequest:
    return QueryRequest(
        query=query,
        earlier_image_id=earlier_id,
        later_image_id=later_id,
    )


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
    yield root
    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()
    get_uploaded_imagery_provider.cache_clear()
    get_settings.cache_clear()


async def _upload_geotiff(
    client,
    upload_root: Path,
    *,
    name: str = "scene.tif",
    acquisition_datetime: str,
    origin_lon: float = 77.59,
    scenario: str = "vegetation_loss",
    role: str | None = None,
) -> str:
    path = upload_root / name
    if role in {"earlier", "later"}:
        write_bi_temporal_scene(
            path,
            role=role,  # type: ignore[arg-type]
            scenario=scenario,  # type: ignore[arg-type]
            origin_lon=origin_lon,
        )
    else:
        if "before" in name:
            inferred_role = "earlier"
        elif "after" in name or name.endswith("2.tif"):
            inferred_role = "later"
        else:
            inferred_role = "earlier" if name.endswith("1.tif") else "later"
        write_bi_temporal_scene(
            path,
            role=inferred_role,  # type: ignore[arg-type]
            scenario=scenario,  # type: ignore[arg-type]
            origin_lon=origin_lon,
        )
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": (name, f, "image/tiff")},
            data={"modality": "multispectral", "acquisition_datetime": acquisition_datetime},
        )
    assert res.status_code == 200
    return res.json()["data"]["image"]["id"]


# TEST 1 — valid bi-temporal optical pair
@pytest.mark.asyncio
async def test_sih_01_valid_bi_temporal_optical_pair(client, upload_root):
    earlier_id = await _upload_geotiff(
        client, upload_root, name="before.tif", acquisition_datetime="2023-01-01T00:00:00+00:00"
    )
    later_id = await _upload_geotiff(
        client, upload_root, name="after.tif", acquisition_datetime="2024-01-01T00:00:00+00:00"
    )
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "What changed between these two dates, and where did the change occur?",
            "earlier_image_id": earlier_id,
            "later_image_id": later_id,
        },
    )
    assert res.status_code == 200
    result = res.json()["data"]["result"]
    assert result["status"] == "completed"
    assert result["bi_temporal_change"]["task"] == "bi_temporal_change_vqa"
    assert "detect_change" in [s["tool_name"] for s in result["trace"]]
    assert "change_understanding" in [s["tool_name"] for s in result["trace"]]


# TEST 2 — reversed temporal order rejected
@pytest.mark.asyncio
async def test_sih_02_reversed_temporal_order_rejected(client, upload_root):
    earlier_id = await _upload_geotiff(
        client, upload_root, name="before.tif", acquisition_datetime="2024-01-01T00:00:00+00:00"
    )
    later_id = await _upload_geotiff(
        client, upload_root, name="after.tif", acquisition_datetime="2023-01-01T00:00:00+00:00"
    )
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "What changed between these two dates?",
            "earlier_image_id": earlier_id,
            "later_image_id": later_id,
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "input_validation_failed"


# TEST 3 — identical dates rejected
def test_sih_03_identical_dates_rejected():
    dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    earlier_id = "0" * 31 + "1"
    later_id = "0" * 31 + "2"
    earlier = ImageInput(
        id=earlier_id,
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="a.tif",
        width=64,
        height=64,
        file_size_bytes=100,
        georeferenced=True,
        bounds=[77.59, 12.97, 77.61, 12.99],
        source=ImageSource.UPLOAD,
        acquisition_datetime=dt,
    )
    later = earlier.model_copy(update={"id": later_id, "filename": "b.tif"})
    result = validate_bi_temporal(earlier, later, require_acquisition_dates=True)
    assert result.valid is False
    assert any("acquisition" in e.lower() or "temporal" in e.lower() for e in result.errors)


# TEST 4 — non-overlapping extents rejected
def test_sih_04_non_overlapping_rejected():
    earlier = ImageInput(
        id="c" * 32,
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="a.tif",
        width=64,
        height=64,
        file_size_bytes=100,
        georeferenced=True,
        bounds=[77.59, 12.97, 77.61, 12.99],
        source=ImageSource.UPLOAD,
        acquisition_datetime=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    later = ImageInput(
        id="d" * 32,
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="b.tif",
        width=64,
        height=64,
        file_size_bytes=100,
        georeferenced=True,
        bounds=[80.0, 12.97, 80.2, 12.99],
        source=ImageSource.UPLOAD,
        acquisition_datetime=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    result = validate_bi_temporal(earlier, later, require_acquisition_dates=True)
    assert result.valid is False


# TEST 5 — incompatible CRS warns
def test_sih_05_incompatible_crs_warning():
    earlier = ImageInput(
        id="e" * 32,
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="a.tif",
        width=64,
        height=64,
        file_size_bytes=100,
        georeferenced=True,
        crs="EPSG:4326",
        bounds=[77.59, 12.97, 77.61, 12.99],
        source=ImageSource.UPLOAD,
        acquisition_datetime=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    later = ImageInput(
        id="f" * 32,
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="b.tif",
        width=64,
        height=64,
        file_size_bytes=100,
        georeferenced=True,
        crs="EPSG:3857",
        bounds=[77.59, 12.97, 77.61, 12.99],
        source=ImageSource.UPLOAD,
        acquisition_datetime=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    result = validate_bi_temporal(earlier, later, require_acquisition_dates=True)
    assert result.valid is True
    assert any("crs" in w.lower() for w in result.warnings)


# TEST 6 — dimension mismatch warns per Phase 8
def test_sih_06_dimension_mismatch_warns():
    earlier = ImageInput(
        id="06060606060606060606060606060606",
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="a.tif",
        width=100,
        height=100,
        file_size_bytes=100,
        georeferenced=True,
        bounds=[77.59, 12.97, 77.61, 12.99],
        source=ImageSource.UPLOAD,
        acquisition_datetime=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    later = ImageInput(
        id="07070707070707070707070707070707",
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="b.tif",
        width=200,
        height=200,
        file_size_bytes=100,
        georeferenced=True,
        bounds=[77.59, 12.97, 77.61, 12.99],
        source=ImageSource.UPLOAD,
        acquisition_datetime=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    result = validate_bi_temporal(earlier, later, require_acquisition_dates=True)
    assert result.valid is True
    assert result.warnings


# TEST 7 — change question routing
def test_sih_07_change_query_routing():
    query = "What changed between these two dates, and where did the change occur?"
    assert is_bi_temporal_change_query(query)
    plan = build_deterministic_plan(_pair_request(query, "a" * 32, "b" * 32))
    assert plan.user_intent == QueryIntent.BI_TEMPORAL_CHANGE_VQA
    assert [t.value for t in plan.required_tools] == [
        "detect_change",
        "change_understanding",
        "generate_evidence",
    ]


# TEST 8 — built-up change query
@pytest.mark.asyncio
async def test_sih_08_built_up_change_query(client, upload_root):
    earlier_id = await _upload_geotiff(
        client,
        upload_root,
        name="b1.tif",
        acquisition_datetime="2023-06-01T00:00:00+00:00",
        scenario="urban",
        role="earlier",
    )
    later_id = await _upload_geotiff(
        client,
        upload_root,
        name="b2.tif",
        acquisition_datetime="2024-06-01T00:00:00+00:00",
        scenario="urban",
        role="later",
    )
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "Has the built-up area increased, decreased, or remained unchanged?",
            "earlier_image_id": earlier_id,
            "later_image_id": later_id,
        },
    )
    assert res.status_code == 200
    assert "built-up" in res.json()["data"]["result"]["bi_temporal_change"]["change_summary"].lower()


# TEST 9 — change regions in result
@pytest.mark.asyncio
async def test_sih_09_change_regions_present(client, upload_root):
    earlier_id = await _upload_geotiff(
        client, upload_root, name="c1.tif", acquisition_datetime="2023-01-01T00:00:00+00:00"
    )
    later_id = await _upload_geotiff(
        client, upload_root, name="c2.tif", acquisition_datetime="2024-01-01T00:00:00+00:00"
    )
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "What changed between these two dates?",
            "earlier_image_id": earlier_id,
            "later_image_id": later_id,
        },
    )
    result = res.json()["data"]["result"]
    assert result["bi_temporal_change"]["changed_region_count"] > 0
    assert len(result["evidence"]) > 0
    assert result["bi_temporal_change"]["change_map_available"] is True


# TEST 10 — no fabricated evidence when zero regions (unit-level)
@pytest.mark.asyncio
async def test_sih_10_no_fabricated_evidence_on_empty(monkeypatch):
    from app.tools.temporal.change_understanding import ChangeUnderstandingTool
    from app.schemas.change_understanding import ChangeUnderstandingToolInput
    from app.schemas.domain import ChangeDetectionOutput, DataMode

    earlier = ImageInput(
        id="2" * 32,
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename="a.tif",
        width=64,
        height=64,
        file_size_bytes=100,
        georeferenced=True,
        source=ImageSource.UPLOAD,
        acquisition_datetime=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    later = earlier.model_copy(update={"id": "3" * 32, "filename": "b.tif", "acquisition_datetime": datetime(2024, 1, 1, tzinfo=timezone.utc)})
    detections = ChangeDetectionOutput(
        regions=[],
        raw_detection_count=0,
        detector="deterministic_change_detector",
        mode=DataMode.DEVELOPMENT,
    )
    out = await ChangeUnderstandingTool().execute(
        ChangeUnderstandingToolInput(
            query="What changed?",
            earlier=earlier,
            later=later,
            detections=detections,
        )
    )
    assert out.result.changed_region_count == 0
    assert out.result.change_map_available is False


# TEST 11 — confidence from CVA preserved
@pytest.mark.asyncio
async def test_sih_11_confidence_preserved(client, upload_root):
    earlier_id = await _upload_geotiff(
        client, upload_root, name="d1.tif", acquisition_datetime="2023-01-01T00:00:00+00:00"
    )
    later_id = await _upload_geotiff(
        client, upload_root, name="d2.tif", acquisition_datetime="2024-01-01T00:00:00+00:00"
    )
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "What changed between these two dates?",
            "earlier_image_id": earlier_id,
            "later_image_id": later_id,
        },
    )
    result = res.json()["data"]["result"]
    assert result["confidence_available"] is True
    assert result["confidence"] > 0


# TEST 12 — trace
@pytest.mark.asyncio
async def test_sih_12_trace(client, upload_root):
    earlier_id = await _upload_geotiff(
        client, upload_root, name="e1.tif", acquisition_datetime="2023-01-01T00:00:00+00:00"
    )
    later_id = await _upload_geotiff(
        client, upload_root, name="e2.tif", acquisition_datetime="2024-01-01T00:00:00+00:00"
    )
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "What changed between these two dates?",
            "earlier_image_id": earlier_id,
            "later_image_id": later_id,
        },
    )
    names = [s["tool_name"] for s in res.json()["data"]["result"]["trace"]]
    assert "input_validation" in names
    assert "plan_query" in names
    assert "detect_change" in names
    assert "change_understanding" in names
    assert "generate_evidence" in names


# TEST 14 — VQA regression
@pytest.mark.asyncio
async def test_sih_14_single_image_vqa_regression(client, upload_root):
    path = upload_root / "vqa.tif"
    write_geotiff(path)
    with path.open("rb") as f:
        up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("vqa.tif", f, "image/tiff")},
        )
    image_id = up.json()["data"]["image"]["id"]
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "What land-cover types are visible?", "image_id": image_id},
    )
    assert res.status_code == 200
    assert res.json()["data"]["result"]["vqa"]["task"] == "single_image_vqa"


# TEST 15 — caption regression
@pytest.mark.asyncio
async def test_sih_15_scene_caption_regression(client, upload_root):
    path = upload_root / "cap.tif"
    write_geotiff(path)
    with path.open("rb") as f:
        up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("cap.tif", f, "image/tiff")},
        )
    image_id = up.json()["data"]["image"]["id"]
    res = await client.post(
        "/api/v1/query/submit",
        json={"query": "Describe this satellite scene.", "image_id": image_id},
    )
    assert res.status_code == 200
    assert res.json()["data"]["result"]["caption"]["task"] == "single_image_caption"


# TEST 16 — EE catalog regression
@pytest.mark.asyncio
async def test_sih_16_catalog_regression(client):
    from tests.test_api import SAMPLE_QUERY

    res = await client.post("/api/v1/query/submit", json=SAMPLE_QUERY.model_dump(mode="json"))
    assert res.status_code == 200


# TEST 17 — malformed pair rejected before specialist
@pytest.mark.asyncio
async def test_sih_17_malformed_pair_rejected(client, upload_root):
    earlier_id = await _upload_geotiff(
        client, upload_root, name="ok.tif", acquisition_datetime="2023-01-01T00:00:00+00:00"
    )
    from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
    from app.storage.factory import get_metadata_registry

    provider = get_uploaded_imagery_provider()
    bad = provider.get(earlier_id).model_copy(update={"georeferenced": False})
    get_metadata_registry().save(bad)
    later_id = await _upload_geotiff(
        client, upload_root, name="ok2.tif", acquisition_datetime="2024-01-01T00:00:00+00:00"
    )
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "What changed?",
            "earlier_image_id": earlier_id,
            "later_image_id": later_id,
        },
    )
    assert res.status_code == 400
    assert "detect_change" not in [s["tool_name"] for s in res.json().get("data", {}).get("trace", [])]


# TEST 18 — production JPEG rejected
@pytest.mark.asyncio
async def test_sih_18_production_jpeg_rejected(client, upload_root):
    path = upload_root / "x.jpg"
    write_jpeg(path)
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("x.jpeg", f, "image/jpeg")},
            data={"benchmark_dataset": "false", "acquisition_datetime": "2023-01-01T00:00:00+00:00"},
        )
    assert res.status_code == 400


# TEST 19 — benchmark JPEG pair accepted at validation
@pytest.mark.asyncio
async def test_sih_19_benchmark_jpeg_pair(client, upload_root):
    a = upload_root / "a.jpg"
    b = upload_root / "b.jpg"
    write_jpeg(a)
    write_jpeg(b)
    with a.open("rb") as fa:
        up_a = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("a.jpeg", fa, "image/jpeg")},
            data={"benchmark_dataset": "true", "acquisition_datetime": "2023-01-01T00:00:00+00:00"},
        )
    with b.open("rb") as fb:
        up_b = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("b.jpeg", fb, "image/jpeg")},
            data={"benchmark_dataset": "true", "acquisition_datetime": "2024-01-01T00:00:00+00:00"},
        )
    assert up_a.status_code == 200 and up_b.status_code == 200
    earlier = up_a.json()["data"]["image"]
    later = up_b.json()["data"]["image"]
    res = await client.post(
        "/api/v1/imagery/validate-input",
        json={"input_type": "bi_temporal", "earlier": earlier, "later": later},
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["detected_input_type"] == "bi_temporal"
