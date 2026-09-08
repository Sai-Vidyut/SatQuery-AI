import type { AOI } from "@/types/domain";
import { bboxFromAoi } from "@/lib/geo";

export type GroundViewSceneCategory =
  | "urban_roadside"
  | "vegetation_edge"
  | "construction_edge"
  | "water_edge"
  | "roadside_open";

export interface GroundViewPoint {
  id: string;
  latitude: number;
  longitude: number;
  title: string;
  category: GroundViewSceneCategory;
  description: string;
  imageUrl: string;
  imageAlt: string;
  assetId: string;
  heading: number;
  captureDate: string;
  panorama360: boolean;
  panoramaSpan: number;
}

export const GROUND_VIEW_DISCLOSURE =
  "Demonstration imagery — not real Street View.";

export const GROUND_VIEW_PANORAMA_HINT = "Drag horizontally to look around the mock panorama.";

const POSITION_GRID: Array<[number, number]> = [
  [0.32, 0.34],
  [0.68, 0.38],
  [0.5, 0.66],
];

const CATEGORY_ORDER: GroundViewSceneCategory[] = [
  "urban_roadside",
  "vegetation_edge",
  "construction_edge",
  "water_edge",
  "roadside_open",
];

const SCENE_LIBRARY: Record<
  GroundViewSceneCategory,
  Pick<
    GroundViewPoint,
    | "title"
    | "description"
    | "imageUrl"
    | "imageAlt"
    | "assetId"
    | "panorama360"
    | "panoramaSpan"
  >
> = {
  urban_roadside: {
    title: "Urban plaza context",
    description: "Mock 360° ground-level panorama associated with the selected AOI.",
    assetId: "mock-ground-panorama-urban",
    imageUrl: "/mock-ground/panorama-urban-plaza.jpg",
    imageAlt: "Demonstration urban plaza panorama (not real Street View)",
    panorama360: true,
    panoramaSpan: 2.6,
  },
  vegetation_edge: {
    title: "Scenic overlook context",
    description: "Mock 360° ground-level panorama associated with the selected AOI.",
    assetId: "mock-ground-panorama-scenic",
    imageUrl: "/mock-ground/panorama-scenic-overlook.jpg",
    imageAlt: "Demonstration scenic overlook panorama (not real Street View)",
    panorama360: true,
    panoramaSpan: 2.8,
  },
  construction_edge: {
    title: "Developed streetscape context",
    description: "Mock 360° ground-level panorama associated with the selected AOI.",
    assetId: "mock-ground-panorama-street",
    imageUrl: "/mock-ground/panorama-roadside-street.jpg",
    imageAlt: "Demonstration streetscape panorama (not real Street View)",
    panorama360: true,
    panoramaSpan: 2.5,
  },
  water_edge: {
    title: "River valley context",
    description: "Mock 360° ground-level panorama associated with the selected AOI.",
    assetId: "mock-ground-panorama-scenic",
    imageUrl: "/mock-ground/panorama-scenic-overlook.jpg",
    imageAlt: "Demonstration river valley panorama (not real Street View)",
    panorama360: true,
    panoramaSpan: 2.8,
  },
  roadside_open: {
    title: "Roadside street context",
    description: "Mock 360° ground-level panorama associated with the selected AOI.",
    assetId: "mock-ground-panorama-street",
    imageUrl: "/mock-ground/panorama-roadside-street.jpg",
    imageAlt: "Demonstration roadside street panorama (not real Street View)",
    panorama360: true,
    panoramaSpan: 2.5,
  },
};

function stableDigest(input: string): number {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function stableInt(key: string, salt: string, modulo: number): number {
  return stableDigest(`${key}|${salt}`) % modulo;
}

export function aoiGeometryKey(aoi: AOI): string {
  return JSON.stringify(aoi.geometry.coordinates);
}

export function pointCountForAoi(aoi: AOI): number {
  return 1 + stableInt(aoiGeometryKey(aoi), "point-count", 3);
}

export function initialPanPercent(heading: number): number {
  const normalized = ((heading % 360) + 360) % 360;
  return normalized / 360;
}

export function headingFromPan(baseHeading: number, pan: number): number {
  const normalizedPan = Math.min(1, Math.max(0, pan));
  return Math.round((baseHeading + normalizedPan * 360) % 360);
}

export function panoramaTranslatePercent(pan: number, span: number): number {
  const normalizedPan = Math.min(1, Math.max(0, pan));
  const maxShift = ((span - 1) / span) * 100;
  return -normalizedPan * maxShift;
}

export function generateAoiGroundViewPoints(aoi: AOI): GroundViewPoint[] {
  const key = aoiGeometryKey(aoi);
  const [minLon, minLat, maxLon, maxLat] = bboxFromAoi(aoi);
  const count = pointCountForAoi(aoi);
  const startIndex = stableInt(key, "grid-start", POSITION_GRID.length);

  return Array.from({ length: count }, (_, index) => {
    const grid = POSITION_GRID[(startIndex + index) % POSITION_GRID.length];
    const lon = minLon + (maxLon - minLon) * grid[0];
    const lat = minLat + (maxLat - minLat) * grid[1];
    const category =
      CATEGORY_ORDER[(stableInt(key, `category-${index}`, CATEGORY_ORDER.length) + index) %
        CATEGORY_ORDER.length];
    const scene = SCENE_LIBRARY[category];
    const heading = stableInt(key, `heading-${index}`, 360);
    const captureOffsetDays = stableInt(key, `capture-${index}`, 28);
    const capture = new Date(Date.UTC(2024, 5, 15));
    capture.setUTCDate(capture.getUTCDate() - captureOffsetDays);

    return {
      id: `ground-view-${index + 1}-${stableInt(key, `id-${index}`, 10_000)}`,
      latitude: lat,
      longitude: lon,
      category,
      heading,
      captureDate: capture.toISOString().slice(0, 10),
      ...scene,
    };
  });
}

export function shouldShowAoiGroundViewMarkers(aoi: AOI | null, drawMode: boolean): boolean {
  return Boolean(aoi) && !drawMode;
}

export function formatGroundViewCoordinates(latitude: number, longitude: number): string {
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
}

export function formatGroundViewHeading(heading: number): string {
  return `${Math.round(heading)}°`;
}
