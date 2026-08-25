from __future__ import annotations

from datetime import date

import pytest

from app.adapters.imagery.earth_engine.sentinel1 import (
    scene_has_polarizations,
    select_s1_anchor_scenes,
)
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.core.errors import SatQueryError


def _scene(scene_id: str, acquired: date, orbit: int) -> SceneCandidate:
    return SceneCandidate(
        scene_id=scene_id,
        platform_id=f"COPERNICUS/S1_GRD/{scene_id}",
        acquisition_date=acquired,
        cloud_cover_percent=0.0,
        metadata={"relative_orbit": orbit, "polarizations": ["VV", "VH"]},
    )


def test_select_s1_anchor_scenes_same_orbit():
    candidates = [
        _scene("s1-a", date(2024, 12, 5), 78),
        _scene("s1-b", date(2024, 12, 20), 78),
        _scene("s1-c", date(2025, 2, 15), 78),
        _scene("s1-d", date(2024, 12, 8), 99),
    ]
    selected = select_s1_anchor_scenes(candidates, date(2024, 12, 1), date(2025, 3, 1))
    assert len(selected) == 2
    assert all(s.metadata["relative_orbit"] == 78 for s in selected)
    assert selected[0].scene_id == "s1-a"
    assert selected[1].scene_id == "s1-c"


def test_select_s1_anchor_scenes_requires_orbit_metadata():
    candidates = [
        SceneCandidate("x", "COPERNICUS/S1_GRD/x", date(2024, 12, 1), 0.0, {}),
    ]
    with pytest.raises(SatQueryError) as exc:
        select_s1_anchor_scenes(candidates, date(2024, 12, 1), date(2025, 3, 1))
    assert exc.value.code == "no_imagery_found"


def test_scene_has_polarizations():
    scene = _scene("s1-a", date(2024, 12, 5), 78)
    assert scene_has_polarizations(scene) == {"VV": True, "VH": True}
