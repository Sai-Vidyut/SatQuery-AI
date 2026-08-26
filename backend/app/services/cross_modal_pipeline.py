"""Assemble cross-modal result and metrics."""

from __future__ import annotations

from app.schemas.cross_modal import (
    CoRegistrationStatus,
    CrossModalFusionSummary,
    CrossModalOpticalSARResult,
    CrossModalProviderKind,
    CrossModalTask,
    ModalityAnalysisSummary,
)
from app.schemas.domain import Metric, QueryRequest


def build_cross_modal_result(
    request: QueryRequest,
    *,
    optical: ModalityAnalysisSummary,
    sar: ModalityAnalysisSummary,
    fused: CrossModalFusionSummary,
    co_registration_status: CoRegistrationStatus,
    co_registration_provenance: str,
    optical_image_id: str,
    sar_image_id: str,
    fused_regions_count: int,
) -> CrossModalOpticalSARResult:
    notes = " ".join(fused.complementary_notes[:3])
    answer = (
        f"{fused.summary} Optical: {optical.summary} SAR: {sar.summary} "
        f"Joint notes: {notes}".strip()
    )
    return CrossModalOpticalSARResult(
        task=CrossModalTask.CROSS_MODAL_OPTICAL_SAR,
        answer=answer,
        question=request.query,
        optical_analysis=optical,
        sar_analysis=sar,
        fused_analysis=fused,
        co_registration_status=co_registration_status,
        co_registration_provenance=co_registration_provenance,
        optical_image_id=optical_image_id,
        sar_image_id=sar_image_id,
        provider=CrossModalProviderKind.DEVELOPMENT,
        provenance="Development uploaded cross-modal optical+SAR pipeline",
        confidence=None,
        confidence_available=False,
        inference_metadata={"fused_region_count": fused_regions_count},
    )


def build_cross_modal_metrics(result: CrossModalOpticalSARResult) -> list[Metric]:
    return [
        Metric(name="cross_modal_provider", value=result.provider.value, source="cross_modal_fusion"),
        Metric(name="optical_analyzer", value=result.optical_analysis.analyzer, source="optical_analysis"),
        Metric(name="sar_analyzer", value=result.sar_analysis.analyzer, source="sar_analysis"),
        Metric(
            name="co_registration_status",
            value=result.co_registration_status.value,
            source="input_validation",
        ),
        Metric(
            name="fused_region_count",
            value=result.fused_analysis.fused_region_count,
            source="cross_modal_fusion",
        ),
    ]
