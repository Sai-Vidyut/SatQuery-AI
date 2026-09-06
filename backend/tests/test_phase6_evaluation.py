"""Phase 6 — evaluation harness, metrics, and real-data path tests."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.change_domain import ChangeDomain
from app.schemas.domain import (
    AOI,
    AnalysisResult,
    AnalysisStatus,
    DataMode,
    EvidenceRegion,
    FetchImageryOutput,
    GenerateEvidenceOutput,
    GeoJSONGeometry,
    ImageryResult,
    ImageryScene,
    Metric,
    QueryRequest,
    SensorType,
    SpatialMetadata,
    TraceStatus,
    TraceStep,
)
from app.schemas.planning import QueryIntent
from app.services.planner.deterministic import build_deterministic_plan
from evaluation.metrics import compute_region_metrics
from evaluation.models import EvaluationCase, EvaluationType
from evaluation.runner import EvaluationRunner, load_cases
from evaluation.reports import render_markdown_report


def _aoi(west: float, south: float, east: float, north: float) -> AOI:
    return AOI(
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],
                ]
            ],
        )
    )


def _region(box: list[float], region_id: str = "pred-1") -> EvidenceRegion:
    west, south, east, north = box
    return EvidenceRegion(
        id=region_id,
        type="spectral_change",
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],
                ]
            ],
        ),
        confidence=0.8,
        source="earth_engine_cva",
        metrics=[Metric(name="area_m2", value=1000.0, unit="m²", source="test")],
        metadata={"evidence_type": "spectral_change", "claim_type": "none"},
    )


def test_load_catalog_cases():
    cases = load_cases()
    assert len(cases) == 5
    domains = {case.domain for case in cases}
    assert domains == {
        "urban_expansion",
        "deforestation",
        "water_shrinkage",
        "infrastructure_development",
        "mining",
    }
    assert all(case.evaluation_type == EvaluationType.QUALITATIVE for case in cases)
    assert all(case.later_date > case.earlier_date for case in cases)


@pytest.mark.parametrize(
    ("case_id", "intent", "domain"),
    [
        ("urban_expansion_bengaluru_east", QueryIntent.CONSTRUCTION, ChangeDomain.URBAN_EXPANSION),
        ("deforestation_amazon_rondonia", QueryIntent.SPECTRAL_CHANGE, ChangeDomain.DEFORESTATION),
        ("water_shrinkage_lake_mead", QueryIntent.SPECTRAL_CHANGE, ChangeDomain.WATER_SHRINKAGE),
        ("infrastructure_dubai_south", QueryIntent.CONSTRUCTION, ChangeDomain.INFRASTRUCTURE_DEVELOPMENT),
        ("mining_disturbance_eu_reference", QueryIntent.SPECTRAL_CHANGE, ChangeDomain.MINING),
    ],
)
def test_evaluation_case_planner_routing(case_id: str, intent: QueryIntent, domain: ChangeDomain):
    case = next(c for c in load_cases() if c.case_id == case_id)
    plan = build_deterministic_plan(
        QueryRequest(
            query=case.query,
            aoi=case.aoi,
            earlier_date=case.earlier_date,
            later_date=case.later_date,
        )
    )
    assert plan.user_intent == intent
    assert plan.change_domain == domain


def test_metrics_perfect_overlap():
    box = [0.0, 0.0, 0.01, 0.01]
    gt = GeoJSONGeometry(
        type="Polygon",
        coordinates=[
            [
                [0.0, 0.0],
                [0.01, 0.0],
                [0.01, 0.01],
                [0.0, 0.01],
                [0.0, 0.0],
            ]
        ],
    )
    metrics = compute_region_metrics([_region(box)], gt)
    assert metrics.iou is not None and metrics.iou > 0.9
    assert metrics.precision is not None and metrics.precision > 0.9
    assert metrics.recall is not None and metrics.recall > 0.9


def test_metrics_no_overlap():
    gt = GeoJSONGeometry(
        type="Polygon",
        coordinates=[
            [
                [1.0, 1.0],
                [1.01, 1.0],
                [1.01, 1.01],
                [1.0, 1.01],
                [1.0, 1.0],
            ]
        ],
    )
    metrics = compute_region_metrics([_region([0.0, 0.0, 0.01, 0.01])], gt)
    assert metrics.iou == 0.0
    assert metrics.precision == 0.0


@pytest.mark.asyncio
async def test_evaluation_runner_records_earth_engine_result(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "earth_engine")
    from app.core.config import get_settings

    get_settings.cache_clear()

    ee_imagery = ImageryResult(
        source="earth_engine",
        mode=DataMode.EARTH_ENGINE,
        sensor=SensorType.SENTINEL_2,
        scenes=[
            ImageryScene(
                scene_id="S2A_20240601",
                acquisition_date=date(2024, 6, 1),
                platform_id="COPERNICUS/S2_SR_HARMONIZED/20240601",
                cloud_cover_percent=5.0,
            )
        ],
        spatial=SpatialMetadata(bbox=[77.72, 12.95, 77.78, 13.0]),
        provider_metadata={"selection_policy": "1.0.0"},
    )
    evidence_region = _region([77.73, 12.96, 77.75, 12.98], "ee-1").model_copy(
        update={
            "metadata": {
                "evidence_type": "spectral_change",
                "claim_type": "urban_expansion_candidate",
                "change_domain": "urban_expansion",
            }
        }
    )
    result = AnalysisResult(
        status=AnalysisStatus.COMPLETED,
        session_id="sess-1",
        answer="Imagery policy supports building-instance temporal analysis.",
        confidence=0.72,
        metrics=[],
        evidence=[evidence_region],
        trace=[
            TraceStep(
                id="plan-1",
                tool_name="plan_query",
                status=TraceStatus.COMPLETED,
                metadata={
                    "intent": "construction",
                    "change_domain": "urban_expansion",
                    "required_tools": ["fetch_imagery", "detect_change"],
                },
            ),
            TraceStep(
                id="fetch-1",
                tool_name="fetch_imagery",
                status=TraceStatus.COMPLETED,
                duration_ms=1200,
                metadata={
                    "provider": "earth_engine",
                    "data_mode": "earth_engine",
                    "scenes": [
                        {
                            "scene_id": "S2A_20240601",
                            "acquisition_date": "2024-06-01",
                            "platform_id": "COPERNICUS/S2_SR_HARMONIZED/20240601",
                        }
                    ],
                },
            ),
            TraceStep(
                id="detect-1",
                tool_name="detect_change",
                status=TraceStatus.COMPLETED,
                duration_ms=3400,
                metadata={"detector": "earth_engine_cva", "region_count": 1},
            ),
        ],
        mode=DataMode.EARTH_ENGINE,
    )

    controller = MagicMock()
    controller.submit = AsyncMock(return_value=result)
    runner = EvaluationRunner(controller=controller)
    case = load_cases()[0]
    record = await runner.run_case(case)

    assert record.status == "completed"
    assert record.data_mode == "earth_engine"
    assert record.imagery_provider == "earth_engine"
    assert record.answer_mentions_development_mock is False
    assert record.region_count == 1
    assert record.candidate_region_count == 1
    assert record.planner_intent == "construction"
    assert record.total_duration_ms is not None
    assert any(step.tool_name == "fetch_imagery" for step in record.step_timings)


@pytest.mark.asyncio
async def test_evaluation_runner_records_failure():
    from app.core.errors import SatQueryError

    controller = MagicMock()
    controller.submit = AsyncMock(
        side_effect=SatQueryError("no_imagery_found", "No scenes in date range", status_code=404)
    )
    runner = EvaluationRunner(controller=controller)
    record = await runner.run_case(load_cases()[0])
    assert record.status == "failed"
    assert record.error_code == "no_imagery_found"


def test_render_markdown_report():
    from evaluation.models import EvaluationRecord

    md = render_markdown_report(
        [
            EvaluationRecord(
                case_id="test",
                domain="deforestation",
                evaluation_type=EvaluationType.QUALITATIVE,
                status="completed",
                region_count=2,
            )
        ]
    )
    assert "deforestation" in md
    assert "test" in md


def test_fetch_imagery_trace_metadata_in_controller():
    from app.services.query_controller import QueryController

    controller = QueryController()
    imagery = ImageryResult(
        source="earth_engine",
        mode=DataMode.EARTH_ENGINE,
        sensor=SensorType.SENTINEL_2,
        scenes=[
            ImageryScene(
                scene_id="scene-a",
                acquisition_date=date(2024, 1, 1),
                platform_id="COPERNICUS/S2_SR_HARMONIZED/scene-a",
            )
        ],
        spatial=SpatialMetadata(bbox=[0, 0, 1, 1]),
    )
    output = FetchImageryOutput(result=imagery)
    meta = controller._step_metadata("fetch_imagery", output)
    assert meta is not None
    assert meta["data_mode"] == "earth_engine"
    assert meta["scene_count"] == 1
    assert meta["scenes"][0]["platform_id"].startswith("COPERNICUS/")


def test_sentinel2_date_floor_on_cases():
    cases = load_cases()
    sentinel2_start = date(2015, 6, 23)
    for case in cases:
        assert case.earlier_date >= sentinel2_start
        assert case.later_date >= sentinel2_start
