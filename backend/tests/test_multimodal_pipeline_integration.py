from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

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
    SemanticAnalysisOutput,
    SensorType,
    SpatialMetadata,
)
from app.services.query_controller import QueryController

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
        ImageryScene(scene_id="s2-before", acquisition_date=date(2024, 12, 8), platform_id="COPERNICUS/S2_SR_HARMONIZED/before"),
        ImageryScene(scene_id="s2-after", acquisition_date=date(2025, 2, 26), platform_id="COPERNICUS/S2_SR_HARMONIZED/after"),
    ],
    spatial=SpatialMetadata(bbox=[77.56, 12.94, 77.60, 12.98], resolution_m=10.0),
)

CVA_REGION = EvidenceRegion(
    id="change-region-01",
    geometry=GeoJSONGeometry(
        type="Polygon",
        coordinates=[[[77.57, 12.95], [77.59, 12.95], [77.59, 12.97], [77.57, 12.97], [77.57, 12.95]]],
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
    metrics=[Metric(name="delta_built_probability", value=0.20, unit="probability", source="dynamic_world_built_v1")],
    source="dynamic_world_built_v1",
    metadata={"claim_type": "construction_candidate", "parent_region_id": "change-region-01"},
)

SAR_REGION = EvidenceRegion(
    id="sar-change-region-01",
    geometry=CVA_REGION.geometry,
    type="sar_change",
    confidence=0.86,
    metrics=[Metric(name="mean_sar_change_magnitude", value=6.8, unit="db", source="earth_engine_sar")],
    source="earth_engine_sar",
)

MULTIMODAL_QUERY = QueryRequest(
    query="Show me significant new construction and compare optical and radar evidence.",
    aoi=SAMPLE_AOI,
    earlier_date=date(2024, 12, 1),
    later_date=date(2025, 3, 1),
)


@pytest.mark.asyncio
async def test_multimodal_pipeline_trace_ordering(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "earth_engine")
    from app.core.config import get_settings

    get_settings.cache_clear()

    controller = QueryController()
    controller._fetch.execute = AsyncMock(return_value=FetchImageryOutput(result=EE_IMAGERY))
    controller._detect.execute = AsyncMock(
        return_value=ChangeDetectionOutput(
            regions=[CVA_REGION], raw_detection_count=1, detector="earth_engine_cva", mode=DataMode.EARTH_ENGINE
        )
    )
    controller._semantic.execute = AsyncMock(
        return_value=SemanticAnalysisOutput(
            regions=[SEMANTIC_REGION], claims=[], analyzer="dynamic_world_built_v1", mode=DataMode.EARTH_ENGINE
        )
    )
    controller._detect_sar.execute = AsyncMock(
        return_value=ChangeDetectionOutput(
            regions=[SAR_REGION], raw_detection_count=1, detector="earth_engine_sar", mode=DataMode.EARTH_ENGINE
        )
    )

    result = await controller.submit(MULTIMODAL_QUERY)

    tool_names = [s.tool_name for s in result.trace]
    assert tool_names == [
        "plan_query",
        "fetch_imagery",
        "detect_change",
        "analyze_semantics",
        "detect_sar_change",
        "fuse_evidence",
        "generate_evidence",
    ]
    assert result.status == AnalysisStatus.COMPLETED
    claim_types = {r.metadata.get("claim_type") for r in result.evidence}
    modalities = {r.metadata.get("evidence_modality") for r in result.evidence}
    assert "construction_candidate" in claim_types
    assert "optical+semantic+sar" in modalities
    assert "confirmed_construction" not in result.answer.lower()
