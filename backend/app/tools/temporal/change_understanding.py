"""Query-aware change interpretation for uploaded bi-temporal pairs."""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.bi_temporal_change import (
    BiTemporalChangeProviderKind,
    BiTemporalChangeResult,
    BiTemporalChangeTask,
    ChangeUnderstandingOutput,
)
from app.schemas.change_understanding import ChangeUnderstandingToolInput
from app.schemas.domain import EvidenceRegion


def _region_areas(regions: list[EvidenceRegion]) -> float:
    total = 0.0
    for region in regions:
        for metric in region.metrics:
            if metric.name == "estimated_area":
                total += float(metric.value)
    return total


def _compose_summary(query: str, regions: list[EvidenceRegion], *, earlier_date, later_date) -> str:
    q = query.strip().lower()
    count = len(regions)
    period = f"{earlier_date.isoformat()} to {later_date.isoformat()}"

    if count == 0:
        if "built-up" in q or "built up" in q:
            return (
                f"No detectable built-up area change was found between {period}. "
                "Built-up extent appears unchanged within detector sensitivity."
            )
        if "vegetation" in q:
            return (
                f"No vegetation-loss regions were detected between {period} "
                "in the uploaded pair overlap."
            )
        return f"No significant spectral change regions were detected between {period}."

    area_total = _region_areas(regions)
    area_clause = f" Combined estimated changed area ≈ {area_total:,.0f} m²." if area_total else ""

    if "built-up" in q or "built up" in q:
        built_regions = [r for r in regions if "construction" in r.type or "built" in r.type]
        if built_regions:
            return (
                f"Built-up change signal detected in {len(built_regions)} region"
                f"{'s' if len(built_regions) != 1 else ''} between {period}.{area_clause} "
                "Review mapped evidence regions for spatial detail."
            )
        return (
            f"No built-up expansion detected between {period}; "
            f"{count} other change region{'s' if count != 1 else ''} were found.{area_clause}"
        )

    if "vegetation" in q:
        return (
            f"Potential vegetation-related change appears in {count} region"
            f"{'s' if count != 1 else ''} between {period}.{area_clause} "
            "See mapped change regions for locations."
        )

    if "where" in q:
        ids = ", ".join(r.id for r in regions[:5])
        suffix = "…" if count > 5 else ""
        return (
            f"Detected {count} change region{'s' if count != 1 else ''} between {period} "
            f"at: {ids}{suffix}.{area_clause}"
        )

    return (
        f"Detected {count} significant change region{'s' if count != 1 else ''} "
        f"between {period} for query \"{query.strip()}\".{area_clause}"
    )


class ChangeUnderstandingTool:
    name = "change_understanding"
    description = "Interpret uploaded bi-temporal CVA output relative to the user question."

    async def execute(self, payload: ChangeUnderstandingToolInput) -> ChangeUnderstandingOutput:
        regions = payload.detections.regions
        earlier_dt = payload.earlier.acquisition_datetime
        later_dt = payload.later.acquisition_datetime
        if not earlier_dt or not later_dt:
            raise ValueError("Both images must include acquisition_datetime.")

        summary = _compose_summary(
            payload.query,
            regions,
            earlier_date=earlier_dt.date(),
            later_date=later_dt.date(),
        )
        avg_conf = sum(r.confidence for r in regions) / len(regions) if regions else None
        result = BiTemporalChangeResult(
            task=BiTemporalChangeTask.BI_TEMPORAL_CHANGE_VQA,
            change_summary=summary,
            question=payload.query,
            changed_region_count=len(regions),
            change_map_available=len(regions) > 0,
            detector=payload.detections.detector,
            provider=BiTemporalChangeProviderKind.DEVELOPMENT,
            provenance=(
                f"{payload.detections.detector} on uploaded bi-temporal pair "
                f"({payload.earlier.id} → {payload.later.id})"
            ),
            confidence=round(avg_conf, 3) if avg_conf is not None else None,
            confidence_available=avg_conf is not None and len(regions) > 0,
            earlier_image_id=payload.earlier.id,
            later_image_id=payload.later.id,
            earlier_acquisition=earlier_dt,
            later_acquisition=later_dt,
            earlier_date=earlier_dt.date(),
            later_date=later_dt.date(),
            inference_metadata={
                "detector_metadata": payload.detections.detector_metadata,
                "raw_detection_count": payload.detections.raw_detection_count,
                "interpreted_at": datetime.now(UTC).isoformat(),
            },
        )
        return ChangeUnderstandingOutput(result=result)
