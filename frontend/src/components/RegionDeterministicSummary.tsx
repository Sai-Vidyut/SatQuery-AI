"use client";

import type { AnalysisResult, EvidenceRegion } from "@/types/domain";
import { shouldShowRegionInterpretation } from "@/lib/regionInterpretation";

type Props = {
  result: AnalysisResult;
  selectedRegion: EvidenceRegion;
};

export function RegionDeterministicSummary({ result, selectedRegion }: Props) {
  if (!shouldShowRegionInterpretation(result, selectedRegion)) {
    return null;
  }

  const bt = result.bi_temporal_change!;

  return (
    <div className="inspector-section region-interpretation" data-testid="region-deterministic-summary">
      <p className="inspector-section__label">Detected region evidence</p>
      <p className="inspector-note mb-2">
        Use GeoChat below for follow-up questions about this region. It does not decide whether change
        exists.
      </p>

      <div className="region-interpretation__deterministic" data-testid="region-deterministic-detection">
        <p className="region-interpretation__subheading">Deterministic detection</p>
        <dl className="m-0">
          <div className="inspector-metric-row">
            <dt>Region</dt>
            <dd>{selectedRegion.id}</dd>
          </div>
          <div className="inspector-metric-row">
            <dt>Detector</dt>
            <dd>{bt.detector}</dd>
          </div>
          <div className="inspector-metric-row">
            <dt>Separability</dt>
            <dd>{Math.round(selectedRegion.confidence * 100)}%</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
