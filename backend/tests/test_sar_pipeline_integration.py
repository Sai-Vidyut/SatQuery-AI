from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.change.earth_engine.sar_detector import EarthEngineSARChangeDetector
from app.schemas.domain import (
    AOI,
    AnalysisStatus,
    ChangeDetectionOutput,
    DataMode,
    EvidenceRegion,
    FetchImageryOutput,
    GeoJSONGeometry,
    ImageryResult,
    ImageryScene,
    Metric,
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
                [77.56, 12.94],
                [77.60, 12.94],
                [77.60, 12.98],
                [77.56, 12.98],
                [77.56, 12.94],
            ]
        ],
    ),
    area_km2=19.2,
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
    provider_metadata={
        "polarization_availability": {"VV": True, "VH": True},
        "relative_orbit": 78,
    },
)

SAR_REGION = EvidenceRegion(
    id="sar-change-region-01",
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
    type="sar_change",
    confidence=0.55,
    metrics=[
        Metric(name="mean_sar_change_magnitude", value=3.2, unit="db", source="earth_engine_sar"),
        Metric(name="area_km2", value=0.01, unit="km²", source="earth_engine_sar"),
        Metric(name="polarization", value="VV", unit=None, source="earth_engine_sar"),
    ],
    source="earth_engine_sar",
    metadata={
        "claim_type": "none",
        "evidence_modality": "sar",
        "provenance_chain": ["earth_engine_sar"],
    },
)

MOCK_SAR_OUTPUT = ChangeDetectionOutput(
    regions=[SAR_REGION],
    raw_detection_count=1,
    detector="earth_engine_sar",
    mode=DataMode.EARTH_ENGINE,
    detector_metadata={
        "method": "sar_backscatter_change",
        "primary_polarization": "VV",
        "polarization_availability": {"VV": True, "VH": True},
    },
)

SAMPLE_QUERY = QueryRequest(
    query="Detect significant SAR radar backscatter change.",
    aoi=SAMPLE_AOI,
    earlier_date=date(2024, 12, 1),
    later_date=date(2025, 3, 1),
    sensor=SensorType.SENTINEL_1,
)


@pytest.mark.asyncio
async def test_sar_pipeline_integration():
    mock_detector = MagicMock(spec=EarthEngineSARChangeDetector)
    mock_detector.detect = AsyncMock(return_value=MOCK_SAR_OUTPUT)

    controller = QueryController()
    controller._detect = DetectChangeTool(detector=mock_detector)

    with patch.object(
        controller._fetch,
        "execute",
        new=AsyncMock(return_value=FetchImageryOutput(result=S1_IMAGERY)),
    ):
        result = await controller.submit(SAMPLE_QUERY)

    assert result.status == AnalysisStatus.COMPLETED
    assert result.mode == DataMode.EARTH_ENGINE
    assert len(result.evidence) == 1
    assert result.evidence[0].type == "sar_change"
    assert result.evidence[0].metadata["evidence_modality"] == "sar"
    assert "radar backscatter change" in result.answer.lower()
    assert "construction" not in result.answer.lower() or "not" in result.answer.lower()

    tool_names = [step.tool_name for step in result.trace]
    assert "fetch_imagery" in tool_names
    assert "detect_change" in tool_names
    assert "generate_evidence" in tool_names
    assert "analyze_semantics" in tool_names
    semantic_step = next(s for s in result.trace if s.tool_name == "analyze_semantics")
    assert "skipped" in (semantic_step.summary or "").lower()
