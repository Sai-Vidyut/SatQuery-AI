from __future__ import annotations

from app.adapters.change.base import ChangeDetector
from app.adapters.change.deterministic import DeterministicChangeDetector
from app.adapters.change.earth_engine import EarthEngineChangeDetector, EarthEngineSARChangeDetector
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.schemas.domain import DataMode, SensorType


def get_change_detector(
    imagery_mode: DataMode | None = None,
    sensor: SensorType | None = None,
) -> ChangeDetector:
    """
    Resolve change detector from configuration, imagery mode, and sensor.
    Never silently mixes development imagery with Earth Engine detection.
    """
    settings = get_settings()
    effective = settings.effective_change_detector
    sar_effective = settings.effective_sar_change_detector

    if imagery_mode == DataMode.EARTH_ENGINE:
        if sensor == SensorType.SENTINEL_1:
            if sar_effective != "earth_engine":
                raise SatQueryError(
                    "change_detector_misconfigured",
                    "Sentinel-1 imagery requires SAR_CHANGE_DETECTOR=earth_engine "
                    "(or CHANGE_DETECTOR/IMAGERY_PROVIDER=earth_engine).",
                    status_code=500,
                )
            return EarthEngineSARChangeDetector()

        if effective != "earth_engine":
            raise SatQueryError(
                "change_detector_misconfigured",
                "Earth Engine imagery requires CHANGE_DETECTOR=earth_engine (or IMAGERY_PROVIDER=earth_engine).",
                status_code=500,
            )
        return EarthEngineChangeDetector()

    if imagery_mode == DataMode.DEVELOPMENT:
        if sensor == SensorType.SENTINEL_1 and sar_effective == "earth_engine":
            raise SatQueryError(
                "change_detector_misconfigured",
                "Development imagery cannot use the Earth Engine SAR change detector.",
                status_code=500,
            )
        if effective == "earth_engine":
            raise SatQueryError(
                "change_detector_misconfigured",
                "Development imagery cannot use the Earth Engine change detector.",
                status_code=500,
            )
        return DeterministicChangeDetector()

    if sensor == SensorType.SENTINEL_1:
        if sar_effective == "earth_engine":
            return EarthEngineSARChangeDetector()
        return DeterministicChangeDetector()

    if effective == "earth_engine":
        return EarthEngineChangeDetector()
    return DeterministicChangeDetector()
