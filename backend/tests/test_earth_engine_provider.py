from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.imagery.development import DevelopmentImageryProvider
from app.adapters.imagery.earth_engine.client import EarthEngineClient
from app.adapters.imagery.earth_engine.provider import EarthEngineProvider
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.core.errors import SatQueryError
from app.schemas.domain import (
    AOI,
    DataMode,
    GeoJSONGeometry,
    ImageryPreferences,
    ImageryRequest,
    SensorType,
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

SAMPLE_REQUEST = ImageryRequest(
    aoi=SAMPLE_AOI,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 3, 31),
    sensor=SensorType.SENTINEL_2,
    preferences=ImageryPreferences(cloud_cover_max=30.0),
)

MOCK_CANDIDATES = [
    SceneCandidate("20240112T050701", "COPERNICUS/S2_SR_HARMONIZED/20240112T050701", date(2024, 1, 12), 8.5, {}),
    SceneCandidate("20240325T050701", "COPERNICUS/S2_SR_HARMONIZED/20240325T050701", date(2024, 3, 25), 12.0, {}),
]


@pytest.fixture
def mock_ee_client():
    ee = MagicMock()
    ee.Geometry.Polygon = MagicMock(return_value="aoi-geom")
    client = EarthEngineClient(ee=ee, project="test-project")
    return client


@pytest.mark.asyncio
async def test_earth_engine_provider_returns_real_metadata(mock_ee_client):
    provider = EarthEngineProvider(client=mock_ee_client)

    with (
        patch(
            "app.adapters.imagery.earth_engine.provider.query_sentinel2_scenes",
            return_value=MOCK_CANDIDATES,
        ),
        patch(
            "app.adapters.imagery.earth_engine.provider.build_composite_epochs",
        ) as mock_composite,
    ):
        from app.adapters.imagery.earth_engine.composite import build_composite_epochs

        mock_composite.side_effect = lambda c, **kw: build_composite_epochs(
            c,
            requested_start=kw["requested_start"],
            requested_end=kw["requested_end"],
        )
        result = await provider.fetch(SAMPLE_REQUEST)

    assert result.mode == DataMode.EARTH_ENGINE
    assert result.source == "google-earth-engine"
    assert result.collection_id == "COPERNICUS/S2_SR_HARMONIZED"
    assert len(result.scenes) == 2
    assert result.scenes[0].platform_id.startswith("COMPOSITE/MEDIAN/")
    assert result.provider_metadata["selection_policy"] == "2.1.0"
    assert result.provider_metadata["imagery_strategy"] == "seasonal_median_composite"


@pytest.mark.asyncio
async def test_earth_engine_sentinel1_supported(mock_ee_client):
    provider = EarthEngineProvider(client=mock_ee_client)
    request = SAMPLE_REQUEST.model_copy(update={"sensor": SensorType.SENTINEL_1})

    with (
        patch(
            "app.adapters.imagery.earth_engine.provider.query_sentinel1_scenes",
            return_value=MOCK_CANDIDATES,
        ),
        patch(
            "app.adapters.imagery.earth_engine.provider.select_s1_anchor_scenes",
            return_value=MOCK_CANDIDATES,
        ),
    ):
        result = await provider.fetch(request)

    assert result.sensor == SensorType.SENTINEL_1
    assert result.collection_id == "COPERNICUS/S1_GRD"


@pytest.mark.asyncio
async def test_earth_engine_no_imagery_propagates(mock_ee_client):
    provider = EarthEngineProvider(client=mock_ee_client)

    with patch(
        "app.adapters.imagery.earth_engine.provider.query_sentinel2_scenes",
        side_effect=SatQueryError("no_imagery_found", "No scenes", status_code=404),
    ):
        with pytest.raises(SatQueryError) as exc:
            await provider.fetch(SAMPLE_REQUEST)
        assert exc.value.code == "no_imagery_found"


@pytest.mark.asyncio
async def test_earth_engine_auth_failure():
    with patch(
        "app.adapters.imagery.earth_engine.client.EarthEngineClient.initialize",
        side_effect=SatQueryError("earth_engine_auth_failed", "auth failed", status_code=503),
    ):
        provider = EarthEngineProvider()
        with pytest.raises(SatQueryError) as exc:
            await provider.fetch(SAMPLE_REQUEST)
        assert exc.value.code == "earth_engine_auth_failed"


@pytest.mark.asyncio
async def test_development_provider_still_labeled_development():
    provider = DevelopmentImageryProvider()
    result = await provider.fetch(SAMPLE_REQUEST)
    assert result.mode == DataMode.DEVELOPMENT
    assert result.source == "satquery-development-imagery"
    assert "DEMONSTRATION DATA" in (result.message or "")
    assert result.provider_metadata.get("demonstration_data") is True


@pytest.mark.asyncio
async def test_invalid_date_range_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ImageryRequest(
            aoi=SAMPLE_AOI,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 1, 1),
        )
