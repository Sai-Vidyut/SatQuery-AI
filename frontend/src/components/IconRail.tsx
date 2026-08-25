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
      className="chrome-rail absolute left-3 top-3 z-20 flex flex-col items-center gap-1 py-2"
      aria-label="Main navigation"
    >
      <div className="flex flex-col items-center gap-1 px-2 pb-2">
        <span className="chrome-rail__mark" aria-hidden />
        <span className="chrome-rail__wordmark" translate="no">
          SATQUERY
        </span>
      </div>

      <button
        type="button"
        className="chrome-btn"
        aria-label={drawMode ? "Drawing AOI active" : "Draw AOI"}
        aria-pressed={drawMode}
        data-tooltip="Draw AOI (A)"
        onClick={onToggleDraw}
      >
        <BoundingBox size={16} weight="regular" />
      </button>
      <button
        type="button"
        className="chrome-btn"
        aria-label="Pan map"
        aria-pressed={!drawMode}
        data-tooltip="Pan map"
        onClick={onTogglePan}
      >
        <Hand size={16} weight="regular" />
      </button>
    </nav>
  );
}
