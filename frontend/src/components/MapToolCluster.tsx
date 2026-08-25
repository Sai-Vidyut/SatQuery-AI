"use client";

import { useState } from "react";
import { Minus, Plus, Stack } from "@phosphor-icons/react";

type LayerState = {
  detections: boolean;
  aoi: boolean;
};

type Props = {
  onZoomIn: () => void;
  onZoomOut: () => void;
  layers: LayerState;
  onLayersChange: (next: LayerState) => void;
};

export function MapToolCluster({ onZoomIn, onZoomOut, layers, onLayersChange }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="absolute right-3 top-3 z-20" data-testid="map-tools">
      <div className="map-tool-cluster">
        <div className="relative">
          <button
            type="button"
            data-testid="layer-toggle"
            className="map-tool-btn"
            aria-label="Layers"
            aria-expanded={open}
            title="Layers"
            onClick={() => setOpen((v) => !v)}
          >
            <Stack size={20} weight="regular" />
          </button>
          {open ? (
            <div
              className="layer-popover absolute right-0 top-[calc(100%+4px)] w-[220px] p-3"
              role="group"
              aria-label="Map layers"
            >
              <p className="composer-label mb-2">Layers</p>
              <label className="flex cursor-pointer items-center gap-2 py-1 text-[12px]">
                <input
                  type="checkbox"
                  checked={layers.detections}
                  onChange={(e) =>
                    onLayersChange({ ...layers, detections: e.target.checked })
                  }
                />
                Detections
              </label>
              <label className="flex cursor-pointer items-center gap-2 py-1 text-[12px]">
                <input
                  type="checkbox"
                  checked={layers.aoi}
                  onChange={(e) => onLayersChange({ ...layers, aoi: e.target.checked })}
                />
                AOI
              </label>
            </div>
          ) : null}
        </div>
        <button
          type="button"
          className="map-tool-btn"
          aria-label="Zoom in"
          title="Zoom in"
          onClick={onZoomIn}
        >
          <Plus size={20} weight="regular" />
        </button>
        <button
          type="button"
          className="map-tool-btn"
          aria-label="Zoom out"
          title="Zoom out"
          onClick={onZoomOut}
        >
          <Minus size={20} weight="regular" />
        </button>
      </div>
    </div>
  );
}
