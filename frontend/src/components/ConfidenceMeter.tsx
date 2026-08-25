"use client";

import { confidenceBand } from "@/lib/geo";

type Props = {
  confidence: number;
  testId?: string;
};

export function ConfidenceMeter({ confidence, testId = "confidence" }: Props) {
  const pct = Math.round(confidence * 100);
  return (
    <div data-testid={testId}>
      <div className="mb-1 flex justify-between text-[11px] text-[var(--sq-text-muted)]">
        <span>Confidence</span>
        <span className="tabular-nums" style={{ fontFamily: "var(--sq-font-mono)" }}>
          {pct}% · {confidenceBand(confidence)}
        </span>
      </div>
      <div className="h-[3px] rounded-sm" style={{ background: "var(--sq-amber-dim)" }}>
        <div
          className="h-full rounded-sm"
          style={{ width: `${pct}%`, background: "var(--sq-amber)" }}
        />
      </div>
    </div>
  );
}
