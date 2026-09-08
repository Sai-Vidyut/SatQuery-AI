"""Evidence-grounded conversational GeoChat for selected bi-temporal change regions."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from time import perf_counter

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
from app.schemas.region_chat import (
    BiTemporalRegionChatResult,
    ConversationTurnRecord,
    RegionConversationRecord,
)
from app.schemas.vqa import GeoChatVQAParameters, VQAProviderKind
from app.services.region_interpretation import (
    EVIDENCE_INPUTS,
    _find_region,
    _region_area_clause,
    format_preview_bbox,
    padded_bbox_from_geometry,
    render_before_after_composite,
)
from app.services.session_store import ConversationTurn, RegionConversation, SessionStore, session_store
from app.storage.factory import get_image_storage

MAX_CONVERSATION_TURNS = 10
MAX_HISTORY_CHARS = 8000

OUT_OF_SCOPE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bfind (?:other|all|every|any)\b", re.I),
    re.compile(r"\bwhole city\b", re.I),
    re.compile(r"\banalyze the whole\b", re.I),
    re.compile(r"\ball damaged\b", re.I),
    re.compile(r"\bsomewhere else\b", re.I),
    re.compile(r"\banother area\b", re.I),
    re.compile(r"\bdifferent region\b", re.I),
    re.compile(r"\bnew analysis\b", re.I),
    re.compile(r"\bentire (?:scene|image|aoi|area|city)\b", re.I),
    re.compile(r"\bwhat happened (?:elsewhere|outside)\b", re.I),
)

SCOPE_LIMITED_ANSWER = (
    "This conversation is limited to the already-detected region shown in the Before/After "
    "evidence. I cannot search for other changed areas, analyze the whole scene, or run a "
    "new detection from here. Submit a new analysis with a different question or AOI to "
    "investigate another area."
)


def is_out_of_scope_message(message: str) -> bool:
    return any(pattern.search(message) for pattern in OUT_OF_SCOPE_PATTERNS)


def _history_char_count(turns: list[ConversationTurn]) -> int:
    total = 0
    for turn in turns:
        total += len(turn.user_message) + len(turn.assistant_answer)
    return total


def _format_history(turns: list[ConversationTurn]) -> str:
    if not turns:
        return "(none)"
    lines: list[str] = []
    for turn in turns:
        lines.append(f"User: {turn.user_message.strip()}")
        lines.append(f"Assistant: {turn.assistant_answer.strip()}")
    return "\n".join(lines)


def build_region_chat_prompt(
    *,
    region: EvidenceRegion,
    result: AnalysisResult,
    message: str,
    prior_turns: list[ConversationTurn],
) -> str:
    bt = result.bi_temporal_change
    if bt is None:
        raise SatQueryError(
            "not_bi_temporal_session",
            "Region chat requires a bi-temporal analysis session.",
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
    claim_type = str(region.metadata.get("claim_type") or "none")
    modality = region.metadata.get("evidence_modality") or "optical"
    area_clause = _region_area_clause(region)

    guard = (
        "A change detection system has ALREADY identified this region.\n"
        "You are interpreting supplied Before/After evidence for follow-up conversation.\n"
        "Do NOT decide whether change exists.\n"
        "Do NOT invent new regions, bounding boxes, detector metrics, or confidence scores.\n"
        "Distinguish observation from inference and express uncertainty when appropriate.\n"
        "LEFT panel = BEFORE. RIGHT panel = AFTER.\n"
        "Answer only about this selected detected region using the supplied evidence."
    )
    context_lines = [
        f"Region ID: {region.id}",
        f"Acquisition dates: {bt.earlier_date.isoformat()} to {bt.later_date.isoformat()}",
        f"Detector: {bt.detector}",
        f"Claim type: {claim_type}",
        f"Primary index: {format_primary_index(primary_index)}",
        f"Direction hint: {humanize_direction_hint(str(direction_hint) if direction_hint else None)} (heuristic only, not a confirmed event)",
        f"Separability: {region.confidence:.0%} ({confidence_kind} — not event probability)",
        f"Modality: {modality}",
    ]
    if area_clause:
        context_lines.append(area_clause)

    return (
        f"{guard}\n\n"
        "Authoritative context:\n"
        + "\n".join(context_lines)
        + "\n\nPrevious conversation (same region only):\n"
        + _format_history(prior_turns)
        + f"\n\nCurrent user message: {message.strip()}"
    )


def _conversation_record(conversation: RegionConversation) -> RegionConversationRecord:
    return RegionConversationRecord(
        conversation_id=conversation.conversation_id,
        session_id=conversation.session_id,
        region_id=conversation.region_id,
        turns=[
            ConversationTurnRecord(
                turn_id=turn.turn_id,
                turn_index=turn.turn_index,
                user_message=turn.user_message,
                assistant_answer=turn.assistant_answer,
                created_at=turn.created_at,
            )
            for turn in conversation.turns
        ],
    )


def _validate_history_limits(conversation: RegionConversation) -> None:
    if len(conversation.turns) >= MAX_CONVERSATION_TURNS:
        raise SatQueryError(
            "conversation_history_too_large",
            f"Conversation is limited to {MAX_CONVERSATION_TURNS} turns for this region.",
            status_code=422,
        )
    if _history_char_count(conversation.turns) >= MAX_HISTORY_CHARS:
        raise SatQueryError(
            "conversation_history_too_large",
            "Conversation history is too large for another turn.",
            status_code=422,
        )


class RegionChatService:
    def __init__(self, store: SessionStore | None = None) -> None:
        self._store = store or session_store

    async def chat(
        self,
        session_id: str,
        region_id: str,
        message: str,
    ) -> tuple[BiTemporalRegionChatResult, TraceStep]:
        cleaned = message.strip()
        if len(cleaned) < 1:
            raise SatQueryError(
                "invalid_chat_message",
                "Chat message must not be empty.",
                status_code=422,
                field="message",
            )

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
                "Region chat is only available for bi-temporal upload analyses.",
                status_code=422,
            )

        region = _find_region(result, region_id)
        conversation = self._store.get_or_create_conversation(session_id, region_id)
        _validate_history_limits(conversation)

        bt = result.bi_temporal_change
        bbox = padded_bbox_from_geometry(region.geometry.model_dump())
        bbox_param = format_preview_bbox(bbox)

        upload_provider = get_uploaded_imagery_provider()
        earlier = upload_provider.get(bt.earlier_image_id)
        later = upload_provider.get(bt.later_image_id)
        storage = get_image_storage()
        earlier_path = resolve_upload_path(earlier, storage)
        later_path = resolve_upload_path(later, storage)
        composite_png = render_before_after_composite(
            earlier_path,
            later_path,
            bbox_wgs84=bbox,
        )

        prior_turns = list(conversation.turns)
        turn_index = len(prior_turns)
        turn_id = str(uuid.uuid4())
        step_id = f"geochat_region_chat-{len(session.trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()

        step = TraceStep(
            id=step_id,
            tool_name="geochat_region_chat",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Running evidence-scoped GeoChat conversation…",
            metadata={
                "session_id": session_id,
                "region_id": region_id,
                "conversation_id": conversation.conversation_id,
                "turn_id": turn_id,
                "turn_index": turn_index,
                "evidence_inputs": EVIDENCE_INPUTS,
                "preview_bbox_wgs84": bbox_param,
            },
        )
        session.trace.append(step)

        scope_limited = is_out_of_scope_message(cleaned)
        try:
            if scope_limited:
                vlm = get_geochat_vlm()
                answer = SCOPE_LIMITED_ANSWER
                provider_kind = VQAProviderKind(vlm.provider_kind)
                model_name = "satquery-scope-guard"
                model_version = "1.0.0"
                provenance = "SatQuery region scope guard — no new detection performed."
                inference_metadata = {
                    "scope_guard": True,
                    "geochat_called": False,
                    "evidence_inputs": EVIDENCE_INPUTS,
                    "preview_bbox_wgs84": bbox_param,
                }
            else:
                prompt = build_region_chat_prompt(
                    region=region,
                    result=result,
                    message=cleaned,
                    prior_turns=prior_turns,
                )
                vlm = get_geochat_vlm()
                vqa_result = await vlm.run_composite_vqa(
                    composite_png=composite_png,
                    question=prompt,
                    parameters=GeoChatVQAParameters(),
                    composite_image_id=f"{session_id}:{region_id}:{conversation.conversation_id}",
                    modality=str(region.metadata.get("evidence_modality") or "optical"),
                )
                answer = vqa_result.answer
                provider_kind = vqa_result.provider
                model_name = vqa_result.model_name
                model_version = vqa_result.model_version
                provenance = vqa_result.provenance
                inference_metadata = {
                    **vqa_result.inference_metadata,
                    "scope_guard": False,
                    "geochat_called": True,
                    "evidence_inputs": EVIDENCE_INPUTS,
                    "preview_bbox_wgs84": bbox_param,
                    "composite_bytes": len(composite_png),
                    "turn_index": turn_index,
                }
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
        self._store.append_turn(
            session_id,
            region_id,
            ConversationTurn(
                turn_id=turn_id,
                turn_index=turn_index,
                user_message=cleaned,
                assistant_answer=answer,
            ),
        )
        updated_conversation = self._store.get_conversation(session_id, region_id)
        if updated_conversation is None:
            raise SatQueryError(
                "conversation_not_found",
                "Conversation state was lost before the turn could be recorded.",
                status_code=500,
            )

        direction_hint = region.metadata.get("change_direction_hint")
        if not direction_hint and bt.detector_summary:
            direction_hint = bt.detector_summary.change_direction_hint

        chat_result = BiTemporalRegionChatResult(
            answer=answer,
            session_id=session_id,
            region_id=region_id,
            conversation_id=updated_conversation.conversation_id,
            turn_id=turn_id,
            turn_index=turn_index,
            message=cleaned,
            detector=bt.detector,
            region_confidence=region.confidence,
            confidence_kind=region.metadata.get("confidence_kind")
            or bt.confidence_kind
            or CONFIDENCE_KIND,
            change_direction_hint=str(direction_hint) if direction_hint else None,
            model_name=model_name,
            model_version=model_version,
            provider=provider_kind,
            provenance=provenance,
            confidence_available=False,
            inference_metadata=inference_metadata,
            preview_bbox_wgs84=bbox_param,
            evidence_inputs=EVIDENCE_INPUTS,
            scope_limited=scope_limited,
            conversation=_conversation_record(updated_conversation),
        )

        step.status = TraceStatus.COMPLETED
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        step.summary = "GeoChat region conversation turn completed."
        step.metadata = {
            **(step.metadata or {}),
            "provider": provider_kind.value,
            "model_name": model_name,
            "model_version": model_version,
            "status": TraceStatus.COMPLETED.value,
            "duration_ms": elapsed,
            "scope_limited": scope_limited,
        }
        return chat_result, step


region_chat_service = RegionChatService()
