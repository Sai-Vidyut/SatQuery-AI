"""Phase 5A — imagery policy layer and building-temporal intent routing."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from app.core.errors import SatQueryError
from app.schemas.domain import AOI, GeoJSONGeometry, QueryRequest
from app.schemas.imagery_policy import ImageryProductMode, PolicyDecision
from app.schemas.input import ImageFormat, ImageInput, ImageModality, ImageSource
from app.schemas.planning import PlannerToolName, QueryIntent
from app.services.building_temporal_intent import is_building_temporal_query
from app.services.planner.deterministic import build_deterministic_plan
from app.services.temporal_imagery_resolver import TemporalImageryResolver
from app.services.query_controller import QueryController


def _aoi(bbox: tuple[float, float, float, float]) -> AOI:
    west, south, east, north = bbox
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


GLOBAL_AOI = _aoi((77.56, 12.94, 77.60, 12.98))
CONUS_AOI = _aoi((-105.0, 39.7, -104.9, 39.8))

RESOLVER = TemporalImageryResolver()


def _upload_image(
    *,
    image_id: str,
    gsd_m: float,
    acquired: date,
    bounds: list[float] | None = None,
) -> ImageInput:
    return ImageInput(
        id=image_id,
        modality=ImageModality.OPTICAL,
        format=ImageFormat.GEOTIFF,
        filename=f"{image_id}.tif",
        acquisition_datetime=datetime(acquired.year, acquired.month, acquired.day, tzinfo=timezone.utc),
        width=1000,
        height=1000,
        resolution_x=gsd_m,
        resolution_y=gsd_m,
        bounds=bounds or [-105.0, 39.7, -104.9, 39.8],
        file_size_bytes=1024,
        georeferenced=True,
        source=ImageSource.UPLOAD,
    )


def test_2011_global_building_instance_rejected():
    resolution = RESOLVER.resolve_catalog(
        GLOBAL_AOI,
        date(2011, 1, 1),
        date(2026, 1, 1),
        ImageryProductMode.BUILDING_INSTANCE,
    )
    report = resolution.report
    assert report.policy_decision == PolicyDecision.UNSUPPORTED
    assert report.reason_code in {"gsd_too_coarse", "cross_sensor_resolution"}
    assert report.earlier is not None
    assert report.earlier.sensor.value == "landsat"
    assert report.later is not None
    assert report.later.sensor.value == "sentinel-2"
    assert report.earlier.gsd_m == 30.0


def test_coarse_landsat_s2_building_instance_rejected():
    resolution = RESOLVER.resolve_catalog(
        GLOBAL_AOI,
        date(2012, 6, 1),
        date(2024, 6, 1),
        ImageryProductMode.BUILDING_INSTANCE,
    )
    assert resolution.report.policy_decision == PolicyDecision.UNSUPPORTED
    assert resolution.report.reason_code == "gsd_too_coarse"


def test_suitable_vhr_upload_pair_accepted():
    earlier = _upload_image(image_id="vhr-earlier", gsd_m=0.5, acquired=date(2020, 6, 1))
    later = _upload_image(image_id="vhr-later", gsd_m=0.6, acquired=date(2023, 6, 1))
    resolution = RESOLVER.resolve_upload_pair(earlier, later, ImageryProductMode.BUILDING_INSTANCE)
    assert resolution.report.policy_decision == PolicyDecision.SUPPORTED
    assert resolution.report.gsd_mismatch_ratio is not None
    assert resolution.report.gsd_mismatch_ratio <= 2.0


def test_naip_us_catalog_pair_accepted():
    resolution = RESOLVER.resolve_catalog(
        CONUS_AOI,
        date(2018, 6, 1),
        date(2021, 6, 1),
        ImageryProductMode.BUILDING_INSTANCE,
    )
    report = resolution.report
    assert report.policy_decision == PolicyDecision.SUPPORTED
    assert report.earlier is not None
    assert report.later is not None
    assert report.earlier.sensor.value == "naip"
    assert report.later.sensor.value == "naip"
    assert report.earlier.gsd_m <= 2.0
    assert report.later.gsd_m <= 2.0
    assert report.earlier.actual_acquisition_date is not None
    assert report.earlier.actual_acquisition_date.year in {2017, 2018}
    assert any("not exact year match" in w.lower() or "epoch" in w.lower() for w in report.warnings) or (
        report.earlier.requested_date != report.earlier.actual_acquisition_date
    )


def test_gsd_mismatch_greater_than_2x_rejected():
    earlier = _upload_image(image_id="fine", gsd_m=0.8, acquired=date(2020, 1, 1))
    later = _upload_image(image_id="coarse", gsd_m=2.0, acquired=date(2023, 1, 1))
    resolution = RESOLVER.resolve_upload_pair(earlier, later, ImageryProductMode.BUILDING_INSTANCE)
    assert resolution.report.policy_decision == PolicyDecision.UNSUPPORTED
    assert resolution.report.reason_code == "gsd_mismatch"


def test_built_area_mode_accepts_landsat_s2_pair():
    resolution = RESOLVER.resolve_catalog(
        GLOBAL_AOI,
        date(2011, 1, 1),
        date(2026, 1, 1),
        ImageryProductMode.BUILT_AREA,
    )
    assert resolution.report.policy_decision == PolicyDecision.SUPPORTED


@pytest.mark.parametrize(
    "query",
    [
        "Show me new buildings between these dates.",
        "Find new buildings in this AOI.",
        "Which buildings were built here?",
        "Show buildings that appeared.",
        "Show new construction",
    ],
)
def test_building_temporal_intent_detection(query: str):
    assert is_building_temporal_query(query)


def test_building_temporal_intent_routing():
    request = QueryRequest(
        query="Show me new buildings in this AOI.",
        aoi=GLOBAL_AOI,
        earlier_date=date(2011, 1, 1),
        later_date=date(2026, 1, 1),
    )
    plan = build_deterministic_plan(request)
    assert plan.user_intent == QueryIntent.BUILDING_TEMPORAL_CHANGE
    assert plan.required_tools == [PlannerToolName.IMAGERY_POLICY]


def test_construction_routing_unchanged():
    request = QueryRequest(
        query="Show me significant new construction.",
        aoi=GLOBAL_AOI,
        earlier_date=date(2024, 1, 1),
        later_date=date(2025, 1, 1),
    )
    plan = build_deterministic_plan(request)
    assert plan.user_intent == QueryIntent.CONSTRUCTION
    assert PlannerToolName.ANALYZE_SEMANTICS in plan.required_tools


def test_spectral_change_routing_unchanged():
    request = QueryRequest(
        query="Show me significant spectral change.",
        aoi=GLOBAL_AOI,
        earlier_date=date(2024, 1, 1),
        later_date=date(2025, 1, 1),
    )
    plan = build_deterministic_plan(request)
    assert plan.user_intent == QueryIntent.SPECTRAL_CHANGE
    assert PlannerToolName.FETCH_IMAGERY in plan.required_tools


def test_upload_bi_temporal_intent_unchanged():
    from app.services.bi_temporal_intent import is_bi_temporal_change_query

    request = QueryRequest(
        query="What changed between these images?",
        earlier_image_id="img-a",
        later_image_id="img-b",
    )
    assert is_bi_temporal_change_query(request.query)
    plan = build_deterministic_plan(request)
    assert plan.user_intent == QueryIntent.BI_TEMPORAL_CHANGE_VQA


@pytest.mark.asyncio
async def test_controller_rejects_unsupported_building_policy():
    controller = QueryController()
    request = QueryRequest(
        query="Show me new buildings.",
        aoi=GLOBAL_AOI,
        earlier_date=date(2011, 1, 1),
        later_date=date(2026, 1, 1),
    )
    session_id: str | None = None
    original_create = controller._store.create

    def capture_create() -> str:
        nonlocal session_id
        session_id = original_create()
        return session_id

    controller._store.create = capture_create  # type: ignore[method-assign]

    with pytest.raises(SatQueryError) as exc_info:
        await controller.submit(request)
    assert exc_info.value.code == "imagery_policy_unsupported"
    assert session_id is not None
    session = controller._store.get(session_id)
    assert session is not None
    policy_steps = [s for s in session.trace if s.tool_name == "imagery_policy"]
    assert len(policy_steps) == 1
    assert policy_steps[0].metadata["policy_decision"] == "unsupported"


@pytest.mark.asyncio
async def test_controller_building_policy_trace_metadata():
    controller = QueryController()
    request = QueryRequest(
        query="Find new buildings.",
        aoi=GLOBAL_AOI,
        earlier_date=date(2011, 1, 1),
        later_date=date(2026, 1, 1),
    )
    session_id: str | None = None
    original_create = controller._store.create

    def capture_create() -> str:
        nonlocal session_id
        session_id = original_create()
        return session_id

    controller._store.create = capture_create  # type: ignore[method-assign]

    with pytest.raises(SatQueryError):
        await controller.submit(request)
    assert session_id is not None
    session = controller._store.get(session_id)
    assert session is not None
    trace = session.trace
    policy_steps = [s for s in trace if s.tool_name == "imagery_policy"]
    assert len(policy_steps) == 1
    meta = policy_steps[0].metadata or {}
    assert meta.get("requested_mode") == "building_instance"
    assert meta.get("policy_decision") == "unsupported"
    assert meta.get("t1_sensor") == "landsat"
    assert meta.get("t2_sensor") == "sentinel-2"
    assert meta.get("t1_gsd_m") == 30.0
    assert meta.get("t2_gsd_m") == 10.0
    assert meta.get("status") == "completed"


@pytest.mark.asyncio
async def test_controller_accepts_naip_supported_policy():
    controller = QueryController()
    request = QueryRequest(
        query="Which buildings were built?",
        aoi=CONUS_AOI,
        earlier_date=date(2018, 6, 1),
        later_date=date(2021, 6, 1),
    )
    result = await controller.submit(request)
    assert result.status.value == "completed"
    assert result.imagery_policy is not None
    assert result.imagery_policy.policy_decision == PolicyDecision.SUPPORTED
    assert "not yet implemented" in result.answer.lower()
    assert result.evidence == []
    policy_steps = [s for s in result.trace if s.tool_name == "imagery_policy"]
    assert policy_steps
    assert policy_steps[0].metadata["policy_decision"] == "supported"


def test_no_filesystem_paths_leaked_in_policy_report():
    resolution = RESOLVER.resolve_catalog(
        CONUS_AOI,
        date(2018, 6, 1),
        date(2021, 6, 1),
        ImageryProductMode.BUILDING_INSTANCE,
    )
    payload = json.dumps(resolution.report.model_dump(mode="json"))
    assert "/Users/" not in payload
    assert "uploads/" not in payload
    assert ".tif" not in payload


@pytest.mark.asyncio
async def test_no_filesystem_paths_in_controller_trace():
    controller = QueryController()
    request = QueryRequest(
        query="Find new buildings.",
        aoi=CONUS_AOI,
        earlier_date=date(2018, 6, 1),
        later_date=date(2021, 6, 1),
    )
    result = await controller.submit(request)
    trace_blob = json.dumps([s.model_dump(mode="json") for s in result.trace])
    assert "/Users/" not in trace_blob
    assert "uploads/" not in trace_blob
