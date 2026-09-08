"""Region-scoped GeoChat interpretation contracts (evidence-grounded, non-authoritative)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.vqa import VQAProviderKind


class RegionInterpretationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        min_length=3,
        max_length=2000,
        default="What visible change occurred in this detected region between the two dates?",
    )


class BiTemporalRegionInterpretationResult(BaseModel):
    """GeoChat interpretation of an already-detected change region — not authoritative detection."""

    model_config = ConfigDict(extra="forbid")

    task: Literal["bi_temporal_region_interpretation"] = "bi_temporal_region_interpretation"
    answer: str = Field(min_length=1)
    region_id: str
    session_id: str
    question: str

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

    earlier_image_id: str
    later_image_id: str
    preview_bbox_wgs84: str
    evidence_inputs: Literal["before_after_composite_crop"] = "before_after_composite_crop"


class InterpretRegionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interpretation: BiTemporalRegionInterpretationResult
    trace_step: dict[str, Any]
