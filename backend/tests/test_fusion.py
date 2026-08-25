from __future__ import annotations

from datetime import date

import pytest

from app.evidence.fusion import annotate_cva_regions, compute_overlap_fraction, fuse_cva_and_semantic
from app.schemas.domain import (
    DataMode,
    EvidenceRegion,
    GeoJSONGeometry,
    Metric,
    SemanticAnalysisOutput,
    SemanticClaim,
)


def _region(
    region_id: str,
    source: str,
    coords: list[list[float]],
    confidence: float,
    *,
    claim_type: str | None = None,
    parent_id: str | None = None,
    delta: float = 0.18,
) -> EvidenceRegion:
    metadata = {}
    if claim_type:
        metadata["claim_type"] = claim_type
    if parent_id:
        metadata["parent_region_id"] = parent_id
    return EvidenceRegion(
        id=region_id,
        geometry=GeoJSONGeometry(type="Polygon", coordinates=[coords]),
        type="spectral_change" if claim_type is None else "semantic_evidence",
        confidence=confidence,
        metrics=[
            Metric(
                name="delta_built_probability",
                value=delta,
                unit="probability",
                source="development_semantic_analyzer",
            )
        ],
        source=source,
        metadata=metadata,
    )


CVA = _region(
    "change-region-01",
    "earth_engine_cva",
    [
        [77.59, 12.97],
        [77.61, 12.97],
        [77.61, 12.99],
        [77.59, 12.99],
        [77.59, 12.97],
    ],
    0.7,
)

SEMANTIC_INSIDE = _region(
    "semantic-candidate-01",
    "development_semantic_analyzer",
    [
        [77.595, 12.975],
        [77.605, 12.975],
        [77.605, 12.985],
        [77.595, 12.985],
        [77.595, 12.975],
    ],
    0.55,
    claim_type="construction_candidate",
    parent_id="change-region-01",
)

SEMANTIC_OUTSIDE = _region(
    "semantic-candidate-02",
    "development_semantic_analyzer",
    [
        [78.0, 12.97],
        [78.01, 12.97],
        [78.01, 12.98],
        [78.0, 12.98],
        [78.0, 12.97],
    ],
    0.55,
    claim_type="construction_candidate",
    parent_id="change-region-01",
)


def test_cva_only_regions_marked_spectral_change():
    annotated = annotate_cva_regions([CVA])
    assert annotated[0].metadata["claim_type"] == "none"
    assert annotated[0].source == "earth_engine_cva"


def test_fusion_requires_cva_overlap():
    semantic = SemanticAnalysisOutput(
        regions=[SEMANTIC_OUTSIDE],
        claims=[],
        analyzer="development_semantic_analyzer",
        mode=DataMode.DEVELOPMENT,
    )
    fused = fuse_cva_and_semantic([CVA], semantic)
    claim_types = [r.metadata.get("claim_type") for r in fused]
    assert claim_types.count("none") == 1
    assert "construction_candidate" not in claim_types


def test_fusion_adds_construction_candidate_with_overlap():
    semantic = SemanticAnalysisOutput(
        regions=[SEMANTIC_INSIDE],
        claims=[
            SemanticClaim(
                claim_type="construction_candidate",
                region_id=SEMANTIC_INSIDE.id,
                confidence=0.55,
            )
        ],
        analyzer="development_semantic_analyzer",
        mode=DataMode.DEVELOPMENT,
    )
    fused = fuse_cva_and_semantic([CVA], semantic)
    candidates = [r for r in fused if r.metadata.get("claim_type") == "construction_candidate"]
    assert len(candidates) == 1
    assert candidates[0].metadata["parent_region_id"] == "change-region-01"
    assert candidates[0].metadata["provenance_chain"] == ["earth_engine_cva", "development_semantic_analyzer"]


def test_fusion_confidence_is_min_of_cva_and_semantic():
    semantic = SemanticAnalysisOutput(
        regions=[SEMANTIC_INSIDE],
        claims=[],
        analyzer="development_semantic_analyzer",
        mode=DataMode.DEVELOPMENT,
    )
    fused = fuse_cva_and_semantic([CVA], semantic)
    candidate = next(r for r in fused if r.metadata.get("claim_type") == "construction_candidate")
    assert candidate.confidence == pytest.approx(0.55)


def test_overlap_fraction_is_deterministic():
    overlap = compute_overlap_fraction(CVA, SEMANTIC_INSIDE)
    assert 0 < overlap <= 1.0
