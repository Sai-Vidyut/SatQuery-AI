import { describe, expect, it } from "vitest";
import type { AnalysisResult, EvidenceRegion } from "@/types/domain";
import {
  buildCatalogFollowUpQuery,
  extractGeoChatReply,
  geoChatCollapseKey,
  geoChatDrawerTitle,
  resolveGeoChatDrawerMode,
  shouldUseRegionGeoChatApi,
} from "@/lib/geoChatDrawer";

const REGION: EvidenceRegion = {
  id: "change-region-01",
  geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] },
  type: "spectral_change",
  confidence: 0.9,
  metrics: [],
  source: "test",
  metadata: {},
};

describe("resolveGeoChatDrawerMode", () => {
  it("maps result shapes to drawer modes", () => {
    expect(
      resolveGeoChatDrawerMode({
        bi_temporal_change: { task: "bi_temporal_change_vqa" },
      } as AnalysisResult),
    ).toBe("bi_temporal_region");
    expect(
      resolveGeoChatDrawerMode({ vqa: { task: "single_image_vqa" } } as AnalysisResult),
    ).toBe("upload_vqa");
    expect(
      resolveGeoChatDrawerMode({ caption: { task: "single_image_caption" } } as AnalysisResult),
    ).toBe("upload_caption");
    expect(
      resolveGeoChatDrawerMode({
        cross_modal: { task: "cross_modal_optical_sar" },
      } as AnalysisResult),
    ).toBe("cross_modal");
    expect(resolveGeoChatDrawerMode({ answer: "catalog" } as AnalysisResult)).toBe("catalog");
  });
});

describe("shouldUseRegionGeoChatApi", () => {
  it("uses region chat only for bi-temporal sessions with a selected region", () => {
    expect(
      shouldUseRegionGeoChatApi(
        { bi_temporal_change: { task: "bi_temporal_change_vqa" } } as AnalysisResult,
        REGION,
      ),
    ).toBe(true);
    expect(
      shouldUseRegionGeoChatApi({ answer: "catalog", evidence: [REGION] } as AnalysisResult, REGION),
    ).toBe(false);
  });
});

describe("extractGeoChatReply", () => {
  it("returns the most specific answer field available", () => {
    expect(extractGeoChatReply({ vqa: { answer: "VQA" } } as AnalysisResult)).toBe("VQA");
    expect(extractGeoChatReply({ caption: { description: "Caption" } } as AnalysisResult)).toBe(
      "Caption",
    );
    expect(extractGeoChatReply({ cross_modal: { answer: "Joint" } } as AnalysisResult)).toBe("Joint");
    expect(extractGeoChatReply({ answer: "Fallback" } as AnalysisResult)).toBe("Fallback");
  });
});

describe("geoChatDrawerTitle", () => {
  it("uses mode-specific titles", () => {
    expect(geoChatDrawerTitle("catalog")).toContain("analysis");
    expect(geoChatDrawerTitle("upload_vqa")).toContain("image");
  });
});

describe("buildCatalogFollowUpQuery", () => {
  it("prefixes region context when a region is selected", () => {
    expect(buildCatalogFollowUpQuery("Why construction?", "region-01")).toContain("region-01");
    expect(buildCatalogFollowUpQuery("Why construction?", null)).toBe("Why construction?");
  });
});

describe("geoChatCollapseKey", () => {
  it("changes when analysis or region changes", () => {
    const base = geoChatCollapseKey(1, "change-region-01");
    expect(base).toBe("1:change-region-01");
    expect(geoChatCollapseKey(2, "change-region-01")).not.toBe(base);
    expect(geoChatCollapseKey(1, "change-region-02")).not.toBe(base);
    expect(geoChatCollapseKey(1, null)).not.toBe(base);
  });
});

describe("geoChat drawer height helpers", () => {
  it("clamps drawer height between min and max", async () => {
    const { clampGeoChatDrawerHeight, GEOCHAT_DRAWER_MIN_HEIGHT } = await import("@/lib/geoChatDrawer");
    expect(clampGeoChatDrawerHeight(100, 500)).toBe(GEOCHAT_DRAWER_MIN_HEIGHT);
    expect(clampGeoChatDrawerHeight(900, 500)).toBe(500);
    expect(clampGeoChatDrawerHeight(320, 500)).toBe(320);
  });
});
