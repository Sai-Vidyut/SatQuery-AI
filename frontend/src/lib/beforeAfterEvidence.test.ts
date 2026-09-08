import { describe, expect, it } from "vitest";
import { shouldShowBeforeAfterEvidence } from "@/lib/regionPreview";
import type { AnalysisResult, EvidenceRegion } from "@/types/domain";

const REGION: EvidenceRegion = {
  id: "ev-1",
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
  confidence: 0.7,
  metrics: [],
  source: "test",
  metadata: {},
};

const BI_TEMPORAL: AnalysisResult = {
  status: "completed",
  session_id: "sess-1",
  answer: "Detected change",
  confidence: 0.7,
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

describe("beforeAfterEvidence visibility", () => {
  it("shows for bi-temporal results with a selected region", () => {
    expect(shouldShowBeforeAfterEvidence(BI_TEMPORAL, REGION)).toBe(true);
  });

  it("hides for catalog-only results", () => {
    const catalogResult: AnalysisResult = {
      ...BI_TEMPORAL,
      bi_temporal_change: null,
    };
    expect(shouldShowBeforeAfterEvidence(catalogResult, REGION)).toBe(false);
  });

  it("hides when no region is selected", () => {
    expect(shouldShowBeforeAfterEvidence(BI_TEMPORAL, null)).toBe(false);
  });
});
