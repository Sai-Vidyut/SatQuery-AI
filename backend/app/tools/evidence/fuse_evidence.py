from __future__ import annotations

from app.evidence.multimodal_fusion import FUSION_POLICY_VERSION, fuse_multimodal_evidence
from app.schemas.domain import FuseEvidenceInput, FuseEvidenceOutput
from app.tools.registry import Tool


class FuseEvidenceTool(Tool[FuseEvidenceInput, FuseEvidenceOutput]):
    name = "fuse_evidence"
    description = "Fuse optical CVA, semantic, and SAR evidence deterministically."
    input_model = FuseEvidenceInput
    output_model = FuseEvidenceOutput

    async def execute(self, payload: FuseEvidenceInput) -> FuseEvidenceOutput:
        regions = fuse_multimodal_evidence(
            payload.cva_detections.regions,
            payload.semantic,
            payload.sar_detections,
        )
        return FuseEvidenceOutput(
            regions=regions,
            fusion_metadata={
                "fusion_policy": FUSION_POLICY_VERSION,
                "cva_region_count": len(payload.cva_detections.regions),
                "semantic_region_count": len(payload.semantic.regions) if payload.semantic else 0,
                "sar_region_count": len(payload.sar_detections.regions) if payload.sar_detections else 0,
                "fused_region_count": len(regions),
                "detector_metadata": payload.cva_detections.detector_metadata or {},
                "confidence_kind": (
                    (payload.cva_detections.detector_metadata or {}).get("confidence_kind")
                    or "histogram_separability"
                ),
            },
        )
