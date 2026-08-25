from __future__ import annotations

from app.services.query_profiles import (
    BUILDING_CONSTRUCTION_PROFILE,
    resolve_analysis_profile,
)


def test_construction_keyword_profile_matching():
    assert resolve_analysis_profile("Show me significant new construction.") == BUILDING_CONSTRUCTION_PROFILE
    assert resolve_analysis_profile("building growth in AOI") == BUILDING_CONSTRUCTION_PROFILE
    assert resolve_analysis_profile("built-up expansion") == BUILDING_CONSTRUCTION_PROFILE
    assert resolve_analysis_profile("urban development changes") == BUILDING_CONSTRUCTION_PROFILE


def test_non_construction_query_has_no_profile():
    assert resolve_analysis_profile("Show spectral change in vegetation.") is None
    assert resolve_analysis_profile("What changed between these dates?") is None
