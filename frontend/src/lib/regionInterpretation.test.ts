import { describe, expect, it } from "vitest";
import { shouldShowRegionInterpretation, regionInterpretationProviderLabel } from "@/lib/regionInterpretation";
import type { AnalysisResult, EvidenceRegion } from "@/types/domain";

const REGION: EvidenceRegion = {
  id: "change-region-01",
  geometry: {
    type: "Polygon",
    coordinates: [
      [
        [77.591, 12.991],
        [77.593, 12.991],
        [77.593, 12.993],
        [77.591, 12.993],
        [77.591, 12.991],
      ],
    ],
  },
  type: "change",
  confidence: 0.47,
  metrics: [],
  source: "uploaded_bi_temporal",
  metadata: {},
};

const BI_TEMPORAL: AnalysisResult = {
  status: "completed",
  session_id: "sess-1",
  answer: "Detected change",
  confidence: 0.47,
  confidence_available: true,
  metrics: [],
  evidence: [REGION],
  trace: [],
  mode: "development",
  demonstration_data: false,
  bi_temporal_change: {
    task: "bi_temporal_change_vqa",
    change_summary: "Change detected",
    question: "What changed?",
    changed_region_count: 1,
    change_map_available: true,
    detector: "uploaded_bi_temporal",
    provider: "uploaded_cva",
    provenance: "test",
    confidence_available: false,
    earlier_image_id: "a".repeat(32),
    later_image_id: "b".repeat(32),
    earlier_acquisition: "2023-01-01T00:00:00Z",
    later_acquisition: "2024-01-01T00:00:00Z",
    earlier_date: "2023-01-01",
    later_date: "2024-01-01",
  },
};

describe("shouldShowRegionInterpretation", () => {
  it("shows for bi-temporal selected region", () => {
    expect(shouldShowRegionInterpretation(BI_TEMPORAL, REGION)).toBe(true);
  });

  it("hides for catalog-only result", () => {
    expect(shouldShowRegionInterpretation({ ...BI_TEMPORAL, bi_temporal_change: null }, REGION)).toBe(
      false,
    );
  });

  it("hides when no region selected", () => {
    expect(shouldShowRegionInterpretation(BI_TEMPORAL, null)).toBe(false);
  });
});

describe("regionInterpretationProviderLabel", () => {
  it("labels development provider", () => {
    expect(regionInterpretationProviderLabel("development")).toBe("DEVELOPMENT MOCK");
  });

  it("labels real GeoChat provider", () => {
    expect(regionInterpretationProviderLabel("geochat_service")).toBe("REAL GeoChat-7B");
  });
});
