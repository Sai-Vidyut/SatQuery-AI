import { describe, expect, it } from "vitest";
import { aoiFromBbox, bboxFromAoi, confidenceBand, detectionFillOpacity, normalizeBbox } from "@/lib/geo";

describe("geo helpers", () => {
  it("maps confidence to band labels", () => {
    expect(confidenceBand(0.8)).toBe("High");
    expect(confidenceBand(0.5)).toBe("Medium");
    expect(confidenceBand(0.2)).toBe("Low");
  });

  it("computes detection fill opacity", () => {
    expect(detectionFillOpacity(0.5)).toBeCloseTo(0.24);
  });

  it("normalizes bbox regardless of drag direction", () => {
    const forward = normalizeBbox(77.59, 12.97, 77.61, 12.99);
    const reverse = normalizeBbox(77.61, 12.99, 77.59, 12.97);
    expect(reverse).toEqual(forward);
  });

  it("produces closed polygon rings from both drag directions", () => {
    const forward = aoiFromBbox([77.59, 12.97, 77.61, 12.99]);
    const reverse = aoiFromBbox([77.61, 12.99, 77.59, 12.97]);
    expect(bboxFromAoi(forward)).toEqual(bboxFromAoi(reverse));
    const ring = forward.geometry.coordinates[0] as number[][];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });
});
