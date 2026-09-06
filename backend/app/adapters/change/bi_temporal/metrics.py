"""Area metrics and heuristic change-direction hints (not semantic claims)."""

from __future__ import annotations

import numpy as np

ChangeDirectionHint = str

_MIN_CHANGED_FRACTION = 0.001


def pixel_area_m2(transform) -> float:
    gsd_x = abs(float(transform.a))
    gsd_y = abs(float(transform.e))
    if gsd_x < 0.05:
        m_per_deg = 111_319.0
        return (gsd_x * m_per_deg) * (gsd_y * m_per_deg)
    return gsd_x * gsd_y


def compute_area_metrics(mask: np.ndarray, transform) -> dict[str, float | int]:
    n_changed = int(mask.sum())
    total_px = int(mask.size)
    px_area = pixel_area_m2(transform)
    area_m2 = n_changed * px_area
    return {
        "changed_pixel_count": n_changed,
        "total_pixel_count": total_px,
        "changed_percentage": round(100.0 * n_changed / max(total_px, 1), 4),
        "area_m2": round(area_m2, 2),
        "area_ha": round(area_m2 / 10_000.0, 4),
        "area_km2": round(area_m2 / 1_000_000.0, 6),
        "region_count": 0,
    }


def classify_change_direction_hint(
    signed_diff: np.ndarray,
    change_mask: np.ndarray,
    primary_index: str,
) -> ChangeDirectionHint:
    """Heuristic index-direction hint — not a semantic land-cover claim."""
    pct_changed = change_mask.sum() / max(change_mask.size, 1)
    if pct_changed < _MIN_CHANGED_FRACTION:
        return "no_change"

    changed_pixels = signed_diff[change_mask]
    if changed_pixels.size == 0:
        return "no_change"

    mean_delta = float(np.median(changed_pixels))
    idx = primary_index.lower()
    threshold = 0.02

    if abs(mean_delta) < threshold:
        return "no_change"
    if idx == "ndvi":
        return "vegetation_gain" if mean_delta > 0 else "vegetation_loss"
    if idx == "ndwi":
        return "water_expansion" if mean_delta > 0 else "water_contraction"
    if idx == "ndbi":
        return "built_up_increase" if mean_delta > 0 else "built_up_decrease"
    if idx == "rvi":
        return "sar_backscatter_increase" if mean_delta > 0 else "sar_backscatter_decrease"
    return "index_increase" if mean_delta > 0 else "index_decrease"
