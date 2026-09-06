"""Change understanding tool input/output contracts."""

from __future__ import annotations

from app.schemas.bi_temporal_change import BiTemporalChangeResult, ChangeUnderstandingOutput
from app.schemas.change_domain import ChangeDomain
from app.schemas.domain import ChangeDetectionOutput
from app.schemas.input import ImageInput
from pydantic import BaseModel, ConfigDict, Field


class ChangeUnderstandingToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=2000)
    earlier: ImageInput
    later: ImageInput
    detections: ChangeDetectionOutput
    change_domain: ChangeDomain | None = None
