from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.semantic.earth_engine.dynamic_world_built import EarthEngineDynamicWorldBuiltAnalyzer
from app.schemas.domain import (
    AOI,
    AnalysisStatus,
    ChangeDetectionOutput,
    DataMode,
    EvidenceRegion,
    FetchImageryOutput,
    GeoJSONGeometry,
    Metric,
    ImageryResult,
    ImageryScene,
    QueryRequest,
    SensorType,
    SpatialMetadata,
)
from app.services.query_controller import QueryController
from app.tools.semantic.analyze_semantics import AnalyzeSemanticsTool

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
    spatial=SpatialMetadata(bbox=[77.56, 12.94, 77.60, 12.98], resolution_m=10.0),
)

CVA_REGION = EvidenceRegion(
    id="change-region-01",
    geometry=GeoJSONGeometry(
        type="Polygon",
        coordinates=[
            [
                [77.57, 12.95],
                [77.59, 12.95],
                [77.59, 12.97],
                [77.57, 12.97],
                [77.57, 12.95],
            ]
        ],
    ),
    type="spectral_change",
    confidence=0.6,
    metrics=[],
    source="earth_engine_cva",
)

SEMANTIC_REGION = EvidenceRegion(
    id="semantic-candidate-01",
    geometry=CVA_REGION.geometry,
    type="semantic_evidence",
    confidence=0.45,
    metrics=[
        Metric(name="delta_built_probability", value=0.20, unit="probability", source="dynamic_world_built_v1"),
    ],
    source="dynamic_world_built_v1",
    metadata={
        "claim_type": "construction_candidate",
        "parent_region_id": "change-region-01",
        "provenance_chain": ["earth_engine_cva", "dynamic_world_built_v1"],
    },
)

CONSTRUCTION_QUERY = QueryRequest(
    query="Show me significant new construction.",
    aoi=SAMPLE_AOI,
    earlier_date=date(2024, 12, 1),
    later_date=date(2025, 3, 1),
)


@pytest.mark.asyncio
async def test_full_pipeline_with_dynamic_world_semantic_mocked():
    mock_fetch = MagicMock()
    mock_fetch.execute = AsyncMock(return_value=FetchImageryOutput(result=EE_IMAGERY))

    mock_detect = MagicMock()
    mock_detect.execute = AsyncMock(
        return_value=ChangeDetectionOutput(
            regions=[CVA_REGION],
            raw_detection_count=1,
            detector="earth_engine_cva",
            mode=DataMode.EARTH_ENGINE,
        )
    )

    mock_analyzer = MagicMock(spec=EarthEngineDynamicWorldBuiltAnalyzer)
    from app.schemas.domain import SemanticAnalysisOutput, SemanticClaim

    mock_analyzer.analyze = AsyncMock(
        return_value=SemanticAnalysisOutput(
            regions=[SEMANTIC_REGION],
            claims=[
                SemanticClaim(
                    claim_type="construction_candidate",
                    region_id="semantic-candidate-01",
                    confidence=0.45,
                )
            ],
            analyzer="dynamic_world_built_v1",
            mode=DataMode.EARTH_ENGINE,
            analyzer_metadata={"policy": "dynamic_world_built_construction_v1"},
        )
    )

    controller = QueryController()
    controller._fetch = mock_fetch
    controller._detect = mock_detect
    controller._semantic = AnalyzeSemanticsTool(analyzer=mock_analyzer)

    result = await controller.submit(CONSTRUCTION_QUERY)

    assert result.status == AnalysisStatus.COMPLETED
    assert result.mode == DataMode.EARTH_ENGINE
    assert "construction candidate" in result.answer.lower()
    assert "confirmed" not in result.answer.lower()
    claim_types = [r.metadata.get("claim_type") for r in result.evidence]
    assert "construction_candidate" in claim_types
    assert "none" in claim_types
    semantic_steps = [s for s in result.trace if s.tool_name == "analyze_semantics"]
    assert len(semantic_steps) == 1
    assert semantic_steps[0].status.value == "completed"
