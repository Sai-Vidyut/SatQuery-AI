from __future__ import annotations

from app.adapters.change.base import ChangeDetector
from app.adapters.change.deterministic import DeterministicChangeDetector
from app.adapters.change.earth_engine import EarthEngineChangeDetector, EarthEngineSARChangeDetector
from app.adapters.change.uploaded_bitemporal import UploadedBiTemporalChangeDetector
from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.schemas.domain import DataMode, SensorType

_VALID_UPLOAD_CHANGE_DETECTORS = frozenset({"bi_temporal", "deterministic"})


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


def get_upload_change_detector() -> ChangeDetector:
    """
    Resolve change detector for uploaded bi-temporal GeoTIFF pairs.
    Catalog development mock and Earth Engine paths are unchanged.
    """
    settings = get_settings()
    mode = settings.upload_change_detector
    if mode not in _VALID_UPLOAD_CHANGE_DETECTORS:
        raise SatQueryError(
            "change_detector_misconfigured",
            "UPLOAD_CHANGE_DETECTOR must be 'bi_temporal' or 'deterministic'; "
            f"got {mode!r}.",
            status_code=500,
        )
    if mode == "deterministic":
        return DeterministicChangeDetector()
    return UploadedBiTemporalChangeDetector()
