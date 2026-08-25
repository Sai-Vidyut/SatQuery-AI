"""Pure metric/threshold helpers for SAR change detection (testable, no EE)."""

from __future__ import annotations

from app.adapters.change.earth_engine.sar_constants import (
    MAX_PLAUSIBLE_CHANGE_DB,
    SAR_CHANGE_THRESHOLD_DB,
    SAR_CONFIDENCE_PERCENTILE,
    SAR_CONFIDENCE_REFERENCE_DB,
)


def is_valid_linear_backscatter(value: float, *, min_linear: float, max_linear: float) -> bool:
    """Return whether a linear sigma0 sample is within the valid backscatter range."""
    return min_linear <= value <= max_linear


def is_plausible_change_db(delta_db: float, *, max_plausible_db: float = MAX_PLAUSIBLE_CHANGE_DB) -> bool:
    """Return whether a per-pixel dB change is physically plausible (artifact rejection)."""
    return 0.0 <= delta_db <= max_plausible_db


def linear_to_db(value: float) -> float:
    """Convert linear sigma0 to decibels. Caller must ensure value > 0."""
    if value <= 0:
        raise ValueError("linear backscatter must be positive for dB conversion")
    import math

    return 10.0 * math.log10(value)


def compute_sar_confidence(
    percentile_value: float,
    *,
    mean_value: float | None = None,
    max_value: float | None = None,
    threshold_db: float = SAR_CHANGE_THRESHOLD_DB,
    reference_db: float = SAR_CONFIDENCE_REFERENCE_DB,
    percentile: int = SAR_CONFIDENCE_PERCENTILE,
) -> float:
    """
    Confidence from the region's robust change statistic (default: p90).

    Confidence is derived from the percentile statistic only — not from max —
    so a single extreme pixel cannot saturate confidence at 1.0.
    """
    _ = mean_value, max_value, percentile  # documented inputs for traceability
    if percentile_value <= threshold_db:
        return 0.0
    span = reference_db - threshold_db
    if span <= 0:
        return 1.0
    return round(min(1.0, (percentile_value - threshold_db) / span), 3)


def combine_polarization_changes(vv_delta: float | None, vh_delta: float | None) -> float:
    """Per-pixel combination policy: max absolute dB change across available polarizations."""
    values = [v for v in (vv_delta, vh_delta) if v is not None]
    if not values:
        raise ValueError("at least one polarization delta is required")
    return max(values)
