"use client";

import type { AnalysisResult, EvidenceRegion } from "@/types/domain";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { ExecutionTrace } from "./ExecutionTrace";

type Props = {
  result: AnalysisResult | null;
  selectedRegion: EvidenceRegion | null;
  running: boolean;
  error: string | null;
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
  if (typeof claim === "string" && claim !== "none") return claim.replace(/_/g, " ");
  return "spectral change";
}

export function EvidenceInspector({
  result,
  selectedRegion,
  running,
  error,
  onSelectRegion,
  onClose,
}: Props) {
  if (!result && !running && !error) return null;

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
      className="inspector-panel absolute right-3 top-3 z-25 flex max-h-[calc(100dvh-96px)] w-[min(380px,calc(100%-24px))] flex-col overflow-hidden rounded-md"
      style={{ zIndex: 25 }}
    >
      <header className="flex items-center justify-between border-b border-[var(--sq-line)] px-3 py-2">
        <h2 className="text-[16px] font-medium">Results</h2>
        <button
          type="button"
          className="border-0 bg-transparent px-0 text-[11px] text-[var(--sq-text-muted)] hover:text-[var(--sq-text)] focus-visible:outline-none focus-visible:[box-shadow:var(--sq-focus)]"
          onClick={onClose}
          aria-label="Close inspector"
        >
          Close
        </button>
      </header>

      <ExecutionTrace steps={result?.trace ?? []} loading={running} />

      {error && !running ? (
        <div className="border-b border-[var(--sq-line)] px-3 py-2 text-[12px] text-[var(--sq-danger)]" role="alert">
          {error}
        </div>
      ) : null}

      {result ? (
        <div className="border-b border-[var(--sq-line)] px-3 py-2 text-[12px] text-[var(--sq-text-muted)]">
          <p>{result.answer}</p>
          {isPartialSemantic ? (
            <p className="mt-1 text-[11px] text-[var(--sq-warning)]">
              Partial evidence: spectral change detected without semantic construction support.
            </p>
          ) : null}
          {evidence.length === 0 ? (
            <p className="mt-1 text-[11px]">
              No significant change in this AOI for the selected dates. Widen the date range or AOI.
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto">
        {result && evidence.length > 0 ? (
          <>
            <h3 className="px-3 pt-2 text-[11px] font-medium uppercase tracking-[0.04em] text-[var(--sq-text-muted)]">
              Regions ({evidence.length})
            </h3>
            <ul role="listbox" aria-label="Detection regions">
              {evidence.map((region) => (
                <li key={region.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={selectedRegion?.id === region.id}
                    data-testid="region-row"
                    className="flex w-full items-center justify-between border-b border-[var(--sq-line)] px-3 py-2 text-left hover:bg-[var(--sq-amber-dim)] focus-visible:outline-none focus-visible:[box-shadow:var(--sq-focus)]"
                    style={{
                      background:
                        selectedRegion?.id === region.id ? "var(--sq-amber-dim)" : undefined,
                    }}
                    onClick={() => onSelectRegion(region.id)}
                  >
                    <span className="text-[13px]">{region.id}</span>
                    <span
                      className="tabular-nums text-[11px] text-[var(--sq-text-muted)]"
                      style={{ fontFamily: "var(--sq-font-mono)" }}
                    >
                      {Math.round(region.confidence * 100)}%
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : result && !running ? (
          <p className="px-3 py-4 text-[12px] text-[var(--sq-text-muted)]">
            No regions to display.
          </p>
        ) : null}

        {selectedRegion ? (
          <div className="border-t border-[var(--sq-line)] px-3 py-2">
            <h3 className="mb-2 text-[13px] font-medium">{selectedRegion.id}</h3>
            <ConfidenceMeter confidence={selectedRegion.confidence} />
            <dl className="mt-3 space-y-1">
              <div className="flex justify-between text-[12px]">
                <dt className="text-[var(--sq-text-muted)]">Modality</dt>
                <dd style={{ fontFamily: "var(--sq-font-mono)" }}>{modalityLabel(selectedRegion)}</dd>
              </div>
              <div className="flex justify-between text-[12px]">
                <dt className="text-[var(--sq-text-muted)]">Claim</dt>
                <dd style={{ fontFamily: "var(--sq-font-mono)" }}>{claimLabel(selectedRegion)}</dd>
              </div>
              <div className="flex justify-between text-[12px]">
                <dt className="text-[var(--sq-text-muted)]">Provenance</dt>
                <dd style={{ fontFamily: "var(--sq-font-mono)" }}>{selectedRegion.source}</dd>
              </div>
              {selectedRegion.metrics.map((m) => (
                <div key={m.name} className="flex justify-between text-[12px]">
                  <dt className="text-[var(--sq-text-muted)]">{m.name}</dt>
                  <dd className="tabular-nums" style={{ fontFamily: "var(--sq-font-mono)" }}>
                    {m.value}
                    {m.unit ? ` ${m.unit}` : ""}
                  </dd>
                </div>
              ))}
            </dl>
            {hasConstructionCandidates && selectedRegion.metadata?.semantic_confidence != null ? (
              <p className="mt-2 text-[11px] text-[var(--sq-text-muted)]">
                Semantic built-area evidence available for this region.
              </p>
            ) : null}
          </div>
        ) : result && evidence.length > 0 ? (
          <p className="px-3 py-4 text-[12px] text-[var(--sq-text-muted)]">
            Select a region on the map.
          </p>
        ) : null}
      </div>
    </aside>
  );
}
