"""Session-scoped conversational follow-up for catalog/upload/cross-modal analyses."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from time import perf_counter

from app.adapters.llm.groq_service import complete_general_assistant
from app.core.errors import SatQueryError
from app.schemas.domain import TraceStatus, TraceStep
from app.schemas.region_chat import BiTemporalRegionChatResult, RegionChatProviderKind
from app.services.conversational_development import development_session_chat_reply
from app.services.region_chat import (
    _conversation_record,
    _validate_history_limits,
)
from app.services.region_chat_router import classify_region_chat_message, is_out_of_scope_message
from app.services.region_interpretation import _find_region
from app.services.session_store import ConversationTurn, SessionStore, session_store

SESSION_CHAT_SCOPE_KEY = "session"
SESSION_SCOPE_LIMITED_ANSWER = (
    "This follow-up is limited to the current analysis result and selected context. "
    "I cannot search the whole scene, run a new detection, or investigate another area from here. "
    "Submit a new analysis with a different question or AOI to explore further."
)


class SessionChatService:
    def __init__(self, store: SessionStore | None = None) -> None:
        self._store = store or session_store

    def _conversation_scope(self, region_id: str | None) -> str:
        return region_id or SESSION_CHAT_SCOPE_KEY

    async def chat(
        self,
        session_id: str,
        message: str,
        *,
        region_id: str | None = None,
    ) -> tuple[BiTemporalRegionChatResult, TraceStep]:
        cleaned = message.strip()
        if not cleaned:
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
        if result.bi_temporal_change:
            raise SatQueryError(
                "use_region_chat",
                "Use region chat for bi-temporal analyses with a selected region.",
                status_code=422,
            )

        region = _find_region(result, region_id) if region_id else None
        scope_key = self._conversation_scope(region_id)
        conversation = self._store.get_or_create_conversation(session_id, scope_key)
        _validate_history_limits(conversation)

        prior_turns = list(conversation.turns)
        turn_index = len(prior_turns)
        turn_id = str(uuid.uuid4())
        route_decision = classify_region_chat_message(
            cleaned,
            region_id=region_id or scope_key,
            prior_turns=prior_turns,
        )

        step_id = f"session_chat-{len(session.trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="session_chat",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Running session chat turn…",
            metadata={
                "session_id": session_id,
                "region_id": region_id,
                "conversation_id": conversation.conversation_id,
                "turn_id": turn_id,
                "route": route_decision.route,
                "classification": route_decision.classification.value,
            },
        )
        session.trace.append(step)

        route = route_decision.route
        classification = route_decision.classification.value
        scope = "general_assistant" if route == "general" else "selected_region"
        scope_limited = False
        evidence_inputs: str = "analysis_summary_no_imagery"
        detector = "session_analysis"
        region_confidence = region.confidence if region else result.confidence

        try:
            if route == "general":
                groq_result = await complete_general_assistant(cleaned, prior_turns=prior_turns)
                answer = groq_result.answer
                provider_kind = RegionChatProviderKind.GROQ
                model_name = groq_result.model_name
                model_version = groq_result.model_version
                provenance = groq_result.provenance
                inference_metadata = {
                    **groq_result.inference_metadata,
                    "route": route,
                    "classification": classification,
                    "scope": scope,
                    "geochat_called": False,
                    "groq_called": bool(groq_result.inference_metadata.get("groq_called")),
                    "evidence_inputs": evidence_inputs,
                }
            else:
                scope_limited = is_out_of_scope_message(cleaned)
                if scope_limited:
                    answer = SESSION_SCOPE_LIMITED_ANSWER
                    provider_kind = RegionChatProviderKind.DEVELOPMENT
                    model_name = "satquery-scope-guard"
                    model_version = "1.0.0"
                    provenance = "SatQuery session scope guard — no new detection performed."
                    inference_metadata = {
                        "route": route,
                        "classification": classification,
                        "scope": scope,
                        "scope_guard": True,
                        "geochat_called": False,
                        "groq_called": False,
                        "evidence_inputs": evidence_inputs,
                    }
                else:
                    answer = development_session_chat_reply(
                        message=cleaned,
                        result=result,
                        region=region,
                        prior_turns=prior_turns,
                    )
                    provider_kind = RegionChatProviderKind.DEVELOPMENT
                    model_name = "development-session-chat"
                    model_version = "0.0.0-dev"
                    provenance = "Development session chat mock — not analysis re-submission."
                    inference_metadata = {
                        "route": route,
                        "classification": classification,
                        "scope": scope,
                        "scope_guard": False,
                        "geochat_called": False,
                        "groq_called": False,
                        "evidence_inputs": evidence_inputs,
                        "development_mock": True,
                    }
        except SatQueryError as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = int((perf_counter() - t0) * 1000)
            step.error = exc.message
            step.metadata = {**(step.metadata or {}), "error_code": exc.code, "status": TraceStatus.FAILED.value}
            raise

        elapsed = int((perf_counter() - t0) * 1000)
        self._store.append_turn(
            session_id,
            scope_key,
            ConversationTurn(
                turn_id=turn_id,
                turn_index=turn_index,
                user_message=cleaned,
                assistant_answer=answer,
                route=route,
                provider=provider_kind.value,
                scope=scope,
            ),
        )
        updated = self._store.get_conversation(session_id, scope_key)
        if updated is None:
            raise SatQueryError("conversation_not_found", "Conversation state was lost.", status_code=500)

        chat_result = BiTemporalRegionChatResult(
            answer=answer,
            session_id=session_id,
            region_id=region_id or scope_key,
            conversation_id=updated.conversation_id,
            turn_id=turn_id,
            turn_index=turn_index,
            message=cleaned,
            detector=detector,
            region_confidence=region_confidence,
            confidence_kind=None,
            change_direction_hint=str(region.metadata.get("change_direction_hint")) if region else None,
            model_name=model_name,
            model_version=model_version,
            provider=provider_kind,
            provenance=provenance,
            confidence_available=False,
            inference_metadata=inference_metadata,
            route=route,  # type: ignore[arg-type]
            classification=classification,  # type: ignore[arg-type]
            scope=scope,  # type: ignore[arg-type]
            preview_bbox_wgs84="",
            evidence_inputs=evidence_inputs,  # type: ignore[arg-type]
            scope_limited=scope_limited,
            conversation=_conversation_record(updated),
        )

        step.status = TraceStatus.COMPLETED
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        step.summary = "Session chat turn completed."
        step.metadata = {
            **(step.metadata or {}),
            "provider": provider_kind.value,
            "model_name": model_name,
            "status": TraceStatus.COMPLETED.value,
            "scope_limited": scope_limited,
            "route": route,
        }
        return chat_result, step


session_chat_service = SessionChatService()
