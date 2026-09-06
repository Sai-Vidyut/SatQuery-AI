"""Configurable defaults for the uploaded bi-temporal change detection pipeline."""

from __future__ import annotations

from dataclasses import dataclass

DETECTOR_VERSION = "1.0.0"
DETECTOR_NAME = "uploaded_bi_temporal"
SOURCE_LABEL = "uploaded_bi_temporal"


@dataclass(frozen=True)
class BiTemporalConfig:
    """Safe defaults for the local raster change pipeline."""

    suppress_pseudo_changes: bool = True
    pseudo_window_size: int = 9
    pseudo_uniformity_threshold: float = 0.15
    smooth_sigma: float = 1.5
    otsu_enabled: bool = True
    otsu_percentile_clip: float = 98.0
    open_radius: int = 1
    close_radius: int = 3
    min_region_area_px: int = 8
    min_region_area_m2: float = 500.0
    max_regions: int = 50
    confidence_imbalance_low: float = 0.005
    confidence_imbalance_high: float = 0.60
    resolution_mismatch_factor: float = 10.0


DEFAULT_CONFIG = BiTemporalConfig()


def config_snapshot(cfg: BiTemporalConfig | None = None) -> dict[str, bool | float | int]:
    """Material configuration values exposed in detector provenance."""
    c = cfg or DEFAULT_CONFIG
    return {
        "suppress_pseudo_changes": c.suppress_pseudo_changes,
        "pseudo_window_size": c.pseudo_window_size,
        "pseudo_uniformity_threshold": c.pseudo_uniformity_threshold,
        "smooth_sigma": c.smooth_sigma,
        "otsu_enabled": c.otsu_enabled,
        "otsu_percentile_clip": c.otsu_percentile_clip,
        "open_radius": c.open_radius,
        "close_radius": c.close_radius,
        "min_region_area_px": c.min_region_area_px,
        "min_region_area_m2": c.min_region_area_m2,
        "max_regions": c.max_regions,
    }
