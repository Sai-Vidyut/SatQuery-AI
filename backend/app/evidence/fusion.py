from __future__ import annotations

from typing import Any

from app.evidence.geometry import overlap_fraction_of_child
from app.schemas.domain import EvidenceRegion, SemanticAnalysisOutput

SEMANTIC_POLICY_VERSION = "1.0.0"
DEFAULT_MIN_OVERLAP_FRACTION = 0.30
DEFAULT_MIN_SEMANTIC_DELTA = 0.15  # dynamic_world_built_construction_v1


def compute_overlap_fraction(parent: EvidenceRegion, child: EvidenceRegion) -> float:
    """Fraction of the child region area that intersects the parent polygon."""
    return overlap_fraction_of_child(parent.geometry.coordinates[0], child.geometry.coordinates[0])


def annotate_cva_regions(regions: list[EvidenceRegion]) -> list[EvidenceRegion]:
    """Mark change regions as evidence without semantic claims."""
    annotated: list[EvidenceRegion] = []
    for region in regions:
        metadata = dict(region.metadata)
        metadata.setdefault("claim_type", "none")
        if region.type == "sar_change" or region.source == "earth_engine_sar":
            metadata.setdefault("evidence_modality", "sar")
            metadata.setdefault("provenance_chain", ["earth_engine_sar"])
        else:
            metadata.setdefault("provenance_chain", [region.source])
            metadata.setdefault("semantic_policy", SEMANTIC_POLICY_VERSION)
        annotated.append(region.model_copy(update={"metadata": metadata}))
    return annotated


def _semantic_delta_passes(region: EvidenceRegion, min_delta: float) -> bool:
    for metric in region.metrics:
        if metric.name == "delta_built_probability":
            return float(metric.value) >= min_delta
    return True


def fuse_cva_and_semantic(
    cva_regions: list[EvidenceRegion],
    semantic: SemanticAnalysisOutput | None,
    *,
    min_overlap_fraction: float = DEFAULT_MIN_OVERLAP_FRACTION,
    min_semantic_delta: float = DEFAULT_MIN_SEMANTIC_DELTA,
) -> list[EvidenceRegion]:
    """
    Fuse CVA and semantic evidence deterministically.
    CVA regions are preserved; supported construction candidates are added.
    """
    fused: list[EvidenceRegion] = list(annotate_cva_regions(cva_regions))
    if semantic is None or not semantic.regions:
        return fused

    parent_by_id = {region.id: region for region in cva_regions}

    for semantic_region in semantic.regions:
        parent_id = semantic_region.metadata.get("parent_region_id")
        parent = parent_by_id.get(parent_id) if parent_id else None
        if parent is None:
            continue

        overlap = compute_overlap_fraction(parent, semantic_region)
        if overlap < min_overlap_fraction:
            continue
        if not _semantic_delta_passes(semantic_region, min_semantic_delta):
            continue

        claim_type = semantic_region.metadata.get("claim_type", "construction_candidate")
        fused_confidence = round(min(parent.confidence, semantic_region.confidence), 3)
        metadata: dict[str, Any] = {
            **semantic_region.metadata,
            "claim_type": claim_type,
            "provenance_chain": [parent.source, semantic.analyzer],
            "parent_region_id": parent.id,
            "semantic_policy": SEMANTIC_POLICY_VERSION,
            "overlap_fraction": overlap,
        }
        fused.append(
            semantic_region.model_copy(
                update={
                    "confidence": fused_confidence,
                    "metadata": metadata,
                }
            )
        )

    return fused
