from __future__ import annotations

import json
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.schemas.domain import QueryRequest
from app.schemas.input import ImageModality
from app.schemas.planning import FORBIDDEN_PLAN_FIELDS, PlanQueryOutput, QueryAnalysisPlan
from app.services.planner.deterministic import build_deterministic_plan
from app.services.planner.registry import validate_tool_names


class LLMPlannerClient(Protocol):
    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


class MockLLMPlannerClient:
    """Test seam for structured LLM planner output."""

    def __init__(self, response: dict[str, Any] | None = None, *, raises: Exception | None = None) -> None:
        self._response = response
        self._raises = raises

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if self._raises:
            raise self._raises
        if self._response is None:
            raise RuntimeError("mock LLM response not configured")
        return self._response


class OpenAILLMPlannerClient:
    """Optional OpenAI-compatible structured JSON planner."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        content = body["choices"][0]["message"]["content"]
        return json.loads(content)


def _reject_forbidden_fields(payload: dict[str, Any]) -> None:
    for key in payload:
        if key in FORBIDDEN_PLAN_FIELDS:
            raise ValueError(f"forbidden planner field: {key}")


def _system_prompt() -> str:
    return (
        "You are a query planner for SatQuery AI. "
        "Return ONLY a JSON object matching the QueryAnalysisPlan schema. "
        "Select tools and modalities only. Never output evidence values, "
        "confidence, areas, counts, GeoJSON, or claim types."
    )


def _user_prompt(request: QueryRequest) -> str:
    payload: dict[str, object] = {
        "query": request.query,
        "allowed_tools": [
            "fetch_imagery",
            "detect_change",
            "analyze_semantics",
            "detect_sar_change",
            "fuse_evidence",
            "generate_evidence",
            "geochat_vqa",
            "geochat_caption",
            "change_understanding",
            "optical_analysis",
            "sar_analysis",
            "cross_modal_fusion",
        ],
        "allowed_intents": [
            "spectral_change",
            "construction",
            "radar_change",
            "multimodal_comparison",
            "single_image_vqa",
            "single_image_caption",
            "bi_temporal_change_vqa",
            "cross_modal_optical_sar",
        ],
    }
    if request.is_cross_modal_upload:
        payload["input_mode"] = "cross_modal_upload"
        payload["optical_image_id"] = request.optical_image_id
        payload["sar_image_id"] = request.sar_image_id
    elif request.is_bi_temporal_upload:
        payload["input_mode"] = "bi_temporal_upload"
        payload["earlier_image_id"] = request.earlier_image_id
        payload["later_image_id"] = request.later_image_id
    elif request.is_single_image_vqa:
        payload["input_mode"] = "single_image"
        payload["image_id"] = request.image_id
    else:
        payload["earlier_date"] = request.earlier_date.isoformat() if request.earlier_date else None
        payload["later_date"] = request.later_date.isoformat() if request.later_date else None
    return json.dumps(payload)


async def plan_with_llm(
    request: QueryRequest,
    client: LLMPlannerClient,
) -> QueryAnalysisPlan:
    raw = await client.complete_json(_system_prompt(), _user_prompt(request))
    _reject_forbidden_fields(raw)
    plan = QueryAnalysisPlan.model_validate({**raw, "planner": "llm"})
    validate_tool_names(plan.required_tools)
    return plan


def get_llm_client() -> LLMPlannerClient | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return OpenAILLMPlannerClient(settings.openai_api_key, settings.openai_model)


async def plan_query(
    request: QueryRequest,
    *,
    llm_client: LLMPlannerClient | None = None,
    image_modality: ImageModality | None = None,
) -> PlanQueryOutput:
    settings = get_settings()
    if settings.query_planner != "llm" or request.is_single_image_vqa or request.is_bi_temporal_upload or request.is_cross_modal_upload:
        return PlanQueryOutput(
            plan=build_deterministic_plan(request, image_modality=image_modality),
            planner="deterministic",
            fallback_used=False,
        )

    client = llm_client or get_llm_client()
    if client is None:
        return PlanQueryOutput(
            plan=build_deterministic_plan(request, image_modality=image_modality),
            planner="deterministic",
            fallback_used=True,
        )

    try:
        plan = await plan_with_llm(request, client)
        return PlanQueryOutput(plan=plan, planner="llm", fallback_used=False)
    except (ValidationError, ValueError, SatQueryError, httpx.HTTPError, KeyError, json.JSONDecodeError):
        return PlanQueryOutput(
            plan=build_deterministic_plan(request, image_modality=image_modality),
            planner="deterministic",
            fallback_used=True,
        )
