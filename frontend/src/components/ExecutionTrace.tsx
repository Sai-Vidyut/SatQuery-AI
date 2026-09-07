"use client";

import type { FetchImageryMetadata, PlanQueryMetadata, TraceStep } from "@/types/domain";
import { formatDuration, isPlanQueryMetadata, isFetchImageryMetadata, traceStepLabel } from "@/lib/trace";

type Props = {
  steps: TraceStep[];
  loading?: boolean;
};

function statusColor(status: TraceStep["status"]): string {
  switch (status) {
    case "completed":
      return "var(--success)";
    case "running":
      return "var(--accent)";
    case "failed":
      return "var(--danger)";
    default:
      return "var(--text-muted)";
  }
}

function PlanQueryDetails({ metadata }: { metadata: TraceStep["metadata"] }) {
  if (!metadata || !isPlanQueryMetadata(metadata)) return null;
  return (
    <dl className="mt-1 space-y-0.5 text-[10px] text-[var(--text-muted)]">
      {metadata.planner ? (
        <div className="flex justify-between gap-2">
          <dt>Planner</dt>
          <dd className="tabular-nums" style={{ fontFamily: "var(--font-sans)" }}>
            {metadata.planner}
          </dd>
        </div>
      ) : null}
      {metadata.intent ? (
        <div className="flex justify-between gap-2">
          <dt>Intent</dt>
          <dd style={{ fontFamily: "var(--font-sans)" }}>{metadata.intent}</dd>
        </div>
      ) : null}
      {metadata.required_tools?.length ? (
        <div>
          <dt>Tools</dt>
          <dd className="mt-0.5 break-words" style={{ fontFamily: "var(--font-sans)" }}>
            {metadata.required_tools.join(", ")}
          </dd>
        </div>
      ) : null}
      {metadata.requested_modalities?.length ? (
        <div className="flex justify-between gap-2">
          <dt>Modalities</dt>
          <dd style={{ fontFamily: "var(--font-sans)" }}>
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

function FetchImageryDetails({ metadata }: { metadata: FetchImageryMetadata }) {
  const t1 = metadata.t1;
  const t2 = metadata.t2;
  const strategy = metadata.imagery_strategy ?? "unknown";
  return (
    <dl className="mt-1 space-y-0.5 text-[10px] text-[var(--text-muted)]">
      <div>
        <dt>Imagery strategy</dt>
        <dd style={{ fontFamily: "var(--font-sans)" }}>
          {strategy}
          {metadata.composite_method ? ` (${metadata.composite_method})` : ""}
        </dd>
      </div>
      {metadata.demonstration_data ? (
        <div>
          <dt>Data source</dt>
          <dd className="text-[var(--accent)]">DEMONSTRATION DATA</dd>
        </div>
      ) : null}
      {t1 ? (
        <div>
          <dt>T1 requested / window</dt>
          <dd style={{ fontFamily: "var(--font-sans)" }}>
            {t1.requested_date ?? "?"} → {t1.window_start}–{t1.window_end} ·{" "}
            {t1.scene_count ?? "?"} scene(s)
          </dd>
        </div>
      ) : null}
      {t2 ? (
        <div>
          <dt>T2 requested / window</dt>
          <dd style={{ fontFamily: "var(--font-sans)" }}>
            {t2.requested_date ?? "?"} → {t2.window_start}–{t2.window_end} ·{" "}
            {t2.scene_count ?? "?"} scene(s)
          </dd>
        </div>
      ) : null}
      {metadata.fallback_events?.length ? (
        <div>
          <dt>Imagery fallback</dt>
          <dd className="mt-0.5 break-words" style={{ fontFamily: "var(--font-sans)" }}>
            {metadata.fallback_events
              .map((e) => `${String(e.epoch)}: ${String(e.policy_decision ?? "fallback")}`)
              .join("; ")}
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

function TimingSummary({ steps }: { steps: TraceStep[] }) {
  const timed = steps.filter((s) => s.duration_ms != null && s.duration_ms > 0);
  if (timed.length === 0) return null;
  const total = timed.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0);
  const keyTools = ["fetch_imagery", "detect_change", "analyze_semantics", "generate_evidence"];
  const breakdown = keyTools
    .map((name) => {
      const step = timed.find((s) => s.tool_name === name);
      return step ? `${name.replace(/_/g, " ")} ${formatDuration(step.duration_ms)}` : null;
    })
    .filter(Boolean);
  return (
    <p className="mt-2 text-[10px] text-[var(--text-muted)]" data-testid="trace-timing-summary">
      Timing: {breakdown.join(" · ")} · total {formatDuration(total)}
    </p>
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
            <li key={name} className="trace-row text-[var(--text-muted)]">
              <span className="trace-mark bg-[var(--text-muted)]" aria-hidden />
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
              {step.tool_name === "fetch_imagery" && isFetchImageryMetadata(step.metadata) ? (
                <FetchImageryDetails metadata={step.metadata as FetchImageryMetadata} />
              ) : null}
              {step.error ? (
                <p className="mt-0.5 text-[11px] text-[var(--danger)]">{step.error}</p>
              ) : null}
              {step.summary &&
              step.tool_name !== "plan_query" &&
              !step.summary.toLowerCase().includes("running") ? (
                <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{step.summary}</p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      <TimingSummary steps={steps} />
    </section>
  );
}
