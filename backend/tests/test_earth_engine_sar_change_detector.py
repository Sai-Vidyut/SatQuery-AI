from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.change.earth_engine.sar_detector import EarthEngineSARChangeDetector
from app.adapters.change.earth_engine.sar_vectors import features_to_sar_evidence_regions
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
                [77.56, 12.94],
                [77.60, 12.94],
                [77.60, 12.98],
                [77.56, 12.98],
                [77.56, 12.94],
            ]
        ],
    ),
)

S1_IMAGERY = ImageryResult(
    source="google-earth-engine",
    mode=DataMode.EARTH_ENGINE,
    sensor=SensorType.SENTINEL_1,
    collection_id="COPERNICUS/S1_GRD",
    scenes=[
        ImageryScene(
            scene_id="20241210T051234",
            acquisition_date=date(2024, 12, 10),
            platform_id="COPERNICUS/S1_GRD/20241210T051234",
            metadata={"polarizations": ["VV", "VH"], "relative_orbit": 78},
        ),
        ImageryScene(
            scene_id="20250220T051234",
            acquisition_date=date(2025, 2, 20),
            platform_id="COPERNICUS/S1_GRD/20250220T051234",
            metadata={"polarizations": ["VV", "VH"], "relative_orbit": 78},
        ),
    ],
    spatial=SpatialMetadata(bbox=[77.56, 12.94, 77.60, 12.98], resolution_m=10.0),
)

MOCK_FEATURE = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [77.57, 12.95],
                [77.58, 12.95],
                [77.58, 12.96],
                [77.57, 12.96],
                [77.57, 12.95],
            ]
        ],
    },
    "properties": {"mean": 3.5, "max": 5.2, "p90": 4.8},
}


@pytest.fixture
def mock_client():
    ee = MagicMock()
    ee.Geometry.Polygon = MagicMock(return_value="aoi-geom")
    client = MagicMock()
    client.ee = ee
    client.project = "satquery-ai"
    return client


@pytest.mark.asyncio
async def test_sar_detector_returns_sar_evidence(mock_client):
    detector = EarthEngineSARChangeDetector(client=mock_client)

    with patch(
        "app.adapters.change.earth_engine.sar_detector.run_sar_change_detection",
        return_value=([MOCK_FEATURE], "VV", {"VV": True, "VH": True}),
    ):
        output = await detector.detect(
            ChangeDetectionInput(
                aoi=SAMPLE_AOI,
                earlier_date=date(2024, 12, 1),
                later_date=date(2025, 3, 1),
                imagery=S1_IMAGERY,
            )
        )

    assert output.detector == "earth_engine_sar"
    assert output.mode == DataMode.EARTH_ENGINE
    assert output.raw_detection_count == 1
    assert output.regions[0].type == "sar_change"
    assert output.regions[0].metadata["evidence_modality"] == "sar"
    assert output.regions[0].metadata["claim_type"] == "none"
    assert output.detector_metadata["primary_polarization"] == "VV"
    assert output.detector_metadata["polarization_availability"]["VH"] is True


@pytest.mark.asyncio
async def test_sar_detector_rejects_sentinel2_imagery(mock_client):
    s2_imagery = S1_IMAGERY.model_copy(update={"sensor": SensorType.SENTINEL_2})
    detector = EarthEngineSARChangeDetector(client=mock_client)
    with pytest.raises(SatQueryError) as exc:
        await detector.detect(
            ChangeDetectionInput(
                aoi=SAMPLE_AOI,
                earlier_date=date(2024, 12, 1),
                later_date=date(2025, 3, 1),
                imagery=s2_imagery,
            )
        )
    assert exc.value.code == "change_detector_misconfigured"


@pytest.mark.asyncio
async def test_sar_detector_no_change_returns_empty(mock_client):
    detector = EarthEngineSARChangeDetector(client=mock_client)
    with patch(
        "app.adapters.change.earth_engine.sar_detector.run_sar_change_detection",
        return_value=([], "VV", {"VV": True, "VH": True}),
    ):
        output = await detector.detect(
            ChangeDetectionInput(
                aoi=SAMPLE_AOI,
                earlier_date=date(2024, 12, 1),
                later_date=date(2025, 3, 1),
                imagery=S1_IMAGERY,
            )
        )
    assert output.raw_detection_count == 0


def test_features_to_sar_evidence_regions_metrics():
    regions = features_to_sar_evidence_regions(
        [MOCK_FEATURE],
        polarization="VV",
        before_scene_id="before",
        after_scene_id="after",
    )
    assert len(regions) == 1
    metrics = {m.name: m.value for m in regions[0].metrics}
    assert metrics["mean_sar_change_magnitude"] == 3.5
    assert metrics["polarization"] == "VV"
    assert regions[0].metadata["provenance_chain"] == ["earth_engine_sar"]


def test_sar_region_below_area_threshold_filtered():
    tiny = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.57, 12.95],
                    [77.57001, 12.95],
                    [77.57001, 12.95001],
                    [77.57, 12.95001],
                    [77.57, 12.95],
                ]
            ],
        },
        "properties": {"mean": 5.0},
    }
    regions = features_to_sar_evidence_regions(
        [tiny],
        polarization="VV",
        before_scene_id="before",
        after_scene_id="after",
    )
    assert regions == []
