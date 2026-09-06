from __future__ import annotations

from datetime import date

from app.schemas.domain import QueryRequest
from app.schemas.input import ImageModality
from app.schemas.planning import (
    AnalysisProfileName,
    PlannerToolName,
    QueryAnalysisPlan,
    QueryIntent,
    RequestedModality,
    SensorRequirement,
)
from app.services.building_temporal_intent import is_building_temporal_query
from app.services.single_image_intent import single_image_intent_from_query

BUILDING_CONSTRUCTION_PROFILE = "building_construction"
CONSTRUCTION_KEYWORDS = frozenset({"construction", "built", "development"})
SAR_KEYWORDS = frozenset({"sar", "radar", "sentinel-1", "sentinel1", "backscatter"})
MULTIMODAL_KEYWORDS = frozenset({"optical", "radar", "compare", "multimodal"})


def _extract_tokens(query: str) -> set[str]:
    tokens: set[str] = set()
    for word in query.split():
        cleaned = word.strip(".,!?\"'").lower()
        tokens.add(cleaned)
        tokens.update(part for part in cleaned.split("-") if part)
    return tokens

BASE_TOOLS = [
    PlannerToolName.FETCH_IMAGERY,
    PlannerToolName.DETECT_CHANGE,
    PlannerToolName.FUSE_EVIDENCE,
    PlannerToolName.GENERATE_EVIDENCE,
]


def _intent_from_query(query: str) -> QueryIntent:
    if is_building_temporal_query(query):
        return QueryIntent.BUILDING_TEMPORAL_CHANGE

    tokens = _extract_tokens(query)
    has_construction = bool(tokens & CONSTRUCTION_KEYWORDS) or "building" in tokens
    has_sar = bool(tokens & SAR_KEYWORDS)
    has_multimodal = bool(tokens & MULTIMODAL_KEYWORDS) or (
        "optical" in tokens and ("radar" in tokens or "sar" in tokens)
    )

    if has_construction and (has_sar or has_multimodal):
        return QueryIntent.MULTIMODAL_COMPARISON
    if has_construction:
        return QueryIntent.CONSTRUCTION
    if has_sar and not has_construction:
        return QueryIntent.RADAR_CHANGE
    return QueryIntent.SPECTRAL_CHANGE


def build_deterministic_plan(
    request: QueryRequest,
    *,
    planner: str = "deterministic",
    image_modality: ImageModality | None = None,
) -> QueryAnalysisPlan:
    """Keyword-based constrained planner (safe fallback)."""
    if request.is_cross_modal_upload:
        return QueryAnalysisPlan(
            user_intent=QueryIntent.CROSS_MODAL_OPTICAL_SAR,
            requested_modalities=[RequestedModality.OPTICAL, RequestedModality.SAR],
            analysis_profile=AnalysisProfileName.NONE,
            required_tools=[
                PlannerToolName.OPTICAL_ANALYSIS,
                PlannerToolName.SAR_ANALYSIS,
                PlannerToolName.CROSS_MODAL_FUSION,
                PlannerToolName.GENERATE_EVIDENCE,
            ],
            earlier_date=None,
            later_date=None,
            sensor_requirement=SensorRequirement.NOT_APPLICABLE,
            aoi_required=False,
            user_intent_summary="Route to uploaded cross-modal optical+SAR joint analysis.",
            planner=planner,  # type: ignore[arg-type]
        )

    if request.is_bi_temporal_upload:
        return QueryAnalysisPlan(
            user_intent=QueryIntent.BI_TEMPORAL_CHANGE_VQA,
            requested_modalities=[RequestedModality.OPTICAL],
            analysis_profile=AnalysisProfileName.NONE,
            required_tools=[
                PlannerToolName.DETECT_CHANGE,
                PlannerToolName.CHANGE_UNDERSTANDING,
                PlannerToolName.GENERATE_EVIDENCE,
            ],
            earlier_date=None,
            later_date=None,
            sensor_requirement=SensorRequirement.NOT_APPLICABLE,
            aoi_required=False,
            user_intent_summary="Route to uploaded bi-temporal change detection and interpretation.",
            planner=planner,  # type: ignore[arg-type]
        )

    if request.is_single_image_vqa:
        modality = image_modality or ImageModality.OPTICAL
        requested = (
            [RequestedModality.SAR]
            if modality == ImageModality.SAR
            else [RequestedModality.OPTICAL]
        )
        intent = single_image_intent_from_query(request.query)
        if intent == QueryIntent.SINGLE_IMAGE_CAPTION:
            return QueryAnalysisPlan(
                user_intent=QueryIntent.SINGLE_IMAGE_CAPTION,
                requested_modalities=requested,
                analysis_profile=AnalysisProfileName.NONE,
                required_tools=[
                    PlannerToolName.GEOCHAT_CAPTION,
                    PlannerToolName.GENERATE_EVIDENCE,
                ],
                earlier_date=None,
                later_date=None,
                sensor_requirement=SensorRequirement.NOT_APPLICABLE,
                aoi_required=False,
                user_intent_summary="Route to GeoChat single-image scene description specialist.",
                planner=planner,  # type: ignore[arg-type]
            )
        return QueryAnalysisPlan(
            user_intent=QueryIntent.SINGLE_IMAGE_VQA,
            requested_modalities=requested,
            analysis_profile=AnalysisProfileName.NONE,
            required_tools=[
                PlannerToolName.GEOCHAT_VQA,
                PlannerToolName.GENERATE_EVIDENCE,
            ],
            earlier_date=None,
            later_date=None,
            sensor_requirement=SensorRequirement.NOT_APPLICABLE,
            aoi_required=False,
            user_intent_summary="Route to GeoChat single-image VQA specialist.",
            planner=planner,  # type: ignore[arg-type]
        )

    intent = _intent_from_query(request.query)

    if intent == QueryIntent.BUILDING_TEMPORAL_CHANGE:
        return QueryAnalysisPlan(
            user_intent=intent,
            requested_modalities=[RequestedModality.OPTICAL],
            analysis_profile=AnalysisProfileName.NONE,
            required_tools=[PlannerToolName.IMAGERY_POLICY],
            earlier_date=request.earlier_date,
            later_date=request.later_date,
            sensor_requirement=SensorRequirement.SENTINEL_2,
            user_intent_summary=(
                "Route to building-instance temporal imagery policy "
                "(segmentation not yet implemented)."
            ),
            planner=planner,  # type: ignore[arg-type]
        )

    if intent == QueryIntent.RADAR_CHANGE:
        return QueryAnalysisPlan(
            user_intent=intent,
            requested_modalities=[RequestedModality.SAR],
            analysis_profile=AnalysisProfileName.NONE,
            required_tools=BASE_TOOLS,
            earlier_date=request.earlier_date,
            later_date=request.later_date,
            sensor_requirement=SensorRequirement.SENTINEL_1,
            user_intent_summary="Route to Sentinel-1 SAR change detection.",
            planner=planner,  # type: ignore[arg-type]
        )

    if intent == QueryIntent.CONSTRUCTION:
        return QueryAnalysisPlan(
            user_intent=intent,
            requested_modalities=[RequestedModality.OPTICAL, RequestedModality.SEMANTIC],
            analysis_profile=AnalysisProfileName.BUILDING_CONSTRUCTION,
            required_tools=[
                *BASE_TOOLS[:2],
                PlannerToolName.ANALYZE_SEMANTICS,
                *BASE_TOOLS[2:],
            ],
            earlier_date=request.earlier_date,
            later_date=request.later_date,
            sensor_requirement=SensorRequirement.SENTINEL_2,
            user_intent_summary="Route to optical CVA and Dynamic World built semantic analysis.",
            planner=planner,  # type: ignore[arg-type]
        )

    if intent == QueryIntent.MULTIMODAL_COMPARISON:
        return QueryAnalysisPlan(
            user_intent=intent,
            requested_modalities=[
                RequestedModality.OPTICAL,
                RequestedModality.SEMANTIC,
                RequestedModality.SAR,
            ],
            analysis_profile=AnalysisProfileName.BUILDING_CONSTRUCTION,
            required_tools=[
                PlannerToolName.FETCH_IMAGERY,
                PlannerToolName.DETECT_CHANGE,
                PlannerToolName.ANALYZE_SEMANTICS,
                PlannerToolName.DETECT_SAR_CHANGE,
                PlannerToolName.FUSE_EVIDENCE,
                PlannerToolName.GENERATE_EVIDENCE,
            ],
            earlier_date=request.earlier_date,
            later_date=request.later_date,
            sensor_requirement=SensorRequirement.SENTINEL_2_AND_1,
            user_intent_summary="Route to optical CVA, Dynamic World semantics, and Sentinel-1 SAR with fusion.",
            planner=planner,  # type: ignore[arg-type]
        )

    return QueryAnalysisPlan(
        user_intent=QueryIntent.SPECTRAL_CHANGE,
        requested_modalities=[RequestedModality.OPTICAL],
        analysis_profile=AnalysisProfileName.NONE,
        required_tools=BASE_TOOLS,
        earlier_date=request.earlier_date,
        later_date=request.later_date,
        sensor_requirement=SensorRequirement.SENTINEL_2,
        user_intent_summary="Route to Sentinel-2 CVA spectral change detection.",
        planner=planner,  # type: ignore[arg-type]
    )


def resolve_analysis_profile(query: str) -> str | None:
    plan = build_deterministic_plan(
        QueryRequest(
            query=query,
            aoi=_minimal_aoi(),
            earlier_date=date(2024, 1, 1),
            later_date=date(2024, 6, 1),
        )
    )
    return plan.profile


def _minimal_aoi():
    from app.schemas.domain import AOI, GeoJSONGeometry

    return AOI(
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[[[0.0, 0.0], [0.01, 0.0], [0.01, 0.01], [0.0, 0.01], [0.0, 0.0]]],
        )
    )
