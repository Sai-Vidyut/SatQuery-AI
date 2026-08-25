from __future__ import annotations

from datetime import date

from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.core.errors import SatQueryError


def _sort_key_distance_to(target: date, scene: SceneCandidate) -> tuple:
    """Sort key: distance to target date, then cloud, then scene_id."""
    distance = abs((scene.acquisition_date - target).days)
    return (distance, scene.cloud_cover_percent, scene.scene_id)


def select_anchor_scenes(
    candidates: list[SceneCandidate],
    start_date: date,
    end_date: date,
) -> list[SceneCandidate]:
    """
    Deterministic selection policy (v1.0.0):

    - start_anchor: scene closest to start_date (tie: lowest cloud, then scene_id)
    - end_anchor: scene closest to end_date (same tie-breaks)
    - Returns unique scenes sorted by acquisition_date
    """
    if not candidates:
        raise SatQueryError(
            "no_imagery_after_cloud_filter",
            "All scenes were rejected by cloud filtering.",
            status_code=404,
        )

    start_scene = min(candidates, key=lambda s: _sort_key_distance_to(start_date, s))
    end_scene = min(candidates, key=lambda s: _sort_key_distance_to(end_date, s))

    selected: dict[str, SceneCandidate] = {
        start_scene.scene_id: start_scene,
        end_scene.scene_id: end_scene,
    }
    return sorted(selected.values(), key=lambda s: s.acquisition_date)
