import type { BiTemporalRegionChatResult } from "@/types/domain";

export function regionChatProviderBadge(chat: BiTemporalRegionChatResult): string {
  if (chat.scope_limited) {
    return "SCOPE LIMITED";
  }
  if (chat.route === "general" || chat.provider === "groq") {
    return "General AI · Groq";
  }
  if (chat.provider === "geochat_service") {
    return "GeoChat · Region evidence";
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
