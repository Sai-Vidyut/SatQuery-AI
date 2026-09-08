import type { Map } from "maplibre-gl";

export interface MapViewportSnapshot {
  center: [number, number];
  zoom: number;
  bearing: number;
  pitch: number;
}

export function captureMapViewportState(map: Map): MapViewportSnapshot {
  const center = map.getCenter();
  return {
    center: [center.lng, center.lat],
    zoom: map.getZoom(),
    bearing: map.getBearing(),
    pitch: map.getPitch(),
  };
}

export function restoreMapViewportState(map: Map, snapshot: MapViewportSnapshot): void {
  map.jumpTo({
    center: snapshot.center,
    zoom: snapshot.zoom,
    bearing: snapshot.bearing,
    pitch: snapshot.pitch,
  });
}

export function snapshotsEqual(a: MapViewportSnapshot, b: MapViewportSnapshot): boolean {
  return (
    Math.abs(a.center[0] - b.center[0]) < 1e-6 &&
    Math.abs(a.center[1] - b.center[1]) < 1e-6 &&
    Math.abs(a.zoom - b.zoom) < 1e-4 &&
    Math.abs(a.bearing - b.bearing) < 1e-4 &&
    Math.abs(a.pitch - b.pitch) < 1e-4
  );
}
