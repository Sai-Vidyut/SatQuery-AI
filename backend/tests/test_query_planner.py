from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.domain import AOI, GeoJSONGeometry, QueryRequest
from app.schemas.planning import (
    AnalysisProfileName,
    PlannerToolName,
    QueryAnalysisPlan,
    QueryIntent,
    RequestedModality,
    SensorRequirement,
)
from app.services.planner.deterministic import build_deterministic_plan
from app.services.planner.registry import validate_tool_names
from app.services.planner.service import MockLLMPlannerClient, plan_query, plan_with_llm
from app.services.query_profiles import resolve_analysis_plan, resolve_analysis_profile


def _request(query: str) -> QueryRequest:
    return QueryRequest(
        query=query,
        aoi=AOI(
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[[[77.56, 12.94], [77.60, 12.94], [77.60, 12.98], [77.56, 12.98], [77.56, 12.94]]],
            )
        ),
        earlier_date=date(2024, 12, 1),
        later_date=date(2025, 3, 1),
    )


def _base_plan(**overrides):
    payload = {
        "user_intent": QueryIntent.SPECTRAL_CHANGE,
        "requested_modalities": [RequestedModality.OPTICAL],
        "analysis_profile": AnalysisProfileName.NONE,
        "required_tools": [
            PlannerToolName.FETCH_IMAGERY,
            PlannerToolName.DETECT_CHANGE,
            PlannerToolName.FUSE_EVIDENCE,
            PlannerToolName.GENERATE_EVIDENCE,
        ],
        "earlier_date": date(2024, 12, 1),
        "later_date": date(2025, 3, 1),
        "sensor_requirement": SensorRequirement.SENTINEL_2,
        "user_intent_summary": "Spectral change routing only.",
    }
    payload.update(overrides)
    return QueryAnalysisPlan(**payload)


@pytest.mark.parametrize(
    ("query", "intent", "tools", "modalities", "sensor"),
    [
        (
            "Show me significant spectral change.",
            QueryIntent.SPECTRAL_CHANGE,
            [
                "fetch_imagery",
                "detect_change",
                "fuse_evidence",
                "generate_evidence",
            ],
            ["optical"],
            SensorRequirement.SENTINEL_2,
        ),
        (
            "Show me significant new construction.",
            QueryIntent.CONSTRUCTION,
            [
                "fetch_imagery",
                "detect_change",
                "analyze_semantics",
                "fuse_evidence",
                "generate_evidence",
            ],
            ["optical", "semantic"],
            SensorRequirement.SENTINEL_2,
        ),
        (
            "Show me radar change.",
            QueryIntent.RADAR_CHANGE,
            [
                "fetch_imagery",
                "detect_change",
                "fuse_evidence",
                "generate_evidence",
            ],
            ["sar"],
            SensorRequirement.SENTINEL_1,
        ),
        (
            "Show me significant new construction and compare optical and radar evidence.",
            QueryIntent.MULTIMODAL_COMPARISON,
            [
                "fetch_imagery",
                "detect_change",
                "analyze_semantics",
                "detect_sar_change",
                "fuse_evidence",
                "generate_evidence",
            ],
            ["optical", "semantic", "sar"],
            SensorRequirement.SENTINEL_2_AND_1,
        ),
    ],
)
def test_deterministic_intent_plans(query, intent, tools, modalities, sensor):
    plan = build_deterministic_plan(_request(query))
    assert plan.user_intent == intent
    assert [t.value for t in plan.required_tools] == tools
    assert [m.value for m in plan.requested_modalities] == modalities
    assert plan.sensor_requirement == sensor
    assert plan.planner == "deterministic"


def test_construction_keyword_profile_matching():
    assert resolve_analysis_profile("Show me significant new construction.") == "building_construction"
    assert resolve_analysis_profile("building growth in AOI") == "building_construction"
    assert resolve_analysis_profile("Show spectral change in vegetation.") is None


def test_invalid_tool_name_rejected():
    with pytest.raises(ValidationError):
        QueryAnalysisPlan.model_validate(
            {
                "user_intent": "spectral_change",
                "requested_modalities": ["optical"],
                "analysis_profile": "none",
                "required_tools": ["fetch_imagery", "run_magic"],
                "earlier_date": "2024-12-01",
                "later_date": "2025-03-01",
                "sensor_requirement": "sentinel-2",
                "user_intent_summary": "bad tool",
            }
        )


def test_invalid_modality_rejected():
    with pytest.raises(ValidationError, match="semantic modality requires analyze_semantics"):
        _base_plan(
            requested_modalities=[RequestedModality.OPTICAL, RequestedModality.SEMANTIC],
        )


def test_unsupported_combination_sar_on_spectral():
    with pytest.raises(ValidationError, match="detect_sar_change is not valid for spectral_change"):
        _base_plan(
            required_tools=[
                PlannerToolName.FETCH_IMAGERY,
                PlannerToolName.DETECT_CHANGE,
                PlannerToolName.DETECT_SAR_CHANGE,
                PlannerToolName.FUSE_EVIDENCE,
                PlannerToolName.GENERATE_EVIDENCE,
            ],
        )


def test_evidence_fields_cannot_enter_plan():
    with pytest.raises(ValidationError):
        QueryAnalysisPlan.model_validate(
            {
                "user_intent": "spectral_change",
                "requested_modalities": ["optical"],
                "analysis_profile": "none",
                "required_tools": [
                    "fetch_imagery",
                    "detect_change",
                    "fuse_evidence",
                    "generate_evidence",
                ],
                "earlier_date": "2024-12-01",
                "later_date": "2025-03-01",
                "sensor_requirement": "sentinel-2",
                "user_intent_summary": "x",
                "confidence": 0.9,
            }
        )


@pytest.mark.asyncio
async def test_deterministic_fallback_when_llm_not_configured(monkeypatch):
    monkeypatch.setenv("QUERY_PLANNER", "llm")
    from app.core.config import get_settings

    get_settings.cache_clear()
    output = await plan_query(_request("Show me radar change."))
    assert output.planner == "deterministic"
    assert output.fallback_used is True
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_llm_structured_output_validation(monkeypatch):
    monkeypatch.setenv("QUERY_PLANNER", "llm")
    from app.core.config import get_settings

    get_settings.cache_clear()
    valid = {
        "user_intent": "radar_change",
        "requested_modalities": ["sar"],
        "analysis_profile": "none",
        "required_tools": [
            "fetch_imagery",
            "detect_change",
            "fuse_evidence",
            "generate_evidence",
        ],
        "earlier_date": "2024-12-01",
        "later_date": "2025-03-01",
        "sensor_requirement": "sentinel-1",
        "user_intent_summary": "Radar routing.",
    }
    client = MockLLMPlannerClient(valid)
    output = await plan_query(_request("Show me radar change."), llm_client=client)
    assert output.planner == "llm"
    assert output.plan.user_intent == QueryIntent.RADAR_CHANGE
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_malformed_llm_output_falls_back(monkeypatch):
    monkeypatch.setenv("QUERY_PLANNER", "llm")
    from app.core.config import get_settings

    get_settings.cache_clear()
    bad = {
        "user_intent": "spectral_change",
        "requested_modalities": ["optical"],
        "analysis_profile": "none",
        "required_tools": [
            "fetch_imagery",
            "detect_change",
            "detect_sar_change",
            "fuse_evidence",
            "generate_evidence",
        ],
        "earlier_date": "2024-12-01",
        "later_date": "2025-03-01",
        "sensor_requirement": "sentinel-2",
        "user_intent_summary": "invalid combo",
    }
    client = MockLLMPlannerClient(bad)
    output = await plan_query(_request("Show me spectral change."), llm_client=client)
    assert output.planner == "deterministic"
    assert output.fallback_used is True
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_forbidden_llm_evidence_field_rejected():
    with pytest.raises(ValueError, match="forbidden planner field"):
        await plan_with_llm(
            _request("Show change."),
            MockLLMPlannerClient({"confidence": 1.0, "user_intent": "spectral_change"}),
        )


@pytest.mark.asyncio
async def test_planner_trace_metadata_in_controller():
    from app.services.query_controller import QueryController

    controller = QueryController()
    result = await controller.submit(_request("Show me significant spectral change."))
    plan_step = result.trace[0]
    assert plan_step.tool_name == "plan_query"
    assert plan_step.metadata is not None
    assert plan_step.metadata["planner"] == "deterministic"
    assert plan_step.metadata["intent"] == "spectral_change"
    assert "fetch_imagery" in plan_step.metadata["required_tools"]
    assert plan_step.metadata["planner_version"] == "1.0.0"


def test_resolve_analysis_plan_backward_compat():
    plan = resolve_analysis_plan("Show me significant new construction.")
    assert plan.run_semantic is True
    assert plan.profile == "building_construction"


def test_validate_tool_names_registry():
    validate_tool_names([PlannerToolName.FETCH_IMAGERY])
