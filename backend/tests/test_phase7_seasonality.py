"""Phase 7 — seasonality-aware catalog Earth Engine change detection tests."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.change.earth_engine.detector import (
    EarthEngineChangeDetector,
    run_cva_detection,
    run_index_detection,
)
from app.adapters.change.earth_engine.indices import (
    classify_direction_hint_from_median,
    compute_index_change_magnitude,
    select_primary_index_for_catalog,
)
from app.adapters.imagery.earth_engine.seasonality import (
    build_seasonality_provenance,
    circular_month_distance,
    is_cross_season_pair,
    seasonal_selection_penalty,
)
from app.adapters.imagery.earth_engine.selection import select_anchor_scenes
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.core.errors import SatQueryError
from app.schemas.change_domain import ChangeDomain
from app.schemas.domain import (
    AOI,
    ChangeDetectionInput,
    DataMode,
    GeoJSONGeometry,
    ImageryResult,
    ImageryScene,
    SensorType,
    SpatialMetadata,
)

SAMPLE_AOI = AOI(
    geometry=GeoJSONGeometry(
        type="Polygon",
        coordinates=[
            [
                [77.59, 12.97],
                [77.61, 12.97],
                [77.61, 12.99],
                [77.59, 12.99],
                [77.59, 12.97],
            ]
        ],
    ),
)


def _scene(scene_id: str, acq: date, cloud: float = 10.0) -> SceneCandidate:
    return SceneCandidate(
        scene_id=scene_id,
        platform_id=f"COPERNICUS/S2_SR_HARMONIZED/{scene_id}",
        acquisition_date=acq,
        cloud_cover_percent=cloud,
        metadata={},
    )


def _ee_imagery(
    before: date = date(2024, 6, 8),
    after: date = date(2024, 6, 26),
    seasonality: dict | None = None,
) -> ImageryResult:
    return ImageryResult(
        source="google-earth-engine",
        mode=DataMode.EARTH_ENGINE,
        sensor=SensorType.SENTINEL_2,
        scenes=[
            ImageryScene(
                scene_id="20240608T051119",
                acquisition_date=before,
                platform_id="COPERNICUS/S2_SR_HARMONIZED/20240608T051119",
            ),
            ImageryScene(
                scene_id="20240626T050659",
                acquisition_date=after,
                platform_id="COPERNICUS/S2_SR_HARMONIZED/20240626T050659",
            ),
        ],
        spatial=SpatialMetadata(bbox=[77.59, 12.97, 77.61, 12.99], resolution_m=10.0),
        provider_metadata={"seasonality": seasonality or {}},
    )


MOCK_FEATURES = [
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.595, 12.975],
                    [77.605, 12.975],
                    [77.605, 12.985],
                    [77.595, 12.985],
                    [77.595, 12.975],
                ]
            ],
        },
        "properties": {"mean": 0.22, "max": 0.30, "label": 1},
    }
]


# --- Seasonality utilities ---


def test_circular_month_distance_wraps_december_january():
    assert circular_month_distance(12, 1) == 1
    assert circular_month_distance(6, 6) == 0


def test_is_cross_season_pair():
    assert is_cross_season_pair(date(2024, 1, 15), date(2024, 9, 15)) is True
    assert is_cross_season_pair(date(2024, 6, 1), date(2024, 6, 20)) is False
    assert is_cross_season_pair(date(2024, 3, 1), date(2024, 5, 1)) is False


def test_seasonal_selection_penalty_tiers():
    assert seasonal_selection_penalty(date(2024, 6, 1), date(2024, 6, 15)) == 0
    assert seasonal_selection_penalty(date(2024, 6, 1), date(2024, 1, 15)) == 2


def test_build_seasonality_provenance_cross_season_warning():
    prov = build_seasonality_provenance(
        requested_start=date(2024, 1, 1),
        requested_end=date(2024, 9, 1),
        selected_dates=[date(2024, 1, 10), date(2024, 9, 5)],
        selection_policy="2.0.0",
    )
    assert prov["cross_season_comparison"] is True
    assert any("cross_season" in w for w in prov["warnings"])


def test_build_seasonality_provenance_same_season_no_warning():
    prov = build_seasonality_provenance(
        requested_start=date(2024, 6, 1),
        requested_end=date(2024, 6, 20),
        selected_dates=[date(2024, 6, 3), date(2024, 6, 18)],
        selection_policy="2.0.0",
    )
    assert prov["cross_season_comparison"] is False
    assert prov["warnings"] == []


# --- Same-season scene selection ---


def test_select_anchor_scenes_prefers_same_season_when_equidistant():
    """June target should prefer June scene over March scene at same day distance."""
    candidates = [
        _scene("march", date(2024, 3, 10), 5.0),
        _scene("june", date(2024, 6, 10), 8.0),
    ]
    selected = select_anchor_scenes(candidates, date(2024, 6, 10), date(2024, 6, 10))
    assert selected[0].scene_id == "june"


def test_select_anchor_scenes_still_picks_closest_when_same_season():
    candidates = [
        _scene("a", date(2024, 1, 10), 15.0),
        _scene("b", date(2024, 2, 1), 5.0),
        _scene("c", date(2024, 3, 5), 10.0),
    ]
    selected = select_anchor_scenes(candidates, date(2024, 1, 12), date(2024, 3, 3))
    assert [s.scene_id for s in selected] == ["a", "c"]


def test_select_anchor_scenes_empty_raises():
    with pytest.raises(SatQueryError) as exc:
        select_anchor_scenes([], date(2024, 1, 1), date(2024, 3, 1))
    assert exc.value.code == "no_imagery_after_cloud_filter"


# --- Domain index routing ---


def test_select_primary_index_for_domain():
    assert select_primary_index_for_catalog(change_domain=ChangeDomain.DEFORESTATION) == "ndvi"
    assert select_primary_index_for_catalog(change_domain=ChangeDomain.WATER_SHRINKAGE) == "ndwi"
    assert select_primary_index_for_catalog(change_domain=ChangeDomain.URBAN_EXPANSION) == "ndbi"
    assert select_primary_index_for_catalog(change_domain=ChangeDomain.MINING) == "ndvi"
    assert select_primary_index_for_catalog(query_hint="show deforestation") == "ndvi"
    assert select_primary_index_for_catalog() is None


def test_classify_direction_hint_vegetation_loss():
    assert classify_direction_hint_from_median(-0.15, "ndvi") == "vegetation_loss"
    assert classify_direction_hint_from_median(0.15, "ndvi") == "vegetation_gain"


def test_classify_direction_hint_water_contraction():
    assert classify_direction_hint_from_median(-0.12, "ndwi") == "water_contraction"
    assert classify_direction_hint_from_median(0.12, "ndwi") == "water_expansion"


def test_classify_direction_hint_no_change_below_threshold():
    assert classify_direction_hint_from_median(0.005, "ndvi") == "no_change"


# --- Detector routing ---


@pytest.fixture
def mock_client():
    ee = MagicMock()
    ee.Geometry.Polygon = MagicMock(return_value="aoi-geom")
    ee.Reducer.median.return_value = "median-reducer"
    from app.adapters.imagery.earth_engine.client import EarthEngineClient

    return EarthEngineClient(ee=ee, project="satquery-ai")


@pytest.mark.asyncio
async def test_ee_detector_generic_path_uses_cva(mock_client):
    detector = EarthEngineChangeDetector(client=mock_client)
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 6, 8),
        later_date=date(2024, 6, 26),
        imagery=_ee_imagery(),
    )
    with patch(
        "app.adapters.change.earth_engine.detector.run_cva_detection",
        return_value=(MOCK_FEATURES, {"method": "change_vector_analysis", "threshold": 1000.0, "primary_index": None}),
    ) as mock_cva:
        output = await detector.detect(payload)

    mock_cva.assert_called_once()
    assert output.detector_metadata["method"] == "change_vector_analysis"
    assert output.detector_metadata["primary_index"] is None


@pytest.mark.asyncio
async def test_ee_detector_domain_path_uses_index_differencing(mock_client):
    detector = EarthEngineChangeDetector(client=mock_client)
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2019, 8, 1),
        later_date=date(2023, 8, 1),
        imagery=_ee_imagery(),
        change_domain=ChangeDomain.DEFORESTATION.value,
        query_hint="show deforestation",
    )
    with patch(
        "app.adapters.change.earth_engine.detector.run_index_detection",
        return_value=(
            MOCK_FEATURES,
            {
                "method": "index_differencing",
                "threshold": 0.15,
                "primary_index": "ndvi",
                "change_direction_hint": "vegetation_loss",
            },
        ),
    ) as mock_index:
        output = await detector.detect(payload)

    mock_index.assert_called_once()
    assert output.detector_metadata["method"] == "index_differencing"
    assert output.detector_metadata["primary_index"] == "ndvi"
    assert output.detector_metadata["change_direction_hint"] == "vegetation_loss"
    assert output.detector_metadata["change_domain"] == "deforestation"


@pytest.mark.asyncio
async def test_ee_detector_records_seasonality_provenance(mock_client):
    seasonality = build_seasonality_provenance(
        requested_start=date(2024, 6, 1),
        requested_end=date(2024, 6, 20),
        selected_dates=[date(2024, 6, 3), date(2024, 6, 18)],
        selection_policy="2.0.0",
    )
    detector = EarthEngineChangeDetector(client=mock_client)
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 6, 1),
        later_date=date(2024, 6, 20),
        imagery=_ee_imagery(seasonality=seasonality),
        change_domain=ChangeDomain.WATER_SHRINKAGE.value,
    )
    with patch(
        "app.adapters.change.earth_engine.detector.run_index_detection",
        return_value=(
            [],
            {
                "method": "index_differencing",
                "threshold": 0.12,
                "primary_index": "ndwi",
                "change_direction_hint": "no_change",
            },
        ),
    ):
        output = await detector.detect(payload)

    assert output.detector_metadata["seasonality"]["cross_season_comparison"] is False
    assert output.detector_metadata["requested_earlier_date"] == "2024-06-01"


# --- Evaluation scenario fixtures (synthetic, no live EE) ---


@pytest.mark.parametrize(
    ("domain", "index", "direction", "scenario"),
    [
        (ChangeDomain.DEFORESTATION, "ndvi", "vegetation_loss", "genuine_vegetation_loss"),
        (ChangeDomain.DEFORESTATION, "ndvi", "no_change", "vegetation_seasonality_fp"),
        (ChangeDomain.WATER_SHRINKAGE, "ndwi", "water_contraction", "genuine_water_shrinkage"),
        (ChangeDomain.WATER_SHRINKAGE, "ndwi", "no_change", "water_seasonality_fp"),
        (ChangeDomain.URBAN_EXPANSION, "ndbi", "built_up_increase", "unchanged_urban_area"),
    ],
)
def test_evaluation_scenario_index_routing(domain, index, direction, scenario):
    """Document expected index/direction routing for Phase 7 evaluation cases."""
    selected = select_primary_index_for_catalog(change_domain=domain)
    assert selected == index
    if scenario.endswith("_fp") or scenario == "unchanged_urban_area":
        assert classify_direction_hint_from_median(0.01, index) == "no_change"
    else:
        delta = -0.15 if "loss" in direction or "contraction" in direction or "decrease" in direction else 0.15
        assert classify_direction_hint_from_median(delta, index) == direction


# --- Regression: upload / SAR / construction unchanged ---


@pytest.mark.asyncio
async def test_deterministic_detector_unchanged():
    from app.adapters.change.deterministic import DeterministicChangeDetector

    detector = DeterministicChangeDetector()
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 1, 12),
        later_date=date(2025, 3, 3),
        imagery=_ee_imagery().model_copy(update={"mode": DataMode.DEVELOPMENT}),
    )
    output = await detector.detect(payload)
    assert output.mode == DataMode.DEVELOPMENT
    assert output.detector == "deterministic_change_detector"


def test_phase6_evaluation_harness_still_loads():
    from evaluation.runner import load_cases

    cases = load_cases()
    assert len(cases) == 5


def test_run_cva_detection_returns_tuple():
    ee = MagicMock()
    before = ImageryScene(
        scene_id="before",
        acquisition_date=date(2024, 6, 1),
        platform_id="COPERNICUS/S2_SR_HARMONIZED/before",
    )
    after = ImageryScene(
        scene_id="after",
        acquisition_date=date(2024, 6, 20),
        platform_id="COPERNICUS/S2_SR_HARMONIZED/after",
    )
    with patch(
        "app.adapters.change.earth_engine.detector.vectorize_change_regions",
        return_value=[],
    ), patch(
        "app.adapters.change.earth_engine.detector.validate_epoch_coverage",
    ), patch(
        "app.adapters.change.earth_engine.detector.load_epoch_image",
        return_value=MagicMock(),
    ), patch(
        "app.adapters.change.earth_engine.detector.compute_change_magnitude",
        return_value=MagicMock(),
    ):
        features, ctx = run_cva_detection(ee, before, after, "aoi")
    assert features == []
    assert ctx["method"] == "change_vector_analysis"


def test_compute_index_change_magnitude_uses_ee_expressions():
    ee = MagicMock()
    before = MagicMock()
    after = MagicMock()
    before.select.return_value = MagicMock()
    after.select.return_value = MagicMock()
    before_idx = MagicMock()
    after_idx = MagicMock()
    with patch(
        "app.adapters.change.earth_engine.indices.compute_index",
        side_effect=[before_idx, after_idx],
    ):
        before_idx.mask.return_value.And.return_value = MagicMock()
        before_idx.updateMask.return_value = before_idx
        after_idx.updateMask.return_value = after_idx
        after_idx.subtract.return_value.rename.return_value = MagicMock()
        after_idx.subtract.return_value.abs.return_value.rename.return_value = MagicMock()
        mag, signed = compute_index_change_magnitude(before, after, "ndvi", ee)
    assert mag is not None
    assert signed is not None
