import { describe, expect, it } from "vitest";
import { confidenceBand, detectionFillOpacity } from "@/lib/geo";

describe("geo helpers", () => {
  it("maps confidence to band labels", () => {
    expect(confidenceBand(0.8)).toBe("High");
    expect(confidenceBand(0.5)).toBe("Medium");
    expect(confidenceBand(0.2)).toBe("Low");
  });

  it("computes detection fill opacity", () => {
    expect(detectionFillOpacity(0.5)).toBeCloseTo(0.24);
  });
});
