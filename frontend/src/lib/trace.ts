import type { PlanQueryMetadata, TraceStep } from "@/types/domain";

const TOOL_LABELS: Record<string, string> = {
  plan_query: "Plan query",
  fetch_imagery: "Acquire imagery",
  detect_change: "Detect change",
  analyze_semantics: "Analyze semantics",
  detect_sar_change: "Detect SAR change",
  fuse_evidence: "Fuse evidence",
  input_validation: "Validate input",
  geochat_vqa: "GeoChat VQA",
  geochat_caption: "GeoChat scene caption",
  change_understanding: "Change understanding",
  optical_analysis: "Optical analysis",
  sar_analysis: "SAR analysis",
  cross_modal_fusion: "Cross-modal fusion",
  generate_evidence: "Generate evidence",
};

export function traceStepLabel(step: TraceStep): string {
  const base = TOOL_LABELS[step.tool_name] ?? step.tool_name;
  if (step.summary?.toLowerCase().includes("skipped")) {
    return `${base} (skipped)`;
  }
  if (step.status === "running") {
    return `${base}…`;
  }
  return base;
}

export function isPlanQueryMetadata(
  metadata: TraceStep["metadata"],
): metadata is PlanQueryMetadata {
  return metadata != null && typeof metadata === "object" && "planner" in metadata;
}

export function formatDuration(ms: number | null | undefined): string | null {
  if (ms == null) return null;
  return `${(ms / 1000).toFixed(1)}s`;
}
