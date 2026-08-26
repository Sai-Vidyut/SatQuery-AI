"""Phase 13 — SIH mandatory cross-modal optical + SAR analysis tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.imagery.uploaded.compatibility import (
    resolve_co_registration_status,
    validate_optical_sar_pair,
)
from app.core.config import get_settings
from app.main import app
from app.schemas.cross_modal import CoRegistrationStatus
from app.schemas.domain import QueryRequest
from app.schemas.input import ImageFormat, ImageInput, ImageModality, ImageSource
from app.schemas.planning import QueryIntent
from app.services.cross_modal_intent import is_cross_modal_optical_sar_query
from app.services.planner.deterministic import build_deterministic_plan
from tests.fixtures.rasters import write_geotiff, write_invalid_tiff, write_jpeg


def _pair_request(query: str, optical_id: str, sar_id: str) -> QueryRequest:
    return QueryRequest(
        query=query,
        optical_image_id=optical_id,
        sar_image_id=sar_id,
    )


SIH_QUERY = (
    "Use the optical and SAR images together to identify built-up and water-covered regions."
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


async def _upload(
    client,
    upload_root: Path,
    *,
    name: str,
    modality: str,
    origin_lon: float = 77.59,
    benchmark_dataset: bool = False,
    co_registered_benchmark_pair: bool = False,
    benchmark_pair_id: str | None = None,
) -> str:
    path = upload_root / name
    write_geotiff(path, origin_lon=origin_lon)
    data: dict[str, str] = {"modality": modality}
    if benchmark_dataset:
        data["benchmark_dataset"] = "true"
    if co_registered_benchmark_pair:
        data["co_registered_benchmark_pair"] = "true"
    if benchmark_pair_id:
        data["benchmark_pair_id"] = benchmark_pair_id
    with path.open("rb") as f:
        res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": (name, f, "image/tiff")},
            data=data,
        )
    assert res.status_code == 200
    return res.json()["data"]["image"]["id"]


# TEST 1 — valid optical + SAR pair
@pytest.mark.asyncio
async def test_sih_01_valid_optical_sar_pair(client, upload_root):
    optical_id = await _upload(client, upload_root, name="optical.tif", modality="optical")
    sar_id = await _upload(client, upload_root, name="sar.tif", modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    assert res.status_code == 200
    result = res.json()["data"]["result"]
    assert result["status"] == "completed"
    assert result["cross_modal"]["task"] == "cross_modal_optical_sar"


# TEST 2 — optical + optical rejected
@pytest.mark.asyncio
async def test_sih_02_optical_optical_rejected(client, upload_root):
    optical_a = await _upload(client, upload_root, name="opt_a.tif", modality="optical")
    optical_b = await _upload(client, upload_root, name="opt_b.tif", modality="optical")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_a,
            "sar_image_id": optical_b,
        },
    )
    assert res.status_code == 400


# TEST 3 — SAR + SAR rejected
@pytest.mark.asyncio
async def test_sih_03_sar_sar_rejected(client, upload_root):
    sar_a = await _upload(client, upload_root, name="sar_a.tif", modality="sar")
    sar_b = await _upload(client, upload_root, name="sar_b.tif", modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": sar_a,
            "sar_image_id": sar_b,
        },
    )
    assert res.status_code == 400


# TEST 4 — non-overlapping geographic areas rejected
@pytest.mark.asyncio
async def test_sih_04_non_overlapping_rejected(client, upload_root):
    optical_id = await _upload(
        client, upload_root, name="optical.tif", modality="optical", origin_lon=10.0
    )
    sar_id = await _upload(
        client, upload_root, name="sar.tif", modality="sar", origin_lon=120.0
    )
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    assert res.status_code == 400


# TEST 5 — insufficient spatial compatibility (dimension warning)
@pytest.mark.asyncio
async def test_sih_05_dimension_mismatch_warning(upload_root, client):
    optical_path = upload_root / "optical_big.tif"
    sar_path = upload_root / "sar_small.tif"
    write_geotiff(optical_path, width=128, height=128)
    write_geotiff(sar_path, width=64, height=64)
    with optical_path.open("rb") as f:
        optical_res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("optical_big.tif", f, "image/tiff")},
            data={"modality": "optical"},
        )
    with sar_path.open("rb") as f:
        sar_res = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("sar_small.tif", f, "image/tiff")},
            data={"modality": "sar"},
        )
    optical = optical_res.json()["data"]["image"]
    sar = sar_res.json()["data"]["image"]
    from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider

    provider = get_uploaded_imagery_provider()
    validation = validate_optical_sar_pair(provider.get(optical["id"]), provider.get(sar["id"]))
    dim_checks = [c for c in validation.checks if c.check == "dimension_compatibility"]
    assert dim_checks
    assert dim_checks[0].status.value == "warn"
    assert any("Dimension mismatch" in w for w in validation.warnings)


# TEST 6 — co-registration not falsely claimed
@pytest.mark.asyncio
async def test_sih_06_coreg_not_falsely_claimed(client, upload_root):
    optical_id = await _upload(client, upload_root, name="optical.tif", modality="optical")
    sar_id = await _upload(client, upload_root, name="sar.tif", modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    assert res.status_code == 200
    cm = res.json()["data"]["result"]["cross_modal"]
    assert cm["co_registration_status"] == "overlap_only_not_verified"


# TEST 7 — verified benchmark pair
@pytest.mark.asyncio
async def test_sih_07_verified_benchmark_pair(client, upload_root):
    pair_token = "sih-benchmark-pair-001"
    optical_id = await _upload(
        client,
        upload_root,
        name="optical_bench.tif",
        modality="optical",
        benchmark_dataset=True,
        co_registered_benchmark_pair=True,
        benchmark_pair_id=pair_token,
    )
    sar_id = await _upload(
        client,
        upload_root,
        name="sar_bench.tif",
        modality="sar",
        benchmark_dataset=True,
        co_registered_benchmark_pair=True,
        benchmark_pair_id=pair_token,
    )
    from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider

    provider = get_uploaded_imagery_provider()
    status, _ = resolve_co_registration_status(provider.get(optical_id), provider.get(sar_id))
    assert status == CoRegistrationStatus.VERIFIED_BENCHMARK
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    assert res.status_code == 200
    assert (
        res.json()["data"]["result"]["cross_modal"]["co_registration_status"]
        == "verified_benchmark"
    )


# TEST 8 — representative SIH query routing
def test_sih_08_representative_query_intent():
    assert is_cross_modal_optical_sar_query(SIH_QUERY)
    plan = build_deterministic_plan(
        _pair_request(SIH_QUERY, "opt-1", "sar-1"),
    )
    assert plan.user_intent == QueryIntent.CROSS_MODAL_OPTICAL_SAR
    assert plan.user_intent != QueryIntent.SINGLE_IMAGE_VQA
    assert plan.user_intent != QueryIntent.SINGLE_IMAGE_CAPTION
    assert plan.user_intent != QueryIntent.BI_TEMPORAL_CHANGE_VQA


# TEST 9 — complementary-information query
def test_sih_09_complementary_query_routes_cross_modal():
    q = "What complementary information does the SAR image provide?"
    assert is_cross_modal_optical_sar_query(q)
    plan = build_deterministic_plan(_pair_request(q, "opt-1", "sar-1"))
    assert plan.user_intent == QueryIntent.CROSS_MODAL_OPTICAL_SAR


# TEST 10 — tool selection trace
@pytest.mark.asyncio
async def test_sih_10_tool_selection_trace(client, upload_root):
    optical_id = await _upload(client, upload_root, name="optical.tif", modality="optical")
    sar_id = await _upload(client, upload_root, name="sar.tif", modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    tools = [s["tool_name"] for s in res.json()["data"]["result"]["trace"]]
    assert "optical_analysis" in tools
    assert "sar_analysis" in tools
    assert "cross_modal_fusion" in tools


# TEST 11 — explicit fusion stage (not concatenation)
@pytest.mark.asyncio
async def test_sih_11_explicit_fusion_not_concatenation(client, upload_root):
    optical_id = await _upload(client, upload_root, name="optical.tif", modality="optical")
    sar_id = await _upload(client, upload_root, name="sar.tif", modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    cm = res.json()["data"]["result"]["cross_modal"]
    optical_summary = cm["optical_analysis"]["summary"]
    sar_summary = cm["sar_analysis"]["summary"]
    fused_summary = cm["fused_analysis"]["summary"]
    assert cm["fused_analysis"]["fusion_policy"]
    assert fused_summary != f"{optical_summary} {sar_summary}"
    assert "Cross-modal fusion produced" in fused_summary


# TEST 12 — provenance labels
@pytest.mark.asyncio
async def test_sih_12_provenance_labels(client, upload_root):
    optical_id = await _upload(client, upload_root, name="optical.tif", modality="optical")
    sar_id = await _upload(client, upload_root, name="sar.tif", modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    cm = res.json()["data"]["result"]["cross_modal"]
    assert "development" in cm["optical_analysis"]["analyzer"]
    assert "development" in cm["sar_analysis"]["analyzer"]
    assert cm["provider"] == "development"
    assert "development" in cm["provenance"].lower()


# TEST 13 — no fabricated confidence
@pytest.mark.asyncio
async def test_sih_13_no_fabricated_confidence(client, upload_root):
    optical_id = await _upload(client, upload_root, name="optical.tif", modality="optical")
    sar_id = await _upload(client, upload_root, name="sar.tif", modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    result = res.json()["data"]["result"]
    assert result["confidence_available"] is False
    assert result["cross_modal"]["confidence_available"] is False


# TEST 14 — fused regions carry fusion provenance
@pytest.mark.asyncio
async def test_sih_14_fused_regions_provenance(client, upload_root):
    optical_id = await _upload(client, upload_root, name="optical.tif", modality="optical")
    sar_id = await _upload(client, upload_root, name="sar.tif", modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    evidence = res.json()["data"]["result"]["evidence"]
    for region in evidence:
        assert region["metadata"].get("evidence_type") == "cross_modal_fusion"
        assert region["source"] == "cross_modal_fusion"


# TEST 15 — full trace sequence
@pytest.mark.asyncio
async def test_sih_15_trace_sequence(client, upload_root):
    optical_id = await _upload(client, upload_root, name="optical.tif", modality="optical")
    sar_id = await _upload(client, upload_root, name="sar.tif", modality="sar")
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    tools = [s["tool_name"] for s in res.json()["data"]["result"]["trace"]]
    assert tools.index("input_validation") < tools.index("plan_query")
    assert tools.index("plan_query") < tools.index("optical_analysis")
    assert tools.index("optical_analysis") < tools.index("sar_analysis")
    assert tools.index("sar_analysis") < tools.index("cross_modal_fusion")
    assert tools.index("cross_modal_fusion") < tools.index("generate_evidence")


# TEST 16 — malformed optical rejected before specialists
@pytest.mark.asyncio
async def test_sih_16_malformed_optical_rejected(client, upload_root):
    bad_path = upload_root / "bad_optical.tif"
    write_invalid_tiff(bad_path)
    sar_id = await _upload(client, upload_root, name="sar.tif", modality="sar")
    with bad_path.open("rb") as f:
        up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("bad_optical.tif", f, "image/tiff")},
            data={"modality": "optical"},
        )
    if up.status_code != 200:
        pytest.skip("Upload rejects malformed optical at ingest")
    optical_id = up.json()["data"]["image"]["id"]
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    assert res.status_code == 400
    if res.status_code == 200:
        tools = [s["tool_name"] for s in res.json()["data"]["result"]["trace"]]
        assert "optical_analysis" not in tools


# TEST 17 — malformed SAR rejected before specialists
@pytest.mark.asyncio
async def test_sih_17_malformed_sar_rejected(client, upload_root):
    optical_id = await _upload(client, upload_root, name="optical.tif", modality="optical")
    bad_path = upload_root / "bad_sar.tif"
    write_invalid_tiff(bad_path)
    with bad_path.open("rb") as f:
        up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("bad_sar.tif", f, "image/tiff")},
            data={"modality": "sar"},
        )
    if up.status_code != 200:
        pytest.skip("Upload rejects malformed SAR at ingest")
    sar_id = up.json()["data"]["image"]["id"]
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_id,
            "sar_image_id": sar_id,
        },
    )
    assert res.status_code == 400


# TEST 18 — production JPEG policy rejected
@pytest.mark.asyncio
async def test_sih_18_production_jpeg_rejected(client, upload_root):
    optical_path = upload_root / "optical.jpg"
    sar_path = upload_root / "sar.jpg"
    write_jpeg(optical_path)
    write_jpeg(sar_path)
    with optical_path.open("rb") as f:
        optical_up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("optical.jpg", f, "image/jpeg")},
            data={"modality": "optical", "benchmark_dataset": "false"},
        )
    with sar_path.open("rb") as f:
        sar_up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("sar.jpg", f, "image/jpeg")},
            data={"modality": "sar", "benchmark_dataset": "false"},
        )
    assert optical_up.status_code in (400, 422) or not optical_up.json()["success"]
    assert sar_up.status_code in (400, 422) or not sar_up.json()["success"]


# TEST 19 — benchmark JPEG accepted when rules pass
@pytest.mark.asyncio
async def test_sih_19_benchmark_jpeg_accepted(client, upload_root):
    optical_path = upload_root / "optical.jpg"
    sar_path = upload_root / "sar.jpg"
    write_jpeg(optical_path)
    write_jpeg(sar_path)
    with optical_path.open("rb") as f:
        optical_up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("optical.jpg", f, "image/jpeg")},
            data={"modality": "optical", "benchmark_dataset": "true"},
        )
    with sar_path.open("rb") as f:
        sar_up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("sar.jpg", f, "image/jpeg")},
            data={"modality": "sar", "benchmark_dataset": "true"},
        )
    assert optical_up.status_code == 200
    assert sar_up.status_code == 200
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": SIH_QUERY,
            "optical_image_id": optical_up.json()["data"]["image"]["id"],
            "sar_image_id": sar_up.json()["data"]["image"]["id"],
        },
    )
    assert res.status_code == 200


# TEST 21 — Phase 10 VQA regression
@pytest.mark.asyncio
async def test_sih_21_phase10_vqa_regression(client, upload_root):
    path = upload_root / "vqa.tif"
    write_geotiff(path)
    with path.open("rb") as f:
        up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("vqa.tif", f, "image/tiff")},
            data={"modality": "optical"},
        )
    image_id = up.json()["data"]["image"]["id"]
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "What land-cover types are visible?",
            "image_id": image_id,
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["result"]["vqa"]["task"] == "single_image_vqa"


# TEST 22 — Phase 11 caption regression
@pytest.mark.asyncio
async def test_sih_22_phase11_caption_regression(client, upload_root):
    path = upload_root / "caption.tif"
    write_geotiff(path)
    with path.open("rb") as f:
        up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("caption.tif", f, "image/tiff")},
            data={"modality": "optical"},
        )
    image_id = up.json()["data"]["image"]["id"]
    res = await client.post(
        "/api/v1/query/submit",
        json={
            "query": "Describe this satellite scene.",
            "image_id": image_id,
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["result"]["caption"]["task"] == "single_image_caption"


# TEST 23 — Phase 12 bi-temporal regression
@pytest.mark.asyncio
async def test_sih_23_phase12_bi_temporal_regression(client, upload_root):
    earlier_path = upload_root / "before.tif"
    later_path = upload_root / "after.tif"
    write_geotiff(earlier_path)
    write_geotiff(later_path)
    with earlier_path.open("rb") as f:
        earlier_up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("before.tif", f, "image/tiff")},
            data={
                "modality": "optical",
                "acquisition_datetime": "2023-01-01T00:00:00+00:00",
            },
        )
    with later_path.open("rb") as f:
        later_up = await client.post(
            "/api/v1/imagery/upload",
            files={"file": ("after.tif", f, "image/tiff")},
            data={
                "modality": "optical",
                "acquisition_datetime": "2024-01-01T00:00:00+00:00",
            },
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
    assert res.json()["data"]["result"]["bi_temporal_change"]["task"] == "bi_temporal_change_vqa"


# TEST 24 — Earth Engine catalog regression (planner only)
def test_sih_24_catalog_planner_regression():
    from app.schemas.domain import AOI, GeoJSONGeometry

    aoi = AOI(
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[[[0.0, 0.0], [0.01, 0.0], [0.01, 0.01], [0.0, 0.01], [0.0, 0.0]]],
        )
    )
    plan = build_deterministic_plan(
        QueryRequest(
            query="Show significant spectral change",
            aoi=aoi,
            earlier_date="2024-01-01",
            later_date="2024-06-01",
        )
    )
    assert plan.user_intent.value in {"spectral_change", "construction", "radar_change", "multimodal_comparison"}
