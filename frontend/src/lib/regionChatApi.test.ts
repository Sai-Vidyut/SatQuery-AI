import { describe, expect, it, vi, afterEach } from "vitest";
import { api } from "@/lib/api";

describe("api.chatChangeRegion", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts session_id, region_id, and message to the chat endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          chat: {
            task: "bi_temporal_region_chat",
            answer: "Mock chat answer",
            session_id: "sess-1",
            region_id: "change-region-01",
            conversation_id: "conv-1",
            turn_id: "turn-1",
            turn_index: 0,
            message: "Why do you think this is vegetation loss?",
            detector: "uploaded_bi_temporal",
            region_confidence: 0.47,
            model_name: "development-mock-geochat",
            model_version: "0.0.0-dev",
            provider: "development",
            provenance: "mock",
            confidence_available: false,
            preview_bbox_wgs84: "1,2,3,4",
            evidence_inputs: "before_after_composite_crop",
            scope_limited: false,
            conversation: {
              conversation_id: "conv-1",
              session_id: "sess-1",
              region_id: "change-region-01",
              turns: [
                {
                  turn_id: "turn-1",
                  turn_index: 0,
                  user_message: "Why do you think this is vegetation loss?",
                  assistant_answer: "Mock chat answer",
                  created_at: "2026-09-08T09:00:00Z",
                },
              ],
            },
          },
          trace_step: {
            id: "step-1",
            tool_name: "geochat_region_chat",
            status: "completed",
          },
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.chatChangeRegion(
      "sess-1",
      "change-region-01",
      "Why do you think this is vegetation loss?",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/query/sess-1/regions/change-region-01/chat",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "Why do you think this is vegetation loss?" }),
      }),
    );
    expect(result.chat.answer).toBe("Mock chat answer");
    expect(result.chat.conversation.turns).toHaveLength(1);
  });
});
