"use client";

import { confidenceBand } from "@/lib/geo";

type Props = {
  confidence: number;
  testId?: string;
  label?: string;
};

export function ConfidenceMeter({
  confidence,
  testId = "confidence",
  label = "Detector separability",
}: Props) {
  const pct = Math.round(confidence * 100);
  return (
    <div data-testid={testId} className="confidence-meter">
      <div className="confidence-meter__header">
        <span className="confidence-meter__label">{label}</span>
        <span className="confidence-meter__value">
          {pct}%
          <span className="confidence-meter__band"> · {confidenceBand(confidence)}</span>
        </span>
      </div>
      <p className="m-0 text-[13px] text-[var(--text-muted)]">
        Histogram separability — not event probability.
      </p>
      <div className="confidence-meter__track" aria-hidden>
        <div className="confidence-meter__fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
