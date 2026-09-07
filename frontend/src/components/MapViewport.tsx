"use client";

import { useEffect, useRef, useCallback, type MutableRefObject } from "react";
import maplibregl, { type GeoJSONSource, type Map } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import type { AOI, EvidenceRegion } from "@/types/domain";
import { aoiFromBbox, bboxFromAoi, claimTypeColor, detectionFillOpacity, getAccentColor, normalizeBbox } from "@/lib/geo";

const ESRI_ATTRIBUTION =
  "Tiles © Esri — Imagery: Maxar, Earthstar Geographics; Labels: Esri, TomTom, Garmin, FAO, NOAA, USGS, © OpenStreetMap contributors";

const ESRI_IMAGERY_TILES = [
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
];

/** Place-name / boundary overlay (transparent PNG). No API key. Added after imagery loads. */
const ESRI_LABELS_TILES = [
  "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
];

/** Esri World Imagery raster only — labels are added in map.on("load") above imagery, below AOI. */
const SATELLITE_STYLE = {
  version: 8 as const,
  sources: {
    satellite: {
      type: "raster" as const,
      tiles: ESRI_IMAGERY_TILES,
      tileSize: 256,
      attribution: ESRI_ATTRIBUTION,
    },
  },
  layers: [
    {
      id: "satellite",
      type: "raster" as const,
      source: "satellite",
    },
  ],
};

function addLabelsOverlay(map: Map) {
  if (map.getSource("labels")) return;
  map.addSource("labels", {
    type: "raster",
    tiles: ESRI_LABELS_TILES,
    tileSize: 256,
    attribution: ESRI_ATTRIBUTION,
  });
  map.addLayer({
    id: "labels",
    type: "raster",
    source: "labels",
  });
}

const MIN_AOI_SPAN = 0.0001;

type LayerVisibility = {
  detections: boolean;
  aoi: boolean;
};

type Props = {
  aoi: AOI | null;
  evidence: EvidenceRegion[];
  selectedRegionId: string | null;
  drawMode: boolean;
  layerVisibility: LayerVisibility;
  onAoiDrawn: (aoi: AOI) => void;
  onSelectRegion: (id: string | null) => void;
  mapRef?: MutableRefObject<Map | null>;
};

function draftFeatureFromBbox(bbox: [number, number, number, number]): FeatureCollection {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [minLon, minLat],
              [maxLon, minLat],
              [maxLon, maxLat],
              [minLon, maxLat],
              [minLon, minLat],
            ],
          ],
        },
      },
    ],
  };
}

export function MapViewport({
  aoi,
  evidence,
  selectedRegionId,
  drawMode,
  layerVisibility,
  onAoiDrawn,
  onSelectRegion,
  mapRef: externalMapRef,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const internalMapRef = useRef<Map | null>(null);
  const mapRef = externalMapRef ?? internalMapRef;
  const drawingRef = useRef(false);
  const drawStartRef = useRef<[number, number] | null>(null);
  const onAoiDrawnRef = useRef(onAoiDrawn);
  onAoiDrawnRef.current = onAoiDrawn;

  const setDraftBbox = useCallback(
    (bbox: [number, number, number, number] | null) => {
      const map = mapRef.current;
      if (!map || !map.isStyleLoaded()) return;
      const source = map.getSource("aoi-draft") as GeoJSONSource | undefined;
      if (!source) return;
      if (!bbox) {
        source.setData({ type: "FeatureCollection", features: [] });
        return;
      }
      source.setData(draftFeatureFromBbox(bbox));
    },
    [mapRef],
  );

  const clearDrawing = useCallback(() => {
    drawingRef.current = false;
    drawStartRef.current = null;
    setDraftBbox(null);
  }, [setDraftBbox]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // HMR can leave a stale Map on the shared ref while the container is new.
    if (mapRef.current) {
      mapRef.current.remove();
      mapRef.current = null;
    }

    const map = new maplibregl.Map({
      container,
      style: SATELLITE_STYLE,
      center: [77.6, 12.98],
      zoom: 13,
      attributionControl: false,
    });

    map.on("error", (event) => {
      console.error("[map]", event.error?.message ?? event);
    });

    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-left",
    );

    map.on("load", () => {
      try {
        addLabelsOverlay(map);
      } catch (err) {
        console.warn("[map] Labels overlay unavailable; satellite imagery only.", err);
      }

      const accent = getAccentColor();
      map.addSource("aoi", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "aoi-fill",
        type: "fill",
        source: "aoi",
        paint: {
          "fill-color": accent,
          "fill-opacity": 0.14,
        },
      });
      map.addLayer({
        id: "aoi-line",
        type: "line",
        source: "aoi",
        paint: {
          "line-color": accent,
          "line-width": 2,
        },
      });

      map.addSource("aoi-draft", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "aoi-draft-fill",
        type: "fill",
        source: "aoi-draft",
        paint: {
          "fill-color": accent,
          "fill-opacity": 0.08,
        },
      });
      map.addLayer({
        id: "aoi-draft-line",
        type: "line",
        source: "aoi-draft",
        paint: {
          "line-color": accent,
          "line-width": 2,
          "line-dasharray": [2, 1],
        },
      });

      map.addSource("detections", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "detections-fill",
        type: "fill",
        source: "detections",
        paint: {
          "fill-color": ["get", "fillColor"],
          "fill-opacity": ["get", "fillOpacity"],
        },
      });
      map.addLayer({
        id: "detections-line",
        type: "line",
        source: "detections",
        paint: {
          "line-color": ["get", "fillColor"],
          "line-width": ["get", "lineWidth"],
        },
      });
    });

    mapRef.current = map;
    requestAnimationFrame(() => map.resize());

    return () => {
      map.remove();
      if (mapRef.current === map) {
        mapRef.current = null;
      }
    };
  }, [mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = map.getSource("aoi") as GeoJSONSource | undefined;
    if (!source) return;

    if (aoi) {
      source.setData({
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: {},
            geometry: aoi.geometry as FeatureCollection["features"][0]["geometry"],
          },
        ],
      });
    } else {
      source.setData({ type: "FeatureCollection", features: [] });
    }
  }, [aoi, mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const source = map.getSource("detections") as GeoJSONSource | undefined;
    if (!source) return;

    source.setData({
      type: "FeatureCollection",
      features: evidence.map((r) => {
        const selected = r.id === selectedRegionId;
        return {
          type: "Feature" as const,
          properties: {
            id: r.id,
            fillColor: claimTypeColor(
              typeof r.metadata?.claim_type === "string" ? r.metadata.claim_type : undefined,
            ),
            fillOpacity: detectionFillOpacity(r.confidence) + (selected ? 0.1 : 0),
            lineWidth: selected ? 2.5 : 1.5,
          },
          geometry: r.geometry as FeatureCollection["features"][0]["geometry"],
        };
      }),
    });
  }, [evidence, selectedRegionId, mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const vis = layerVisibility.aoi ? "visible" : "none";
    map.setLayoutProperty("aoi-fill", "visibility", vis);
    map.setLayoutProperty("aoi-line", "visibility", vis);
    map.setLayoutProperty("aoi-draft-fill", "visibility", vis);
    map.setLayoutProperty("aoi-draft-line", "visibility", vis);
  }, [layerVisibility.aoi, mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const vis = layerVisibility.detections ? "visible" : "none";
    map.setLayoutProperty("detections-fill", "visibility", vis);
    map.setLayoutProperty("detections-line", "visibility", vis);
  }, [layerVisibility.detections, mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (drawMode) {
      map.dragPan.disable();
      map.boxZoom.disable();
      map.doubleClickZoom.disable();
      map.getCanvas().style.cursor = "crosshair";
    } else {
      map.dragPan.enable();
      map.boxZoom.enable();
      map.doubleClickZoom.enable();
      map.getCanvas().style.cursor = "";
      clearDrawing();
    }
  }, [drawMode, clearDrawing, mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !drawMode) return;

    const canvas = map.getCanvas();

    const lngLatFromPointer = (e: PointerEvent): [number, number] => {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const ll = map.unproject([x, y]);
      return [ll.lng, ll.lat];
    };

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      e.preventDefault();
      e.stopPropagation();
      drawingRef.current = true;
      drawStartRef.current = lngLatFromPointer(e);
      canvas.setPointerCapture(e.pointerId);
    };

    const onPointerMove = (e: PointerEvent) => {
      if (!drawingRef.current || !drawStartRef.current) return;
      e.preventDefault();
      e.stopPropagation();
      const [x0, y0] = drawStartRef.current;
      const [x1, y1] = lngLatFromPointer(e);
      setDraftBbox(normalizeBbox(x0, y0, x1, y1));
    };

    const onPointerUp = (e: PointerEvent) => {
      if (!drawingRef.current || !drawStartRef.current) return;
      e.preventDefault();
      e.stopPropagation();

      const [x0, y0] = drawStartRef.current;
      const [x1, y1] = lngLatFromPointer(e);
      const bbox = normalizeBbox(x0, y0, x1, y1);

      drawingRef.current = false;
      drawStartRef.current = null;
      setDraftBbox(null);

      if (canvas.hasPointerCapture(e.pointerId)) {
        canvas.releasePointerCapture(e.pointerId);
      }

      const [minLon, minLat, maxLon, maxLat] = bbox;
      if (maxLon - minLon < MIN_AOI_SPAN || maxLat - minLat < MIN_AOI_SPAN) {
        return;
      }

      onAoiDrawnRef.current(aoiFromBbox(bbox));
    };

    const onPointerCancel = () => {
      if (canvas.releasePointerCapture) {
        try {
          canvas.releasePointerCapture(0);
        } catch {
          // ignore if no capture
        }
      }
      clearDrawing();
    };

    canvas.addEventListener("pointerdown", onPointerDown, { capture: true });
    canvas.addEventListener("pointermove", onPointerMove, { capture: true });
    canvas.addEventListener("pointerup", onPointerUp, { capture: true });
    canvas.addEventListener("pointercancel", onPointerCancel, { capture: true });

    return () => {
      canvas.removeEventListener("pointerdown", onPointerDown, { capture: true });
      canvas.removeEventListener("pointermove", onPointerMove, { capture: true });
      canvas.removeEventListener("pointerup", onPointerUp, { capture: true });
      canvas.removeEventListener("pointercancel", onPointerCancel, { capture: true });
      clearDrawing();
    };
  }, [drawMode, clearDrawing, setDraftBbox, mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || drawMode) return;

    const onDetectionClick = (e: maplibregl.MapLayerMouseEvent) => {
      const feature = e.features?.[0];
      const id = feature?.properties?.id;
      if (typeof id === "string") {
        onSelectRegion(id);
      }
    };

    const onMapClick = (e: maplibregl.MapMouseEvent) => {
      const hits = map.queryRenderedFeatures(e.point, {
        layers: ["detections-fill", "detections-line"],
      });
      if (hits.length === 0) {
        onSelectRegion(null);
      }
    };

    map.on("click", "detections-fill", onDetectionClick);
    map.on("click", onMapClick);
    map.on("mouseenter", "detections-fill", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "detections-fill", () => {
      map.getCanvas().style.cursor = "";
    });

    return () => {
      map.off("click", "detections-fill", onDetectionClick);
      map.off("click", onMapClick);
    };
  }, [drawMode, onSelectRegion, mapRef]);

  const fitAoi = useCallback(() => {
    const map = mapRef.current;
    if (!map || !aoi) return;
    const bbox = bboxFromAoi(aoi);
    map.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: { top: 48, bottom: 96, left: 56, right: 400 }, duration: 500 },
    );
  }, [aoi, mapRef]);

  useEffect(() => {
    if (aoi) fitAoi();
  }, [aoi, fitAoi]);

  return (
    <div
      ref={containerRef}
      data-testid="map"
      data-draw-active={drawMode ? "true" : "false"}
      className="absolute inset-0 z-0 h-full w-full min-h-[50dvh]"
      role="application"
      aria-label="Satellite map"
    />
  );
}
