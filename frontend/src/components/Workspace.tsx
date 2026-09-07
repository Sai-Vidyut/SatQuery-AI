"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Map } from "maplibre-gl";
import type { AnalysisResult, AOI, ImageInput } from "@/types/domain";
import { api } from "@/lib/api";
import { parseIsoDate, validateDateRange } from "@/lib/dates";
import { normalizeAnalysisError } from "@/lib/errors";
import { aoiFromBbox, bboxFromAoi } from "@/lib/geo";
import { MapViewport } from "@/components/MapViewport";
import { MapToolCluster } from "@/components/MapToolCluster";
import { IconRail } from "@/components/IconRail";
import { QueryComposer, type ComposerInputMode } from "@/components/QueryComposer";
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

const DEFAULT_VQA_QUERY =
  "Describe the land-cover and major objects visible in this image.";
const DEFAULT_TEMPORAL_QUERY =
  "What changed between these two dates, and where did the change occur?";
const DEFAULT_PAIR_EARLIER_DATE = "2023-01-01";
const DEFAULT_PAIR_LATER_DATE = "2024-01-01";
const DEFAULT_CROSS_MODAL_QUERY =
  "Use the optical and SAR images together to identify built-up and water-covered regions.";

function applyUrlParams(params: URLSearchParams): {
  aoi: AOI | null;
  earlierDate: string;
  laterDate: string;
  query: string;
  region: string | null;
  inputMode: ComposerInputMode;
} {
  const mode = params.get("mode");
  const inputMode: ComposerInputMode =
    mode === "upload"
      ? "upload"
      : mode === "temporal_pair"
        ? "temporal_pair"
        : mode === "cross_modal"
          ? "cross_modal"
          : "catalog";
  return {
    aoi: parseBboxParam(params.get("bbox")),
    earlierDate: parseIsoDate(params.get("from")) ?? (
      inputMode === "temporal_pair" ? DEFAULT_PAIR_EARLIER_DATE : DEFAULT_EARLIER_DATE
    ),
    laterDate: parseIsoDate(params.get("to")) ?? (
      inputMode === "temporal_pair" ? DEFAULT_PAIR_LATER_DATE : DEFAULT_LATER_DATE
    ),
    query:
      params.get("q") ??
      (inputMode === "upload"
        ? DEFAULT_VQA_QUERY
        : inputMode === "temporal_pair"
          ? DEFAULT_TEMPORAL_QUERY
          : inputMode === "cross_modal"
            ? DEFAULT_CROSS_MODAL_QUERY
            : DEFAULT_QUERY),
    region: params.get("region"),
    inputMode,
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
  const [validationError, setValidationError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [inputMode, setInputMode] = useState<ComposerInputMode>("catalog");
  const [uploadedImage, setUploadedImage] = useState<ImageInput | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [uploadedEarlierImage, setUploadedEarlierImage] = useState<ImageInput | null>(null);
  const [uploadedLaterImage, setUploadedLaterImage] = useState<ImageInput | null>(null);
  const [uploadedOpticalImage, setUploadedOpticalImage] = useState<ImageInput | null>(null);
  const [uploadedSarImage, setUploadedSarImage] = useState<ImageInput | null>(null);
  const [earlierUploadStatus, setEarlierUploadStatus] = useState<string | null>(null);
  const [laterUploadStatus, setLaterUploadStatus] = useState<string | null>(null);
  const [opticalUploadStatus, setOpticalUploadStatus] = useState<string | null>(null);
  const [sarUploadStatus, setSarUploadStatus] = useState<string | null>(null);
  const [pairValidationStatus, setPairValidationStatus] = useState<string | null>(null);
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
    setInputMode(fromUrl.inputMode);
  }, []);

  const syncUrl = useCallback(
    (patch: {
      aoi?: AOI | null;
      earlierDate?: string;
      laterDate?: string;
      query?: string;
      region?: string | null;
      inputMode?: ComposerInputMode;
    }) => {
      if (typeof window === "undefined") return;
      const params = new URLSearchParams(window.location.search);
      const nextAoi = patch.aoi !== undefined ? patch.aoi : aoi;
      const nextFrom = patch.earlierDate ?? earlierDate;
      const nextTo = patch.laterDate ?? laterDate;
      const nextQ = patch.query ?? query;
      const nextRegion = patch.region !== undefined ? patch.region : selectedRegionId;
      const nextMode = patch.inputMode ?? inputMode;

      if (nextMode === "upload") params.set("mode", "upload");
      else if (nextMode === "temporal_pair") params.set("mode", "temporal_pair");
      else if (nextMode === "cross_modal") params.set("mode", "cross_modal");
      else params.delete("mode");

      if (nextAoi) {
        params.set("bbox", bboxFromAoi(nextAoi).join(","));
      } else {
        params.delete("bbox");
      }
      if (parseIsoDate(nextFrom)) params.set("from", nextFrom);
      if (parseIsoDate(nextTo)) params.set("to", nextTo);
      params.set("q", nextQ);
      if (nextRegion) params.set("region", nextRegion);
      else params.delete("region");

      const next = `${window.location.pathname}?${params.toString()}`;
      window.history.replaceState(null, "", next);
    },
    [aoi, earlierDate, laterDate, query, selectedRegionId, inputMode],
  );

  const uploadWithAcquisition = useCallback(
    async (file: File, acquisitionDate: string) => {
      const iso = `${acquisitionDate}T00:00:00+00:00`;
      return api.uploadImagery(file, { modality: "optical", acquisitionDatetime: iso });
    },
    [],
  );

  const handleFileSelect = useCallback(
    async (file: File) => {
      setValidationError(null);
      setUploadStatus("Uploading…");
      try {
        const data = await api.uploadImagery(file, { modality: "optical" });
        setUploadedImage(data.image);
        setUploadStatus(`Validated ${data.image.format} · ${data.image.width}×${data.image.height}`);
        if (data.image.bounds && data.image.bounds.length === 4) {
          const nextAoi = aoiFromBbox(data.image.bounds as [number, number, number, number]);
          setAoi(nextAoi);
          syncUrl({ aoi: nextAoi, inputMode: "upload" });
        }
      } catch (err) {
        setUploadedImage(null);
        setUploadStatus(null);
        setValidationError(normalizeAnalysisError(err));
      }
    },
    [syncUrl],
  );

  const handleEarlierFileSelect = useCallback(
    async (file: File) => {
      setValidationError(null);
      setEarlierUploadStatus("Uploading earlier image…");
      try {
        const data = await uploadWithAcquisition(file, earlierDate);
        setUploadedEarlierImage(data.image);
        setEarlierUploadStatus(
          `Before · ${data.image.format} · ${data.image.acquisition_datetime?.slice(0, 10) ?? earlierDate}`,
        );
        setPairValidationStatus(null);
        if (data.image.bounds && data.image.bounds.length === 4) {
          const nextAoi = aoiFromBbox(data.image.bounds as [number, number, number, number]);
          setAoi(nextAoi);
          syncUrl({ aoi: nextAoi, inputMode: "temporal_pair" });
        }
      } catch (err) {
        setUploadedEarlierImage(null);
        setEarlierUploadStatus(null);
        setValidationError(normalizeAnalysisError(err));
      }
    },
    [earlierDate, syncUrl, uploadWithAcquisition],
  );

  const handleLaterFileSelect = useCallback(
    async (file: File) => {
      setValidationError(null);
      setLaterUploadStatus("Uploading later image…");
      try {
        const data = await uploadWithAcquisition(file, laterDate);
        setUploadedLaterImage(data.image);
        setLaterUploadStatus(
          `After · ${data.image.format} · ${data.image.acquisition_datetime?.slice(0, 10) ?? laterDate}`,
        );
        setPairValidationStatus("Pair ready when both images are uploaded with distinct dates.");
        if (data.image.bounds && data.image.bounds.length === 4) {
          const nextAoi = aoiFromBbox(data.image.bounds as [number, number, number, number]);
          setAoi(nextAoi);
          syncUrl({ aoi: nextAoi, inputMode: "temporal_pair" });
        }
      } catch (err) {
        setUploadedLaterImage(null);
        setLaterUploadStatus(null);
        setValidationError(normalizeAnalysisError(err));
      }
    },
    [laterDate, syncUrl, uploadWithAcquisition],
  );

  const updateCrossModalValidation = useCallback(
    (optical: ImageInput | null, sar: ImageInput | null) => {
      if (!optical || !sar) {
        setPairValidationStatus(null);
        return;
      }
      const lines = [
        optical.modality === "optical" || optical.modality === "multispectral"
          ? "✓ optical"
          : "✗ optical modality",
        sar.modality === "sar" ? "✓ SAR" : "✗ SAR modality",
        optical.bounds && sar.bounds ? "✓ spatial overlap (bounds present)" : "⚠ overlap unverified",
        optical.co_registered_benchmark && sar.co_registered_benchmark
          ? "✓ co-registration (benchmark)"
          : "⚠ co-registration status not verified",
      ];
      setPairValidationStatus(lines.join(" · "));
    },
    [],
  );

  const handleOpticalFileSelect = useCallback(
    async (file: File) => {
      setValidationError(null);
      setOpticalUploadStatus("Uploading optical image…");
      try {
        const data = await api.uploadImagery(file, { modality: "optical" });
        setUploadedOpticalImage(data.image);
        setOpticalUploadStatus(
          `Optical · ${data.image.format} · ${data.image.width}×${data.image.height}`,
        );
        updateCrossModalValidation(data.image, uploadedSarImage);
        if (data.image.bounds && data.image.bounds.length === 4) {
          const nextAoi = aoiFromBbox(data.image.bounds as [number, number, number, number]);
          setAoi(nextAoi);
        }
      } catch (err) {
        setUploadedOpticalImage(null);
        setOpticalUploadStatus(null);
        setValidationError(normalizeAnalysisError(err));
      }
    },
    [updateCrossModalValidation, uploadedSarImage],
  );

  const handleSarFileSelect = useCallback(
    async (file: File) => {
      setValidationError(null);
      setSarUploadStatus("Uploading SAR image…");
      try {
        const data = await api.uploadImagery(file, { modality: "sar" });
        setUploadedSarImage(data.image);
        setSarUploadStatus(`SAR · ${data.image.format} · ${data.image.width}×${data.image.height}`);
        updateCrossModalValidation(uploadedOpticalImage, data.image);
        if (data.image.bounds && data.image.bounds.length === 4) {
          const nextAoi = aoiFromBbox(data.image.bounds as [number, number, number, number]);
          setAoi(nextAoi);
        }
      } catch (err) {
        setUploadedSarImage(null);
        setSarUploadStatus(null);
        setValidationError(normalizeAnalysisError(err));
      }
    },
    [updateCrossModalValidation, uploadedOpticalImage],
  );

  useEffect(() => {
    if (inputMode === "cross_modal") {
      updateCrossModalValidation(uploadedOpticalImage, uploadedSarImage);
    }
  }, [inputMode, uploadedOpticalImage, uploadedSarImage, updateCrossModalValidation]);

  const handleRun = useCallback(async () => {
    setValidationError(null);

    if (!query.trim()) {
      setValidationError("Query required.");
      return;
    }

    let payload;
    if (inputMode === "cross_modal") {
      if (!uploadedOpticalImage || !uploadedSarImage) {
        setValidationError("Upload both optical and SAR images before running cross-modal analysis.");
        return;
      }
      payload = {
        query,
        optical_image_id: uploadedOpticalImage.id,
        sar_image_id: uploadedSarImage.id,
      };
    } else if (inputMode === "temporal_pair") {
      if (!uploadedEarlierImage || !uploadedLaterImage) {
        setValidationError("Upload both earlier and later images before running change analysis.");
        return;
      }
      if (laterDate <= earlierDate) {
        setValidationError("After date must be later than before date.");
        return;
      }
      payload = {
        query,
        earlier_image_id: uploadedEarlierImage.id,
        later_image_id: uploadedLaterImage.id,
      };
    } else if (inputMode === "upload") {
      if (!uploadedImage) {
        setValidationError("Upload a supported GeoTIFF/TIFF image before running VQA.");
        return;
      }
      payload = { query, image_id: uploadedImage.id };
    } else {
      if (!aoi) {
        setValidationError("AOI required. Draw an area on the map or enter a bounding box.");
        return;
      }
      const dateError = validateDateRange(earlierDate, laterDate);
      if (dateError) {
        setValidationError(dateError);
        return;
      }
      payload = {
        query,
        aoi,
        earlier_date: earlierDate,
        later_date: laterDate,
        demo_mode: demoMode,
      };
    }

    if (process.env.NODE_ENV === "development") {
      console.debug("[SatQuery] submitQuery", payload);
    }

    setRunning(true);
    setAnalysisError(null);
    setResult(null);
    setSelectedRegionId(null);
    setStatusLine(null);
    runStartedAt.current = performance.now();

    try {
      const data = await api.submitQuery(payload);
      const elapsed = runStartedAt.current
        ? ((performance.now() - runStartedAt.current) / 1000).toFixed(1)
        : "?";
      setResult(data.result);
      if (data.result.cross_modal) {
        setStatusLine(
          `Cross-modal · ${data.result.cross_modal.fused_analysis.fused_region_count} fused regions · ${elapsed}s`,
        );
      } else if (data.result.bi_temporal_change) {
        setStatusLine(
          `Bi-temporal change · ${data.result.bi_temporal_change.changed_region_count} regions · ${elapsed}s`,
        );
      } else if (data.result.caption) {
        setStatusLine(
          `Scene Description · ${data.result.caption.model_name} · ${elapsed}s · ${data.result.caption.provider}`,
        );
      } else if (data.result.vqa) {
        setStatusLine(
          `VQA · ${data.result.vqa.model_name} · ${elapsed}s · ${data.result.vqa.provider}`,
        );
      } else {
        setStatusLine(
          `${data.result.evidence.length} regions · ${elapsed}s · ${earlierDate} → ${laterDate}`,
        );
      }
      syncUrl({ region: null });
    } catch (err) {
      setAnalysisError(normalizeAnalysisError(err));
    } finally {
      setRunning(false);
      runStartedAt.current = null;
    }
  }, [aoi, demoMode, earlierDate, laterDate, inputMode, query, syncUrl, uploadedImage, uploadedEarlierImage, uploadedLaterImage, uploadedOpticalImage, uploadedSarImage]);

  const handleBboxSubmit = useCallback(
    (text: string) => {
      const parts = text.split(",").map((p) => Number.parseFloat(p.trim()));
      if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) {
        setValidationError("Invalid bounding box. Use minLon, minLat, maxLon, maxLat.");
        return;
      }
      const next = aoiFromBbox(parts as [number, number, number, number]);
      setAoi(next);
      setDrawMode(false);
      setValidationError(null);
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

  const inspectorOpen = running || result != null || analysisError != null;

  return (
    <main className="relative h-[100dvh] w-full overflow-hidden bg-transparent">
      <a
        href="#map"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-[var(--radius-sm)] focus:bg-[var(--surface-strong)] focus:px-2 focus:py-1 focus:[box-shadow:var(--focus)]"
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
            setValidationError(null);
            syncUrl({ aoi: next });
          }}
          onSelectRegion={handleSelectRegion}
          mapRef={mapRef}
        />
      </div>

      {!aoi && inputMode === "catalog" ? (
        <div
          className="map-hint absolute bottom-[var(--composer-offset)] left-14 z-10"
          data-testid="empty-hint"
          role="status"
        >
          Draw an area to begin
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
        inspectorOpen={inspectorOpen}
      />

      {inspectorOpen ? (
        <EvidenceInspector
          result={result}
          selectedRegion={selectedRegion}
          running={running}
          analysisError={analysisError}
          onSelectRegion={(id) => handleSelectRegion(id)}
          onClose={() => {
            if (running) return;
            setResult(null);
            setSelectedRegionId(null);
            setStatusLine(null);
            setAnalysisError(null);
            syncUrl({ region: null });
          }}
        />
      ) : null}

      <QueryComposer
        inputMode={inputMode}
        uploadedImage={uploadedImage}
        uploadStatus={uploadStatus}
        aoiLabel={aoiLabel}
        earlierDate={earlierDate}
        laterDate={laterDate}
        query={query}
        running={running}
        validationError={validationError}
        statusLine={statusLine}
        onInputModeChange={(mode) => {
          setInputMode(mode);
          setValidationError(null);
          if (mode === "upload" && query === DEFAULT_QUERY) {
            setQuery(DEFAULT_VQA_QUERY);
            syncUrl({ inputMode: mode, query: DEFAULT_VQA_QUERY });
          } else if (mode === "temporal_pair") {
            setQuery(DEFAULT_TEMPORAL_QUERY);
            setEarlierDate(DEFAULT_PAIR_EARLIER_DATE);
            setLaterDate(DEFAULT_PAIR_LATER_DATE);
            syncUrl({
              inputMode: mode,
              query: DEFAULT_TEMPORAL_QUERY,
              earlierDate: DEFAULT_PAIR_EARLIER_DATE,
              laterDate: DEFAULT_PAIR_LATER_DATE,
            });
          } else if (mode === "cross_modal") {
            setQuery(DEFAULT_CROSS_MODAL_QUERY);
            syncUrl({ inputMode: mode, query: DEFAULT_CROSS_MODAL_QUERY });
          } else {
            syncUrl({ inputMode: mode });
          }
        }}
        onFileSelect={handleFileSelect}
        onEarlierFileSelect={handleEarlierFileSelect}
        onLaterFileSelect={handleLaterFileSelect}
        onOpticalFileSelect={handleOpticalFileSelect}
        onSarFileSelect={handleSarFileSelect}
        uploadedEarlierImage={uploadedEarlierImage}
        uploadedLaterImage={uploadedLaterImage}
        uploadedOpticalImage={uploadedOpticalImage}
        uploadedSarImage={uploadedSarImage}
        earlierUploadStatus={earlierUploadStatus}
        laterUploadStatus={laterUploadStatus}
        opticalUploadStatus={opticalUploadStatus}
        sarUploadStatus={sarUploadStatus}
        pairValidationStatus={pairValidationStatus}
        onEarlierChange={(v) => {
          setEarlierDate(v);
          setValidationError(null);
          syncUrl({ earlierDate: v });
        }}
        onLaterChange={(v) => {
          setLaterDate(v);
          setValidationError(null);
          syncUrl({ laterDate: v });
        }}
        onQueryChange={(v) => {
          setQuery(v);
          syncUrl({ query: v });
        }}
        onRun={handleRun}
        onBboxSubmit={handleBboxSubmit}
        demoMode={demoMode}
        onDemoModeChange={setDemoMode}
      />
    </main>
  );
}
