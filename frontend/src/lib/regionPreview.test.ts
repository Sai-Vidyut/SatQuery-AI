import { describe, expect, it } from "vitest";
import type { AnalysisResult, EvidenceRegion } from "@/types/domain";
import {
  bboxFromGeometry,
  formatPreviewBbox,
  paddedBboxFromGeometry,
  shouldShowBeforeAfterEvidence,
} from "@/lib/regionPreview";

const REGION_GEOMETRY = {
  type: "Polygon" as const,
  coordinates: [
    [
      [77.591, 12.991],
      [77.593, 12.991],
      [77.593, 12.993],
      [77.591, 12.993],
      [77.591, 12.991],
    ],
  ],
};

const REGION: EvidenceRegion = {
  id: "ev-1",
  geometry: REGION_GEOMETRY,
  type: "change",
  confidence: 0.7,
  metrics: [],
  source: "test",
  metadata: {},
};

const BI_TEMPORAL_RESULT = {
  bi_temporal_change: {
    task: "bi_temporal_change_vqa" as const,
    change_summary: "Change detected",
    question: "What changed?",
    changed_region_count: 1,
    change_map_available: true,
    detector: "uploaded_bi_temporal",
    provider: "uploaded_cva" as const,
    provenance: "test",
    confidence_available: false,
    earlier_image_id: "a" + "0".repeat(31),
    later_image_id: "b" + "0".repeat(31),
    earlier_acquisition: "2023-01-01T00:00:00Z",
    later_acquisition: "2024-01-01T00:00:00Z",
    earlier_date: "2023-01-01",
    later_date: "2024-01-01",
  },
} as AnalysisResult;

describe("regionPreview helpers", () => {
  it("computes bbox from polygon geometry", () => {
    expect(bboxFromGeometry(REGION_GEOMETRY)).toEqual([77.591, 12.991, 77.593, 12.993]);
  });

  it("adds padding around region bbox", () => {
    const padded = paddedBboxFromGeometry(REGION_GEOMETRY, 0.25);
    expect(padded).not.toBeNull();
    expect(padded![0]).toBeLessThan(77.591);
    expect(padded![2]).toBeGreaterThan(77.593);
  });

  it("formats bbox for preview query param", () => {
    expect(formatPreviewBbox([77.591, 12.991, 77.593, 12.993])).toBe(
      "77.591000,12.991000,77.593000,12.993000",
    );
  });

  it("shows before/after only for bi-temporal results with selected region", () => {
    expect(shouldShowBeforeAfterEvidence(BI_TEMPORAL_RESULT, REGION)).toBe(true);
    expect(shouldShowBeforeAfterEvidence(BI_TEMPORAL_RESULT, null)).toBe(false);
    expect(shouldShowBeforeAfterEvidence({ ...BI_TEMPORAL_RESULT, bi_temporal_change: null }, REGION)).toBe(
      false,
    );
  });
});
