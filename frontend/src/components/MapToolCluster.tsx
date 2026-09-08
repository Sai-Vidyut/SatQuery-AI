"use client";

import { useState } from "react";
import { Minus, Plus, Stack } from "@phosphor-icons/react";
import { SiteMenu } from "@/components/SiteMenu";

type LayerState = {
  detections: boolean;
  aoi: boolean;
};

type Props = {
  onZoomIn: () => void;
  onZoomOut: () => void;
  layers: LayerState;
  onLayersChange: (next: LayerState) => void;
  inspectorOpen?: boolean;
};

function LayerToggle({
  open,
  layers,
  onToggle,
  onLayersChange,
}: {
  open: boolean;
  layers: LayerState;
  onToggle: () => void;
  onLayersChange: (next: LayerState) => void;
}) {
  return (
    <div className="relative">
      <button
        type="button"
        data-testid="layer-toggle"
        className="map-tool-btn"
        aria-label="Layers"
        aria-expanded={open}
        onClick={onToggle}
      >
        <Stack size={20} weight="regular" />
      </button>
      {open ? (
        <div
          className="layer-popover glass-light absolute right-0 top-[calc(100%+4px)] w-[200px] p-3"
          role="group"
          aria-label="Map layers"
        >
          <p className="composer-label mb-2">Layers</p>
          <label className="layer-check">
            <input
              type="checkbox"
              checked={layers.detections}
              onChange={(e) => onLayersChange({ ...layers, detections: e.target.checked })}
            />
            Detections
          </label>
          <label className="layer-check">
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
  );
}

export function MapToolCluster({
  onZoomIn,
  onZoomOut,
  layers,
  onLayersChange,
  inspectorOpen = false,
}: Props) {
  const [open, setOpen] = useState(false);

  if (inspectorOpen) {
    return (
      <div className="map-tools map-tools--dock-inspector" data-testid="map-tools">
        <div
          className="map-tool-cluster map-tool-cluster--horizontal map-tool-cluster--pill glass"
          data-tour="map-tools"
        >
          <button type="button" className="map-tool-btn" aria-label="Zoom out" onClick={onZoomOut}>
            <Minus size={20} weight="regular" />
          </button>
          <button type="button" className="map-tool-btn" aria-label="Zoom in" onClick={onZoomIn}>
            <Plus size={20} weight="regular" />
          </button>
          <LayerToggle
            open={open}
            layers={layers}
            onToggle={() => setOpen((v) => !v)}
            onLayersChange={onLayersChange}
          />
          <span className="map-tool-cluster__divider" aria-hidden="true" />
          <SiteMenu variant="toolbar" />
        </div>
      </div>
    );
  }

  return (
    <div className="map-tools" data-testid="map-tools">
      <div className="map-tool-cluster glass-light" data-tour="map-tools">
        <LayerToggle
          open={open}
          layers={layers}
          onToggle={() => setOpen((v) => !v)}
          onLayersChange={onLayersChange}
        />
        <button type="button" className="map-tool-btn" aria-label="Zoom in" onClick={onZoomIn}>
          <Plus size={20} weight="regular" />
        </button>
        <button type="button" className="map-tool-btn" aria-label="Zoom out" onClick={onZoomOut}>
          <Minus size={20} weight="regular" />
        </button>
      </div>
    </div>
  );
}
