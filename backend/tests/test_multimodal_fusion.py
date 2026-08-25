from __future__ import annotations

from datetime import date

import pytest

from app.evidence.geometry import intersect_polygon_area_m2, overlap_fraction_of_child, polygon_area_km2
from app.evidence.multimodal_fusion import (
    FUSION_POLICY_VERSION,
    PROVENANCE_CVA,
    PROVENANCE_SAR,
    PROVENANCE_SEMANTIC,
    fuse_multimodal_evidence,
)
from app.schemas.domain import (
    ChangeDetectionOutput,
    DataMode,
    EvidenceRegion,
    GeoJSONGeometry,
    Metric,
    SemanticAnalysisOutput,
)


def _square(origin_lon: float, origin_lat: float, size: float = 0.01) -> list[list[float]]:
    return [
        [origin_lon, origin_lat],
        [origin_lon + size, origin_lat],
        [origin_lon + size, origin_lat + size],
        [origin_lon, origin_lat + size],
        [origin_lon, origin_lat],
    ]


def _cva() -> EvidenceRegion:
    return EvidenceRegion(
        id="change-region-01",
        geometry=GeoJSONGeometry(type="Polygon", coordinates=[_square(77.59, 12.97)]),
        type="spectral_change",
        confidence=0.7,
        metrics=[Metric(name="area_km2", value=1.0, unit="km²", source="earth_engine_cva")],
        source="earth_engine_cva",
    )


def _semantic(parent_id: str = "change-region-01", delta: float = 0.20) -> EvidenceRegion:
    return EvidenceRegion(
        id="semantic-candidate-01",
        geometry=GeoJSONGeometry(type="Polygon", coordinates=[_square(77.595, 12.975, 0.005)]),
        type="semantic_evidence",
        confidence=0.55,
        metrics=[Metric(name="delta_built_probability", value=delta, unit="probability", source=PROVENANCE_SEMANTIC)],
        source="dynamic_world_built_v1",
        metadata={"claim_type": "construction_candidate", "parent_region_id": parent_id},
    )


def _sar(offset: float = 0.0) -> EvidenceRegion:
    return EvidenceRegion(
        id="sar-change-region-01",
        geometry=GeoJSONGeometry(type="Polygon", coordinates=[_square(77.595 + offset, 12.975 + offset, 0.005)]),
        type="sar_change",
        confidence=0.86,
        metrics=[
            Metric(name="mean_sar_change_magnitude", value=6.8, unit="db", source=PROVENANCE_SAR),
            Metric(name="polarization", value="VV", unit=None, source=PROVENANCE_SAR),
        ],
        source="earth_engine_sar",
        metadata={"before_scene_id": "s1-before", "after_scene_id": "s1-after"},
    )


def _semantic_output(*regions: EvidenceRegion) -> SemanticAnalysisOutput:
    return SemanticAnalysisOutput(
        regions=list(regions),
        claims=[],
        analyzer="dynamic_world_built_v1",
        mode=DataMode.EARTH_ENGINE,
    )


def _sar_output(*regions: EvidenceRegion) -> ChangeDetectionOutput:
    return ChangeDetectionOutput(
        regions=list(regions),
        raw_detection_count=len(regions),
        detector="earth_engine_sar",
        mode=DataMode.EARTH_ENGINE,
    )


def test_geometry_intersection_full_overlap():
    ring = _square(77.59, 12.97, 0.01)
    inner = _square(77.595, 12.975, 0.005)
    assert overlap_fraction_of_child(ring, inner) == pytest.approx(1.0, abs=0.01)


def test_geometry_zero_overlap():
    parent = _square(77.59, 12.97)
    child = _square(78.0, 12.97)
    assert overlap_fraction_of_child(parent, child) == 0.0
    assert intersect_polygon_area_m2(parent, child) == 0.0


def test_cva_only_fusion():
    fused = fuse_multimodal_evidence([_cva()], None, None)
    assert len(fused) == 1
    assert fused[0].metadata["evidence_type"] == "spectral_change"
    assert fused[0].metadata["claim_type"] == "none"
    assert fused[0].metadata["provenance_chain"] == [PROVENANCE_CVA]


def test_cva_plus_semantic_construction_candidate():
    fused = fuse_multimodal_evidence([_cva()], _semantic_output(_semantic()), None)
    candidates = [r for r in fused if r.metadata.get("claim_type") == "construction_candidate"]
    assert len(candidates) == 1
    assert candidates[0].metadata["evidence_modality"] == "optical+semantic"
    assert candidates[0].metadata["provenance_chain"] == [PROVENANCE_CVA, PROVENANCE_SEMANTIC]
    assert candidates[0].metadata["semantic_overlap_fraction"] >= 0.3
    assert candidates[0].metadata["cva_confidence"] == 0.7
    assert candidates[0].metadata["semantic_confidence"] == 0.55
    assert candidates[0].confidence == pytest.approx(0.55)


def test_cva_plus_sar_multimodal_change_not_construction():
    fused = fuse_multimodal_evidence([_cva()], None, _sar_output(_sar()))
    multimodal = [r for r in fused if r.metadata.get("evidence_type") == "multimodal_change"]
    assert len(multimodal) == 1
    assert multimodal[0].metadata["claim_type"] == "none"
    assert multimodal[0].metadata["evidence_modality"] == "optical+sar"
    assert "construction_candidate" not in {r.metadata.get("claim_type") for r in fused}


def test_cva_semantic_sar_construction_with_sar_support():
    fused = fuse_multimodal_evidence([_cva()], _semantic_output(_semantic()), _sar_output(_sar()))
    candidate = next(r for r in fused if r.metadata.get("claim_type") == "construction_candidate")
    assert candidate.metadata["evidence_modality"] == "optical+semantic+sar"
    assert PROVENANCE_SAR in candidate.metadata["provenance_chain"]
    assert candidate.metadata["sar_overlap_fraction"] >= 0.3
    assert candidate.confidence == pytest.approx(min(0.7, 0.55, 0.86))


def test_sar_only_regions_preserved():
    sar = _sar()
    fused = fuse_multimodal_evidence([], None, _sar_output(sar))
    assert len(fused) == 1
    assert fused[0].metadata["evidence_type"] == "sar_change"
    assert fused[0].metadata["sar_confidence"] == 0.86


def test_partial_overlap_below_threshold_ignored():
    semantic = _semantic()
    semantic = semantic.model_copy(
        update={
            "geometry": GeoJSONGeometry(type="Polygon", coordinates=[_square(78.0, 12.97)]),
            "metadata": {"claim_type": "construction_candidate", "parent_region_id": "change-region-01"},
        }
    )
    fused = fuse_multimodal_evidence([_cva()], _semantic_output(semantic), None)
    assert all(r.metadata.get("claim_type") != "construction_candidate" for r in fused)


def test_semantic_delta_gate():
    low_delta = _semantic(delta=0.05)
    fused = fuse_multimodal_evidence([_cva()], _semantic_output(low_delta), None)
    assert all(r.metadata.get("claim_type") != "construction_candidate" for r in fused)


def test_missing_semantic_is_not_zero_confidence():
    fused = fuse_multimodal_evidence([_cva()], None, None)
    assert fused[0].confidence == 0.7


def test_fusion_policy_version_recorded():
    fused = fuse_multimodal_evidence([_cva()], _semantic_output(_semantic()), _sar_output(_sar()))
    candidate = next(r for r in fused if r.metadata.get("claim_type") == "construction_candidate")
    assert candidate.metadata["fusion_policy"] == FUSION_POLICY_VERSION


def test_cva_area_km2_recorded():
    fused = fuse_multimodal_evidence([_cva()], None, None)
    area = fused[0].metadata["cva_area_km2"]
    assert area == polygon_area_km2(_square(77.59, 12.97))
