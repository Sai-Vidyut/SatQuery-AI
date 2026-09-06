from __future__ import annotations

from app.schemas.domain import (
    GenerateEvidenceInput,
    GenerateEvidenceOutput,
    Metric,
)
from app.tools.registry import Tool


class GenerateEvidenceTool(Tool[GenerateEvidenceInput, GenerateEvidenceOutput]):
    name = "generate_evidence"
    description = "Validate fused evidence and produce aggregate metrics with provenance."
    input_model = GenerateEvidenceInput
    output_model = GenerateEvidenceOutput

    async def execute(self, payload: GenerateEvidenceInput) -> GenerateEvidenceOutput:
        regions = payload.fused_regions
        if not regions:
            return GenerateEvidenceOutput(regions=[], metrics=[], confidence=0.0)

        avg_conf = sum(r.confidence for r in regions) / len(regions)
        metrics = [
            Metric(
                name="region_count",
                value=len(regions),
                unit="regions",
                source="evidence_engine",
            ),
            Metric(
                name="mean_confidence",
                value=round(avg_conf, 3),
                unit="ratio",
                source="evidence_engine",
            ),
            Metric(
                name="imagery_mode",
                value=payload.imagery.mode.value,
                unit=None,
                source=payload.imagery.source,
            ),
            Metric(
                name="construction_candidate_count",
                value=sum(
                    1
                    for r in regions
                    if r.metadata.get("claim_type") in ("construction_candidate", "new_built_area")
                ),
                unit="regions",
                source="evidence_engine",
            ),
            Metric(
                name="multimodal_change_count",
                value=sum(1 for r in regions if r.metadata.get("evidence_type") == "multimodal_change"),
                unit="regions",
                source="evidence_engine",
            ),
            Metric(
                name="sar_only_count",
                value=sum(
                    1
                    for r in regions
                    if r.metadata.get("evidence_type") == "sar_change"
                    and r.metadata.get("evidence_modality") == "sar"
                ),
                unit="regions",
                source="evidence_engine",
            ),
        ]
        fusion_policy = payload.fusion_metadata.get("fusion_policy")
        if fusion_policy:
            metrics.append(
                Metric(
                    name="fusion_policy",
                    value=fusion_policy,
                    unit=None,
                    source="evidence_fusion",
                )
            )

        detector_metadata = payload.fusion_metadata.get("detector_metadata")
        if isinstance(detector_metadata, dict) and detector_metadata:
            from app.evidence.bi_temporal_interpretation import metrics_from_detector_metadata

            source = payload.fusion_metadata.get("source") or "uploaded_bi_temporal_cva"
            existing_names = {metric.name for metric in metrics}
            for metric in metrics_from_detector_metadata(detector_metadata, source=str(source)):
                if metric.name not in existing_names:
                    metrics.append(metric)
                    existing_names.add(metric.name)

        return GenerateEvidenceOutput(
            regions=regions,
            metrics=metrics,
            confidence=round(avg_conf, 3),
        )
