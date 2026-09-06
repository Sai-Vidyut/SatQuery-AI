from datetime import date

import pytest

from app.adapters.imagery.earth_engine.selection import select_anchor_scenes
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate
from app.core.errors import SatQueryError


def _scene(scene_id: str, acq: date, cloud: float) -> SceneCandidate:
    return SceneCandidate(
        scene_id=scene_id,
        platform_id=f"COPERNICUS/S2_SR_HARMONIZED/{scene_id}",
        acquisition_date=acq,
        cloud_cover_percent=cloud,
        metadata={},
    )


def test_select_anchor_scenes_picks_closest_dates():
    candidates = [
        _scene("a", date(2024, 1, 10), 15.0),
        _scene("b", date(2024, 2, 1), 5.0),
        _scene("c", date(2024, 3, 5), 10.0),
    ]
    selected = select_anchor_scenes(candidates, date(2024, 1, 12), date(2024, 3, 3))
    ids = [s.scene_id for s in selected]
    assert ids == ["a", "c"]


def test_select_anchor_scenes_tie_breaks_on_cloud():
    candidates = [
        _scene("a", date(2024, 1, 12), 20.0),
        _scene("b", date(2024, 1, 12), 5.0),
    ]
    selected = select_anchor_scenes(candidates, date(2024, 1, 12), date(2024, 1, 12))
    assert len(selected) == 1
    assert selected[0].scene_id == "b"


def test_select_anchor_scenes_empty_raises():
    with pytest.raises(SatQueryError) as exc:
        select_anchor_scenes([], date(2024, 1, 1), date(2024, 3, 1))
    assert exc.value.code == "no_imagery_after_cloud_filter"


def test_select_anchor_scenes_prefers_same_season_over_closer_cross_season():
    """Policy v1.1.0: same-month scene wins over slightly closer cross-season scene."""
    candidates = [
        _scene("jan", date(2024, 1, 8), 5.0),
        _scene("jun", date(2024, 6, 12), 5.0),
    ]
    selected = select_anchor_scenes(candidates, date(2024, 6, 10), date(2024, 6, 10))
    assert selected[0].scene_id == "jun"


def test_selection_is_deterministic():
    candidates = [
        _scene("z", date(2024, 1, 15), 8.0),
        _scene("a", date(2024, 1, 15), 8.0),
        _scene("m", date(2024, 3, 1), 3.0),
    ]
    first = select_anchor_scenes(candidates, date(2024, 1, 10), date(2024, 3, 5))
    second = select_anchor_scenes(candidates, date(2024, 1, 10), date(2024, 3, 5))
    assert [s.scene_id for s in first] == [s.scene_id for s in second]
