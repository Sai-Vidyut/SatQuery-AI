from __future__ import annotations

from datetime import date

import pytest

from app.adapters.semantic.earth_engine.constants import (
    BUILT_BAND,
    CONFIDENCE_SCALE,
    CVA_OVERLAP_THRESHOLD,
    DELTA_BUILT_THRESHOLD,
    DYNAMIC_WORLD_COLLECTION,
    MIN_REGION_AREA_M2,
    POLICY_NAME,
    POLICY_VERSION,
    WINDOW_DAYS_AFTER,
    WINDOW_DAYS_BEFORE,
)
from app.adapters.semantic.earth_engine.metrics import (
    compute_delta_built,
    compute_semantic_confidence,
    passes_semantic_thresholds,
    polygon_area_m2,
)
from app.adapters.semantic.earth_engine.temporal import anchor_temporal_window


def test_dynamic_world_dataset_configuration():
    assert DYNAMIC_WORLD_COLLECTION == "GOOGLE/DYNAMICWORLD/V1"
    assert BUILT_BAND == "built"
    assert POLICY_NAME == "dynamic_world_built_construction_v1"
    assert POLICY_VERSION == "1.0.0"


def test_temporal_window_anchored_to_scene_date():
    anchor = date(2024, 12, 8)
    start, end = anchor_temporal_window(anchor)
    assert start == date(2024, 12, 8)
    assert end == date(2024, 12, 8 + WINDOW_DAYS_AFTER)
    assert WINDOW_DAYS_BEFORE == 0


def test_compute_delta_built():
    assert compute_delta_built(0.2, 0.38) == pytest.approx(0.18)


def test_confidence_calculation():
    assert compute_semantic_confidence(0.0) == 0.0
    assert compute_semantic_confidence(0.08) == pytest.approx(0.2)
    assert compute_semantic_confidence(0.20) == pytest.approx(0.5)
    assert compute_semantic_confidence(CONFIDENCE_SCALE) == 1.0
    assert compute_semantic_confidence(1.0) == 1.0


def test_threshold_pass_and_fail():
    assert passes_semantic_thresholds(0.15, 0.30, MIN_REGION_AREA_M2)
    assert not passes_semantic_thresholds(0.14, 0.30, MIN_REGION_AREA_M2)
    assert not passes_semantic_thresholds(0.20, 0.29, MIN_REGION_AREA_M2)
    assert not passes_semantic_thresholds(0.20, 0.30, MIN_REGION_AREA_M2 - 1)


def test_minimum_area_pass_fail():
    coords = [
        [77.59, 12.97],
        [77.605, 12.97],
        [77.605, 12.985],
        [77.59, 12.985],
        [77.59, 12.97],
    ]
    assert polygon_area_m2(coords) >= MIN_REGION_AREA_M2


def test_delta_built_threshold_constant():
    assert DELTA_BUILT_THRESHOLD == 0.15
    assert CVA_OVERLAP_THRESHOLD == 0.30
