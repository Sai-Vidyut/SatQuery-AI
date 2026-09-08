import { describe, expect, it, vi, afterEach } from "vitest";
import { api } from "@/lib/api";

describe("api.interpretChangeRegion", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts session_id, region_id, and question to the interpret endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          interpretation: {
            task: "bi_temporal_region_interpretation",
            answer: "Mock answer",
            region_id: "change-region-01",
            session_id: "sess-1",
            question: "What changed here?",
            detector: "uploaded_bi_temporal",
            region_confidence: 0.47,
            model_name: "development-mock-geochat",
            model_version: "0.0.0-dev",
            provider: "development",
            provenance: "mock",
            confidence_available: false,
            earlier_image_id: "a".repeat(32),
            later_image_id: "b".repeat(32),
            preview_bbox_wgs84: "1,2,3,4",
            evidence_inputs: "before_after_composite_crop",
          },
          trace_step: {
            id: "step-1",
            tool_name: "geochat_region_interpretation",
            status: "completed",
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.interpretChangeRegion(
      "sess-1",
      "change-region-01",
      "What changed here?",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/query/sess-1/regions/change-region-01/interpret",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ question: "What changed here?" }),
      }),
    );
    expect(result.interpretation.answer).toBe("Mock answer");
  });
});
