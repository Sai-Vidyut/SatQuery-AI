from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.schemas.domain import AnalysisResult, AnalysisStatus, TraceStep, TraceStatus
from app.schemas.region_interpretation import BiTemporalRegionInterpretationResult


@dataclass
class ConversationTurn:
    turn_id: str
    turn_index: int
    user_message: str
    assistant_answer: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RegionConversation:
    conversation_id: str
    session_id: str
    region_id: str
    turns: list[ConversationTurn] = field(default_factory=list)


@dataclass
class QuerySession:
    session_id: str
    status: AnalysisStatus
    trace: list[TraceStep] = field(default_factory=list)
    result: AnalysisResult | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SessionStore:
    """In-memory session store for Phase 1. No database."""

    def __init__(self) -> None:
        self._sessions: dict[str, QuerySession] = {}
        self._conversations: dict[str, RegionConversation] = {}
        self._interpretations: dict[str, BiTemporalRegionInterpretationResult] = {}

    @staticmethod
    def _conversation_key(session_id: str, region_id: str) -> str:
        return f"{session_id}:{region_id}"

    def get_conversation(self, session_id: str, region_id: str) -> RegionConversation | None:
        return self._conversations.get(self._conversation_key(session_id, region_id))

    def get_or_create_conversation(self, session_id: str, region_id: str) -> RegionConversation:
        key = self._conversation_key(session_id, region_id)
        existing = self._conversations.get(key)
        if existing is not None:
            return existing
        conversation = RegionConversation(
            conversation_id=str(uuid.uuid4()),
            session_id=session_id,
            region_id=region_id,
        )
        self._conversations[key] = conversation
        return conversation

    def append_turn(self, session_id: str, region_id: str, turn: ConversationTurn) -> RegionConversation:
        conversation = self.get_or_create_conversation(session_id, region_id)
        conversation.turns.append(turn)
        return conversation

    def store_interpretation(
        self,
        session_id: str,
        region_id: str,
        interpretation: BiTemporalRegionInterpretationResult,
    ) -> None:
        self._interpretations[self._conversation_key(session_id, region_id)] = interpretation

    def get_latest_interpretation(
        self,
        session_id: str,
        region_id: str,
    ) -> BiTemporalRegionInterpretationResult | None:
        return self._interpretations.get(self._conversation_key(session_id, region_id))

    def create(self) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = QuerySession(
            session_id=session_id,
            status=AnalysisStatus.PENDING,
        )
        return session_id

    def get(self, session_id: str) -> QuerySession | None:
        return self._sessions.get(session_id)

    def update_trace(self, session_id: str, trace: list[TraceStep]) -> None:
        session = self._require(session_id)
        session.trace = trace

    def complete(self, session_id: str, result: AnalysisResult) -> None:
        session = self._require(session_id)
        session.status = result.status
        session.result = result
        session.trace = result.trace

    def _require(self, session_id: str) -> QuerySession:
        session = self.get(session_id)
        if not session:
            raise KeyError(session_id)
        return session


session_store = SessionStore()
