#!/usr/bin/env python3
"""Phase 6 LLM planner validation — guardrails + live EE (OpenAI or mock fallback)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date
from time import perf_counter

os.environ["QUERY_PLANNER"] = "llm"
os.environ.setdefault("IMAGERY_PROVIDER", "earth_engine")
os.environ.setdefault("CHANGE_DETECTOR", "earth_engine")
os.environ.setdefault("SEMANTIC_ANALYZER", "earth_engine")
os.environ.setdefault("SAR_CHANGE_DETECTOR", "earth_engine")
os.environ.setdefault("EARTH_ENGINE_PROJECT", "satquery-ai")

from pydantic import ValidationError

import app.services.planner.service as planner_service
from app.core.config import get_settings
from app.schemas.domain import AOI, GeoJSONGeometry, QueryRequest
from app.schemas.planning import QueryAnalysisPlan
from app.services.planner.deterministic import build_deterministic_plan
from app.services.planner.service import MockLLMPlannerClient, plan_query, plan_with_llm
from app.services.query_controller import QueryController

get_settings.cache_clear()

BENGALURU_AOI = AOI(
    geometry=GeoJSONGeometry(
        type="Polygon",
        coordinates=[[[77.56, 12.94], [77.60, 12.94], [77.60, 12.98], [77.56, 12.98], [77.56, 12.94]]],
    )
)

QUERIES = [
    "Show me significant spectral change.",
    "Show me significant new construction.",
    "Show me radar change.",
    "Show me significant new construction and compare optical and radar evidence.",
]

# Deterministic EE baseline from prior Phase 6 validation (same AOI/dates).
DETERMINISTIC_BASELINE = {
    "Show me significant spectral change.": {"evidence_count": 5, "confidence": 0.45},
    "Show me significant new construction.": {"evidence_count": 5, "confidence": 0.45},
    "Show me radar change.": {"evidence_count": 1, "confidence": 0.864},
    "Show me significant new construction and compare optical and radar evidence.": {
        "evidence_count": 6,
        "confidence": 0.519,
    },
}


def _request(query: str) -> QueryRequest:
    return QueryRequest(
        query=query,
        aoi=BENGALURU_AOI,
        earlier_date=date(2024, 12, 1),
        later_date=date(2025, 3, 1),
    )


def _plan_payload(plan: QueryAnalysisPlan) -> dict:
    return json.loads(plan.model_dump_json())


def _evidence_summary(result) -> list[dict]:
    return [
        {
            "id": r.id,
            "confidence": r.confidence,
            "claim_type": r.metadata.get("claim_type"),
            "evidence_modality": r.metadata.get("evidence_modality"),
        }
        for r in result.evidence
    ]


def _llm_response_for(query: str) -> dict:
    det = build_deterministic_plan(_request(query))
    payload = json.loads(det.model_dump_json())
    payload.pop("planner", None)
    return payload


class DynamicMockLLMClient:
    """Returns deterministic-equivalent plans keyed by query in user_prompt JSON."""

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        data = json.loads(user_prompt)
        return _llm_response_for(data["query"])


async def run_guardrails() -> dict:
    req = _request("Show me spectral change.")
    results: dict = {}

    try:
        await plan_with_llm(req, MockLLMPlannerClient({"confidence": 0.9}))
        results["forbidden_field_rejected"] = False
    except ValueError:
        results["forbidden_field_rejected"] = True

    bad = _llm_response_for("Show me spectral change.")
    bad["required_tools"] = [
        "fetch_imagery",
        "detect_change",
        "detect_sar_change",
        "fuse_evidence",
        "generate_evidence",
    ]
    out = await plan_query(req, llm_client=MockLLMPlannerClient(bad))
    results["invalid_plan_fallback"] = out.fallback_used and out.planner == "deterministic"

    good = _llm_response_for("Show me radar change.")
    out_good = await plan_query(_request("Show me radar change."), llm_client=MockLLMPlannerClient(good))
    results["valid_llm_plan_accepted"] = out_good.planner == "llm" and not out_good.fallback_used

    try:
        QueryAnalysisPlan.model_validate({**_llm_response_for("Show me spectral change."), "confidence": 1.0})
        results["schema_blocks_evidence_fields"] = False
    except ValidationError:
        results["schema_blocks_evidence_fields"] = True

    return results


async def run_live_query(controller: QueryController, query: str) -> dict:
    request = _request(query)
    det = build_deterministic_plan(request)
    plan_output = await plan_query(request)

    t0 = perf_counter()
    result = await controller.submit(request)
    runtime_s = round(perf_counter() - t0, 2)

    baseline = DETERMINISTIC_BASELINE[query]
    same_tools = [t.value for t in plan_output.plan.required_tools] == [t.value for t in det.required_tools]
    parity = {
        "same_tools_as_deterministic": same_tools,
        "evidence_count_matches_baseline": len(result.evidence) == baseline["evidence_count"],
        "confidence_matches_baseline": abs(result.confidence - baseline["confidence"]) < 1e-9,
    }

    return {
        "query": query,
        "llm_plan": _plan_payload(plan_output.plan),
        "intent": plan_output.plan.user_intent.value,
        "required_tools": [t.value for t in plan_output.plan.required_tools],
        "requested_modalities": [m.value for m in plan_output.plan.requested_modalities],
        "planner": plan_output.planner,
        "fallback_used": plan_output.fallback_used,
        "execution_trace": [s.tool_name for s in result.trace],
        "evidence": _evidence_summary(result),
        "evidence_count": len(result.evidence),
        "confidence": result.confidence,
        "answer": result.answer,
        "runtime_s": runtime_s,
        "scientific_parity": parity,
    }


async def main() -> int:
    settings = get_settings()
    use_openai = bool(settings.openai_api_key)
    mode = "openai" if use_openai else "mock_llm_via_get_llm_client"

    print("=== Phase 6 LLM Planner Validation ===")
    print(
        json.dumps(
            {
                "query_planner": settings.query_planner,
                "openai_api_key_configured": use_openai,
                "openai_model": settings.openai_model,
                "execution_mode": mode,
            },
            indent=2,
        )
    )

    if not use_openai:
        planner_service.get_llm_client = lambda: DynamicMockLLMClient()
        print("\nNOTE: OPENAI_API_KEY not set — using DynamicMockLLMClient for LLM path validation.")

    print("\n=== Guardrail checks ===")
    guardrails = await run_guardrails()
    print(json.dumps(guardrails, indent=2))

    print(f"\n=== Live Bengaluru queries ({mode}) ===")
    controller = QueryController()
    reports = []
    for query in QUERIES:
        print(f"\n--- {query} ---", flush=True)
        report = await run_live_query(controller, query)
        reports.append(report)
        print(json.dumps(report, indent=2), flush=True)

    summary = {
        "mode": mode,
        "all_guardrails_pass": all(guardrails.values()),
        "all_used_llm_planner": all(r["planner"] == "llm" and not r["fallback_used"] for r in reports),
        "all_scientific_parity": all(
            r["scientific_parity"]["evidence_count_matches_baseline"]
            and r["scientific_parity"]["confidence_matches_baseline"]
            for r in reports
        ),
        "openai_key_required_for_provider_live_llm": not use_openai,
    }
    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2))
    ok = summary["all_guardrails_pass"] and summary["all_used_llm_planner"] and summary["all_scientific_parity"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
