from __future__ import annotations

from datetime import date

from app.adapters.imagery.earth_engine.seasonality import seasonal_selection_penalty
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.core.errors import SatQueryError


def _sort_key_distance_to(target: date, scene: SceneCandidate) -> tuple:
    """
    Sort key (policy v1.1.0): seasonal preference, then date distance, cloud, scene_id.

    Seasonal preference avoids picking a phenologically mismatched scene when several
    candidates are similarly close to the requested anchor date.
    """
    distance = abs((scene.acquisition_date - target).days)
    seasonal = seasonal_selection_penalty(target, scene.acquisition_date)
    return (seasonal, distance, scene.cloud_cover_percent, scene.scene_id)


def select_anchor_scenes(
    candidates: list[SceneCandidate],
    start_date: date,
    end_date: date,
) -> list[SceneCandidate]:
    """
    Deterministic selection policy (v1.1.0):

    - start_anchor: prefer same-season scenes near start_date, then closest date,
      tie: lowest cloud, then scene_id
    - end_anchor: same rule vs end_date
    - Returns unique scenes sorted by acquisition_date
    - User-requested dates are not altered; selected scene dates may differ and are
      recorded in provider seasonality provenance.
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
