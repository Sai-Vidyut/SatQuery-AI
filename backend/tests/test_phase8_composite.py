"""Phase 8 — multi-scene seasonal median composite tests."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.change.earth_engine.composite_loader import (
    build_median_composite_image,
    load_epoch_image,
    validate_epoch_coverage,
)
from app.adapters.change.earth_engine.detector import EarthEngineChangeDetector
from app.adapters.imagery.earth_engine.composite import (
    COMPOSITE_POLICY_VERSION,
    COMPOSITE_PLATFORM_ID_T1,
    IMAGERY_STRATEGY,
    build_composite_epochs,
    build_composite_scene,
    compute_composite_window,
    select_scenes_for_composite,
)
from app.adapters.imagery.earth_engine.provider import EarthEngineProvider
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.adapters.semantic.earth_engine.dynamic_world_built import evaluate_cva_region
from app.adapters.semantic.earth_engine.imagery_epoch import imagery_epoch_window
from app.core.errors import SatQueryError
from app.schemas.domain import (
    AOI,
    ChangeDetectionInput,
    DataMode,
    EvidenceRegion,
    GeoJSONGeometry,
    ImageryRequest,
    ImageryResult,
    ImageryScene,
    ImageryPreferences,
    Metric,
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

CVA_REGION = EvidenceRegion(
    id="cva-1",
    type="spectral_change",
    geometry=SAMPLE_AOI.geometry,
    confidence=0.8,
    source="earth_engine_cva",
    metrics=[Metric(name="area_m2", value=5000.0, unit="m²", source="test")],
    metadata={},
)


def _scene(scene_id: str, acq: date, cloud: float = 8.0) -> SceneCandidate:
    return SceneCandidate(
        scene_id=scene_id,
        platform_id=f"COPERNICUS/S2_SR_HARMONIZED/{scene_id}",
        acquisition_date=acq,
        cloud_cover_percent=cloud,
        metadata={},
    )


def _composite_scene(epoch: str, requested: date, sources: list[SceneCandidate]) -> ImageryScene:
    window_start, window_end = compute_composite_window(requested)
    return build_composite_scene(
        sources,
        epoch=epoch,
        requested_date=requested,
        window_start=window_start,
        window_end=window_end,
    )


# --- Window generation ---


def test_compute_composite_window_centered_on_anchor():
    anchor = date(2024, 6, 15)
    start, end = compute_composite_window(anchor)
    assert start == date(2024, 5, 31)
    assert end == date(2024, 6, 30)


def test_select_scenes_for_composite_filters_by_window():
    anchor = date(2024, 6, 15)
    candidates = [
        _scene("may", date(2024, 5, 1)),
        _scene("jun1", date(2024, 6, 5)),
        _scene("jun2", date(2024, 6, 20)),
        _scene("jul", date(2024, 7, 20)),
    ]
    selected, w_start, w_end = select_scenes_for_composite(candidates, anchor, epoch_label="T1")
    ids = {s.scene_id for s in selected}
    assert "may" not in ids
    assert "jul" not in ids
    assert "jun1" in ids and "jun2" in ids
    assert w_start == date(2024, 5, 31)
    assert w_end == date(2024, 6, 30)


def test_select_scenes_for_composite_empty_raises():
    with pytest.raises(SatQueryError) as exc:
        select_scenes_for_composite([], date(2024, 6, 1), epoch_label="T1")
    assert exc.value.code == "no_imagery_found"


def test_build_composite_epochs_provenance():
    candidates = [
        _scene("t1a", date(2018, 6, 3)),
        _scene("t1b", date(2018, 6, 18)),
        _scene("t2a", date(2024, 6, 5)),
        _scene("t2b", date(2024, 6, 22)),
    ]
    scenes, prov = build_composite_epochs(
        candidates,
        requested_start=date(2018, 6, 1),
        requested_end=date(2024, 6, 1),
    )
    assert len(scenes) == 2
    assert scenes[0].platform_id == COMPOSITE_PLATFORM_ID_T1
    assert scenes[0].acquisition_date == date(2018, 6, 1)
    assert prov["imagery_strategy"] == IMAGERY_STRATEGY
    assert prov["composite_method"] == "median"
    assert prov["t1"]["scene_count"] >= 1
    assert prov["t2"]["scene_count"] >= 1
    assert prov["selection_policy"] == COMPOSITE_POLICY_VERSION


def test_build_composite_epochs_cross_season_warning():
    candidates = [
        _scene("jan", date(2020, 1, 10)),
        _scene("sep", date(2020, 9, 5)),
    ]
    _, prov = build_composite_epochs(
        candidates,
        requested_start=date(2020, 1, 1),
        requested_end=date(2020, 9, 1),
    )
    assert any("cross_season" in w for w in prov["warnings"])


# --- Composite loader ---


def test_load_epoch_image_single_scene():
    ee = MagicMock()
    scene = ImageryScene(
        scene_id="single",
        acquisition_date=date(2024, 6, 1),
        platform_id="COPERNICUS/S2_SR_HARMONIZED/single",
    )
    with patch(
        "app.adapters.change.earth_engine.composite_loader.load_scene_image",
        return_value=MagicMock(),
    ), patch(
        "app.adapters.change.earth_engine.composite_loader.mask_sentinel2_sr",
        return_value=MagicMock(),
    ) as mask:
        mask.return_value.select.return_value = "prepared"
        result = load_epoch_image(ee, scene)
    assert result == "prepared"


def test_load_epoch_image_composite_uses_median():
    ee = MagicMock()
    sources = [_scene("a", date(2024, 6, 5)), _scene("b", date(2024, 6, 12))]
    scene = _composite_scene("t1", date(2024, 6, 1), sources)
    with patch(
        "app.adapters.change.earth_engine.composite_loader.build_median_composite_image",
        return_value="median-image",
    ) as median:
        result = load_epoch_image(ee, scene)
    median.assert_called_once()
    assert result == "median-image"


def test_build_median_composite_image_requires_scenes():
    with pytest.raises(SatQueryError) as exc:
        build_median_composite_image(MagicMock(), [])
    assert exc.value.code == "insufficient_imagery"


def test_validate_epoch_coverage_empty_raises():
    ee = MagicMock()
    image = MagicMock()
    image.mask.return_value.reduceRegion.return_value.getInfo.return_value = {"B2": 0}
    with pytest.raises(SatQueryError) as exc:
        validate_epoch_coverage(ee, image, "aoi", epoch_label="T1")
    assert exc.value.code == "insufficient_imagery"


# --- Dynamic World alignment ---


def test_imagery_epoch_window_composite_uses_full_window():
    sources = [_scene("a", date(2024, 6, 5))]
    scene = _composite_scene("t1", date(2024, 6, 1), sources)
    start, end = imagery_epoch_window(scene)
    assert start == date(2024, 5, 17)
    assert end == date(2024, 6, 16)


def test_imagery_epoch_window_single_scene_uses_anchor_policy():
    scene = ImageryScene(
        scene_id="single",
        acquisition_date=date(2024, 6, 1),
        platform_id="COPERNICUS/S2_SR_HARMONIZED/single",
    )
    start, end = imagery_epoch_window(scene)
    assert start == date(2024, 6, 1)
    assert end == date(2024, 6, 8)


def test_evaluate_cva_region_uses_composite_window():
    ee = MagicMock()
    client = MagicMock()
    earlier = _composite_scene("t1", date(2024, 6, 1), [_scene("a", date(2024, 6, 5))])
    later = _composite_scene("t2", date(2024, 6, 20), [_scene("b", date(2024, 6, 22))])
    with patch(
        "app.adapters.semantic.earth_engine.dynamic_world_built.sample_built_probability",
        side_effect=[0.1, 0.35],
    ):
        result = evaluate_cva_region(ee, client, CVA_REGION, earlier, later)
    assert result is not None
    assert result["earlier_window"] == ("2024-05-17", "2024-06-16")


# --- Provider integration ---


@pytest.mark.asyncio
async def test_provider_returns_composite_metadata():
    from app.adapters.imagery.earth_engine.client import EarthEngineClient

    ee = MagicMock()
    client = EarthEngineClient(ee=ee, project="test-project")
    provider = EarthEngineProvider(client=client)
    request = ImageryRequest(
        aoi=SAMPLE_AOI,
        start_date=date(2018, 6, 1),
        end_date=date(2024, 6, 1),
        sensor=SensorType.SENTINEL_2,
        preferences=ImageryPreferences(cloud_cover_max=30.0),
    )
    candidates = [
        _scene("t1", date(2018, 6, 5)),
        _scene("t2", date(2024, 6, 3)),
    ]
    composite_scenes = [
        _composite_scene("t1", date(2018, 6, 1), [candidates[0]]),
        _composite_scene("t2", date(2024, 6, 1), [candidates[1]]),
    ]
    provenance = {"imagery_strategy": IMAGERY_STRATEGY, "t1": {"scene_count": 1}, "t2": {"scene_count": 1}}

    with (
        patch(
            "app.adapters.imagery.earth_engine.provider.query_sentinel2_scenes",
            return_value=candidates,
        ),
        patch(
            "app.adapters.imagery.earth_engine.provider.build_composite_epochs",
            return_value=(composite_scenes, provenance),
        ),
    ):
        result = await provider.fetch(request)

    assert result.provider_metadata["imagery_strategy"] == IMAGERY_STRATEGY
    assert result.provider_metadata["selection_policy"] == COMPOSITE_POLICY_VERSION
    assert result.scenes[0].platform_id.startswith("COMPOSITE/")


@pytest.mark.asyncio
async def test_detector_accepts_composite_scenes():
    from app.adapters.imagery.earth_engine.client import EarthEngineClient

    ee = MagicMock()
    client = EarthEngineClient(ee=ee, project="satquery-ai")
    detector = EarthEngineChangeDetector(client=client)
    t1 = _composite_scene("t1", date(2024, 6, 1), [_scene("a", date(2024, 6, 5))])
    t2 = _composite_scene("t2", date(2024, 6, 20), [_scene("b", date(2024, 6, 22))])
    imagery = ImageryResult(
        source="google-earth-engine",
        mode=DataMode.EARTH_ENGINE,
        sensor=SensorType.SENTINEL_2,
        scenes=[t1, t2],
        spatial=SpatialMetadata(bbox=[77.59, 12.97, 77.61, 12.99], resolution_m=10.0),
        provider_metadata={"imagery_strategy": IMAGERY_STRATEGY},
    )
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 6, 1),
        later_date=date(2024, 6, 20),
        imagery=imagery,
    )
    with patch(
        "app.adapters.change.earth_engine.detector.run_cva_detection",
        return_value=([], {"method": "change_vector_analysis", "threshold": 1000.0, "primary_index": None}),
    ):
        output = await detector.detect(payload)
    assert output.detector_metadata.get("imagery_strategy") == IMAGERY_STRATEGY


def test_domain_routing_unchanged_from_phase7():
    from app.adapters.change.earth_engine.indices import select_primary_index_for_catalog
    from app.schemas.change_domain import ChangeDomain

    assert select_primary_index_for_catalog(change_domain=ChangeDomain.WATER_SHRINKAGE) == "ndwi"
    assert select_primary_index_for_catalog(change_domain=ChangeDomain.DEFORESTATION) == "ndvi"
