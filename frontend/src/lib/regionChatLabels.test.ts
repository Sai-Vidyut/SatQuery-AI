import { describe, expect, it } from "vitest";
import type { BiTemporalRegionChatResult } from "@/types/domain";
import { regionChatProviderBadge, regionChatTurnRole } from "@/lib/regionChatLabels";

function chat(overrides: Partial<BiTemporalRegionChatResult>): BiTemporalRegionChatResult {
  return {
    task: "bi_temporal_region_chat",
    answer: "Answer",
    session_id: "sess",
    region_id: "change-region-01",
    conversation_id: "conv",
    turn_id: "turn",
    turn_index: 0,
    message: "Question",
    detector: "uploaded_bi_temporal",
    region_confidence: 0.5,
    model_name: "model",
    model_version: "1",
    provider: "development",
    provenance: "test",
    confidence_available: false,
    route: "geo",
    classification: "geo",
    scope: "selected_region",
    preview_bbox_wgs84: "1,2,3,4",
    evidence_inputs: "before_after_composite_crop",
    scope_limited: false,
    conversation: {
      conversation_id: "conv",
      session_id: "sess",
      region_id: "change-region-01",
      turns: [],
    },
    ...overrides,
  };
}

describe("regionChatProviderBadge", () => {
  it("shows GeoChat region evidence for geo routes", () => {
    expect(regionChatProviderBadge(chat({ route: "geo", provider: "development" }))).toBe(
      "GeoChat · Region evidence",
    );
  });

  it("shows Groq badge for general routes", () => {
    expect(
      regionChatProviderBadge(
        chat({
          route: "general",
          provider: "groq",
          scope: "general_assistant",
          evidence_inputs: "general_assistant_no_imagery",
        }),
      ),
    ).toBe("General AI · Groq");
  });

  it("shows scope limited before provider badge", () => {
    expect(regionChatProviderBadge(chat({ scope_limited: true }))).toBe("SCOPE LIMITED");
  });
});

describe("regionChatTurnRole", () => {
  it("labels Groq turns separately from GeoChat", () => {
    expect(
      regionChatTurnRole({
        turn_id: "t1",
        turn_index: 0,
        user_message: "Hi",
        assistant_answer: "Hello",
        created_at: "2026-01-01T00:00:00Z",
        route: "general",
        provider: "groq",
        scope: "general_assistant",
      }),
    ).toBe("General AI");
    expect(
      regionChatTurnRole({
        turn_id: "t2",
        turn_index: 1,
        user_message: "Change?",
        assistant_answer: "Loss",
        created_at: "2026-01-01T00:00:01Z",
        route: "geo",
        provider: "development",
        scope: "selected_region",
      }),
    ).toBe("GeoChat");
  });
});
