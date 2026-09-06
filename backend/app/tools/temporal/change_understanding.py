"""Query-aware change interpretation for uploaded bi-temporal pairs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.evidence.bi_temporal_interpretation import (
    CONFIDENCE_KIND,
    compact_detector_provenance,
    extract_detector_summary,
    extract_image_provenance,
    extract_scene_metrics,
    format_primary_index,
    humanize_direction_hint,
    region_area_total_m2,
)
from app.schemas.bi_temporal_change import (
    BiTemporalChangeProviderKind,
    BiTemporalChangeResult,
    BiTemporalChangeTask,
    ChangeUnderstandingOutput,
)
from app.schemas.change_understanding import ChangeUnderstandingToolInput
from app.schemas.domain import EvidenceRegion


def _compose_uploaded_summary(
    *,
    query: str,
    regions: list[EvidenceRegion],
    detector_metadata: dict[str, Any],
    earlier_date,
    later_date,
) -> str:
    period = f"{earlier_date.isoformat()} to {later_date.isoformat()}"
    scene = extract_scene_metrics(detector_metadata)
    primary_index = detector_metadata.get("primary_index")
    direction_hint = detector_metadata.get("change_direction_hint")
    index_label = format_primary_index(primary_index)

    if scene and scene.area_ha is not None and scene.area_ha > 0:
        area_clause = f"Detected approximately {scene.area_ha:g} ha of spectral change"
        if scene.changed_percentage is not None:
            area_clause += f", covering {scene.changed_percentage:g}% of the analyzed area"
        area_clause += "."
    elif scene and scene.area_m2 is not None and scene.area_m2 > 0:
        area_clause = f"Detected approximately {scene.area_m2:,.0f} m² of spectral change."
    else:
        area_total = region_area_total_m2(regions)
        area_clause = (
            f"Detected approximately {area_total:,.0f} m² of spectral change."
            if area_total > 0
            else "No significant spectral change regions were detected."
        )

    if not regions and (not scene or not scene.area_ha):
        return (
            f"No significant spectral change regions were detected between {period}. "
            "This does not prove that no change occurred — only that none met detector thresholds."
        )

    signal_clause = f"The primary signal was {index_label}."
    hint_clause = ""
    if direction_hint and direction_hint != "no_change":
        hint_clause = (
            f" The direction hint is consistent with {humanize_direction_hint(direction_hint)} "
            "(heuristic only, not a confirmed event)."
        )

    region_clause = (
        f" {len(regions)} mapped change region{'s' if len(regions) != 1 else ''} "
        f"{'were' if len(regions) != 1 else 'was'} identified between {period}."
        if regions
        else f" Analysis period: {period}."
    )

    q = query.strip().lower()
    if "where" in q and regions:
        ids = ", ".join(r.id for r in regions[:5])
        suffix = "…" if len(regions) > 5 else ""
        region_clause = (
            f" Mapped region IDs: {ids}{suffix} between {period}."
        )

    return f"{area_clause}{signal_clause}{hint_clause}{region_clause}".strip()


def _compose_deterministic_summary(
    query: str,
    regions: list[EvidenceRegion],
    *,
    earlier_date,
    later_date,
) -> str:
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

    area_total = region_area_total_m2(regions)
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

        detector_metadata = payload.detections.detector_metadata or {}
        is_uploaded = payload.detections.detector == "uploaded_bi_temporal"

        if is_uploaded:
            summary = _compose_uploaded_summary(
                query=payload.query,
                regions=regions,
                detector_metadata=detector_metadata,
                earlier_date=earlier_dt.date(),
                later_date=later_dt.date(),
            )
        else:
            summary = _compose_deterministic_summary(
                payload.query,
                regions,
                earlier_date=earlier_dt.date(),
                later_date=later_dt.date(),
            )

        histogram_confidence = detector_metadata.get("histogram_confidence")
        if histogram_confidence is None and regions:
            histogram_confidence = sum(r.confidence for r in regions) / len(regions)
        if histogram_confidence is not None:
            histogram_confidence = round(float(histogram_confidence), 3)

        scene_metrics = extract_scene_metrics(detector_metadata) if is_uploaded else None
        if scene_metrics and scene_metrics.region_count is None:
            scene_metrics = scene_metrics.model_copy(update={"region_count": len(regions)})

        detector_summary = extract_detector_summary(
            payload.detections.detector,
            detector_metadata,
            histogram_confidence=histogram_confidence,
        )
        if is_uploaded:
            image_provenance = extract_image_provenance(
                detector_metadata, payload.earlier, payload.later
            )
        else:
            from app.schemas.bi_temporal_change import BiTemporalImageProvenance

            image_provenance = BiTemporalImageProvenance(
                earlier_source_ref=f"upload://{payload.earlier.id}",
                later_source_ref=f"upload://{payload.later.id}",
                earlier_filename=payload.earlier.filename,
                later_filename=payload.later.filename,
                earlier_modality=payload.earlier.modality.value,
                later_modality=payload.later.modality.value,
                earlier_band_names=payload.earlier.band_names,
                later_band_names=payload.later.band_names,
                crs=payload.earlier.crs,
            )

        result = BiTemporalChangeResult(
            task=BiTemporalChangeTask.BI_TEMPORAL_CHANGE_VQA,
            change_summary=summary,
            question=payload.query,
            changed_region_count=len(regions),
            change_map_available=len(regions) > 0,
            detector=payload.detections.detector,
            provider=(
                BiTemporalChangeProviderKind.UPLOADED_CVA
                if is_uploaded
                else BiTemporalChangeProviderKind.DEVELOPMENT
            ),
            provenance=(
                f"{payload.detections.detector} on uploaded bi-temporal pair "
                f"({payload.earlier.id} → {payload.later.id})"
            ),
            confidence=histogram_confidence,
            confidence_available=histogram_confidence is not None and len(regions) > 0,
            confidence_kind=CONFIDENCE_KIND if histogram_confidence is not None else None,
            earlier_image_id=payload.earlier.id,
            later_image_id=payload.later.id,
            earlier_acquisition=earlier_dt,
            later_acquisition=later_dt,
            earlier_date=earlier_dt.date(),
            later_date=later_dt.date(),
            scene_metrics=scene_metrics,
            detector_summary=detector_summary,
            image_provenance=image_provenance,
            inference_metadata={
                "detector_metadata": compact_detector_provenance(detector_metadata),
                "pipeline_stages": detector_metadata.get("pipeline_stages"),
                "raw_detection_count": payload.detections.raw_detection_count,
                "interpreted_at": datetime.now(UTC).isoformat(),
            },
        )
        return ChangeUnderstandingOutput(result=result)
