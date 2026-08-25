"use client";

import type { TraceStep } from "@/types/domain";
import { formatDuration, isPlanQueryMetadata, traceStepLabel } from "@/lib/trace";

type Props = {
  steps: TraceStep[];
  loading?: boolean;
};

function statusColor(status: TraceStep["status"]): string {
  switch (status) {
    case "completed":
      return "var(--sq-success)";
    case "running":
      return "var(--sq-amber)";
    case "failed":
      return "var(--sq-danger)";
    default:
      return "var(--sq-text-faint)";
  }
}

function PlanQueryDetails({ metadata }: { metadata: TraceStep["metadata"] }) {
  if (!metadata || !isPlanQueryMetadata(metadata)) return null;
  return (
    <dl className="mt-1 space-y-0.5 text-[10px] text-[var(--sq-text-muted)]">
      {metadata.planner ? (
        <div className="flex justify-between gap-2">
          <dt>Planner</dt>
          <dd className="tabular-nums" style={{ fontFamily: "var(--sq-font-mono)" }}>
            {metadata.planner}
          </dd>
        </div>
      ) : null}
      {metadata.intent ? (
        <div className="flex justify-between gap-2">
          <dt>Intent</dt>
          <dd style={{ fontFamily: "var(--sq-font-mono)" }}>{metadata.intent}</dd>
        </div>
      ) : null}
      {metadata.required_tools?.length ? (
        <div>
          <dt>Tools</dt>
          <dd className="mt-0.5 break-words" style={{ fontFamily: "var(--sq-font-mono)" }}>
            {metadata.required_tools.join(", ")}
          </dd>
        </div>
      ) : null}
      {metadata.requested_modalities?.length ? (
        <div className="flex justify-between gap-2">
          <dt>Modalities</dt>
          <dd style={{ fontFamily: "var(--sq-font-mono)" }}>
            {metadata.requested_modalities.join(", ")}
          </dd>
        </div>
      ) : null}
      {metadata.fallback_used != null ? (
        <div className="flex justify-between gap-2">
          <dt>Fallback</dt>
          <dd>{metadata.fallback_used ? "yes" : "no"}</dd>
        </div>
      ) : null}
    </dl>
  );
}

const SKELETON_STEPS = [
  "plan_query",
  "fetch_imagery",
  "detect_change",
  "fuse_evidence",
  "generate_evidence",
];

export function ExecutionTrace({ steps, loading }: Props) {
  if (loading) {
    return (
      <section
        data-testid="trace"
        className="border-b border-[var(--sq-line)] px-3 py-2"
        aria-live="polite"
        aria-label="Execution trace"
        aria-busy="true"
      >
        <h2 className="mb-2 text-[11px] font-medium uppercase tracking-[0.04em] text-[var(--sq-text-muted)]">
          Trace
        </h2>
        <ul className="space-y-1.5">
          {SKELETON_STEPS.map((name) => (
            <li key={name} className="flex items-center gap-2 text-[12px] text-[var(--sq-text-faint)]">
              <span className="inline-block h-1.5 w-1.5 shrink-0 bg-[var(--sq-text-faint)]" aria-hidden />
              <span>{traceStepLabel({ id: name, tool_name: name, status: "running" })}</span>
            </li>
          ))}
        </ul>
      </section>
    );
  }

  if (steps.length === 0) return null;

  return (
    <section
      data-testid="trace"
      className="border-b border-[var(--sq-line)] px-3 py-2"
      aria-live="polite"
      aria-label="Execution trace"
    >
      <h2 className="mb-2 text-[11px] font-medium uppercase tracking-[0.04em] text-[var(--sq-text-muted)]">
        Trace
      </h2>
      <ul className="space-y-1.5">
        {steps.map((step) => (
          <li key={step.id} className="flex items-start gap-2 text-[12px]">
            <span
              className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0"
              style={{ background: statusColor(step.status) }}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <div className="flex justify-between gap-2">
                <span>{traceStepLabel(step)}</span>
                {formatDuration(step.duration_ms) ? (
                  <span
                    className="tabular-nums text-[var(--sq-text-muted)]"
                    style={{ fontFamily: "var(--sq-font-mono)", fontSize: 11 }}
                  >
                    {formatDuration(step.duration_ms)}
                  </span>
                ) : null}
              </div>
              {step.tool_name === "plan_query" && step.metadata ? (
                <PlanQueryDetails metadata={step.metadata} />
              ) : null}
              {step.error ? (
                <p className="text-[11px] text-[var(--sq-danger)]">{step.error}</p>
              ) : null}
              {step.summary &&
              step.tool_name !== "plan_query" &&
              !step.summary.toLowerCase().includes("running") ? (
                <p className="text-[10px] text-[var(--sq-text-faint)]">{step.summary}</p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
