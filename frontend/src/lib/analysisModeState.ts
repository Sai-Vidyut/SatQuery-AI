import type { AnalysisResult } from "@/types/domain";

export type ComposerInputMode = "catalog" | "upload" | "temporal_pair" | "cross_modal";

export type AnalysisDisplayState = {
  result: AnalysisResult | null;
  selectedRegionId: string | null;
  analysisError: string | null;
  statusLine: string | null;
};

export function shouldResetAnalysisOnModeChange(
  previousMode: ComposerInputMode,
  nextMode: ComposerInputMode,
): boolean {
  return previousMode !== nextMode;
}

export function resetAnalysisDisplayStateForModeChange(
  state: AnalysisDisplayState,
  previousMode: ComposerInputMode,
  nextMode: ComposerInputMode,
): AnalysisDisplayState {
  if (!shouldResetAnalysisOnModeChange(previousMode, nextMode)) {
    return state;
  }
  return {
    result: null,
    selectedRegionId: null,
    analysisError: null,
    statusLine: null,
  };
}

/** Mirrors EvidenceInspector visibility guard in Workspace. */
export function inspectorShouldShow(
  state: AnalysisDisplayState,
  running = false,
): boolean {
  return running || state.result != null || state.analysisError != null;
}
