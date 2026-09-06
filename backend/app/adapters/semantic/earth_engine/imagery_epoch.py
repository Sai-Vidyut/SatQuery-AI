"""Temporal window resolution for semantic analysis aligned with imagery epochs."""

from __future__ import annotations

from datetime import date

from app.adapters.imagery.earth_engine.composite import is_composite_scene
from app.adapters.semantic.earth_engine.temporal import anchor_temporal_window
from app.schemas.domain import ImageryScene


def imagery_epoch_window(scene: ImageryScene) -> tuple[date, date]:
    """
    Return the date window for semantic sampling aligned with the imagery epoch.

    Composite epochs use their full composite window; single-scene epochs use the
    existing Dynamic World anchor policy ([anchor-0d, anchor+7d]).
    """
    meta = scene.metadata or {}
    if is_composite_scene(scene):
        return (
            date.fromisoformat(meta["window_start"]),
            date.fromisoformat(meta["window_end"]),
        )
    return anchor_temporal_window(scene.acquisition_date)
