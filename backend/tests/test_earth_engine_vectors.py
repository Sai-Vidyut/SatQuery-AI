from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.adapters.change.earth_engine.constants import CVA_MAGNITUDE_THRESHOLD
from app.adapters.change.earth_engine.vectors import (
    _confidence_from_magnitude,
    features_to_evidence_regions,
)


def _sample_feature(mean: float, max_val: float | None = None) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.59, 12.97],
                    [77.605, 12.97],
                    [77.605, 12.985],
                    [77.59, 12.985],
                    [77.59, 12.97],
                ]
            ],
        },
        "properties": {"mean": mean, "max": max_val or mean * 1.2, "label": 1},
    }


def test_confidence_is_zero_below_threshold():
    assert _confidence_from_magnitude(CVA_MAGNITUDE_THRESHOLD - 1) == 0.0


def test_confidence_increases_above_threshold():
    low = _confidence_from_magnitude(CVA_MAGNITUDE_THRESHOLD + 100)
    high = _confidence_from_magnitude(CVA_MAGNITUDE_THRESHOLD + 1000)
    assert 0 < low < high <= 1.0


def test_features_to_evidence_regions_filters_small_polygons():
    tiny = _sample_feature(CVA_MAGNITUDE_THRESHOLD + 500)
    tiny["geometry"]["coordinates"] = [
        [
            [77.59, 12.97],
            [77.5901, 12.97],
            [77.5901, 12.9701],
            [77.59, 12.9701],
            [77.59, 12.97],
        ]
    ]
    regions = features_to_evidence_regions([tiny])
    assert regions == []


def test_features_to_evidence_regions_produces_metrics():
    regions = features_to_evidence_regions([_sample_feature(CVA_MAGNITUDE_THRESHOLD + 400)])
    assert len(regions) == 1
    region = regions[0]
    assert region.type == "spectral_change"
    assert region.source == "earth_engine_cva"
    metric_names = {m.name for m in region.metrics}
    assert "area_km2" in metric_names
    assert "mean_change_magnitude" in metric_names
    assert "max_change_magnitude" in metric_names
    assert region.confidence > 0


def test_features_sorted_by_area_and_capped():
    large = _sample_feature(CVA_MAGNITUDE_THRESHOLD + 300)
    small = _sample_feature(CVA_MAGNITUDE_THRESHOLD + 900)
    small["geometry"]["coordinates"] = [
        [
            [77.60, 12.97],
            [77.602, 12.97],
            [77.602, 12.972],
            [77.60, 12.972],
            [77.60, 12.97],
        ]
    ]
    regions = features_to_evidence_regions([small, large])
    assert regions[0].metrics[0].value >= regions[-1].metrics[0].value


def test_vectorize_returns_empty_when_no_change_pixels():
    ee = MagicMock()
    change = MagicMock()
    binary = MagicMock()
    filtered = MagicMock()
    change.gt.return_value.byte.return_value.rename.return_value = binary
    binary.connectedPixelCount.return_value.gte.return_value = MagicMock()
    binary.updateMask.return_value = filtered
    filtered.reduceRegion.return_value.getInfo.return_value = {"change_mask": 0}

    from app.adapters.change.earth_engine.vectors import vectorize_change_regions

    result = vectorize_change_regions(ee, change, "aoi")
    assert result == []
    filtered.selfMask.return_value.reduceToVectors.assert_not_called()
    change.reduceRegions.assert_not_called()


def test_vectorize_uses_reduce_regions_for_single_band_stats():
    """Regression: combined reducer on reduceToVectors fails for single-band images."""
    ee = MagicMock()
    change = MagicMock()
    binary = MagicMock()
    filtered = MagicMock()
    change.gt.return_value.byte.return_value.rename.return_value = binary
    binary.connectedPixelCount.return_value.gte.return_value = MagicMock()
    binary.updateMask.return_value = filtered
    filtered.reduceRegion.return_value.getInfo.return_value = {"change_mask": 42}
    vectors_fc = MagicMock()
    filtered.selfMask.return_value.reduceToVectors.return_value = vectors_fc
    clipped_fc = MagicMock()
    vectors_limited = MagicMock()
    ee.FeatureCollection.return_value.map.return_value = clipped_fc
    clipped_fc.limit.return_value = vectors_limited
    stats_fc = MagicMock()
    change.reduceRegions.return_value = stats_fc
    stats_fc.getInfo.return_value = {
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[77.59, 12.97], [77.605, 12.97], [77.605, 12.985], [77.59, 12.985], [77.59, 12.97]]]},
                "properties": {"mean": 1200.0, "max": 1500.0, "label": 1},
            }
        ]
    }

    from app.adapters.change.earth_engine.vectors import vectorize_change_regions

    features = vectorize_change_regions(ee, change, "aoi")
    filtered.selfMask.return_value.reduceToVectors.assert_called_once()
    ee.FeatureCollection.assert_called_once()
    ee.FeatureCollection.return_value.map.assert_called_once()
    clipped_fc.limit.assert_called_once()
    change.reduceRegions.assert_called_once()
    assert len(features) == 1
    assert features[0]["properties"]["mean"] == 1200.0


def test_vectorize_raises_on_ee_failure():
    ee = MagicMock()
    change = MagicMock()
    binary = MagicMock()
    filtered = MagicMock()
    change.gt.return_value.byte.return_value.rename.return_value = binary
    binary.connectedPixelCount.return_value.gte.return_value = MagicMock()
    binary.updateMask.return_value = filtered
    filtered.reduceRegion.return_value.getInfo.side_effect = RuntimeError("ee down")

    from app.adapters.change.earth_engine.vectors import vectorize_change_regions
    from app.core.errors import SatQueryError

    with pytest.raises(SatQueryError) as exc:
        vectorize_change_regions(ee, change, "aoi")
    assert exc.value.code == "earth_engine_request_failed"
