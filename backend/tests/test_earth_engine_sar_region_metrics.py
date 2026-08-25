from __future__ import annotations

from app.adapters.change.earth_engine.sar_metrics import compute_sar_confidence
from app.adapters.change.earth_engine.sar_vectors import features_to_sar_evidence_regions


MOCK_FEATURE = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [77.57, 12.95],
                [77.58, 12.95],
                [77.58, 12.96],
                [77.57, 12.96],
                [77.57, 12.95],
            ]
        ],
    },
    "properties": {"mean": 24.3, "max": 106.5, "p90": 7.2},
}


def test_region_metrics_include_p90_and_version():
    regions = features_to_sar_evidence_regions(
        [MOCK_FEATURE],
        polarization="VV",
        before_scene_id="before",
        after_scene_id="after",
    )
    assert len(regions) == 1
    metrics = {m.name: m.value for m in regions[0].metrics}
    assert metrics["mean_sar_change_magnitude"] == 24.3
    assert metrics["max_sar_change_magnitude"] == 106.5
    assert metrics["p90_sar_change_magnitude"] == 7.2
    assert regions[0].metadata["detector_version"] == "1.1.0"
    assert regions[0].metadata["confidence_percentile"] == 90


def test_region_confidence_from_p90_not_inflated_by_max():
    regions = features_to_sar_evidence_regions(
        [MOCK_FEATURE],
        polarization="VV",
        before_scene_id="before",
        after_scene_id="after",
    )
    expected = compute_sar_confidence(7.2, mean_value=24.3, max_value=106.5)
    assert regions[0].confidence == expected
    assert regions[0].confidence < 1.0


def test_region_confidence_strong_uniform_change():
    feature = {
        **MOCK_FEATURE,
        "properties": {"mean": 10.5, "max": 11.0, "p90": 10.8},
    }
    regions = features_to_sar_evidence_regions(
        [feature],
        polarization="VV",
        before_scene_id="before",
        after_scene_id="after",
    )
    assert regions[0].confidence == compute_sar_confidence(10.8)
    assert regions[0].confidence > 0.5
