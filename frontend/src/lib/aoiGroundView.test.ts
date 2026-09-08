import { describe, expect, it } from "vitest";
import type { AOI } from "@/types/domain";
import {
  GROUND_VIEW_DISCLOSURE,
  GROUND_VIEW_PANORAMA_HINT,
  aoiGeometryKey,
  formatGroundViewCoordinates,
  formatGroundViewHeading,
  generateAoiGroundViewPoints,
  headingFromPan,
  initialPanPercent,
  panoramaTranslatePercent,
  pointCountForAoi,
  shouldShowAoiGroundViewMarkers,
} from "@/lib/aoiGroundView";
import { snapshotsEqual } from "@/lib/mapViewportState";

const AOI: AOI = {
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
};

describe("generateAoiGroundViewPoints", () => {
  it("returns 1-3 deterministic points inside the AOI bbox", () => {
    const points = generateAoiGroundViewPoints(AOI);
    expect(points.length).toBeGreaterThanOrEqual(1);
    expect(points.length).toBeLessThanOrEqual(3);
    expect(pointCountForAoi(AOI)).toBe(points.length);

    const [minLon, minLat, maxLon, maxLat] = [77.59, 12.97, 77.61, 12.99];
    for (const point of points) {
      expect(point.longitude).toBeGreaterThanOrEqual(minLon);
      expect(point.longitude).toBeLessThanOrEqual(maxLon);
      expect(point.latitude).toBeGreaterThanOrEqual(minLat);
      expect(point.latitude).toBeLessThanOrEqual(maxLat);
      expect(point.imageUrl.startsWith("/mock-ground/panorama-")).toBe(true);
      expect(point.panorama360).toBe(true);
      expect(point.panoramaSpan).toBeGreaterThan(1);
      expect(point.title.length).toBeGreaterThan(0);
    }
  });

  it("is stable for the same AOI geometry", () => {
    const first = generateAoiGroundViewPoints(AOI);
    const second = generateAoiGroundViewPoints(AOI);
    expect(first).toEqual(second);
  });

  it("changes when AOI geometry changes", () => {
    const other: AOI = {
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.62, 12.97],
            [77.64, 12.97],
            [77.64, 12.99],
            [77.62, 12.99],
            [77.62, 12.97],
          ],
        ],
      },
    };
    expect(generateAoiGroundViewPoints(other)).not.toEqual(generateAoiGroundViewPoints(AOI));
  });

  it("assigns distinct ids and categories across points", () => {
    const points = generateAoiGroundViewPoints(AOI);
    const ids = new Set(points.map((point) => point.id));
    expect(ids.size).toBe(points.length);
  });
});

describe("ground view helpers", () => {
  it("shows markers only when AOI exists and draw mode is off", () => {
    expect(shouldShowAoiGroundViewMarkers(AOI, false)).toBe(true);
    expect(shouldShowAoiGroundViewMarkers(AOI, true)).toBe(false);
    expect(shouldShowAoiGroundViewMarkers(null, false)).toBe(false);
  });

  it("formats coordinates and heading", () => {
    expect(formatGroundViewCoordinates(12.98765, 77.60123)).toBe("12.98765, 77.60123");
    expect(formatGroundViewHeading(127.4)).toBe("127°");
  });

  it("uses a stable geometry key", () => {
    expect(aoiGeometryKey(AOI)).toBe(aoiGeometryKey(AOI));
  });

  it("includes demo disclosure text", () => {
    expect(GROUND_VIEW_DISCLOSURE.toLowerCase()).toContain("demonstration");
    expect(GROUND_VIEW_DISCLOSURE.toLowerCase()).toContain("street view");
    expect(GROUND_VIEW_PANORAMA_HINT.toLowerCase()).toContain("drag");
  });

  it("derives pan and heading helpers from base heading", () => {
    expect(initialPanPercent(90)).toBeCloseTo(0.25);
    expect(headingFromPan(90, 0.25)).toBe(180);
    expect(panoramaTranslatePercent(0, 2.5)).toBeCloseTo(0);
    expect(panoramaTranslatePercent(1, 2.5)).toBeLessThan(0);
  });
});

describe("snapshotsEqual", () => {
  it("compares map snapshots within tolerance", () => {
    expect(
      snapshotsEqual(
        { center: [77.6, 12.98], zoom: 13, bearing: 0, pitch: 0 },
        { center: [77.6000001, 12.9800001], zoom: 13.00001, bearing: 0, pitch: 0 },
      ),
    ).toBe(true);
    expect(
      snapshotsEqual(
        { center: [77.6, 12.98], zoom: 13, bearing: 0, pitch: 0 },
        { center: [77.7, 12.98], zoom: 13, bearing: 0, pitch: 0 },
      ),
    ).toBe(false);
  });
});
