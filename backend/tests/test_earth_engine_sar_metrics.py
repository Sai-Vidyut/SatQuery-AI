from __future__ import annotations

import math

import pytest

from app.adapters.change.earth_engine.sar_constants import (
    MAX_PLAUSIBLE_CHANGE_DB,
    MAX_VALID_LINEAR_BACKSCATTER,
    MIN_VALID_LINEAR_BACKSCATTER,
    SAR_CHANGE_THRESHOLD_DB,
    SAR_CONFIDENCE_REFERENCE_DB,
)
from app.adapters.change.earth_engine.sar_metrics import (
    combine_polarization_changes,
    compute_sar_confidence,
    is_plausible_change_db,
    is_valid_linear_backscatter,
    linear_to_db,
)


def test_near_zero_linear_backscatter_rejected():
    assert is_valid_linear_backscatter(1e-10, min_linear=MIN_VALID_LINEAR_BACKSCATTER, max_linear=MAX_VALID_LINEAR_BACKSCATTER) is False
    assert is_valid_linear_backscatter(1e-4, min_linear=MIN_VALID_LINEAR_BACKSCATTER, max_linear=MAX_VALID_LINEAR_BACKSCATTER) is True


def test_extreme_db_delta_rejected_as_implausible():
    assert is_plausible_change_db(106.5) is False
    assert is_plausible_change_db(25.0) is True
    assert is_plausible_change_db(25.1) is False


def test_linear_to_db_conversion():
    assert linear_to_db(1.0) == pytest.approx(0.0)
    assert linear_to_db(0.01) == pytest.approx(-20.0)
    with pytest.raises(ValueError):
        linear_to_db(0.0)


def test_v1_floor_artifact_explains_extreme_delta():
    """v1.0.0 used 1e-10 floor (-100 dB); differencing against -10 dB yields ~90 dB artifact."""
    artifact_db = abs(linear_to_db(0.1) - linear_to_db(1e-10))
    assert artifact_db > 50
    assert is_plausible_change_db(artifact_db) is False


def test_valid_strong_backscatter_change_preserved():
    before_db = linear_to_db(0.05)
    after_db = linear_to_db(0.12)
    delta = abs(after_db - before_db)
    assert 2.0 < delta < MAX_PLAUSIBLE_CHANGE_DB
    assert is_plausible_change_db(delta) is True


def test_vv_vh_combination_uses_max():
    assert combine_polarization_changes(3.0, 5.5) == 5.5
    assert combine_polarization_changes(7.0, None) == 7.0


def test_confidence_uses_percentile_not_max():
    # Strong p90 but extreme max should not saturate confidence at 1.0
    conf = compute_sar_confidence(7.0, mean_value=24.3, max_value=106.5)
    expected = (7.0 - SAR_CHANGE_THRESHOLD_DB) / (SAR_CONFIDENCE_REFERENCE_DB - SAR_CHANGE_THRESHOLD_DB)
    assert conf == pytest.approx(round(min(1.0, expected), 3))
    assert conf < 1.0


def test_confidence_strong_genuine_change():
    conf = compute_sar_confidence(11.0)
    assert conf == pytest.approx(0.692, abs=0.01)


def test_confidence_below_threshold():
    assert compute_sar_confidence(1.5) == 0.0
    assert compute_sar_confidence(SAR_CHANGE_THRESHOLD_DB) == 0.0


def test_confidence_at_reference():
    assert compute_sar_confidence(SAR_CONFIDENCE_REFERENCE_DB) == 1.0
