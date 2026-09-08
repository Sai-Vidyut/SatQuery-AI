import type { AnalysisResult, EvidenceRegion } from "@/types/domain";
import { shouldShowBeforeAfterEvidence } from "@/lib/regionPreview";

export function shouldShowRegionInterpretation(
  result: AnalysisResult | null,
  selectedRegion: EvidenceRegion | null,
): boolean {
  return shouldShowBeforeAfterEvidence(result, selectedRegion);
}

export const REGION_INTERPRETATION_PRESETS = [
  "What visible change occurred in this detected region between the two dates?",
  "Describe the land-cover transition visible between before and after.",
  "Does the visible change appear consistent with vegetation loss, flooding, construction, or another transition?",
] as const;

export function regionInterpretationProviderLabel(
  provider: "development" | "geochat_service",
): string {
  return provider === "geochat_service" ? "REAL GeoChat-7B" : "DEVELOPMENT MOCK";
}
