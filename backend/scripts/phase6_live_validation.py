#!/usr/bin/env python3
"""Phase 6 live validation — Bengaluru AOI, four planner queries."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date
from time import perf_counter

# EE production config
os.environ.setdefault("IMAGERY_PROVIDER", "earth_engine")
os.environ.setdefault("CHANGE_DETECTOR", "earth_engine")
os.environ.setdefault("SEMANTIC_ANALYZER", "earth_engine")
os.environ.setdefault("SAR_CHANGE_DETECTOR", "earth_engine")
os.environ.setdefault("EARTH_ENGINE_PROJECT", "satquery-ai")
os.environ.setdefault("QUERY_PLANNER", "deterministic")

from app.schemas.domain import AOI, GeoJSONGeometry, QueryRequest
from app.services.query_controller import QueryController

BENGALURU_AOI = AOI(
    geometry=GeoJSONGeometry(
        type="Polygon",
        coordinates=[[[77.56, 12.94], [77.60, 12.94], [77.60, 12.98], [77.56, 12.98], [77.56, 12.94]]],
    )
)

QUERIES = [
    ("Show me significant spectral change.", ["fetch_imagery", "detect_change", "fuse_evidence", "generate_evidence"]),
    (
        "Show me significant new construction.",
        ["fetch_imagery", "detect_change", "analyze_semantics", "fuse_evidence", "generate_evidence"],
    ),
    ("Show me radar change.", ["fetch_imagery", "detect_change", "fuse_evidence", "generate_evidence"]),
    (
        "Show me significant new construction and compare optical and radar evidence.",
        [
            "fetch_imagery",
            "detect_change",
            "analyze_semantics",
            "detect_sar_change",
            "fuse_evidence",
            "generate_evidence",
        ],
    ),
]


async def run_one(controller: QueryController, query: str, expected_tools: list[str]) -> dict:
    request = QueryRequest(
        query=query,
        aoi=BENGALURU_AOI,
        earlier_date=date(2024, 12, 1),
        later_date=date(2025, 3, 1),
    )
    t0 = perf_counter()
    result = await controller.submit(request)
    runtime_s = round(perf_counter() - t0, 2)

    plan_step = result.trace[0]
    plan_meta = plan_step.metadata or {}
    tool_names = [s.tool_name for s in result.trace if s.tool_name != "plan_query"]

    return {
        "query": query,
        "planner": plan_meta.get("planner"),
        "intent": plan_meta.get("intent"),
        "plan_tools": plan_meta.get("required_tools"),
        "expected_tools": expected_tools,
        "tools_match": plan_meta.get("required_tools") == expected_tools,
        "execution_trace": [s.tool_name for s in result.trace],
        "modalities": plan_meta.get("requested_modalities"),
        "planner_version": plan_meta.get("planner_version"),
        "evidence_count": len(result.evidence),
        "confidence": result.confidence,
        "answer": result.answer,
        "metrics": [{"name": m.name, "value": m.value, "unit": m.unit} for m in result.metrics],
        "runtime_s": runtime_s,
    }


async def main() -> int:
    controller = QueryController()
    reports = []
    for query, expected in QUERIES:
        print(f"\n=== {query} ===", flush=True)
        report = await run_one(controller, query, expected)
        reports.append(report)
        print(json.dumps(report, indent=2), flush=True)

    all_match = all(r["tools_match"] for r in reports)
    print(f"\nAll tool plans match expected: {all_match}", flush=True)
    return 0 if all_match else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
