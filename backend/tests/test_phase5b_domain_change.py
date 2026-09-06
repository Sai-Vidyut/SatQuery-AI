"""Phase 5B — competition change-domain routing, claims, and significance."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.adapters.change.bi_temporal.indices import select_primary_index
from app.core.errors import SatQueryError
from app.schemas.change_domain import ChangeDomain, ClaimStrength
from app.schemas.domain import AOI, DataMode, EvidenceRegion, GenerateEvidenceOutput, GeoJSONGeometry, Metric, QueryRequest
from app.schemas.planning import QueryIntent
from app.services.answer_engine import AnswerEngine
from app.services.change_domain import (
    annotate_regions_for_domain,
    compute_significance_score,
    domain_claim_type,
    evaluate_domain_support,
    resolve_change_domain,
)
from app.services.planner.deterministic import build_deterministic_plan
from app.services.query_controller import QueryController
from tests.fixtures.rasters import SENTINEL2_BAND_NAMES, write_bi_temporal_scene
from tests.test_uploaded_bitemporal_change import _image_input


def _aoi() -> AOI:
    return AOI(
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [77.56, 12.94],
                    [77.60, 12.94],
                    [77.60, 12.98],
                    [77.56, 12.98],
                    [77.56, 12.94],
                ]
            ],
        )
    )


def _region(confidence: float = 0.7, area_m2: float = 1000.0, region_id: str = "r-1") -> EvidenceRegion:
    return EvidenceRegion(
        id=region_id,
        type="spectral_change",
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [77.57, 12.95],
                    [77.58, 12.95],
                    [77.58, 12.96],
                    [77.57, 12.96],
                    [77.57, 12.95],
                ]
            ],
        ),
        confidence=confidence,
        source="test",
        metrics=[Metric(name="area_m2", value=area_m2, unit="m²", source="test")],
        metadata={"evidence_type": "spectral_change", "claim_type": "none"},
    )


@pytest.mark.parametrize(
    ("query", "domain"),
    [
        ("Show urban expansion in this AOI.", ChangeDomain.URBAN_EXPANSION),
        ("Find deforestation between these dates.", ChangeDomain.DEFORESTATION),
        ("Show water shrinkage in the lake.", ChangeDomain.WATER_SHRINKAGE),
        ("Find infrastructure development changes.", ChangeDomain.INFRASTRUCTURE_DEVELOPMENT),
        ("Find mining activity in this area.", ChangeDomain.MINING),
    ],
)
def test_domain_query_resolution(query: str, domain: ChangeDomain):
    assert resolve_change_domain(query) == domain


@pytest.mark.parametrize(
    ("query", "intent", "domain"),
    [
        ("Show urban expansion.", QueryIntent.CONSTRUCTION, ChangeDomain.URBAN_EXPANSION),
        ("Show deforestation.", QueryIntent.SPECTRAL_CHANGE, ChangeDomain.DEFORESTATION),
        ("Show water shrinkage.", QueryIntent.SPECTRAL_CHANGE, ChangeDomain.WATER_SHRINKAGE),
        ("Show infrastructure development.", QueryIntent.CONSTRUCTION, ChangeDomain.INFRASTRUCTURE_DEVELOPMENT),
        ("Find mining activity.", QueryIntent.SPECTRAL_CHANGE, ChangeDomain.MINING),
        ("Show me significant new construction.", QueryIntent.CONSTRUCTION, None),
        ("Show me significant spectral change.", QueryIntent.SPECTRAL_CHANGE, None),
    ],
)
def test_planner_domain_routing(query: str, intent: QueryIntent, domain: ChangeDomain | None):
    plan = build_deterministic_plan(
        QueryRequest(
            query=query,
            aoi=_aoi(),
            earlier_date=date(2024, 1, 1),
            later_date=date(2025, 1, 1),
        )
    )
    assert plan.user_intent == intent
    assert plan.change_domain == domain


def test_index_routing_for_domains():
    band_map = {"red": 0, "green": 1, "nir": 2, "swir": 3}
    assert select_primary_index(4, band_map, query_hint="show deforestation") == "ndvi"
    assert select_primary_index(5, {**band_map, "swir": 4}, query_hint="urban expansion") == "ndbi"
    assert select_primary_index(4, band_map, query_hint="water shrinkage") == "ndwi"
    assert select_primary_index(4, band_map, query_hint="mining activity") == "ndvi"


def test_claim_type_and_strength_for_deforestation():
    strength, score = evaluate_domain_support(
        ChangeDomain.DEFORESTATION,
        direction_hint="vegetation_loss",
        primary_index="ndvi",
    )
    assert strength == ClaimStrength.SUPPORTED
    assert score >= 0.45
    regions = annotate_regions_for_domain(
        [_region()],
        ChangeDomain.DEFORESTATION,
        direction_hint="vegetation_loss",
        primary_index="ndvi",
    )
    assert regions[0].metadata["claim_type"] == domain_claim_type(ChangeDomain.DEFORESTATION)
    assert regions[0].metadata["claim_strength"] == ClaimStrength.SUPPORTED.value
    assert regions[0].metadata["significance_score"] > 0


def test_mining_does_not_claim_proof_in_answer():
    engine = AnswerEngine()
    evidence = GenerateEvidenceOutput(
        regions=annotate_regions_for_domain(
            [_region()],
            ChangeDomain.MINING,
            direction_hint="vegetation_loss",
            primary_index="ndvi",
        ),
        metrics=[],
        confidence=0.6,
    )
    answer = engine.compose(
        QueryRequest(
            query="Find mining activity.",
            aoi=_aoi(),
            earlier_date=date(2024, 1, 1),
            later_date=date(2025, 1, 1),
        ),
        evidence,
        DataMode.DEVELOPMENT,
        change_domain=ChangeDomain.MINING,
    )
    assert "cannot confirm mining" in answer.lower()


def test_significance_ranking_orders_by_score():
    low = _region(confidence=0.3, area_m2=100.0, region_id="r-low")
    high = _region(confidence=0.9, area_m2=5000.0, region_id="r-high")
    ranked = annotate_regions_for_domain(
        [low, high],
        ChangeDomain.DEFORESTATION,
        direction_hint="vegetation_loss",
        primary_index="ndvi",
    )
    assert ranked[0].id == "r-high"
    assert ranked[0].metadata["significance_score"] >= ranked[1].metadata["significance_score"]


def test_significance_formula_components():
    region = _region(confidence=0.5, area_m2=250.0)
    score = compute_significance_score(region, total_changed_area_m2=1000.0, domain_support_score=0.8)
    assert 0.0 < score <= 1.0


@pytest.mark.asyncio
async def test_upload_deforestation_domain_metadata(tmp_path, monkeypatch):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(upload_root))
    monkeypatch.setenv("UPLOAD_CHANGE_DETECTOR", "bi_temporal")
    from app.core.config import get_settings
    from app.storage.factory import get_image_storage, get_metadata_registry

    get_settings.cache_clear()
    get_image_storage.cache_clear()
    get_metadata_registry.cache_clear()

    earlier_path = tmp_path / "earlier.tif"
    later_path = tmp_path / "later.tif"
    write_bi_temporal_scene(earlier_path, role="earlier", scenario="vegetation_loss")
    write_bi_temporal_scene(later_path, role="later", scenario="vegetation_loss")

    storage = get_image_storage()
    earlier_id = "2" * 31 + "1"
    later_id = "2" * 31 + "2"
    for image_id, src_path in ((earlier_id, earlier_path), (later_id, later_path)):
        with src_path.open("rb") as handle:
            storage.save(image_id, ".tif", handle)

    earlier = _image_input(earlier_id, earlier_path, band_names=SENTINEL2_BAND_NAMES).model_copy(
        update={"acquisition_datetime": datetime(2020, 1, 1, tzinfo=timezone.utc)}
    )
    later = _image_input(later_id, later_path, band_names=SENTINEL2_BAND_NAMES).model_copy(
        update={
            "id": later_id,
            "acquisition_datetime": datetime(2023, 1, 1, tzinfo=timezone.utc),
        }
    )
    registry = get_metadata_registry()
    registry.save(earlier)
    registry.save(later)

    controller = QueryController()
    result = await controller.submit(
        QueryRequest(
            query="Show deforestation between these images.",
            earlier_image_id=earlier_id,
            later_image_id=later_id,
        )
    )
    assert result.bi_temporal_change is not None
    assert "definitive proof of deforestation" in result.answer.lower()
    if result.evidence:
        assert result.evidence[0].metadata.get("change_domain") == ChangeDomain.DEFORESTATION.value
        assert "significance_score" in result.evidence[0].metadata


@pytest.mark.asyncio
async def test_building_policy_still_rejects_2011():
    controller = QueryController()
    request = QueryRequest(
        query="Show me new buildings.",
        aoi=_aoi(),
        earlier_date=date(2011, 1, 1),
        later_date=date(2026, 1, 1),
    )
    with pytest.raises(SatQueryError) as exc_info:
        await controller.submit(request)
    assert exc_info.value.code == "imagery_policy_unsupported"
