"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Map } from "maplibre-gl";
import type { AnalysisResult, AOI } from "@/types/domain";
import { api } from "@/lib/api";
import { aoiFromBbox, bboxFromAoi } from "@/lib/geo";
import { MapViewport } from "@/components/MapViewport";
import { MapToolCluster } from "@/components/MapToolCluster";
import { IconRail } from "@/components/IconRail";
import { QueryComposer } from "@/components/QueryComposer";
import { EvidenceInspector } from "@/components/EvidenceInspector";

const DEFAULT_EARLIER_DATE = "2024-12-01";
const DEFAULT_LATER_DATE = "2025-03-01";
const DEFAULT_QUERY = "Show me significant new construction.";

function parseBboxParam(value: string | null): AOI | null {
  if (!value) return null;
  const parts = value.split(",").map((p) => Number.parseFloat(p.trim()));
  if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) return null;
  return aoiFromBbox(parts as [number, number, number, number]);
}

function applyUrlParams(params: URLSearchParams): {
  aoi: AOI | null;
  earlierDate: string;
  laterDate: string;
  query: string;
  region: string | null;
} {
  return {
    aoi: parseBboxParam(params.get("bbox")),
    earlierDate: params.get("from") ?? DEFAULT_EARLIER_DATE,
    laterDate: params.get("to") ?? DEFAULT_LATER_DATE,
    query: params.get("q") ?? DEFAULT_QUERY,
    region: params.get("region"),
  };
}

export function Workspace() {
  const mapRef = useRef<Map | null>(null);
  const urlHydratedRef = useRef(false);

  const [aoi, setAoi] = useState<AOI | null>(null);
  const [drawMode, setDrawMode] = useState(false);
  const [earlierDate, setEarlierDate] = useState(DEFAULT_EARLIER_DATE);
  const [laterDate, setLaterDate] = useState(DEFAULT_LATER_DATE);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [layerVisibility, setLayerVisibility] = useState({ detections: true, aoi: true });
  const runStartedAt = useRef<number | null>(null);

  useEffect(() => {
    if (urlHydratedRef.current) return;
    urlHydratedRef.current = true;

    const fromUrl = applyUrlParams(new URLSearchParams(window.location.search));
    setAoi(fromUrl.aoi);
    setEarlierDate(fromUrl.earlierDate);
    setLaterDate(fromUrl.laterDate);
    setQuery(fromUrl.query);
    setSelectedRegionId(fromUrl.region);
  }, []);

  const syncUrl = useCallback(
    (patch: {
      aoi?: AOI | null;
      earlierDate?: string;
      laterDate?: string;
      query?: string;
      region?: string | null;
    }) => {
      if (typeof window === "undefined") return;
      const params = new URLSearchParams(window.location.search);
      const nextAoi = patch.aoi !== undefined ? patch.aoi : aoi;
      const nextFrom = patch.earlierDate ?? earlierDate;
      const nextTo = patch.laterDate ?? laterDate;
      const nextQ = patch.query ?? query;
      const nextRegion = patch.region !== undefined ? patch.region : selectedRegionId;

      if (nextAoi) {
        params.set("bbox", bboxFromAoi(nextAoi).join(","));
      } else {
        params.delete("bbox");
      }
      params.set("from", nextFrom);
      params.set("to", nextTo);
      params.set("q", nextQ);
      if (nextRegion) params.set("region", nextRegion);
      else params.delete("region");

      const next = `${window.location.pathname}?${params.toString()}`;
      window.history.replaceState(null, "", next);
    },
    [aoi, earlierDate, laterDate, query, selectedRegionId],
  );

  const handleRun = useCallback(async () => {
    if (!aoi) {
      setError("AOI required. Draw an area on the map or enter a bounding box.");
      return;
    }
    if (!query.trim()) {
      setError("Query required.");
      return;
    }
    if (laterDate <= earlierDate) {
      setError("Later date must be after earlier date.");
      return;
    }

    setRunning(true);
    setError(null);
    setResult(null);
    setSelectedRegionId(null);
    setStatusLine(null);
    runStartedAt.current = performance.now();

    try {
      const data = await api.submitQuery({
        query,
        aoi,
        earlier_date: earlierDate,
        later_date: laterDate,
      });
      const elapsed = runStartedAt.current
        ? ((performance.now() - runStartedAt.current) / 1000).toFixed(1)
        : "?";
      setResult(data.result);
      setStatusLine(
        `${data.result.evidence.length} regions · ${elapsed}s · ${earlierDate} → ${laterDate}`,
      );
      syncUrl({ region: null });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setRunning(false);
      runStartedAt.current = null;
    }
  }, [aoi, earlierDate, laterDate, query, syncUrl]);

  const handleBboxSubmit = useCallback(
    (text: string) => {
      const parts = text.split(",").map((p) => Number.parseFloat(p.trim()));
      if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) {
        setError("Invalid bounding box. Use minLon, minLat, maxLon, maxLat.");
        return;
      }
      const next = aoiFromBbox(parts as [number, number, number, number]);
      setAoi(next);
      setDrawMode(false);
      setError(null);
      syncUrl({ aoi: next });
    },
    [syncUrl],
  );

  const handleSelectRegion = useCallback(
    (id: string | null) => {
      setSelectedRegionId(id);
      syncUrl({ region: id });
    },
    [syncUrl],
  );

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        document.getElementById("composer-query")?.focus();
      }
      if (e.key.toLowerCase() === "a" && !e.metaKey && !e.ctrlKey) {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA") return;
        e.preventDefault();
        setDrawMode(true);
      }
      if (e.key === "Escape") {
        setDrawMode(false);
        if (selectedRegionId) handleSelectRegion(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleSelectRegion, selectedRegionId]);

  useEffect(() => {
    if (running) {
      const handler = (e: BeforeUnloadEvent) => {
        e.preventDefault();
      };
      window.addEventListener("beforeunload", handler);
      return () => window.removeEventListener("beforeunload", handler);
    }
  }, [running]);

  const selectedRegion =
    result?.evidence.find((r) => r.id === selectedRegionId) ?? null;

  const aoiLabel = aoi
    ? `AOI · ${aoi.area_km2?.toFixed(1) ?? "?"} km²`
    : "Draw AOI";

  const inspectorOpen = running || result != null || (error != null && !running);

  return (
    <main className="relative h-[100dvh] w-full overflow-hidden bg-[var(--sq-void)]">
      <a
        href="#map"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-sm focus:bg-[var(--sq-panel)] focus:px-2 focus:py-1 focus:[box-shadow:var(--sq-focus)]"
      >
        Skip to map
      </a>

      <div id="map" className="absolute inset-0">
        <MapViewport
          aoi={aoi}
          evidence={result?.evidence ?? []}
          selectedRegionId={selectedRegionId}
          drawMode={drawMode}
          layerVisibility={layerVisibility}
          onAoiDrawn={(next) => {
            setAoi(next);
            setDrawMode(false);
            syncUrl({ aoi: next });
          }}
          onSelectRegion={handleSelectRegion}
          mapRef={mapRef}
        />
      </div>

      {!aoi ? (
        <div
          className="map-hint absolute bottom-[var(--sq-composer-offset)] left-14 z-10"
          data-testid="empty-hint"
          role="status"
        >
          Draw an area to analyze
        </div>
      ) : null}

      <IconRail
        drawMode={drawMode}
        onToggleDraw={() => setDrawMode(true)}
        onTogglePan={() => setDrawMode(false)}
      />

      <MapToolCluster
        layers={layerVisibility}
        onLayersChange={setLayerVisibility}
        onZoomIn={() => mapRef.current?.zoomIn()}
        onZoomOut={() => mapRef.current?.zoomOut()}
      />

      {inspectorOpen ? (
        <EvidenceInspector
          result={result}
          selectedRegion={selectedRegion}
          running={running}
          error={error}
          onSelectRegion={(id) => handleSelectRegion(id)}
          onClose={() => {
            if (running) return;
            setResult(null);
            setSelectedRegionId(null);
            setStatusLine(null);
            setError(null);
            syncUrl({ region: null });
          }}
        />
      ) : null}

      <QueryComposer
        aoiLabel={aoiLabel}
        earlierDate={earlierDate}
        laterDate={laterDate}
        query={query}
        running={running}
        error={error}
        statusLine={statusLine}
        onEarlierChange={(v) => {
          setEarlierDate(v);
          syncUrl({ earlierDate: v });
        }}
        onLaterChange={(v) => {
          setLaterDate(v);
          syncUrl({ laterDate: v });
        }}
        onQueryChange={(v) => {
          setQuery(v);
          syncUrl({ query: v });
        }}
        onRun={handleRun}
        onBboxSubmit={handleBboxSubmit}
      />
    </main>
  );
}
