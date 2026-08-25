from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.schemas.domain import AnalysisResult, AnalysisStatus, TraceStep, TraceStatus


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
