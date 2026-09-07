import { describe, expect, it } from "vitest";
import {
  inspectorShouldShow,
  resetAnalysisDisplayStateForModeChange,
  type AnalysisDisplayState,
} from "./analysisModeState";
import type { AnalysisResult } from "@/types/domain";

const catalogResult: AnalysisResult = {
  status: "completed",
  session_id: "mode-a-session",
  answer: "Catalog mode answer with construction regions.",
  confidence: 0.72,
  metrics: [],
  evidence: [
    {
      id: "ev-1",
      type: "change",
      geometry: { type: "Polygon", coordinates: [] },
      confidence: 0.7,
      metrics: [],
      source: "deterministic_change",
      metadata: {},
    },
  ],
  trace: [],
  mode: "development",
};

const modeAResultState = (): AnalysisDisplayState => ({
  result: catalogResult,
  selectedRegionId: "ev-1",
  analysisError: null,
  statusLine: "2 regions · 1.1s · 2024-12-01 → 2025-03-01",
});

describe("resetAnalysisDisplayStateForModeChange", () => {
  it("clears mode A result when switching to mode B so inspector stays hidden", () => {
    const before = modeAResultState();
    expect(inspectorShouldShow(before)).toBe(true);

    const after = resetAnalysisDisplayStateForModeChange(before, "catalog", "upload");

    expect(after.result).toBeNull();
    expect(after.selectedRegionId).toBeNull();
    expect(after.analysisError).toBeNull();
    expect(after.statusLine).toBeNull();
    expect(inspectorShouldShow(after)).toBe(false);
  });

  it("clears stale analysis error when switching modes", () => {
    const before: AnalysisDisplayState = {
      result: null,
      selectedRegionId: null,
      analysisError: "Catalog analysis failed.",
      statusLine: null,
    };
    expect(inspectorShouldShow(before)).toBe(true);

    const after = resetAnalysisDisplayStateForModeChange(before, "catalog", "temporal_pair");

    expect(after.analysisError).toBeNull();
    expect(inspectorShouldShow(after)).toBe(false);
  });

  it("preserves display state when mode is unchanged", () => {
    const before = modeAResultState();
    const after = resetAnalysisDisplayStateForModeChange(before, "catalog", "catalog");
    expect(after).toEqual(before);
  });
});
