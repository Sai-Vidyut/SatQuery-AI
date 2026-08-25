from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.adapters.change.deterministic import DeterministicChangeDetector
from app.adapters.change.earth_engine import EarthEngineChangeDetector, EarthEngineSARChangeDetector
from app.adapters.change.factory import get_change_detector
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
                [77.59, 12.97],
                [77.61, 12.97],
                [77.61, 12.99],
                [77.59, 12.99],
                [77.59, 12.97],
            ]
        ],
    ),
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

DEV_IMAGERY = ImageryResult(
    source="satquery-development-imagery",
    mode=DataMode.DEVELOPMENT,
    sensor=SensorType.SENTINEL_2,
    scenes=[
        ImageryScene(scene_id="dev-1", acquisition_date=date(2024, 1, 12)),
        ImageryScene(scene_id="dev-2", acquisition_date=date(2025, 3, 3)),
    ],
    spatial=SpatialMetadata(bbox=[77.59, 12.97, 77.61, 12.99]),
    message="Development imagery adapter",
)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_factory_returns_deterministic_for_development_imagery(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "development")
    monkeypatch.setenv("CHANGE_DETECTOR", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()
    detector = get_change_detector(DataMode.DEVELOPMENT)
    assert isinstance(detector, DeterministicChangeDetector)


def test_factory_returns_earth_engine_for_ee_imagery(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "earth_engine")
    monkeypatch.setenv("CHANGE_DETECTOR", "earth_engine")
    from app.core.config import get_settings

    get_settings.cache_clear()
    detector = get_change_detector(DataMode.EARTH_ENGINE)
    assert isinstance(detector, EarthEngineChangeDetector)


def test_factory_rejects_ee_imagery_with_dev_detector(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "development")
    monkeypatch.setenv("CHANGE_DETECTOR", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(SatQueryError) as exc:
        get_change_detector(DataMode.EARTH_ENGINE)
    assert exc.value.code == "change_detector_misconfigured"


def test_factory_rejects_dev_imagery_with_ee_detector(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "earth_engine")
    monkeypatch.setenv("CHANGE_DETECTOR", "earth_engine")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(SatQueryError) as exc:
        get_change_detector(DataMode.DEVELOPMENT)
    assert exc.value.code == "change_detector_misconfigured"


@pytest.mark.asyncio
async def test_ee_detector_rejects_development_imagery():
    detector = EarthEngineChangeDetector(client=MagicMock())
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 12, 8),
        later_date=date(2025, 2, 26),
        imagery=DEV_IMAGERY,
    )
    with pytest.raises(SatQueryError) as exc:
        await detector.detect(payload)
    assert exc.value.code == "change_detector_misconfigured"


@pytest.mark.asyncio
async def test_ee_detector_requires_two_scenes():
    detector = EarthEngineChangeDetector(client=MagicMock())
    bad_imagery = EE_IMAGERY.model_copy(update={"scenes": EE_IMAGERY.scenes[:1]})
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 12, 8),
        later_date=date(2025, 2, 26),
        imagery=bad_imagery,
    )
    with pytest.raises(SatQueryError) as exc:
        await detector.detect(payload)
    assert exc.value.code == "insufficient_imagery"


def test_factory_returns_sar_detector_for_sentinel1_ee(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "earth_engine")
    monkeypatch.setenv("CHANGE_DETECTOR", "earth_engine")
    monkeypatch.setenv("SAR_CHANGE_DETECTOR", "earth_engine")
    from app.core.config import get_settings

    get_settings.cache_clear()
    detector = get_change_detector(DataMode.EARTH_ENGINE, SensorType.SENTINEL_1)
    assert isinstance(detector, EarthEngineSARChangeDetector)


def test_factory_rejects_s1_without_sar_detector_config(monkeypatch):
    monkeypatch.setenv("IMAGERY_PROVIDER", "earth_engine")
    monkeypatch.setenv("CHANGE_DETECTOR", "development")
    monkeypatch.setenv("SAR_CHANGE_DETECTOR", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(SatQueryError) as exc:
        get_change_detector(DataMode.EARTH_ENGINE, SensorType.SENTINEL_1)
    assert exc.value.code == "change_detector_misconfigured"


@pytest.mark.asyncio
async def test_ee_cva_detector_rejects_sentinel1():
    detector = EarthEngineChangeDetector(client=MagicMock())
    payload = ChangeDetectionInput(
        aoi=SAMPLE_AOI,
        earlier_date=date(2024, 12, 8),
        later_date=date(2025, 2, 26),
        imagery=EE_IMAGERY.model_copy(update={"sensor": SensorType.SENTINEL_1}),
    )
    with pytest.raises(SatQueryError) as exc:
        await detector.detect(payload)
    assert exc.value.code == "change_detector_misconfigured"
