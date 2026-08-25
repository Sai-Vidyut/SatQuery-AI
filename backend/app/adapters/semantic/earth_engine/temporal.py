from __future__ import annotations

from datetime import date, timedelta

from app.adapters.semantic.earth_engine.constants import (
    WINDOW_DAYS_AFTER,
    WINDOW_DAYS_BEFORE,
)


def anchor_temporal_window(anchor_date: date) -> tuple[date, date]:
    """
    Deterministic Dynamic World sampling window around a Sentinel-2 anchor date.
    Policy v1.0.0: [anchor_date - BEFORE, anchor_date + AFTER] inclusive.
    """
    start = anchor_date - timedelta(days=WINDOW_DAYS_BEFORE)
    end = anchor_date + timedelta(days=WINDOW_DAYS_AFTER)
    return start, end
