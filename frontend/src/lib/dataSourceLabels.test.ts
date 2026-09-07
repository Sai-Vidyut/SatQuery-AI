import { describe, expect, it } from "vitest";
import { DATA_SOURCE_BANNER_TEXT, getDataSourceBanner } from "./dataSourceLabels";
import type { AnalysisResult } from "@/types/domain";

function minimalResult(overrides: Partial<AnalysisResult>): AnalysisResult {
  return {
    status: "completed",
    session_id: "sess-1",
    answer: "Answer text.",
    confidence: 0.5,
    metrics: [],
    evidence: [],
    trace: [],
    mode: "development",
    ...overrides,
  };
}

describe("getDataSourceBanner", () => {
  it("shows demo banner when user explicitly requested demo mode", () => {
    const banner = getDataSourceBanner(
      minimalResult({ demonstration_data: true, mode: "development" }),
    );
    expect(banner).toBe("demo_mode");
    expect(DATA_SOURCE_BANNER_TEXT[banner!]).toContain("user-selected demo mode");
  });

  it("shows mock-provider banner when development provider is used without demo mode", () => {
    const banner = getDataSourceBanner(
      minimalResult({ demonstration_data: false, mode: "development" }),
    );
    expect(banner).toBe("mock_providers");
    expect(DATA_SOURCE_BANNER_TEXT[banner!]).toContain("development environment");
  });

  it("shows no banner for production earth engine results", () => {
    const banner = getDataSourceBanner(
      minimalResult({ demonstration_data: false, mode: "earth_engine" }),
    );
    expect(banner).toBeNull();
  });
});
