"use client";

import { useEffect, useRef, useCallback, type MutableRefObject } from "react";
import maplibregl, { type GeoJSONSource, type Map } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import type { AOI, EvidenceRegion } from "@/types/domain";
import { aoiFromBbox, bboxFromAoi, detectionFillOpacity } from "@/lib/geo";

const SATELLITE_STYLE = {
  version: 8 as const,
  sources: {
    satellite: {
      type: "raster" as const,
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution:
        "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
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
  const drawStartRef = useRef<[number, number] | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: SATELLITE_STYLE,
      center: [77.6, 12.98],
      zoom: 13,
      attributionControl: false,
    });

    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-left",
    );

    map.on("load", () => {
      map.addSource("aoi", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "aoi-fill",
        type: "fill",
        source: "aoi",
        paint: {
          "fill-color": "#c9a227",
          "fill-opacity": 0.14,
        },
      });
      map.addLayer({
        id: "aoi-line",
        type: "line",
        source: "aoi",
        paint: {
          "line-color": "#c9a227",
          "line-width": 2,
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
          "fill-color": "#c9a227",
          "fill-opacity": ["get", "fillOpacity"],
        },
      });
      map.addLayer({
        id: "detections-line",
        type: "line",
        source: "detections",
        paint: {
          "line-color": "#c9a227",
          "line-width": ["get", "lineWidth"],
        },
      });
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
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

    const onMouseDown = (e: maplibregl.MapMouseEvent) => {
      if (!drawMode) return;
      drawStartRef.current = [e.lngLat.lng, e.lngLat.lat];
      map.getCanvas().style.cursor = "crosshair";
    };

    const onMouseUp = (e: maplibregl.MapMouseEvent) => {
      if (!drawMode || !drawStartRef.current) return;
      const [x0, y0] = drawStartRef.current;
      const x1 = e.lngLat.lng;
      const y1 = e.lngLat.lat;
      drawStartRef.current = null;
      map.getCanvas().style.cursor = "";

      const minLon = Math.min(x0, x1);
      const maxLon = Math.max(x0, x1);
      const minLat = Math.min(y0, y1);
      const maxLat = Math.max(y0, y1);

      if (Math.abs(maxLon - minLon) < 0.0001 || Math.abs(maxLat - minLat) < 0.0001) return;

      onAoiDrawn(aoiFromBbox([minLon, minLat, maxLon, maxLat]));
    };

    const onDetectionClick = (e: maplibregl.MapLayerMouseEvent) => {
      if (drawMode) return;
      const feature = e.features?.[0];
      const id = feature?.properties?.id;
      if (typeof id === "string") {
        onSelectRegion(id);
      }
    };

    const onMapClick = (e: maplibregl.MapMouseEvent) => {
      if (drawMode) return;
      const hits = map.queryRenderedFeatures(e.point, {
        layers: ["detections-fill", "detections-line"],
      });
      if (hits.length === 0) {
        onSelectRegion(null);
      }
    };

    map.on("mousedown", onMouseDown);
    map.on("mouseup", onMouseUp);
    map.on("click", "detections-fill", onDetectionClick);
    map.on("click", onMapClick);
    map.on("mouseenter", "detections-fill", () => {
      if (!drawMode) map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "detections-fill", () => {
      if (!drawMode) map.getCanvas().style.cursor = "";
    });

    return () => {
      map.off("mousedown", onMouseDown);
      map.off("mouseup", onMouseUp);
      map.off("click", "detections-fill", onDetectionClick);
      map.off("click", onMapClick);
    };
  }, [drawMode, onAoiDrawn, onSelectRegion, mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.getCanvas().style.cursor = drawMode ? "crosshair" : "";
  }, [drawMode, mapRef]);

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
      className="absolute inset-0 z-0 h-full w-full min-h-[50dvh]"
      role="application"
      aria-label="Satellite map"
    />
  );
}

export function useMapControls(mapRef: React.RefObject<Map | null>) {
  return {
    zoomIn: () => mapRef.current?.zoomIn(),
    zoomOut: () => mapRef.current?.zoomOut(),
    recenterAoi: (aoi: AOI | null) => {
      if (!mapRef.current || !aoi) return;
      const bbox = bboxFromAoi(aoi);
      mapRef.current.fitBounds(
        [
          [bbox[0], bbox[1]],
          [bbox[2], bbox[3]],
        ],
        { padding: { top: 48, bottom: 96, left: 56, right: 400 }, duration: 500 },
      );
    },
  };
}
