/**
 * Integration test: requires backend at SATQUERY_API_URL (default http://127.0.0.1:8001).
 * Run: SATQUERY_API_URL=http://127.0.0.1:8001 npm test -- src/lib/api.integration.test.ts
 */
import { describe, expect, it } from "vitest";

const API = process.env.SATQUERY_API_URL ?? "http://127.0.0.1:8001";

const sampleQuery = {
  query: "Show me significant new construction.",
  aoi: {
    geometry: {
      type: "Polygon" as const,
      coordinates: [
        [
          [77.59, 12.97],
          [77.61, 12.97],
          [77.61, 12.99],
          [77.59, 12.99],
          [77.59, 12.97],
        ],
      ],
    },
  },
  earlier_date: "2024-01-12",
  later_date: "2025-03-03",
};

describe("API integration", () => {
  it("health and query submit return evidence from backend", async () => {
    let health: Response;
    try {
      health = await fetch(`${API}/health`);
    } catch {
      console.warn("Backend not running; skip integration test");
      return;
    }
    expect(health.ok).toBe(true);

    const res = await fetch(`${API}/api/v1/query/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sampleQuery),
    });
    expect(res.ok).toBe(true);
    const body = await res.json();
    expect(body.data.result.evidence.length).toBeGreaterThanOrEqual(1);
    expect(body.data.result.mode).toBe("development");
  });
});
