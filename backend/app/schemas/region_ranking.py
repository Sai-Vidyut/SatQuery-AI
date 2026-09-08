"""Read-only bi-temporal region inspection priority contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.domain import Metric


class RankedRegionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    region_id: str
    priority_score: float = Field(ge=0, le=1)
    priority_label: Literal["high", "medium", "low"]
    confidence: float = Field(ge=0, le=1)
    confidence_kind: Literal["histogram_separability"] | None = None
    change_direction_hint: str | None = None
    claim_type: str | None = None
    metrics: list[Metric] = Field(default_factory=list)


class BiTemporalRegionRankingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: Literal["bi_temporal_region_ranking"] = "bi_temporal_region_ranking"
    session_id: str
    detector: str
    ranking_policy: str = "bi_temporal_inspection_priority_v1.0.0"
    regions: list[RankedRegionItem] = Field(default_factory=list)
