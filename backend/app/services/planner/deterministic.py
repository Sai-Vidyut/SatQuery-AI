from __future__ import annotations

from datetime import date

from app.schemas.domain import QueryRequest
from app.schemas.planning import (
    AnalysisProfileName,
    PlannerToolName,
    QueryAnalysisPlan,
    QueryIntent,
    RequestedModality,
    SensorRequirement,
)
BUILDING_CONSTRUCTION_PROFILE = "building_construction"
CONSTRUCTION_KEYWORDS = frozenset({"construction", "building", "built", "development"})
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
    tokens = _extract_tokens(query)
    has_construction = bool(tokens & CONSTRUCTION_KEYWORDS)
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
) -> QueryAnalysisPlan:
    """Keyword-based constrained planner (safe fallback)."""
    intent = _intent_from_query(request.query)

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
