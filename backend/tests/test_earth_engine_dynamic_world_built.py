from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.imagery.earth_engine.client import EarthEngineClient
from app.adapters.semantic.earth_engine.dynamic_world_built import (
    EarthEngineDynamicWorldBuiltAnalyzer,
    evaluate_cva_region,
    sample_built_probability,
)
from app.core.errors import SatQueryError
from app.schemas.domain import (
    AOI,
    DataMode,
    EvidenceRegion,
    GeoJSONGeometry,
    ImageryResult,
    ImageryScene,
    SemanticAnalysisInput,
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
    confidence=0.7,
    metrics=[],
    source="earth_engine_cva",
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


@pytest.fixture
def mock_client():
    ee = MagicMock()
    ee.Geometry.Polygon = MagicMock(return_value="ee-geom")
    ee.Reducer.mean = MagicMock(return_value="mean-reducer")
    client = MagicMock()
    client.ee = ee
    client.project = "satquery-ai"
    return client


def test_sample_built_probability_returns_mean(mock_client):
    ee = mock_client.ee
    collection = MagicMock()
    filtered = MagicMock()
    mock_client.image_collection.return_value = collection
    collection.filterBounds.return_value = collection
    collection.filterDate.return_value = filtered
    filtered.size.return_value.getInfo.return_value = 3
    mean_image = MagicMock()
    filtered.select.return_value.mean.return_value = mean_image
    mean_image.reduceRegion.return_value.getInfo.return_value = {"built": 0.42}

    value = sample_built_probability(
        ee,
        mock_client,
        "geom",
        date(2024, 12, 8),
        date(2024, 12, 15),
    )
    assert value == 0.42
    collection.filterDate.assert_called_once()


def test_evaluate_cva_region_passes_with_mocked_probabilities(mock_client):
    ee = mock_client.ee
    with patch(
        "app.adapters.semantic.earth_engine.dynamic_world_built.sample_built_probability",
        side_effect=[0.10, 0.30],
    ):
        result = evaluate_cva_region(
            ee, mock_client, CVA_REGION, EE_IMAGERY.scenes[0], EE_IMAGERY.scenes[-1]
        )

    assert result is not None
    assert result["delta_built"] == pytest.approx(0.20)
    assert result["confidence"] == pytest.approx(0.5)


def test_evaluate_cva_region_fails_low_delta(mock_client):
    ee = mock_client.ee
    with patch(
        "app.adapters.semantic.earth_engine.dynamic_world_built.sample_built_probability",
        side_effect=[0.20, 0.30],
    ):
        result = evaluate_cva_region(
            ee, mock_client, CVA_REGION, EE_IMAGERY.scenes[0], EE_IMAGERY.scenes[-1]
        )
    assert result is None


@pytest.mark.asyncio
async def test_ee_semantic_analyzer_produces_construction_candidate(mock_client):
    analyzer = EarthEngineDynamicWorldBuiltAnalyzer(client=mock_client)
    payload = SemanticAnalysisInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 12, 1),
        later_date=date(2025, 3, 1),
        imagery=EE_IMAGERY,
        change_regions=[CVA_REGION],
        analysis_profile="building_construction",
    )

    with patch(
        "app.adapters.semantic.earth_engine.dynamic_world_built.sample_built_probability",
        side_effect=[0.08, 0.28],
    ):
        output = await analyzer.analyze(payload)

    assert output.mode == DataMode.EARTH_ENGINE
    assert output.analyzer == "dynamic_world_built_v1"
    assert len(output.regions) == 1
    region = output.regions[0]
    assert region.metadata["claim_type"] == "construction_candidate"
    assert region.metadata["dataset"] == "GOOGLE/DYNAMICWORLD/V1"
    assert region.metadata["band"] == "built"
    assert region.metadata["provenance_chain"] == ["earth_engine_cva", "dynamic_world_built_v1"]
    assert "confirmed" not in str(region.metadata).lower()
    metric_names = {m.name for m in region.metrics}
    assert {"delta_built_probability", "earlier_built_mean", "later_built_mean", "overlap_fraction", "area_km2"} <= metric_names


@pytest.mark.asyncio
async def test_ee_semantic_rejects_development_imagery(mock_client):
    analyzer = EarthEngineDynamicWorldBuiltAnalyzer(client=mock_client)
    payload = SemanticAnalysisInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 12, 1),
        later_date=date(2025, 3, 1),
        imagery=EE_IMAGERY.model_copy(update={"mode": DataMode.DEVELOPMENT}),
        change_regions=[CVA_REGION],
        analysis_profile="building_construction",
    )
    with pytest.raises(SatQueryError) as exc:
        await analyzer.analyze(payload)
    assert exc.value.code == "semantic_analyzer_misconfigured"


@pytest.mark.asyncio
async def test_ee_semantic_auth_failure():
    with patch(
        "app.adapters.semantic.earth_engine.dynamic_world_built.EarthEngineClient.initialize",
        side_effect=SatQueryError("earth_engine_auth_failed", "auth failed", status_code=503),
    ):
        analyzer = EarthEngineDynamicWorldBuiltAnalyzer()
        payload = SemanticAnalysisInput(
            aoi=SAMPLE_AOI,
            earlier_date=date(2024, 12, 1),
            later_date=date(2025, 3, 1),
            imagery=EE_IMAGERY,
            change_regions=[CVA_REGION],
            analysis_profile="building_construction",
        )
        with pytest.raises(SatQueryError) as exc:
            await analyzer.analyze(payload)
        assert exc.value.code == "earth_engine_auth_failed"
