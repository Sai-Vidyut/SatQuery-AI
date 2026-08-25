from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.imagery.earth_engine.client import EarthEngineClient
from app.adapters.imagery.earth_engine.provider import EarthEngineProvider
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.core.errors import SatQueryError
from app.schemas.domain import (
    AOI,
    DataMode,
    GeoJSONGeometry,
    ImageryRequest,
    SensorType,
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

S1_REQUEST = ImageryRequest(
    aoi=SAMPLE_AOI,
    start_date=date(2024, 12, 1),
    end_date=date(2025, 3, 1),
    sensor=SensorType.SENTINEL_1,
)

MOCK_S1_CANDIDATES = [
    SceneCandidate(
        "20241210T051234",
        "COPERNICUS/S1_GRD/20241210T051234",
        date(2024, 12, 10),
        0.0,
        {
            "relative_orbit": 78,
            "polarizations": ["VV", "VH"],
            "instrument_mode": "IW",
        },
    ),
    SceneCandidate(
        "20250220T051234",
        "COPERNICUS/S1_GRD/20250220T051234",
        date(2025, 2, 20),
        0.0,
        {
            "relative_orbit": 78,
            "polarizations": ["VV", "VH"],
            "instrument_mode": "IW",
        },
    ),
]


@pytest.fixture
def mock_ee_client():
    ee = MagicMock()
    ee.Geometry.Polygon = MagicMock(return_value="aoi-geom")
    return EarthEngineClient(ee=ee, project="test-project")


@pytest.mark.asyncio
async def test_earth_engine_provider_returns_sentinel1_metadata(mock_ee_client):
    provider = EarthEngineProvider(client=mock_ee_client)

    with (
        patch(
            "app.adapters.imagery.earth_engine.provider.query_sentinel1_scenes",
            return_value=MOCK_S1_CANDIDATES,
        ),
        patch(
            "app.adapters.imagery.earth_engine.provider.select_s1_anchor_scenes",
            return_value=MOCK_S1_CANDIDATES,
        ),
    ):
        result = await provider.fetch(S1_REQUEST)

    assert result.mode == DataMode.EARTH_ENGINE
    assert result.sensor == SensorType.SENTINEL_1
    assert result.collection_id == "COPERNICUS/S1_GRD"
    assert len(result.scenes) == 2
    assert result.scenes[0].platform_id.startswith("COPERNICUS/S1_GRD/")
    assert result.provider_metadata["selection_policy"] == "1.0.0"
    assert result.provider_metadata["polarization_availability"]["VV"] is True
    assert result.provider_metadata["polarization_availability"]["VH"] is True
    assert result.provider_metadata["relative_orbit"] == 78


@pytest.mark.asyncio
async def test_earth_engine_sentinel1_no_imagery_propagates(mock_ee_client):
    provider = EarthEngineProvider(client=mock_ee_client)

    with patch(
        "app.adapters.imagery.earth_engine.provider.query_sentinel1_scenes",
        side_effect=SatQueryError("no_imagery_found", "No scenes", status_code=404),
    ):
        with pytest.raises(SatQueryError) as exc:
            await provider.fetch(S1_REQUEST)
        assert exc.value.code == "no_imagery_found"


@pytest.mark.asyncio
async def test_earth_engine_sentinel1_auth_failure():
    request = S1_REQUEST
    with patch(
        "app.adapters.imagery.earth_engine.client.EarthEngineClient.initialize",
        side_effect=SatQueryError("earth_engine_auth_failed", "auth failed", status_code=503),
    ):
        provider = EarthEngineProvider()
        with pytest.raises(SatQueryError) as exc:
            await provider.fetch(request)
        assert exc.value.code == "earth_engine_auth_failed"
