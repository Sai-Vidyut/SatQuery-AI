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
    <dl className="mt-1 space-y-0.5 text-[10px] text-[var(--sq-text-faint)]">
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
        className="inspector-section"
        aria-live="polite"
        aria-label="Execution trace"
        aria-busy="true"
      >
        <p className="inspector-section__label">Trace</p>
        <ul className="m-0 list-none space-y-1.5 p-0">
          {SKELETON_STEPS.map((name) => (
            <li key={name} className="trace-row text-[var(--sq-text-faint)]">
              <span className="trace-mark bg-[var(--sq-text-faint)]" aria-hidden />
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
      className="inspector-section"
      aria-live="polite"
      aria-label="Execution trace"
    >
      <p className="inspector-section__label">Trace</p>
      <ul className="m-0 list-none space-y-1.5 p-0">
        {steps.map((step) => (
          <li key={step.id} className="trace-row">
            <span
              className="trace-mark"
              style={{ background: statusColor(step.status) }}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <div className="flex justify-between gap-2">
                <span>{traceStepLabel(step)}</span>
                {formatDuration(step.duration_ms) ? (
                  <span className="trace-row__duration">{formatDuration(step.duration_ms)}</span>
                ) : null}
              </div>
              {step.tool_name === "plan_query" && step.metadata ? (
                <PlanQueryDetails metadata={step.metadata} />
              ) : null}
              {step.error ? (
                <p className="mt-0.5 text-[11px] text-[var(--sq-danger)]">{step.error}</p>
              ) : null}
              {step.summary &&
              step.tool_name !== "plan_query" &&
              !step.summary.toLowerCase().includes("running") ? (
                <p className="mt-0.5 text-[10px] text-[var(--sq-text-faint)]">{step.summary}</p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
