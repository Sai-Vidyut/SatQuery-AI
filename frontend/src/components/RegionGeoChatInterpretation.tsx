"use client";

import { useEffect, useState } from "react";
import type { AnalysisResult, BiTemporalRegionInterpretationResult, EvidenceRegion } from "@/types/domain";
import { api } from "@/lib/api";
import { normalizeAnalysisError } from "@/lib/errors";
import { shouldShowRegionInterpretation, regionInterpretationProviderLabel } from "@/lib/regionInterpretation";

const PRESET_QUESTIONS = [
  "What visible change occurred in this detected region between the two dates?",
  "Describe the land-cover transition visible between before and after.",
  "Does the visible change appear consistent with vegetation loss, flooding, construction, or another transition?",
] as const;

type Props = {
  sessionId: string;
  result: AnalysisResult;
  selectedRegion: EvidenceRegion;
};

function providerBadge(provider: BiTemporalRegionInterpretationResult["provider"]): string {
  return regionInterpretationProviderLabel(provider);
}

export function RegionGeoChatInterpretation({ sessionId, result, selectedRegion }: Props) {
  const [question, setQuestion] = useState<string>(PRESET_QUESTIONS[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [interpretation, setInterpretation] = useState<BiTemporalRegionInterpretationResult | null>(
    null,
  );

  useEffect(() => {
    setInterpretation(null);
    setError(null);
    setLoading(false);
    setQuestion(PRESET_QUESTIONS[0]);
  }, [selectedRegion.id, sessionId]);

  if (!shouldShowRegionInterpretation(result, selectedRegion)) {
    return null;
  }

  const bt = result.bi_temporal_change!;

  async function handleInterpret() {
    setLoading(true);
    setError(null);
    try {
      const response = await api.interpretChangeRegion(sessionId, selectedRegion.id, question.trim());
      setInterpretation(response.interpretation);
    } catch (err) {
      setInterpretation(null);
      setError(normalizeAnalysisError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="inspector-section region-interpretation" data-testid="region-geochat-interpretation">
      <p className="inspector-section__label">AI Interpretation</p>
      <p className="inspector-note mb-2">
        GeoChat interprets the selected evidence. It does not decide whether change exists.
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

      <label className="inspector-section__label mt-3" htmlFor="region-interpretation-question">
        Question
      </label>
      <select
        id="region-interpretation-question"
        className="region-interpretation__select"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        data-testid="region-interpretation-preset"
      >
        {PRESET_QUESTIONS.map((preset) => (
          <option key={preset} value={preset}>
            {preset}
          </option>
        ))}
      </select>
      <textarea
        className="region-interpretation__question mt-2"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        rows={3}
        data-testid="region-interpretation-question"
      />

      <button
        type="button"
        className="btn btn--secondary mt-2"
        onClick={() => void handleInterpret()}
        disabled={loading || question.trim().length < 3}
        data-testid="region-interpretation-run"
      >
        {loading ? "Interpreting…" : "Interpret this region"}
      </button>

      {loading ? (
        <p className="inspector-note mt-2" data-testid="region-interpretation-loading">
          Running GeoChat interpretation…
        </p>
      ) : null}

      {error ? (
        <p className="inspector-note inspector-note--error mt-2" data-testid="region-interpretation-error">
          {error}
        </p>
      ) : null}

      {interpretation ? (
        <div className="region-interpretation__ai mt-3" data-testid="region-interpretation-success">
          <p className="region-interpretation__subheading">AI interpretation</p>
          <p
            className="region-interpretation__badge"
            data-testid="region-interpretation-provider-badge"
          >
            {providerBadge(interpretation.provider)}
          </p>
          <p className="region-interpretation__answer">{interpretation.answer}</p>
          <dl className="m-0 mt-2">
            <div className="inspector-metric-row">
              <dt>Provider</dt>
              <dd>{interpretation.provider}</dd>
            </div>
            <div className="inspector-metric-row">
              <dt>Model</dt>
              <dd>{interpretation.model_name}</dd>
            </div>
          </dl>
          <p className="inspector-note mt-2">{interpretation.provenance}</p>
        </div>
      ) : null}
    </div>
  );
}
