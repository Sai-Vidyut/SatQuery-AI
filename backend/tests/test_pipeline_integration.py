from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.change.earth_engine.detector import EarthEngineChangeDetector
from app.schemas.domain import (
    AOI,
    AnalysisStatus,
    ChangeDetectionOutput,
    DataMode,
    FetchImageryOutput,
    GeoJSONGeometry,
    ImageryResult,
    ImageryScene,
    QueryRequest,
    SensorType,
    SpatialMetadata,
)
from app.services.query_controller import QueryController
from app.tools.temporal.detect_change import DetectChangeTool

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
    area_km2=4.8,
)

EE_IMAGERY = ImageryResult(
    source="google-earth-engine",
    mode=DataMode.EARTH_ENGINE,
    sensor=SensorType.SENTINEL_2,
    collection_id="COPERNICUS/S2_SR_HARMONIZED",
    scenes=[
        ImageryScene(
            scene_id="20241208T051119",
            acquisition_date=date(2024, 12, 8),
            cloud_cover_percent=5.0,
            platform_id="COPERNICUS/S2_SR_HARMONIZED/20241208T051119",
        ),
        ImageryScene(
            scene_id="20250226T050659",
            acquisition_date=date(2025, 2, 26),
            cloud_cover_percent=8.0,
            platform_id="COPERNICUS/S2_SR_HARMONIZED/20250226T050659",
        ),
    ],
    spatial=SpatialMetadata(bbox=[77.59, 12.97, 77.61, 12.99], resolution_m=10.0),
    provider_metadata={"candidate_count": 12, "selected_count": 2},
)

MOCK_CHANGE_OUTPUT = ChangeDetectionOutput(
    regions=[],
    raw_detection_count=1,
    detector="earth_engine_cva",
    mode=DataMode.EARTH_ENGINE,
    detector_metadata={"method": "change_vector_analysis"},
)

SAMPLE_QUERY = QueryRequest(
    query="Show significant spectral change between these dates.",
    aoi=SAMPLE_AOI,
    earlier_date=date(2024, 12, 8),
    later_date=date(2025, 2, 26),
)


@pytest.mark.asyncio
async def test_earth_engine_pipeline_produces_analysis_result():
    """
    Integration-style: AOI + dates → imagery provider → EE change detector interface → AnalysisResult.
    Earth Engine is mocked at the adapter boundary; no network required.
    """
    mock_fetch = MagicMock()
    mock_fetch.execute = AsyncMock(
        return_value=FetchImageryOutput(result=EE_IMAGERY),
    )

    mock_detector = MagicMock(spec=EarthEngineChangeDetector)
    mock_detector.detect = AsyncMock(return_value=MOCK_CHANGE_OUTPUT)
    mock_detector.name = "earth_engine_cva"

    controller = QueryController()
    controller._fetch = mock_fetch
    controller._detect = DetectChangeTool(detector=mock_detector)

    with patch(
        "app.adapters.change.earth_engine.detector.run_cva_detection",
        return_value=[],
    ):
        result = await controller.submit(SAMPLE_QUERY)

    assert result.status == AnalysisStatus.COMPLETED
    assert result.mode == DataMode.EARTH_ENGINE
    assert len(result.trace) == 7
    assert all(step.status.value == "completed" for step in result.trace)
    mock_fetch.execute.assert_called_once()
    mock_detector.detect.assert_called_once()
    detect_arg = mock_detector.detect.call_args[0][0]
    assert detect_arg.imagery.mode == DataMode.EARTH_ENGINE
    assert len(detect_arg.imagery.scenes) == 2
