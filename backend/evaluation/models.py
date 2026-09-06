"""Evaluation case and result contracts (Phase 6)."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.domain import AOI, GeoJSONGeometry


class EvaluationType(str, Enum):
    QUALITATIVE = "qualitative"
    QUANTITATIVE = "quantitative"


class GroundTruthSpec(BaseModel):
    """Optional reference geometry for quantitative evaluation."""

    model_config = ConfigDict(extra="forbid")

    source: str
    license_note: str | None = None
    geometry: GeoJSONGeometry
    reference_url: str | None = None


class EvaluationCase(BaseModel):
    """One reproducible real-world evaluation scenario."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    domain: Literal[
        "urban_expansion",
        "deforestation",
        "water_shrinkage",
        "infrastructure_development",
        "mining",
    ]
    title: str
    query: str
    aoi: AOI
    earlier_date: date
    later_date: date
    expected_change: str
    evaluation_type: EvaluationType = EvaluationType.QUALITATIVE
    sensor: Literal["sentinel-2"] = "sentinel-2"
    collection: str = "COPERNICUS/S2_SR_HARMONIZED"
    reference: str
    reference_url: str | None = None
    ground_truth_available: bool = False
    ground_truth: GroundTruthSpec | None = None
    notes: str | None = None


class StepTiming(BaseModel):
    tool_name: str
    duration_ms: int | None = None
    status: str | None = None


class QuantitativeMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iou: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    predicted_area_m2: float | None = None
    ground_truth_area_m2: float | None = None
    changed_area_error_m2: float | None = None
    region_count_error: int | None = None


class EvaluationRecord(BaseModel):
    """Recorded outcome for one evaluation case run."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    domain: str
    evaluation_type: EvaluationType
    status: Literal["completed", "failed", "skipped"]
    error_code: str | None = None
    error_message: str | None = None

    imagery_provider: str | None = None
    data_mode: str | None = None
    detector: str | None = None
    scenes: list[dict[str, Any]] = Field(default_factory=list)

    planner_intent: str | None = None
    change_domain: str | None = None
    required_tools: list[str] = Field(default_factory=list)

    region_count: int = 0
    candidate_region_count: int = 0
    changed_area_m2: float | None = None
    confidence: float | None = None

    answer: str | None = None
    answer_mentions_development_mock: bool = False

    step_timings: list[StepTiming] = Field(default_factory=list)
    total_duration_ms: int | None = None

    detector_metadata: dict[str, Any] = Field(default_factory=dict)
    trace_summary: list[dict[str, Any]] = Field(default_factory=list)
    quantitative: QuantitativeMetrics | None = None

    qualitative_assessment: dict[str, Any] = Field(default_factory=dict)
