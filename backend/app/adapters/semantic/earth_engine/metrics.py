from __future__ import annotations

import math

from app.adapters.semantic.earth_engine.constants import (
    CONFIDENCE_SCALE,
    CVA_OVERLAP_THRESHOLD,
    DELTA_BUILT_THRESHOLD,
    MIN_REGION_AREA_M2,
)


def polygon_area_m2(coords: list[list[float]]) -> float:
    ring = coords[:-1] if len(coords) > 1 and coords[0] == coords[-1] else coords
    if len(ring) < 3:
        return 0.0
    mean_lat = sum(p[1] for p in ring) / len(ring)
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * math.cos(math.radians(mean_lat))
    area = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i][0] * lon_scale, ring[i][1] * lat_scale
        x2, y2 = ring[(i + 1) % len(ring)][0] * lon_scale, ring[(i + 1) % len(ring)][1] * lat_scale
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def compute_delta_built(earlier_built_mean: float, later_built_mean: float) -> float:
    return round(later_built_mean - earlier_built_mean, 6)


def compute_semantic_confidence(delta_built: float) -> float:
    if delta_built <= 0:
        return 0.0
    return round(min(1.0, max(0.0, delta_built / CONFIDENCE_SCALE)), 3)


def passes_semantic_thresholds(
    delta_built: float,
    overlap_fraction: float,
    area_m2: float,
    *,
    delta_threshold: float = DELTA_BUILT_THRESHOLD,
    overlap_threshold: float = CVA_OVERLAP_THRESHOLD,
    min_area_m2: float = MIN_REGION_AREA_M2,
) -> bool:
    return (
        delta_built >= delta_threshold
        and overlap_fraction >= overlap_threshold
        and area_m2 >= min_area_m2
    )
