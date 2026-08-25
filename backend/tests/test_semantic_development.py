from __future__ import annotations

from datetime import date

import pytest

from app.adapters.semantic.base import SemanticAnalyzer
from app.adapters.semantic.development import DevelopmentSemanticAnalyzer
from app.schemas.domain import (
    AOI,
    DataMode,
    EvidenceRegion,
    GeoJSONGeometry,
    ImageryResult,
    SensorType,
    SemanticAnalysisInput,
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
    id="change-region-01",
    geometry=GeoJSONGeometry(
        type="Polygon",
        coordinates=[
            [
                [77.595, 12.975],
                [77.605, 12.975],
                [77.605, 12.985],
                [77.595, 12.985],
                [77.595, 12.975],
            ]
        ],
    ),
    type="spectral_change",
    confidence=0.6,
    metrics=[],
    source="earth_engine_cva",
)

DEV_IMAGERY = ImageryResult(
    source="satquery-development-imagery",
    mode=DataMode.DEVELOPMENT,
    sensor=SensorType.SENTINEL_2,
    scenes=[],
    spatial=SpatialMetadata(bbox=[77.59, 12.97, 77.61, 12.99]),
)


def test_semantic_analyzer_contract():
    analyzer = DevelopmentSemanticAnalyzer()
    assert isinstance(analyzer, SemanticAnalyzer)
    assert analyzer.name == "development_semantic_analyzer"
    assert "construction_candidate" in analyzer.supported_claims


@pytest.mark.asyncio
async def test_development_semantic_analyzer_returns_development_mode():
    analyzer = DevelopmentSemanticAnalyzer()
    output = await analyzer.analyze(
        SemanticAnalysisInput(
            aoi=SAMPLE_AOI,
            earlier_date=date(2024, 1, 1),
            later_date=date(2025, 1, 1),
            imagery=DEV_IMAGERY,
            change_regions=[CVA_REGION],
            analysis_profile="building_construction",
        )
    )
    assert output.mode == DataMode.DEVELOPMENT
    assert output.analyzer == "development_semantic_analyzer"
    assert len(output.regions) >= 1
    assert output.regions[0].metadata["development_disclaimer"] is True
    assert output.regions[0].metadata["claim_type"] in ("construction_candidate", "new_built_area")
    assert "confirmed" not in output.analyzer_metadata.get("message", "").lower()


@pytest.mark.asyncio
async def test_development_semantic_empty_without_cva_regions():
    analyzer = DevelopmentSemanticAnalyzer()
    output = await analyzer.analyze(
        SemanticAnalysisInput(
            aoi=SAMPLE_AOI,
            earlier_date=date(2024, 1, 1),
            later_date=date(2025, 1, 1),
            imagery=DEV_IMAGERY,
            change_regions=[],
            analysis_profile="building_construction",
        )
    )
    assert output.regions == []
