from __future__ import annotations

from app.schemas.planning import PlannerToolName

REGISTERED_PLANNER_TOOLS: frozenset[PlannerToolName] = frozenset(PlannerToolName)

TOOL_DESCRIPTIONS: dict[PlannerToolName, str] = {
    PlannerToolName.IMAGERY_POLICY: "Evaluate catalog/upload imagery suitability for the product mode.",
    PlannerToolName.FETCH_IMAGERY: "Acquire Sentinel imagery for the AOI and date range.",
    PlannerToolName.DETECT_CHANGE: "Run optical CVA or SAR change detection on fetched imagery.",
    PlannerToolName.ANALYZE_SEMANTICS: "Run Dynamic World built semantic analysis on CVA regions.",
    PlannerToolName.DETECT_SAR_CHANGE: "Fetch Sentinel-1 imagery and run SAR change detection.",
    PlannerToolName.FUSE_EVIDENCE: "Fuse optical, semantic, and SAR evidence deterministically.",
    PlannerToolName.GENERATE_EVIDENCE: "Validate fused evidence and compute aggregate metrics.",
    PlannerToolName.GEOCHAT_VQA: "Run GeoChat-7B single-image visual question answering.",
    PlannerToolName.GEOCHAT_CAPTION: "Run GeoChat-7B single-image scene description / captioning.",
    PlannerToolName.CHANGE_UNDERSTANDING: "Interpret bi-temporal CVA output for the user question.",
    PlannerToolName.OPTICAL_ANALYSIS: "Analyze uploaded optical/multispectral imagery for cross-modal cues.",
    PlannerToolName.SAR_ANALYSIS: "Analyze uploaded SAR imagery for cross-modal cues.",
    PlannerToolName.CROSS_MODAL_FUSION: "Fuse uploaded optical and SAR analyses into joint evidence.",
}


def validate_tool_names(tools: list[PlannerToolName]) -> None:
    unknown = [t for t in tools if t not in REGISTERED_PLANNER_TOOLS]
    if unknown:
        raise ValueError(f"Unknown planner tools: {unknown}")


def list_registered_tools() -> list[dict[str, str]]:
    return [
        {"name": tool.value, "description": TOOL_DESCRIPTIONS[tool]}
        for tool in sorted(REGISTERED_PLANNER_TOOLS, key=lambda t: t.value)
    ]
