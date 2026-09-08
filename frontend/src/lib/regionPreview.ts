import type { AnalysisResult, EvidenceRegion, GeoJSONGeometry } from "@/types/domain";
import { bboxFromAoi, normalizeBbox } from "@/lib/geo";

export type PreviewBbox = [number, number, number, number];

export function bboxFromGeometry(geometry: GeoJSONGeometry): PreviewBbox | null {
  if (geometry.type !== "Polygon") return null;
  const ring = geometry.coordinates[0] as number[][];
  if (!ring?.length) return null;
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return normalizeBbox(
    Math.min(...lons),
    Math.min(...lats),
    Math.max(...lons),
    Math.max(...lats),
  );
}

export function paddedBboxFromGeometry(
  geometry: GeoJSONGeometry,
  paddingRatio = 0.25,
): PreviewBbox | null {
  const bbox = bboxFromGeometry(geometry);
  if (!bbox) return null;
  const [minLon, minLat, maxLon, maxLat] = bbox;
  const padLon = Math.max((maxLon - minLon) * paddingRatio, 0.00005);
  const padLat = Math.max((maxLat - minLat) * paddingRatio, 0.00005);
  return normalizeBbox(minLon - padLon, minLat - padLat, maxLon + padLon, maxLat + padLat);
}

export function formatPreviewBbox(bbox: PreviewBbox): string {
  return bbox.map((value) => value.toFixed(6)).join(",");
}

export function shouldShowBeforeAfterEvidence(
  result: AnalysisResult | null,
  selectedRegion: EvidenceRegion | null,
): boolean {
  return Boolean(result?.bi_temporal_change && selectedRegion);
}

export function beforeAfterImageIds(result: AnalysisResult): {
  earlierImageId: string;
  laterImageId: string;
} | null {
  const bt = result.bi_temporal_change;
  if (!bt) return null;
  return {
    earlierImageId: bt.earlier_image_id,
    laterImageId: bt.later_image_id,
  };
}

/** Re-export for map fitBounds on region selection. */
export { bboxFromAoi };
