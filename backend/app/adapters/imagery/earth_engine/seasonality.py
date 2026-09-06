"""Seasonality utilities for Earth Engine Sentinel-2 scene selection (Phase 7)."""

from __future__ import annotations

from datetime import date
from typing import Any

SEASONALITY_POLICY_VERSION = "1.0.0"

# Circular month gap above which T1/T2 pair is flagged cross-season.
CROSS_SEASON_MONTH_GAP = 3

# Month distance at or below which a scene is considered same-season with target.
SAME_SEASON_MONTH_GAP = 1


def circular_month_distance(month_a: int, month_b: int) -> int:
    """Minimum circular distance between two calendar months (1–12)."""
    diff = abs(month_a - month_b)
    return min(diff, 12 - diff)


def is_cross_season_pair(date_a: date, date_b: date) -> bool:
    """True when acquisition months are far enough apart to risk phenology false positives."""
    return circular_month_distance(date_a.month, date_b.month) > CROSS_SEASON_MONTH_GAP


def seasonal_selection_penalty(target: date, scene_date: date) -> int:
    """
    Selection preference tier (lower is better).

    0 = same/adjacent month (<= SAME_SEASON_MONTH_GAP)
    1 = moderate seasonal offset (2–3 months)
    2 = cross-season (> CROSS_SEASON_MONTH_GAP)
    """
    md = circular_month_distance(target.month, scene_date.month)
    if md <= SAME_SEASON_MONTH_GAP:
        return 0
    if md <= CROSS_SEASON_MONTH_GAP:
        return 1
    return 2


def build_seasonality_provenance(
    *,
    requested_start: date,
    requested_end: date,
    selected_dates: list[date],
    selection_policy: str,
) -> dict[str, Any]:
    """Compact seasonality metadata for imagery provider provenance."""
    actual_start = selected_dates[0] if selected_dates else None
    actual_end = selected_dates[-1] if selected_dates else None
    cross_season = False
    if actual_start and actual_end and len(selected_dates) >= 2:
        cross_season = is_cross_season_pair(actual_start, actual_end)

    start_offset_days = (
        (actual_start - requested_start).days if actual_start else None
    )
    end_offset_days = (
        (actual_end - requested_end).days if actual_end else None
    )

    warnings: list[str] = []
    if cross_season:
        warnings.append(
            "cross_season_comparison: T1/T2 scene months differ by more than "
            f"{CROSS_SEASON_MONTH_GAP} months; seasonal vegetation/water variation "
            "may cause false positives."
        )
    if start_offset_days is not None and abs(start_offset_days) > 31:
        warnings.append(
            f"start_date_adjusted: requested {requested_start.isoformat()}, "
            f"selected {actual_start.isoformat()} ({start_offset_days:+d} days)."
        )
    if end_offset_days is not None and abs(end_offset_days) > 31:
        warnings.append(
            f"end_date_adjusted: requested {requested_end.isoformat()}, "
            f"selected {actual_end.isoformat()} ({end_offset_days:+d} days)."
        )

    return {
        "seasonality_policy": SEASONALITY_POLICY_VERSION,
        "selection_policy": selection_policy,
        "requested_start_date": requested_start.isoformat(),
        "requested_end_date": requested_end.isoformat(),
        "actual_start_date": actual_start.isoformat() if actual_start else None,
        "actual_end_date": actual_end.isoformat() if actual_end else None,
        "start_date_offset_days": start_offset_days,
        "end_date_offset_days": end_offset_days,
        "cross_season_comparison": cross_season,
        "dates_adjusted": bool(warnings),
        "warnings": warnings,
    }
