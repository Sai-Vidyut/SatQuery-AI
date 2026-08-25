from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.semantic.development import DevelopmentSemanticAnalyzer
from app.schemas.domain import (
    AOI,
    AnalysisStatus,
    ChangeDetectionOutput,
    DataMode,
    FetchImageryOutput,
    GeoJSONGeometry,
    ImageryResult,
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
                [77.59, 12.97],
                [77.61, 12.97],
                [77.61, 12.99],
                [77.59, 12.99],
                [77.59, 12.97],
            ]
        ],
    ),
)

DEV_IMAGERY = ImageryResult(
    source="satquery-development-imagery",
    mode=DataMode.DEVELOPMENT,
    sensor=SensorType.SENTINEL_2,
    scenes=[],
    spatial=SpatialMetadata(bbox=[77.59, 12.97, 77.61, 12.99]),
)

CONSTRUCTION_QUERY = QueryRequest(
    query="Show me significant new construction.",
    aoi=SAMPLE_AOI,
    earlier_date=date(2024, 1, 1),
    later_date=date(2025, 1, 1),
)

NON_CONSTRUCTION_QUERY = QueryRequest(
    query="Show spectral vegetation change.",
    aoi=SAMPLE_AOI,
    earlier_date=date(2024, 1, 1),
    later_date=date(2025, 1, 1),
)


@pytest.mark.asyncio
async def test_construction_query_runs_semantic_analysis():
    controller = QueryController()
    controller._fetch.execute = AsyncMock(
        return_value=FetchImageryOutput(result=DEV_IMAGERY),
    )
    controller._detect.execute = AsyncMock(
        return_value=ChangeDetectionOutput(
            regions=[],
            raw_detection_count=0,
            detector="deterministic_change_detector",
            mode=DataMode.DEVELOPMENT,
        )
    )
    controller._semantic = AnalyzeSemanticsTool(analyzer=DevelopmentSemanticAnalyzer())

    result = await controller.submit(CONSTRUCTION_QUERY)
    semantic_steps = [s for s in result.trace if s.tool_name == "analyze_semantics"]
    assert len(semantic_steps) == 1
    assert semantic_steps[0].status.value == "completed"
    assert "Produced" in (semantic_steps[0].summary or "")


@pytest.mark.asyncio
async def test_non_construction_query_skips_semantic_analysis():
    controller = QueryController()
    controller._fetch.execute = AsyncMock(
        return_value=FetchImageryOutput(result=DEV_IMAGERY),
    )
    controller._detect.execute = AsyncMock(
        return_value=ChangeDetectionOutput(
            regions=[],
            raw_detection_count=0,
            detector="deterministic_change_detector",
            mode=DataMode.DEVELOPMENT,
        )
    )
    controller._semantic.execute = AsyncMock()

    result = await controller.submit(NON_CONSTRUCTION_QUERY)
    controller._semantic.execute.assert_not_called()
    semantic_steps = [s for s in result.trace if s.tool_name == "analyze_semantics"]
    assert len(semantic_steps) == 1
    assert semantic_steps[0].status.value == "completed"
    assert "skipped" in (semantic_steps[0].summary or "").lower()
    assert result.status == AnalysisStatus.COMPLETED
