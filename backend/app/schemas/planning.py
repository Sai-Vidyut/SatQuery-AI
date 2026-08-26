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
    SINGLE_IMAGE_VQA = "single_image_vqa"
    SINGLE_IMAGE_CAPTION = "single_image_caption"
    BI_TEMPORAL_CHANGE_VQA = "bi_temporal_change_vqa"
    CROSS_MODAL_OPTICAL_SAR = "cross_modal_optical_sar"


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
    GEOCHAT_VQA = "geochat_vqa"
    GEOCHAT_CAPTION = "geochat_caption"
    CHANGE_UNDERSTANDING = "change_understanding"
    OPTICAL_ANALYSIS = "optical_analysis"
    SAR_ANALYSIS = "sar_analysis"
    CROSS_MODAL_FUSION = "cross_modal_fusion"


class SensorRequirement(str, Enum):
    SENTINEL_2 = "sentinel-2"
    SENTINEL_1 = "sentinel-1"
    SENTINEL_2_AND_1 = "sentinel-2+sentinel-1"
    NOT_APPLICABLE = "not_applicable"


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
    earlier_date: date | None = None
    later_date: date | None = None
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

        if self.user_intent == QueryIntent.SINGLE_IMAGE_VQA:
            expected = {PlannerToolName.GEOCHAT_VQA, PlannerToolName.GENERATE_EVIDENCE}
            if tools != expected:
                raise ValueError("single_image_vqa requires geochat_vqa and generate_evidence only")
            if self.earlier_date is not None or self.later_date is not None:
                raise ValueError("single_image_vqa must not include temporal dates")
            if self.aoi_required:
                raise ValueError("single_image_vqa must set aoi_required=False")
            return self

        if self.user_intent == QueryIntent.SINGLE_IMAGE_CAPTION:
            expected = {PlannerToolName.GEOCHAT_CAPTION, PlannerToolName.GENERATE_EVIDENCE}
            if tools != expected:
                raise ValueError("single_image_caption requires geochat_caption and generate_evidence only")
            if self.earlier_date is not None or self.later_date is not None:
                raise ValueError("single_image_caption must not include temporal dates")
            if self.aoi_required:
                raise ValueError("single_image_caption must set aoi_required=False")
            return self

        if self.user_intent == QueryIntent.BI_TEMPORAL_CHANGE_VQA:
            expected = {
                PlannerToolName.DETECT_CHANGE,
                PlannerToolName.CHANGE_UNDERSTANDING,
                PlannerToolName.GENERATE_EVIDENCE,
            }
            if tools != expected:
                raise ValueError(
                    "bi_temporal_change_vqa requires detect_change, change_understanding, "
                    "and generate_evidence only"
                )
            if self.earlier_date is not None or self.later_date is not None:
                raise ValueError("bi_temporal_change_vqa must not include catalog temporal dates")
            if self.aoi_required:
                raise ValueError("bi_temporal_change_vqa must set aoi_required=False")
            return self

        if self.user_intent == QueryIntent.CROSS_MODAL_OPTICAL_SAR:
            expected = {
                PlannerToolName.OPTICAL_ANALYSIS,
                PlannerToolName.SAR_ANALYSIS,
                PlannerToolName.CROSS_MODAL_FUSION,
                PlannerToolName.GENERATE_EVIDENCE,
            }
            if tools != expected:
                raise ValueError(
                    "cross_modal_optical_sar requires optical_analysis, sar_analysis, "
                    "cross_modal_fusion, and generate_evidence only"
                )
            if self.earlier_date is not None or self.later_date is not None:
                raise ValueError("cross_modal_optical_sar must not include catalog temporal dates")
            if self.aoi_required:
                raise ValueError("cross_modal_optical_sar must set aoi_required=False")
            return self

        if self.earlier_date is None or self.later_date is None:
            raise ValueError("earlier_date and later_date are required for temporal analysis intents")
        if self.later_date <= self.earlier_date:
            raise ValueError("later_date must be after earlier_date")

        if PlannerToolName.GEOCHAT_VQA in tools:
            raise ValueError("geochat_vqa is only valid for single_image_vqa intent")
        if PlannerToolName.GEOCHAT_CAPTION in tools:
            raise ValueError("geochat_caption is only valid for single_image_caption intent")
        if PlannerToolName.CHANGE_UNDERSTANDING in tools:
            raise ValueError("change_understanding is only valid for bi_temporal_change_vqa intent")
        if PlannerToolName.OPTICAL_ANALYSIS in tools:
            raise ValueError("optical_analysis is only valid for cross_modal_optical_sar intent")
        if PlannerToolName.SAR_ANALYSIS in tools:
            raise ValueError("sar_analysis is only valid for cross_modal_optical_sar intent")
        if PlannerToolName.CROSS_MODAL_FUSION in tools:
            raise ValueError("cross_modal_fusion is only valid for cross_modal_optical_sar intent")

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
