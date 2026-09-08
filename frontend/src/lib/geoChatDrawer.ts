import type { AnalysisResult, EvidenceRegion } from "@/types/domain";

export type GeoChatDrawerMode =
  | "bi_temporal_region"
  | "upload_vqa"
  | "upload_caption"
  | "cross_modal"
  | "catalog";

export type GeoChatTurn = {
  id: string;
  userMessage: string;
  assistantAnswer: string;
};

export function resolveGeoChatDrawerMode(result: AnalysisResult): GeoChatDrawerMode {
  if (result.bi_temporal_change) return "bi_temporal_region";
  if (result.vqa) return "upload_vqa";
  if (result.caption) return "upload_caption";
  if (result.cross_modal) return "cross_modal";
  return "catalog";
}

export function shouldUseRegionGeoChatApi(
  result: AnalysisResult,
  selectedRegion: EvidenceRegion | null,
): boolean {
  return Boolean(result.bi_temporal_change && selectedRegion);
}

export function geoChatDrawerTitle(mode: GeoChatDrawerMode): string {
  switch (mode) {
    case "bi_temporal_region":
      return "Ask GeoChat about this region";
    case "upload_vqa":
      return "Ask GeoChat about this image";
    case "upload_caption":
      return "Ask GeoChat about this scene";
    case "cross_modal":
      return "Ask GeoChat about this optical + SAR pair";
    default:
      return "Ask GeoChat about this analysis";
  }
}

export function geoChatDrawerHint(
  mode: GeoChatDrawerMode,
  selectedRegion: EvidenceRegion | null,
): string {
  if (mode === "bi_temporal_region") {
    return selectedRegion
      ? `Talk to GeoChat about ${selectedRegion.id}. Out-of-scope requests stay region-limited.`
      : "Select a detected region to start a GeoChat conversation.";
  }
  if (mode === "upload_vqa" || mode === "upload_caption") {
    return "Ask follow-up questions about the uploaded image.";
  }
  if (mode === "cross_modal") {
    return "Ask follow-up questions about the joint optical and SAR analysis.";
  }
  return selectedRegion
    ? `Ask follow-up questions about ${selectedRegion.id} or the overall analysis.`
    : "Ask follow-up questions about this analysis result.";
}

export function extractGeoChatReply(result: AnalysisResult): string {
  if (result.vqa?.answer) return result.vqa.answer;
  if (result.caption?.description) return result.caption.description;
  if (result.cross_modal?.answer) return result.cross_modal.answer;
  if (result.bi_temporal_change?.change_summary) return result.bi_temporal_change.change_summary;
  return result.answer;
}

export function buildCatalogFollowUpQuery(message: string, regionId: string | null): string {
  if (!regionId) return message;
  return `Regarding detected region ${regionId}: ${message}`;
}

export function geoChatCollapseKey(chatResetKey: number, regionId: string | null): string {
  return `${chatResetKey}:${regionId ?? "none"}`;
}

export const GEOCHAT_DRAWER_MIN_HEIGHT = 240;
export const GEOCHAT_DRAWER_DEFAULT_HEIGHT = 300;
export const GEOCHAT_DRAWER_MAX_HEIGHT_RATIO = 0.72;

export function resolveGeoChatDrawerMaxHeight(container: HTMLElement | null): number {
  const inspector =
    container?.closest('[data-testid="inspector"]') ??
    (typeof document !== "undefined"
      ? document.querySelector('[data-testid="inspector"]')
      : null);
  if (inspector instanceof HTMLElement && inspector.clientHeight > 0) {
    return Math.max(
      GEOCHAT_DRAWER_MIN_HEIGHT,
      Math.floor(inspector.clientHeight * GEOCHAT_DRAWER_MAX_HEIGHT_RATIO),
    );
  }
  return 480;
}

export function clampGeoChatDrawerHeight(height: number, maxHeight: number): number {
  return Math.min(Math.max(height, GEOCHAT_DRAWER_MIN_HEIGHT), maxHeight);
}
