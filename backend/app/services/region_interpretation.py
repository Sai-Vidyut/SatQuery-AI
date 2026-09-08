"""Evidence-grounded GeoChat interpretation for selected bi-temporal change regions."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from time import perf_counter

from PIL import Image, ImageDraw, ImageFont

from app.adapters.change.bi_temporal.validator import resolve_upload_path
from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
from app.adapters.rsvlm.factory import get_geochat_vlm
from app.core.errors import SatQueryError
from app.evidence.bi_temporal_interpretation import (
    CONFIDENCE_KIND,
    format_primary_index,
    humanize_direction_hint,
)
from app.schemas.domain import AnalysisResult, EvidenceRegion, TraceStatus, TraceStep
from app.schemas.region_interpretation import BiTemporalRegionInterpretationResult
from app.schemas.vqa import GeoChatVQAParameters, VQAProviderKind
from app.services.imagery_preview import render_raster_preview_png
from app.services.session_store import SessionStore, session_store
from app.storage.factory import get_image_storage

EVIDENCE_INPUTS = "before_after_composite_crop"
LABEL_HEIGHT = 28


def padded_bbox_from_geometry(geometry: dict, padding_ratio: float = 0.25) -> tuple[float, float, float, float]:
    ring = geometry["coordinates"][0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    pad_lon = max((max_lon - min_lon) * padding_ratio, 0.00005)
    pad_lat = max((max_lat - min_lat) * padding_ratio, 0.00005)
    return (min_lon - pad_lon, min_lat - pad_lat, max_lon + pad_lon, max_lat + pad_lat)


def format_preview_bbox(bbox: tuple[float, float, float, float]) -> str:
    return ",".join(f"{value:.6f}" for value in bbox)


def _region_area_clause(region: EvidenceRegion) -> str | None:
    for metric in region.metrics:
        if metric.name in {"estimated_area", "area_m2"}:
            unit = metric.unit or "m²"
            return f"{metric.name}: {metric.value} {unit}".strip()
    return None


def build_evidence_prompt(
    *,
    region: EvidenceRegion,
    result: AnalysisResult,
    question: str,
) -> str:
    bt = result.bi_temporal_change
    if bt is None:
        raise SatQueryError(
            "not_bi_temporal_session",
            "Region interpretation requires a bi-temporal analysis session.",
            status_code=422,
        )

    detector_summary = bt.detector_summary
    primary_index = (
        detector_summary.primary_index if detector_summary and detector_summary.primary_index else None
    )
    direction_hint = (
        region.metadata.get("change_direction_hint")
        or (detector_summary.change_direction_hint if detector_summary else None)
    )
    confidence_kind = (
        region.metadata.get("confidence_kind")
        or bt.confidence_kind
        or CONFIDENCE_KIND
    )
    modality = region.metadata.get("evidence_modality") or "optical"
    area_clause = _region_area_clause(region)

    guard = (
        "A change detection system has ALREADY identified this region.\n"
        "Do NOT decide whether change exists.\n"
        "Do NOT invent new regions, bounding boxes, or confidence scores.\n"
        "LEFT panel = BEFORE. RIGHT panel = AFTER.\n"
        "Describe visible differences consistent with the provided detector context.\n"
        "If unclear, say so."
    )
    context_lines = [
        f"Region ID: {region.id}",
        f"Acquisition dates: {bt.earlier_date.isoformat()} to {bt.later_date.isoformat()}",
        f"Detector: {bt.detector}",
        f"Primary index: {format_primary_index(primary_index)}",
        f"Direction hint: {humanize_direction_hint(str(direction_hint) if direction_hint else None)} (heuristic only, not a confirmed event)",
        f"Separability: {region.confidence:.0%} ({confidence_kind} — not event probability)",
        f"Modality: {modality}",
    ]
    if area_clause:
        context_lines.append(area_clause)

    return (
        f"{guard}\n\n"
        "Context:\n"
        + "\n".join(context_lines)
        + f"\n\nUser question: {question.strip()}"
    )


def render_before_after_composite(
    earlier_path,
    later_path,
    *,
    bbox_wgs84: tuple[float, float, float, float],
    max_size: int = 512,
) -> bytes:
    before_png = render_raster_preview_png(earlier_path, bbox_wgs84=bbox_wgs84, max_size=max_size)
    after_png = render_raster_preview_png(later_path, bbox_wgs84=bbox_wgs84, max_size=max_size)
    before_img = Image.open(io.BytesIO(before_png)).convert("RGB")
    after_img = Image.open(io.BytesIO(after_png)).convert("RGB")

    panel_h = max(before_img.height, after_img.height)
    panel_w = before_img.width + after_img.width
    canvas = Image.new("RGB", (panel_w, panel_h + LABEL_HEIGHT), color=(16, 20, 26))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.text((8, 6), "BEFORE", fill=(220, 230, 240), font=font)
    draw.text((before_img.width + 8, 6), "AFTER", fill=(220, 230, 240), font=font)
    canvas.paste(before_img, (0, LABEL_HEIGHT))
    canvas.paste(after_img, (before_img.width, LABEL_HEIGHT))

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def _find_region(result: AnalysisResult, region_id: str) -> EvidenceRegion:
    for region in result.evidence:
        if region.id == region_id:
            return region
    raise SatQueryError(
        "region_not_found",
        f"No evidence region {region_id!r} in this session.",
        status_code=404,
        field="region_id",
    )


class RegionInterpretationService:
    def __init__(self, store: SessionStore | None = None) -> None:
        self._store = store or session_store

    async def interpret_region(
        self,
        session_id: str,
        region_id: str,
        question: str,
    ) -> tuple[BiTemporalRegionInterpretationResult, TraceStep]:
        session = self._store.get(session_id)
        if not session or not session.result:
            raise SatQueryError(
                "session_not_found",
                f"No result for session: {session_id}",
                status_code=404,
            )

        result = session.result
        if not result.bi_temporal_change:
            raise SatQueryError(
                "not_bi_temporal_session",
                "Region interpretation requires a bi-temporal analysis session.",
                status_code=422,
            )

        region = _find_region(result, region_id)
        bt = result.bi_temporal_change
        bbox = padded_bbox_from_geometry(region.geometry.model_dump())
        bbox_param = format_preview_bbox(bbox)

        provider = get_uploaded_imagery_provider()
        earlier = provider.get(bt.earlier_image_id)
        later = provider.get(bt.later_image_id)
        storage = get_image_storage()
        earlier_path = resolve_upload_path(earlier, storage)
        later_path = resolve_upload_path(later, storage)

        composite_png = render_before_after_composite(
            earlier_path,
            later_path,
            bbox_wgs84=bbox,
        )
        prompt = build_evidence_prompt(region=region, result=result, question=question)

        step_id = f"geochat_region_interpretation-{len(session.trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="geochat_region_interpretation",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Interpreting selected change region with GeoChat…",
            metadata={
                "region_id": region_id,
                "session_id": session_id,
                "preview_bbox_wgs84": bbox_param,
                "evidence_inputs": EVIDENCE_INPUTS,
            },
        )
        session.trace.append(step)

        try:
            vlm = get_geochat_vlm()
            vqa_result = await vlm.run_composite_vqa(
                composite_png=composite_png,
                question=prompt,
                parameters=GeoChatVQAParameters(),
                composite_image_id=f"{session_id}:{region_id}",
                modality=str(region.metadata.get("evidence_modality") or "optical"),
            )
        except SatQueryError as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = int((perf_counter() - t0) * 1000)
            step.error = exc.message
            step.metadata = {
                **(step.metadata or {}),
                "error_code": exc.code,
                "status": TraceStatus.FAILED.value,
            }
            raise

        elapsed = int((perf_counter() - t0) * 1000)
        direction_hint = region.metadata.get("change_direction_hint")
        if not direction_hint and bt.detector_summary:
            direction_hint = bt.detector_summary.change_direction_hint

        interpretation = BiTemporalRegionInterpretationResult(
            answer=vqa_result.answer,
            region_id=region_id,
            session_id=session_id,
            question=question.strip(),
            detector=bt.detector,
            region_confidence=region.confidence,
            confidence_kind=region.metadata.get("confidence_kind")
            or bt.confidence_kind
            or CONFIDENCE_KIND,
            change_direction_hint=str(direction_hint) if direction_hint else None,
            model_name=vqa_result.model_name,
            model_version=vqa_result.model_version,
            provider=vqa_result.provider,
            provenance=vqa_result.provenance,
            confidence_available=False,
            inference_metadata={
                **vqa_result.inference_metadata,
                "evidence_inputs": EVIDENCE_INPUTS,
                "preview_bbox_wgs84": bbox_param,
                "composite_bytes": len(composite_png),
            },
            earlier_image_id=bt.earlier_image_id,
            later_image_id=bt.later_image_id,
            preview_bbox_wgs84=bbox_param,
            evidence_inputs=EVIDENCE_INPUTS,
        )

        step.status = TraceStatus.COMPLETED
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        step.summary = "GeoChat region interpretation completed."
        step.metadata = {
            **(step.metadata or {}),
            "provider": vqa_result.provider.value,
            "model_name": vqa_result.model_name,
            "model_version": vqa_result.model_version,
            "status": TraceStatus.COMPLETED.value,
            "duration_ms": elapsed,
        }
        return interpretation, step


region_interpretation_service = RegionInterpretationService()
