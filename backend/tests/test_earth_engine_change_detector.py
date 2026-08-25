from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.change.earth_engine.detector import EarthEngineChangeDetector
from app.adapters.imagery.earth_engine.client import EarthEngineClient
from app.core.errors import SatQueryError
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

EE_IMAGERY = ImageryResult(
    source="google-earth-engine",
    mode=DataMode.EARTH_ENGINE,
    sensor=SensorType.SENTINEL_2,
    scenes=[
        ImageryScene(
            scene_id="20241208T051119",
            acquisition_date=date(2024, 12, 8),
            platform_id="COPERNICUS/S2_SR_HARMONIZED/20241208T051119",
        ),
        ImageryScene(
            scene_id="20250226T050659",
            acquisition_date=date(2025, 2, 26),
            platform_id="COPERNICUS/S2_SR_HARMONIZED/20250226T050659",
        ),
    ],
    spatial=SpatialMetadata(bbox=[77.59, 12.97, 77.61, 12.99], resolution_m=10.0),
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
        "properties": {"mean": 1200.0, "max": 1500.0, "label": 1},
    }
]


@pytest.fixture
def mock_client():
    ee = MagicMock()
    ee.Geometry.Polygon = MagicMock(return_value="aoi-geom")
    return EarthEngineClient(ee=ee, project="satquery-ai")


@pytest.mark.asyncio
async def test_ee_change_detector_returns_earth_engine_output(mock_client):
    detector = EarthEngineChangeDetector(client=mock_client)
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 12, 8),
        later_date=date(2025, 2, 26),
        imagery=EE_IMAGERY,
    )

    with patch(
        "app.adapters.change.earth_engine.detector.run_cva_detection",
        return_value=MOCK_FEATURES,
    ):
        output = await detector.detect(payload)

    assert output.mode == DataMode.EARTH_ENGINE
    assert output.detector == "earth_engine_cva"
    assert output.raw_detection_count == 1
    assert len(output.regions) == 1
    assert output.regions[0].source == "earth_engine_cva"
    assert output.detector_metadata["method"] == "change_vector_analysis"
    assert output.detector_metadata["before_scene_id"] == "20241208T051119"
    assert output.detector_metadata["project"] == "satquery-ai"


@pytest.mark.asyncio
async def test_ee_change_detector_no_change_returns_empty_regions(mock_client):
    detector = EarthEngineChangeDetector(client=mock_client)
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 12, 8),
        later_date=date(2025, 2, 26),
        imagery=EE_IMAGERY,
    )

    with patch(
        "app.adapters.change.earth_engine.detector.run_cva_detection",
        return_value=[],
    ):
        output = await detector.detect(payload)

    assert output.raw_detection_count == 0
    assert output.regions == []


@pytest.mark.asyncio
async def test_ee_change_detector_auth_failure():
    with patch(
        "app.adapters.change.earth_engine.detector.EarthEngineClient.initialize",
        side_effect=SatQueryError("earth_engine_auth_failed", "auth failed", status_code=503),
    ):
        detector = EarthEngineChangeDetector()
        payload = ChangeDetectionInput(
            aoi=SAMPLE_AOI,
            earlier_date=date(2024, 12, 8),
            later_date=date(2025, 2, 26),
            imagery=EE_IMAGERY,
        )
        with pytest.raises(SatQueryError) as exc:
            await detector.detect(payload)
        assert exc.value.code == "earth_engine_auth_failed"


@pytest.mark.asyncio
async def test_deterministic_detector_still_labeled_development():
    from app.adapters.change.deterministic import DeterministicChangeDetector

    detector = DeterministicChangeDetector()
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 1, 12),
        later_date=date(2025, 3, 3),
        imagery=EE_IMAGERY.model_copy(update={"mode": DataMode.DEVELOPMENT}),
    )
    output = await detector.detect(payload)
    assert output.mode == DataMode.DEVELOPMENT
    assert output.detector == "deterministic_change_detector"
