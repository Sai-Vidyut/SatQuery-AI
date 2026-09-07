import type { AnalysisResult } from "@/types/domain";

export type DataSourceBannerKind = "demo_mode" | "mock_providers";

export function getDataSourceBanner(result: AnalysisResult): DataSourceBannerKind | null {
  if (result.demonstration_data) {
    return "demo_mode";
  }
  if (result.mode === "development") {
    return "mock_providers";
  }
  return null;
}

export const DATA_SOURCE_BANNER_TEXT: Record<DataSourceBannerKind, string> = {
  demo_mode: "DEMONSTRATION DATA — user-selected demo mode; deterministic fixtures, not real Earth observation.",
  mock_providers:
    "MOCK PROVIDERS — development environment configuration; not live production satellite analysis.",
};
