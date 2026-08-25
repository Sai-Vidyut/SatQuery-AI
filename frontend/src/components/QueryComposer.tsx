"use client";

import { useState } from "react";

type Props = {
  aoiLabel: string;
  earlierDate: string;
  laterDate: string;
  query: string;
  running: boolean;
  error: string | null;
  statusLine: string | null;
  onEarlierChange: (v: string) => void;
  onLaterChange: (v: string) => void;
  onQueryChange: (v: string) => void;
  onRun: () => void;
  onBboxSubmit: (bbox: string) => void;
};

export function QueryComposer({
  aoiLabel,
  earlierDate,
  laterDate,
  query,
  running,
  error,
  statusLine,
  onEarlierChange,
  onLaterChange,
  onQueryChange,
  onRun,
  onBboxSubmit,
}: Props) {
  const [showBbox, setShowBbox] = useState(false);
  const [bboxText, setBboxText] = useState("");

  return (
    <div
      className="absolute bottom-3 left-1/2 z-30 w-[min(920px,calc(100%-24px))] -translate-x-1/2"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      {statusLine ? <p className="composer-status">{statusLine}</p> : null}

      <div data-testid="composer" className="glass composer-shell">
        <form
          className="composer-row"
          onSubmit={(e) => {
            e.preventDefault();
            onRun();
          }}
        >
          <div className="composer-segment">
            <span className="composer-label">AOI</span>
            <button
              type="button"
              id="aoi-status"
              data-testid="aoi-status"
              className="composer-aoi-btn tabular-nums"
              onClick={() => setShowBbox((v) => !v)}
              aria-expanded={showBbox}
            >
              {aoiLabel}
            </button>
          </div>

          <div className="composer-segment">
            <label htmlFor="composer-date-from" className="composer-label">
              Earlier
            </label>
            <input
              id="composer-date-from"
              data-testid="composer-date-from"
              type="date"
              className="input-field input-field--date"
              value={earlierDate}
              onChange={(e) => onEarlierChange(e.target.value)}
              required
            />
          </div>

          <div className="composer-segment">
            <label htmlFor="composer-date-to" className="composer-label">
              Later
            </label>
            <input
              id="composer-date-to"
              data-testid="composer-date-to"
              type="date"
              className="input-field input-field--date"
              value={laterDate}
              onChange={(e) => onLaterChange(e.target.value)}
              required
            />
          </div>

          <div className="composer-segment composer-segment--grow">
            <label htmlFor="composer-query" className="composer-label">
              Query
            </label>
            <input
              id="composer-query"
              data-testid="composer-query"
              type="text"
              className="input-field input-field--query w-full"
              placeholder="Show significant new construction…"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              spellCheck={false}
              autoComplete="off"
              required
            />
          </div>

          <div className="composer-segment border-l border-[var(--sq-line)] pl-3">
            <span className="composer-label sr-only">Run</span>
            <button
              type="submit"
              data-testid="composer-run"
              className="btn-primary h-8 min-w-[108px] px-3"
              disabled={running}
              aria-busy={running}
            >
              {running ? "Running…" : "Run Analysis"}
            </button>
          </div>
        </form>

        {showBbox ? (
          <div className="mt-2 flex flex-wrap items-end gap-2 border-t border-[var(--sq-line)] pt-2">
            <div className="flex min-w-[280px] flex-1 flex-col gap-1">
              <label htmlFor="aoi-bbox" className="composer-label">
                Bounding box (minLon, minLat, maxLon, maxLat)
              </label>
              <input
                id="aoi-bbox"
                data-testid="aoi-bbox"
                type="text"
                className="input-field w-full"
                style={{ fontFamily: "var(--sq-font-mono)", fontSize: 12 }}
                placeholder="77.56, 12.94, 77.60, 12.98"
                value={bboxText}
                onChange={(e) => setBboxText(e.target.value)}
                spellCheck={false}
                autoComplete="off"
              />
            </div>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onBboxSubmit(bboxText)}
            >
              Set AOI
            </button>
          </div>
        ) : null}

        {error ? (
          <p className="mt-2 text-[11px] text-[var(--sq-danger)]" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}
