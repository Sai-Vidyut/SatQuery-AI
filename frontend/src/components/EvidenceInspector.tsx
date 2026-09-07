"use client";

import type { AnalysisResult, EvidenceRegion, FetchImageryMetadata, TraceStep } from "@/types/domain";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { claimTypeLabel } from "@/lib/geo";
import { isFetchImageryMetadata } from "@/lib/trace";
import { ExecutionTrace } from "./ExecutionTrace";

function catalogProvenanceFromTrace(trace: TraceStep[]) {
  const fetch = trace.find((s) => s.tool_name === "fetch_imagery");
  const detect = trace.find((s) => s.tool_name === "detect_change");
  const plan = trace.find((s) => s.tool_name === "plan_query");
  const fetchMeta =
    fetch?.metadata && isFetchImageryMetadata(fetch.metadata)
      ? (fetch.metadata as FetchImageryMetadata)
      : null;
  const detectMeta = (detect?.metadata ?? {}) as Record<string, unknown>;
  const planMeta = (plan?.metadata ?? {}) as Record<string, unknown>;
  return { fetchMeta, detectMeta, planMeta };
}

function CatalogProvenance({ result }: { result: AnalysisResult }) {
  const { fetchMeta, detectMeta, planMeta } = catalogProvenanceFromTrace(result.trace);
  if (!fetchMeta && !detectMeta.change_direction_hint && !planMeta.change_domain) {
    return null;
  }
  return (
    <div className="inspector-bitemporal-meta" data-testid="inspector-catalog-provenance">
      <p className="inspector-section__label" style={{ marginTop: 12 }}>
        Data provenance
      </p>
      <dl className="m-0">
        {fetchMeta?.t1?.requested_date ? (
          <div className="inspector-metric-row">
            <dt>Requested T1 / T2</dt>
            <dd>
              {fetchMeta.t1.requested_date} / {fetchMeta.t2?.requested_date ?? "?"}
            </dd>
          </div>
        ) : null}
        {fetchMeta?.imagery_strategy ? (
          <div className="inspector-metric-row">
            <dt>Imagery strategy</dt>
            <dd>{fetchMeta.imagery_strategy}</dd>
          </div>
        ) : null}
        {typeof detectMeta.detector === "string" ? (
          <div className="inspector-metric-row">
            <dt>Detector</dt>
            <dd>{detectMeta.detector}</dd>
          </div>
        ) : null}
        {typeof detectMeta.primary_index === "string" ? (
          <div className="inspector-metric-row">
            <dt>Primary signal</dt>
            <dd>{String(detectMeta.primary_index).toUpperCase()}</dd>
          </div>
        ) : null}
        {typeof detectMeta.change_direction_hint === "string" ? (
          <div className="inspector-metric-row">
            <dt>Direction hint</dt>
            <dd>{detectMeta.change_direction_hint.replace(/_/g, " ")}</dd>
          </div>
        ) : null}
        {typeof planMeta.change_domain === "string" ? (
          <div className="inspector-metric-row">
            <dt>Domain</dt>
            <dd>{planMeta.change_domain.replace(/_/g, " ")}</dd>
          </div>
        ) : null}
        {detectMeta.area_ha != null ? (
          <div className="inspector-metric-row">
            <dt>Changed area</dt>
            <dd>{String(detectMeta.area_ha)} ha</dd>
          </div>
        ) : null}
        <div className="inspector-metric-row">
          <dt>Confidence type</dt>
          <dd>{String(detectMeta.confidence_kind ?? "histogram_separability").replace(/_/g, " ")}</dd>
        </div>
      </dl>
      {fetchMeta?.fallback_events?.length ? (
        <p className="inspector-note inspector-note--warning mt-2">
          Imagery fallback applied:{" "}
          {fetchMeta.fallback_events.map((e) => String(e.policy_decision ?? "fallback")).join(", ")}
        </p>
      ) : null}
    </div>
  );
}

type Props = {
  result: AnalysisResult | null;
  selectedRegion: EvidenceRegion | null;
  running: boolean;
  analysisError: string | null;
  onSelectRegion: (id: string) => void;
  onClose: () => void;
};

function modalityLabel(region: EvidenceRegion): string {
  const modality = region.metadata?.evidence_modality;
  if (typeof modality === "string") return modality;
  return region.type;
}

function claimLabel(region: EvidenceRegion): string {
  const claim = region.metadata?.claim_type;
  if (typeof claim === "string") {
    const label = claimTypeLabel(claim);
    if (label) return label;
  }
  return "Spectral change";
}

export function EvidenceInspector({
  result,
  selectedRegion,
  running,
  analysisError,
  onSelectRegion,
  onClose,
}: Props) {
  if (!result && !running && !analysisError) return null;

  const evidence = result?.evidence ?? [];
  const hasConstructionCandidates = evidence.some(
    (r) => r.metadata?.claim_type === "construction_candidate",
  );
  const isPartialSemantic =
    result != null &&
    result.answer.toLowerCase().includes("no construction candidates") &&
    evidence.length > 0;

  return (
    <aside
      data-testid="inspector"
      className="inspector-panel absolute right-3 top-3 z-25 flex max-h-[calc(100dvh-var(--composer-offset))] w-[min(380px,calc(100%-24px))] flex-col overflow-hidden"
      style={{ zIndex: 25 }}
    >
      <header className="inspector-header">
        <h2 className="inspector-header__title">Results</h2>
        <button type="button" className="inspector-close" onClick={onClose} aria-label="Close inspector">
          Close
        </button>
      </header>

      <ExecutionTrace steps={result?.trace ?? []} loading={running} />

      {analysisError && !running ? (
        <div className="inspector-section" role="alert" data-testid="inspector-analysis-error">
          <p className="inspector-section__label">Error</p>
          <p className="inspector-note inspector-note--error">{analysisError}</p>
        </div>
      ) : null}

      {result ? (
        <div className="inspector-section">
          {result.demonstration_data ? (
            <p
              className="inspector-note inspector-note--warning mb-2"
              data-testid="inspector-demo-banner"
              role="status"
            >
              DEMONSTRATION DATA — deterministic fixtures, not real Earth observation.
            </p>
          ) : null}
          <p className="inspector-section__label">Answer</p>
          <p className="inspector-answer">{result.answer}</p>
          {isPartialSemantic ? (
            <p className="inspector-note inspector-note--warning">
              Partial evidence: spectral change without semantic construction support.
            </p>
          ) : null}
          {evidence.length === 0 && !result.vqa && !result.caption ? (
            <p className="inspector-note">
              No significant change in this AOI for the selected dates. Widen the date range or AOI.
            </p>
          ) : null}
          {!result.vqa && !result.caption && !result.bi_temporal_change && !result.cross_modal ? (
            <CatalogProvenance result={result} />
          ) : null}
          {result.cross_modal ? (
            <div className="inspector-crossmodal-meta" data-testid="inspector-crossmodal-provenance">
              <p className="inspector-section__label" style={{ marginTop: 12 }}>
                Optical analysis
              </p>
              <p className="inspector-answer" data-testid="inspector-optical-analysis">
                {result.cross_modal.optical_analysis.summary}
              </p>
              <p className="inspector-section__label" style={{ marginTop: 12 }}>
                SAR analysis
              </p>
              <p className="inspector-answer" data-testid="inspector-sar-analysis">
                {result.cross_modal.sar_analysis.summary}
              </p>
              <p className="inspector-section__label" style={{ marginTop: 12 }}>
                Joint analysis
              </p>
              <p className="inspector-answer" data-testid="inspector-joint-analysis">
                {result.cross_modal.fused_analysis.summary}
              </p>
              <p className="inspector-section__label" style={{ marginTop: 12 }}>
                Co-registration
              </p>
              <p className="inspector-note" data-testid="inspector-coregistration-status">
                {result.cross_modal.co_registration_status.replace(/_/g, " ")} —{" "}
                {result.cross_modal.co_registration_provenance}
              </p>
              <dl className="m-0">
                <div className="inspector-metric-row">
                  <dt>Optical tool</dt>
                  <dd>{result.cross_modal.optical_analysis.analyzer}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>SAR tool</dt>
                  <dd>{result.cross_modal.sar_analysis.analyzer}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Fusion policy</dt>
                  <dd>{result.cross_modal.fused_analysis.fusion_policy}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Provider</dt>
                  <dd>{result.cross_modal.provider}</dd>
                </div>
              </dl>
            </div>
          ) : null}
          {result.bi_temporal_change ? (
            <div className="inspector-bitemporal-meta" data-testid="inspector-bitemporal-provenance">
              <p className="inspector-section__label" style={{ marginTop: 12 }}>
                Change analysis
              </p>
              <p className="inspector-answer" data-testid="inspector-change-summary">
                {result.bi_temporal_change.change_summary}
              </p>
              <p className="inspector-section__label" style={{ marginTop: 12 }}>
                Model / provenance
              </p>
              <dl className="m-0">
                <div className="inspector-metric-row">
                  <dt>Detector</dt>
                  <dd>{result.bi_temporal_change.detector}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Provider</dt>
                  <dd>{result.bi_temporal_change.provider}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Task</dt>
                  <dd>Bi-temporal Change</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Regions</dt>
                  <dd>{result.bi_temporal_change.changed_region_count}</dd>
                </div>
              </dl>
              <p className="font-telemetry m-0 mt-2 text-[13px] text-[var(--text-muted)]">
                {result.bi_temporal_change.provenance}
              </p>
            </div>
          ) : null}
          {result.caption ? (
            <div className="inspector-caption-meta" data-testid="inspector-caption-provenance">
              <p className="inspector-section__label" style={{ marginTop: 12 }}>
                Scene description
              </p>
              <p className="inspector-answer" data-testid="inspector-scene-description">
                {result.caption.description}
              </p>
              <p className="inspector-section__label" style={{ marginTop: 12 }}>
                Model / provenance
              </p>
              <dl className="m-0">
                <div className="inspector-metric-row">
                  <dt>Model</dt>
                  <dd>{result.caption.model_name}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Provider</dt>
                  <dd>{result.caption.provider}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Task</dt>
                  <dd>Scene Description</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Confidence</dt>
                  <dd>
                    {result.caption.confidence_available && result.caption.confidence != null
                      ? `${Math.round(result.caption.confidence * 100)}%`
                      : "unavailable"}
                  </dd>
                </div>
              </dl>
              <p className="font-telemetry m-0 mt-2 text-[13px] text-[var(--text-muted)]">
                {result.caption.provenance}
              </p>
            </div>
          ) : null}
          {result.vqa ? (
            <div className="inspector-vqa-meta" data-testid="inspector-vqa-provenance">
              <p className="inspector-section__label" style={{ marginTop: 12 }}>
                VQA answer
              </p>
              <p className="inspector-section__label" style={{ marginTop: 12 }}>
                Model / provenance
              </p>
              <dl className="m-0">
                <div className="inspector-metric-row">
                  <dt>Model</dt>
                  <dd>{result.vqa.model_name}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Provider</dt>
                  <dd>{result.vqa.provider}</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Task</dt>
                  <dd>Visual Question Answering</dd>
                </div>
                <div className="inspector-metric-row">
                  <dt>Confidence</dt>
                  <dd>
                    {result.vqa.confidence_available && result.vqa.confidence != null
                      ? `${Math.round(result.vqa.confidence * 100)}%`
                      : "unavailable"}
                  </dd>
                </div>
              </dl>
              <p className="font-telemetry m-0 mt-2 text-[13px] text-[var(--text-muted)]">
                {result.vqa.provenance}
              </p>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="inspector-section inspector-section--scroll">
        {result && evidence.length > 0 ? (
          <>
            <p className="inspector-section__label">Regions ({evidence.length})</p>
            <ul role="listbox" aria-label="Detection regions" className="m-0 list-none p-0">
              {evidence.map((region) => (
                <li key={region.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={selectedRegion?.id === region.id}
                    data-testid="region-row"
                    className="inspector-region-row"
                    onClick={() => onSelectRegion(region.id)}
                  >
                    <span>{region.id}</span>
                    <span className="inspector-region-row__pct">
                      {typeof region.metadata?.significance_score === "number"
                        ? `sig ${region.metadata.significance_score}`
                        : `${Math.round(region.confidence * 100)}%`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : result && !running ? (
          <p className="inspector-empty">No regions to display.</p>
        ) : null}

        {selectedRegion ? (
          <div className="inspector-section" style={{ borderBottom: "none", paddingTop: 0 }}>
            <p className="inspector-section__label">Selected region</p>
            <p
              className="font-telemetry m-0 mb-2 text-[15px] font-medium"
            >
              {selectedRegion.id}
            </p>
            <ConfidenceMeter confidence={selectedRegion.confidence} />

            <p className="inspector-section__label" style={{ marginTop: 12 }}>
              Metrics
            </p>
            <dl className="m-0">
              <div className="inspector-metric-row">
                <dt>Modality</dt>
                <dd>{modalityLabel(selectedRegion)}</dd>
              </div>
              <div className="inspector-metric-row">
                <dt>Claim</dt>
                <dd>{claimLabel(selectedRegion)}</dd>
              </div>
              {typeof selectedRegion.metadata?.significance_score === "number" ? (
                <div className="inspector-metric-row">
                  <dt>Significance</dt>
                  <dd>{selectedRegion.metadata.significance_score}</dd>
                </div>
              ) : null}
              {typeof selectedRegion.metadata?.claim_strength === "string" ? (
                <div className="inspector-metric-row">
                  <dt>Claim strength</dt>
                  <dd>{selectedRegion.metadata.claim_strength}</dd>
                </div>
              ) : null}
              {selectedRegion.metrics.map((m) => (
                <div key={m.name} className="inspector-metric-row">
                  <dt>{m.name}</dt>
                  <dd>
                    {m.value}
                    {m.unit ? ` ${m.unit}` : ""}
                  </dd>
                </div>
              ))}
            </dl>

            <p className="inspector-section__label" style={{ marginTop: 12 }}>
              Provenance
            </p>
            <p
              className="font-telemetry m-0 text-[13px] text-[var(--text-muted)]"
            >
              {selectedRegion.source}
            </p>

            {hasConstructionCandidates && selectedRegion.metadata?.semantic_confidence != null ? (
              <p className="inspector-note">
                Semantic built-area evidence available for this region.
              </p>
            ) : null}
          </div>
        ) : result && evidence.length > 0 ? (
          <p className="inspector-empty">Select a region on the map.</p>
        ) : null}
      </div>
    </aside>
  );
}
