"use client";

import { BoundingBox, Hand } from "@phosphor-icons/react";

type Props = {
  drawMode: boolean;
  onToggleDraw: () => void;
  onTogglePan: () => void;
};

export function IconRail({ drawMode, onToggleDraw, onTogglePan }: Props) {
  return (
    <nav
      data-testid="rail"
      className="chrome-rail glass-light absolute left-3 top-3 z-20 flex flex-col items-center pb-2"
      aria-label="Main navigation"
    >
      <div className="chrome-rail__brand">
        <span className="chrome-rail__mark" aria-hidden />
        <span className="chrome-rail__wordmark" translate="no">
          SatQuery
        </span>
      </div>

      <button
        type="button"
        className={`chrome-btn${drawMode ? " chrome-btn--active" : ""}`}
        data-testid="rail-draw-aoi"
        data-tour="rail-draw-aoi"
        aria-label={drawMode ? "Drawing AOI — drag on map to draw a rectangle" : "Draw AOI"}
        aria-pressed={drawMode}
        title="Draw AOI"
        data-tooltip="Draw AOI"
        onClick={onToggleDraw}
      >
        <BoundingBox size={16} weight={drawMode ? "fill" : "regular"} />
      </button>
      <button
        type="button"
        className={`chrome-btn${!drawMode ? " chrome-btn--active" : ""}`}
        aria-label="Pan map"
        aria-pressed={!drawMode}
        title="Pan map"
        data-tooltip="Pan map"
        onClick={onTogglePan}
      >
        <Hand size={16} weight={!drawMode ? "fill" : "regular"} />
      </button>
    </nav>
  );
}
