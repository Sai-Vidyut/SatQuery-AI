from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PLANNER_VERSION = "1.0.0"


class QueryIntent(str, Enum):
    SPECTRAL_CHANGE = "spectral_change"
    CONSTRUCTION = "construction"
    RADAR_CHANGE = "radar_change"
    MULTIMODAL_COMPARISON = "multimodal_comparison"


class RequestedModality(str, Enum):
    OPTICAL = "optical"
    SEMANTIC = "semantic"
    SAR = "sar"


class PlannerToolName(str, Enum):
    FETCH_IMAGERY = "fetch_imagery"
    DETECT_CHANGE = "detect_change"
    ANALYZE_SEMANTICS = "analyze_semantics"
    DETECT_SAR_CHANGE = "detect_sar_change"
    FUSE_EVIDENCE = "fuse_evidence"
    GENERATE_EVIDENCE = "generate_evidence"


class SensorRequirement(str, Enum):
    SENTINEL_2 = "sentinel-2"
    SENTINEL_1 = "sentinel-1"
    SENTINEL_2_AND_1 = "sentinel-2+sentinel-1"


class AnalysisProfileName(str, Enum):
    NONE = "none"
    BUILDING_CONSTRUCTION = "building_construction"


PlannerSource = Literal["deterministic", "llm"]

FORBIDDEN_PLAN_FIELDS = frozenset(
    {
        "confidence",
        "area",
        "area_km2",
        "region_count",
        "change_magnitude",
        "geojson",
        "geometry",
        "evidence",
        "claim_type",
    }
)


class QueryAnalysisPlan(BaseModel):
    """
    Constrained execution plan for specialist tools.
    Must not contain evidence values — routing and modality selection only.
    """

    model_config = ConfigDict(extra="forbid")

    user_intent: QueryIntent
    requested_modalities: list[RequestedModality]
    analysis_profile: AnalysisProfileName = AnalysisProfileName.NONE
    required_tools: list[PlannerToolName]
    earlier_date: date
    later_date: date
    sensor_requirement: SensorRequirement
    aoi_required: bool = True
    user_intent_summary: str = Field(
        min_length=3,
        max_length=500,
        description="Short natural-language summary of routing intent (not scientific evidence).",
    )
    planner_version: str = PLANNER_VERSION
    planner: PlannerSource = "deterministic"

    @field_validator("required_tools")
    @classmethod
    def tools_non_empty(cls, tools: list[PlannerToolName]) -> list[PlannerToolName]:
        if not tools:
            raise ValueError("required_tools must not be empty")
        return tools

    @model_validator(mode="after")
    def validate_tool_combinations(self) -> QueryAnalysisPlan:
        tools = set(self.required_tools)

        if PlannerToolName.ANALYZE_SEMANTICS in tools and PlannerToolName.DETECT_CHANGE not in tools:
            raise ValueError("analyze_semantics requires detect_change")
        if PlannerToolName.DETECT_SAR_CHANGE in tools and self.user_intent == QueryIntent.SPECTRAL_CHANGE:
            raise ValueError("detect_sar_change is not valid for spectral_change intent")
        if (
            PlannerToolName.ANALYZE_SEMANTICS in tools
            and self.user_intent == QueryIntent.RADAR_CHANGE
        ):
            raise ValueError("analyze_semantics is not valid for radar_change intent")
        if self.user_intent == QueryIntent.RADAR_CHANGE and PlannerToolName.DETECT_SAR_CHANGE in tools:
            raise ValueError("radar_change uses detect_change on Sentinel-1, not detect_sar_change")
        if self.user_intent == QueryIntent.MULTIMODAL_COMPARISON and PlannerToolName.DETECT_SAR_CHANGE not in tools:
            raise ValueError("multimodal_comparison requires detect_sar_change")
        if (
            self.user_intent in (QueryIntent.CONSTRUCTION, QueryIntent.MULTIMODAL_COMPARISON)
            and PlannerToolName.ANALYZE_SEMANTICS not in tools
        ):
            raise ValueError("construction intents require analyze_semantics")

        for modality in self.requested_modalities:
            if modality == RequestedModality.SEMANTIC and PlannerToolName.ANALYZE_SEMANTICS not in tools:
                raise ValueError("semantic modality requires analyze_semantics tool")
            if modality == RequestedModality.SAR and PlannerToolName.DETECT_SAR_CHANGE not in tools:
                if self.user_intent != QueryIntent.RADAR_CHANGE:
                    raise ValueError("sar modality requires detect_sar_change tool")

        if PlannerToolName.FUSE_EVIDENCE not in tools or PlannerToolName.GENERATE_EVIDENCE not in tools:
            raise ValueError("fuse_evidence and generate_evidence are required")

        return self

    @property
    def run_semantic(self) -> bool:
        return PlannerToolName.ANALYZE_SEMANTICS in self.required_tools

    @property
    def run_sar(self) -> bool:
        return PlannerToolName.DETECT_SAR_CHANGE in self.required_tools

    @property
    def profile(self) -> str | None:
        if self.analysis_profile == AnalysisProfileName.BUILDING_CONSTRUCTION:
            return "building_construction"
        return None


class PlanQueryInput(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    earlier_date: date
    later_date: date


class PlanQueryOutput(BaseModel):
    plan: QueryAnalysisPlan
    planner: PlannerSource
    fallback_used: bool = False
