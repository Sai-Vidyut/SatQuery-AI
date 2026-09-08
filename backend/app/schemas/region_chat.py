"""Region-scoped conversational GeoChat contracts (evidence-grounded, non-authoritative)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.vqa import VQAProviderKind


class RegionChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)


class ConversationTurnRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: str
    turn_index: int = Field(ge=0)
    user_message: str
    assistant_answer: str
    created_at: datetime


class RegionConversationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    session_id: str
    region_id: str
    turns: list[ConversationTurnRecord] = Field(default_factory=list)


class BiTemporalRegionChatResult(BaseModel):
    """GeoChat conversational turn for an already-detected change region."""

    model_config = ConfigDict(extra="forbid")

    task: Literal["bi_temporal_region_chat"] = "bi_temporal_region_chat"
    answer: str = Field(min_length=1)
    session_id: str
    region_id: str
    conversation_id: str
    turn_id: str
    turn_index: int = Field(ge=0)
    message: str

    detector: str
    region_confidence: float = Field(ge=0, le=1)
    confidence_kind: Literal["histogram_separability"] | None = None
    change_direction_hint: str | None = None

    model_name: str
    model_version: str
    provider: VQAProviderKind
    provenance: str
    confidence_available: bool = False
    inference_metadata: dict[str, Any] = Field(default_factory=dict)

    preview_bbox_wgs84: str
    evidence_inputs: Literal["before_after_composite_crop"] = "before_after_composite_crop"
    scope_limited: bool = False
    conversation: RegionConversationRecord


class RegionChatData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat: BiTemporalRegionChatResult
    trace_step: dict[str, Any]
