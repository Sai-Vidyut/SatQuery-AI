import type { AOI, GeoJSONGeometry } from "@/types/domain";

/** Default demo AOI near Bengaluru for first load. */
export const DEFAULT_AOI: AOI = {
  geometry: {
    type: "Polygon",
    coordinates: [
      [
        [77.59, 12.97],
        [77.61, 12.97],
        [77.61, 12.99],
        [77.59, 12.99],
        [77.59, 12.97],
      ],
    ],
  },
  area_km2: 4.8,
};

export function bboxFromAoi(aoi: AOI): [number, number, number, number] {
  const ring = (aoi.geometry.coordinates as number[][][])[0];
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
}

export function aoiFromBbox(bbox: [number, number, number, number]): AOI {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  const geometry: GeoJSONGeometry = {
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
  };
  const width = (maxLon - minLon) * 111 * Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
  const height = (maxLat - minLat) * 111;
  return {
    geometry,
    area_km2: Math.round(width * height * 100) / 100,
  };
}

export function confidenceBand(confidence: number): string {
  if (confidence >= 0.75) return "High";
  if (confidence >= 0.45) return "Medium";
  return "Low";
}

export function detectionFillOpacity(confidence: number): number {
  return 0.08 + 0.32 * confidence;
}
