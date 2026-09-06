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

export function normalizeBbox(
  minLon: number,
  minLat: number,
  maxLon: number,
  maxLat: number,
): [number, number, number, number] {
  return [Math.min(minLon, maxLon), Math.min(minLat, maxLat), Math.max(minLon, maxLon), Math.max(minLat, maxLat)];
}

export function aoiFromBbox(bbox: [number, number, number, number]): AOI {
  const [minLon, minLat, maxLon, maxLat] = normalizeBbox(bbox[0], bbox[1], bbox[2], bbox[3]);
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

export function claimTypeColor(claimType: string | undefined): string {
  switch (claimType) {
    case "urban_expansion_candidate":
      return "#e07b39";
    case "vegetation_loss_candidate":
      return "#3d8b5f";
    case "water_shrinkage_candidate":
      return "#3b82c4";
    case "infrastructure_change_candidate":
      return "#9b7bd4";
    case "mining_change_candidate":
      return "#a67c52";
    case "construction_candidate":
    case "new_built_area":
      return "#c9a227";
    default:
      return "#c9a227";
  }
}

export function claimTypeLabel(claimType: string | undefined): string | null {
  switch (claimType) {
    case "urban_expansion_candidate":
      return "Urban expansion candidate";
    case "vegetation_loss_candidate":
      return "Vegetation loss candidate";
    case "water_shrinkage_candidate":
      return "Water shrinkage candidate";
    case "infrastructure_change_candidate":
      return "Infrastructure change candidate";
    case "mining_change_candidate":
      return "Mining change candidate";
    case "construction_candidate":
      return "Construction candidate";
    case "new_built_area":
      return "New built area";
    default:
      return null;
  }
}

export function confidenceBand(confidence: number): string {
  if (confidence >= 0.75) return "High";
  if (confidence >= 0.45) return "Medium";
  return "Low";
}

export function detectionFillOpacity(confidence: number): number {
  return 0.08 + 0.32 * confidence;
}
