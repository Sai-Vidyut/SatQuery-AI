from __future__ import annotations

from typing import Any

from app.evidence.fusion import DEFAULT_MIN_SEMANTIC_DELTA, SEMANTIC_POLICY_VERSION
from app.evidence.geometry import overlap_fraction_of_child, polygon_area_km2
from app.schemas.domain import ChangeDetectionOutput, EvidenceRegion, Metric, SemanticAnalysisOutput

FUSION_POLICY_VERSION = "1.0.0"
MIN_SAR_OVERLAP_FRACTION = 0.30
MIN_SEMANTIC_OVERLAP_FRACTION = 0.30

PROVENANCE_CVA = "earth_engine_cva_v1.1"
PROVENANCE_SEMANTIC = "dynamic_world_built_v1"
PROVENANCE_SAR = "sentinel1_sar_v1.1"


def _ring(region: EvidenceRegion) -> list[list[float]]:
    return region.geometry.coordinates[0]


def _metric_value(region: EvidenceRegion, name: str) -> float | str | None:
    for metric in region.metrics:
        if metric.name == name:
            return metric.value
    return None


def _semantic_delta_passes(region: EvidenceRegion, min_delta: float = DEFAULT_MIN_SEMANTIC_DELTA) -> bool:
    for metric in region.metrics:
        if metric.name == "delta_built_probability":
            return float(metric.value) >= min_delta
    return True


def _fused_confidence(*confidences: float | None) -> float:
    """Conservative fusion: minimum of available modality confidences."""
    available = [c for c in confidences if c is not None]
    if not available:
        return 0.0
    return round(min(available), 3)


def _annotate_cva(cva: EvidenceRegion) -> EvidenceRegion:
    metadata = dict(cva.metadata)
    metadata.setdefault("claim_type", "none")
    metadata.setdefault("evidence_type", "spectral_change")
    metadata.setdefault("evidence_modality", "optical")
    metadata.setdefault("provenance_chain", [PROVENANCE_CVA])
    metadata.setdefault("cva_area_km2", polygon_area_km2(_ring(cva)))
    return cva.model_copy(update={"metadata": metadata})


def _annotate_sar_only(sar: EvidenceRegion) -> EvidenceRegion:
    metadata = dict(sar.metadata)
    metadata["claim_type"] = "none"
    metadata["evidence_type"] = "sar_change"
    metadata["evidence_modality"] = "sar"
    metadata["provenance_chain"] = [PROVENANCE_SAR]
    metadata.setdefault("sar_confidence", sar.confidence)
    return sar.model_copy(update={"metadata": metadata, "type": "sar_change"})


def _best_semantic_for_cva(
    cva: EvidenceRegion,
    semantic_regions: list[EvidenceRegion],
    *,
    min_overlap: float,
) -> tuple[EvidenceRegion | None, float]:
    parent_ring = _ring(cva)
    best: EvidenceRegion | None = None
    best_overlap = 0.0
    for region in semantic_regions:
        parent_id = region.metadata.get("parent_region_id")
        if parent_id and parent_id != cva.id:
            continue
        overlap = overlap_fraction_of_child(parent_ring, _ring(region))
        if overlap >= min_overlap and overlap > best_overlap:
            if _semantic_delta_passes(region):
                best = region
                best_overlap = overlap
    return best, best_overlap


def _best_sar_for_cva(
    cva: EvidenceRegion,
    sar_regions: list[EvidenceRegion],
    *,
    min_overlap: float,
) -> tuple[EvidenceRegion | None, float]:
    parent_ring = _ring(cva)
    best: EvidenceRegion | None = None
    best_overlap = 0.0
    for sar in sar_regions:
        overlap = overlap_fraction_of_child(parent_ring, _ring(sar))
        if overlap >= min_overlap and overlap > best_overlap:
            best = sar
            best_overlap = overlap
    return best, best_overlap


def _build_construction_candidate(
    cva: EvidenceRegion,
    semantic: EvidenceRegion,
    *,
    semantic_overlap: float,
    sar: EvidenceRegion | None = None,
    sar_overlap: float | None = None,
    semantic_analyzer: str,
) -> EvidenceRegion:
    modalities = ["optical", "semantic"]
    provenance = [PROVENANCE_CVA, PROVENANCE_SEMANTIC]
    evidence_modality = "optical+semantic"
    if sar is not None and sar_overlap is not None:
        modalities.append("sar")
        provenance.append(PROVENANCE_SAR)
        evidence_modality = "optical+semantic+sar"

    metadata: dict[str, Any] = {
        **semantic.metadata,
        "claim_type": "construction_candidate",
        "evidence_type": "construction_candidate",
        "evidence_modality": evidence_modality,
        "provenance_chain": provenance,
        "parent_region_id": cva.id,
        "semantic_region_id": semantic.id,
        "semantic_policy": SEMANTIC_POLICY_VERSION,
        "fusion_policy": FUSION_POLICY_VERSION,
        "cva_area_km2": polygon_area_km2(_ring(cva)),
        "semantic_overlap_fraction": semantic_overlap,
        "cva_confidence": cva.confidence,
        "semantic_confidence": semantic.confidence,
    }
    if sar is not None:
        metadata["sar_region_id"] = sar.id
        metadata["sar_overlap_fraction"] = sar_overlap
        metadata["sar_confidence"] = sar.confidence
        metadata["sar_polarization"] = _metric_value(sar, "polarization")
        metadata["before_scene_id"] = metadata.get("before_scene_id") or sar.metadata.get("before_scene_id")
        metadata["after_scene_id"] = metadata.get("after_scene_id") or sar.metadata.get("after_scene_id")

    confidences = [cva.confidence, semantic.confidence]
    if sar is not None:
        confidences.append(sar.confidence)

    return semantic.model_copy(
        update={
            "confidence": _fused_confidence(*confidences),
            "metadata": metadata,
        }
    )


def _build_multimodal_change(
    cva: EvidenceRegion,
    sar: EvidenceRegion,
    *,
    sar_overlap: float,
) -> EvidenceRegion:
    metadata: dict[str, Any] = {
        "claim_type": "none",
        "evidence_type": "multimodal_change",
        "evidence_modality": "optical+sar",
        "provenance_chain": [PROVENANCE_CVA, PROVENANCE_SAR],
        "parent_region_id": cva.id,
        "sar_region_id": sar.id,
        "fusion_policy": FUSION_POLICY_VERSION,
        "cva_area_km2": polygon_area_km2(_ring(cva)),
        "sar_overlap_fraction": sar_overlap,
        "cva_confidence": cva.confidence,
        "sar_confidence": sar.confidence,
        "fused_confidence": _fused_confidence(cva.confidence, sar.confidence),
        "sar_polarization": _metric_value(sar, "polarization"),
        "before_scene_id": sar.metadata.get("before_scene_id"),
        "after_scene_id": sar.metadata.get("after_scene_id"),
    }
    return EvidenceRegion(
        id=f"fused-multimodal-{cva.id}-{sar.id}",
        geometry=cva.geometry,
        type="fused_evidence",
        confidence=metadata["fused_confidence"],
        metrics=[
            Metric(name="cva_area_km2", value=metadata["cva_area_km2"], unit="km²", source="evidence_fusion"),
            Metric(name="sar_overlap_fraction", value=sar_overlap, unit="ratio", source="evidence_fusion"),
            Metric(
                name="mean_sar_change_magnitude",
                value=_metric_value(sar, "mean_sar_change_magnitude") or 0,
                unit="db",
                source=PROVENANCE_SAR,
            ),
        ],
        source="evidence_fusion",
        metadata=metadata,
    )


def fuse_multimodal_evidence(
    cva_regions: list[EvidenceRegion],
    semantic: SemanticAnalysisOutput | None = None,
    sar_detections: ChangeDetectionOutput | None = None,
    *,
    min_semantic_overlap: float = MIN_SEMANTIC_OVERLAP_FRACTION,
    min_sar_overlap: float = MIN_SAR_OVERLAP_FRACTION,
) -> list[EvidenceRegion]:
    """
    Deterministic multimodal evidence fusion (policy v1.0.0).
    Never upgrades claims beyond supporting evidence.
    """
    semantic_regions = semantic.regions if semantic is not None else []
    sar_regions = sar_detections.regions if sar_detections is not None else []
    semantic_analyzer = semantic.analyzer if semantic is not None else PROVENANCE_SEMANTIC

    fused: list[EvidenceRegion] = []
    matched_sar_ids: set[str] = set()
    emitted_semantic_ids: set[str] = set()

    for cva in cva_regions:
        fused.append(_annotate_cva(cva))
        semantic_match, semantic_overlap = _best_semantic_for_cva(
            cva, semantic_regions, min_overlap=min_semantic_overlap
        )
        sar_match, sar_overlap = _best_sar_for_cva(cva, sar_regions, min_overlap=min_sar_overlap)

        if semantic_match is not None:
            candidate = _build_construction_candidate(
                cva,
                semantic_match,
                semantic_overlap=semantic_overlap,
                sar=sar_match,
                sar_overlap=sar_overlap if sar_match else None,
                semantic_analyzer=semantic_analyzer,
            )
            fused.append(candidate)
            emitted_semantic_ids.add(semantic_match.id)
            if sar_match is not None:
                matched_sar_ids.add(sar_match.id)
        elif sar_match is not None:
            fused.append(_build_multimodal_change(cva, sar_match, sar_overlap=sar_overlap))
            matched_sar_ids.add(sar_match.id)

    for sar in sar_regions:
        if sar.id not in matched_sar_ids:
            fused.append(_annotate_sar_only(sar))

    return fused
