"""Export a downloadable evidence package for a selected bi-temporal change region."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any

from app.adapters.change.bi_temporal.validator import resolve_upload_path
from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
from app.core.errors import SatQueryError
from app.evidence.bi_temporal_interpretation import CONFIDENCE_KIND
from app.schemas.domain import AnalysisResult, EvidenceRegion, TraceStep
from app.schemas.region_interpretation import BiTemporalRegionInterpretationResult
from app.services.imagery_preview import render_raster_preview_png
from app.services.region_interpretation import (
    _find_region,
    format_preview_bbox,
    padded_bbox_from_geometry,
)
from app.services.session_store import ConversationTurn, RegionConversation, SessionStore, session_store
from app.storage.factory import get_image_storage

EXPORT_VERSION = "1.0.0"
DEFAULT_PREVIEW_MAX_SIZE = 512


def build_region_geojson_feature(region: EvidenceRegion) -> dict[str, Any]:
    """GeoJSON Feature preserving authoritative region metadata."""
    return {
        "type": "Feature",
        "geometry": region.geometry.model_dump(mode="json"),
        "properties": {
            "id": region.id,
            "type": region.type,
            "confidence": region.confidence,
            "source": region.source,
            "metrics": [metric.model_dump(mode="json") for metric in region.metrics],
            "metadata": region.metadata,
        },
    }


def serialize_conversation(conversation: RegionConversation) -> dict[str, Any]:
    return {
        "conversation_id": conversation.conversation_id,
        "session_id": conversation.session_id,
        "region_id": conversation.region_id,
        "turns": [
            {
                "turn_id": turn.turn_id,
                "turn_index": turn.turn_index,
                "user_message": turn.user_message,
                "assistant_answer": turn.assistant_answer,
                "created_at": turn.created_at.isoformat(),
            }
            for turn in conversation.turns
        ],
    }


def build_export_metadata(
    *,
    session_id: str,
    region: EvidenceRegion,
    result: AnalysisResult,
    preview_bbox_wgs84: str,
    exported_at: datetime,
) -> dict[str, Any]:
    bt = result.bi_temporal_change
    if bt is None:
        raise SatQueryError(
            "not_bi_temporal_session",
            "Region evidence export requires a bi-temporal analysis session.",
            status_code=422,
        )

    direction_hint = region.metadata.get("change_direction_hint")
    if not direction_hint and bt.detector_summary:
        direction_hint = bt.detector_summary.change_direction_hint

    confidence_kind = (
        region.metadata.get("confidence_kind")
        or bt.confidence_kind
        or CONFIDENCE_KIND
    )

    metadata: dict[str, Any] = {
        "export_version": EXPORT_VERSION,
        "session_id": session_id,
        "region_id": region.id,
        "workflow_type": bt.task.value if hasattr(bt.task, "value") else str(bt.task),
        "detector": bt.detector,
        "analysis_dates": {
            "earlier": bt.earlier_date.isoformat(),
            "later": bt.later_date.isoformat(),
        },
        "source_image_ids": {
            "earlier_image_id": bt.earlier_image_id,
            "later_image_id": bt.later_image_id,
        },
        "region_confidence": region.confidence,
        "confidence_kind": confidence_kind,
        "change_direction_hint": direction_hint,
        "claim_type": region.metadata.get("claim_type"),
        "modality": region.metadata.get("evidence_modality") or "optical",
        "region_metrics": [metric.model_dump(mode="json") for metric in region.metrics],
        "preview_bbox_wgs84": preview_bbox_wgs84,
        "exported_at": exported_at.isoformat(),
    }

    if bt.detector_summary is not None:
        metadata["detector_summary"] = bt.detector_summary.model_dump(mode="json")
    if bt.scene_metrics is not None:
        metadata["scene_metrics"] = bt.scene_metrics.model_dump(mode="json")
    if bt.image_provenance is not None:
        metadata["image_provenance"] = bt.image_provenance.model_dump(mode="json")

    return metadata


def serialize_trace(trace: list[TraceStep]) -> list[dict[str, Any]]:
    return [step.model_dump(mode="json") for step in trace]


def build_evidence_zip_bytes(
    *,
    metadata: dict[str, Any],
    region_feature: dict[str, Any],
    before_png: bytes,
    after_png: bytes,
    trace: list[dict[str, Any]],
    interpretation: BiTemporalRegionInterpretationResult | None,
    conversation: RegionConversation | None,
) -> bytes:
    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json.dumps(metadata, indent=2, sort_keys=True))
            archive.writestr("region.geojson", json.dumps(region_feature, indent=2, sort_keys=True))
            archive.writestr("before.png", before_png)
            archive.writestr("after.png", after_png)
            archive.writestr("trace.json", json.dumps(trace, indent=2, sort_keys=True))
            if interpretation is not None:
                archive.writestr(
                    "interpretation.json",
                    json.dumps(interpretation.model_dump(mode="json"), indent=2, sort_keys=True),
                )
            if conversation is not None and conversation.turns:
                archive.writestr(
                    "chat.json",
                    json.dumps(serialize_conversation(conversation), indent=2, sort_keys=True),
                )
    except Exception as exc:
        raise SatQueryError(
            "evidence_export_failed",
            "Failed to build region evidence export package.",
            status_code=500,
        ) from exc

    return buffer.getvalue()


def build_export_filename(session_id: str, region_id: str) -> str:
    safe_region = region_id.replace("/", "-").replace("\\", "-")
    return f"satquery-evidence-{session_id[:8]}-{safe_region}.zip"


class RegionEvidenceExportService:
    def __init__(self, store: SessionStore | None = None) -> None:
        self._store = store or session_store

    def export_region_evidence(
        self,
        session_id: str,
        region_id: str,
        *,
        preview_max_size: int = DEFAULT_PREVIEW_MAX_SIZE,
    ) -> tuple[bytes, str]:
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
                "Region evidence export requires a bi-temporal analysis session.",
                status_code=422,
            )

        region = _find_region(result, region_id)
        bt = result.bi_temporal_change
        bbox = padded_bbox_from_geometry(region.geometry.model_dump())
        preview_bbox = format_preview_bbox(bbox)

        provider = get_uploaded_imagery_provider()
        storage = get_image_storage()
        try:
            earlier = provider.get(bt.earlier_image_id)
            later = provider.get(bt.later_image_id)
        except SatQueryError:
            raise
        except Exception as exc:
            raise SatQueryError(
                "image_not_found",
                "Source imagery for this session is unavailable.",
                status_code=404,
            ) from exc

        earlier_path = resolve_upload_path(earlier, storage)
        later_path = resolve_upload_path(later, storage)

        before_png = render_raster_preview_png(
            earlier_path,
            bbox_wgs84=bbox,
            max_size=preview_max_size,
        )
        after_png = render_raster_preview_png(
            later_path,
            bbox_wgs84=bbox,
            max_size=preview_max_size,
        )

        exported_at = datetime.now(UTC)
        metadata = build_export_metadata(
            session_id=session_id,
            region=region,
            result=result,
            preview_bbox_wgs84=preview_bbox,
            exported_at=exported_at,
        )
        region_feature = build_region_geojson_feature(region)
        trace = serialize_trace(session.trace)
        interpretation = self._store.get_latest_interpretation(session_id, region_id)
        conversation = self._store.get_conversation(session_id, region_id)

        zip_bytes = build_evidence_zip_bytes(
            metadata=metadata,
            region_feature=region_feature,
            before_png=before_png,
            after_png=after_png,
            trace=trace,
            interpretation=interpretation,
            conversation=conversation,
        )
        filename = build_export_filename(session_id, region_id)
        return zip_bytes, filename


region_evidence_export_service = RegionEvidenceExportService()
