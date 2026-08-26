"""Bi-temporal uploaded change analysis contracts (Phase 12 — SIH mandatory)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BiTemporalChangeTask(str, Enum):
    BI_TEMPORAL_CHANGE_VQA = "bi_temporal_change_vqa"


class BiTemporalChangeProviderKind(str, Enum):
    DEVELOPMENT = "development"
    UPLOADED_CVA = "uploaded_cva"


class BiTemporalChangeResult(BaseModel):
    """Structured specialist output for uploaded bi-temporal change understanding."""

    model_config = ConfigDict(extra="forbid")

    task: Literal[BiTemporalChangeTask.BI_TEMPORAL_CHANGE_VQA] = (
        BiTemporalChangeTask.BI_TEMPORAL_CHANGE_VQA
    )
    change_summary: str = Field(min_length=1)
    question: str
    changed_region_count: int = Field(ge=0)
    change_map_available: bool = False
    detector: str
    provider: BiTemporalChangeProviderKind
    provenance: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_available: bool = False
    earlier_image_id: str
    later_image_id: str
    earlier_acquisition: datetime
    later_acquisition: datetime
    earlier_date: date
    later_date: date
    inference_metadata: dict[str, Any] = Field(default_factory=dict)


class ChangeUnderstandingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: BiTemporalChangeResult
