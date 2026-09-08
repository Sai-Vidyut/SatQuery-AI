import type { BiTemporalRegionChatResult } from "@/types/domain";

function isDemoGeneral(chat: BiTemporalRegionChatResult): boolean {
  if (chat.route !== "general" && chat.provider !== "groq") return false;
  const meta = chat.inference_metadata;
  return Boolean(meta?.development_mock || meta?.groq_fallback);
}

export function regionChatProviderBadge(chat: BiTemporalRegionChatResult): string {
  if (chat.scope_limited) {
    return "SCOPE LIMITED";
  }
  if (chat.route === "general" || chat.provider === "groq") {
    return isDemoGeneral(chat) ? "General AI · DEMO" : "General AI · Groq";
  }
  if (chat.provider === "development") {
    return "GeoChat · DEVELOPMENT MOCK";
  }
  if (chat.provider === "geochat_service") {
    return "GeoChat · REAL GeoChat-7B";
  }
  return "GeoChat · Region evidence";
}

export function regionChatTurnRole(
  turn: BiTemporalRegionChatResult["conversation"]["turns"][number],
): string {
  if (turn.route === "general" || turn.provider === "groq") {
    return "General AI";
  }
  return "GeoChat";
}
