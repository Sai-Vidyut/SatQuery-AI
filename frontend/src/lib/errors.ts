import { ApiError } from "@/types/domain";
import type { ErrorResponse } from "@/types/domain";

/** Mirrors backend app/core/user_errors.py — authoritative operator messages. */
export const API_ERROR_MESSAGES: Record<string, string> = {
  no_imagery_found:
    "No usable satellite imagery was found for the requested dates and AOI. Try different dates, widen the range, or adjust cloud-cover preferences.",
  no_imagery_after_cloud_filter:
    "All candidate scenes were rejected by cloud filtering. Increase cloud_cover_max or choose different dates.",
  invalid_date_range:
    "The earlier and later dates are not valid for this analysis. Ensure the earlier date is before the later date and both are after Sentinel-2 launch (2015-06-23).",
  unsupported_date:
    "One or both dates are outside the supported Sentinel-2 catalog range.",
  insufficient_valid_observations:
    "Not enough valid observations were available to run change detection.",
  imagery_policy_unsupported:
    "Imagery policy does not support this analysis mode for the selected dates.",
  policy_rejection: "The request was rejected by imagery or analysis policy.",
  analysis_failed:
    "Processing failed before a result could be produced. Check the execution trace for details.",
  input_validation_failed:
    "Uploaded imagery did not pass validation. Review file format, overlap, and acquisition dates.",
  image_not_found:
    "The referenced uploaded image was not found. Re-upload or check the image id.",
  change_detector_misconfigured:
    "Change detector configuration is inconsistent with the imagery provider.",
  session_not_found: "Analysis session not found. Submit a new query.",
  invalid_request:
    "The request is missing required fields or uses an unsupported combination of inputs.",
  catalog_sar_unsupported:
    "Catalog AOI optical+SAR fusion requires Earth Engine imagery. In development mode, use the Cross-modal upload workflow with separate optical and SAR images.",
  unsupported_format:
    "Unsupported file type. Allowed uploads: GeoTIFF, TIFF, PNG, or JPEG (PNG/JPEG require benchmark mode).",
  invalid_raster: "The uploaded file is not a readable raster image.",
  file_too_large: "The uploaded file exceeds the maximum allowed size.",
  empty_file: "The uploaded file is empty.",
  benchmark_required: "PNG/JPEG uploads require benchmark dataset mode.",
  missing_georeferencing: "GeoTIFF/TIFF must include georeferencing tags.",
  upload_failed: "Image upload failed. Try again with a valid GeoTIFF/TIFF.",
  missing_filename: "Upload filename is required.",
  invalid_acquisition_datetime: "Acquisition date must be in ISO-8601 format.",
  preview_bbox_no_intersection: "The preview area does not overlap this image.",
  invalid_preview_bbox: "Preview bbox must be minx,miny,maxx,maxy in WGS84 degrees.",
  preview_render_failed: "Could not render an image preview for this crop.",
  region_not_found: "The selected change region was not found in this analysis session.",
  not_bi_temporal_session: "Region interpretation is only available for bi-temporal upload analyses.",
  path_traversal: "Invalid upload path.",
  planner_routing_error:
    "Analysis routing failed. Try a simpler query or check your inputs.",
  geochat_service_error: "GeoChat VQA service returned an error. Check service configuration.",
  geochat_service_misconfigured: "GeoChat VQA service is not configured for this environment.",
  geochat_service_timeout: "GeoChat VQA service timed out. Try again later.",
  geochat_vqa_misconfigured: "GeoChat VQA is not configured for this environment.",
  earth_engine_auth_failed: "Earth Engine authentication failed.",
  earth_engine_unavailable: "Earth Engine is unavailable.",
  earth_engine_request_failed: "Earth Engine request failed.",
  change_detection_failed: "Change detection failed for the uploaded image pair.",
  coregistration_failed: "Image co-registration failed for the uploaded pair.",
  index_unavailable: "The selected change index is unavailable for this image pair.",
  invalid_aoi: "The area of interest is invalid.",
  invalid_imagery_metadata: "Imagery metadata is invalid.",
  insufficient_imagery: "Insufficient imagery available for this analysis.",
  spatial_overlap: "Uploaded images do not overlap sufficiently.",
  temporal_order: "Earlier and later images are not in valid temporal order.",
  unsupported_sensor: "Unsupported sensor type for this analysis.",
  semantic_analyzer_misconfigured: "Semantic analyzer configuration is inconsistent.",
  polygonization_failed: "Failed to generate change regions from detection results.",
  validation_error: "The request failed validation. Check required fields and input formats.",
  invalid_response: "The server returned an unexpected response. Try again.",
  server_error:
    "The SatQuery backend encountered an unexpected error. Try again or check server logs.",
  network_error:
    "Could not reach the SatQuery backend. Check that the API server is running and reachable.",
  timeout_error: "The request timed out. Try again or simplify the analysis.",
};

const GENERIC_FALLBACK = "Analysis failed.";

const INTERNAL_MESSAGE_PATTERN =
  /traceback|exception:|error at|\.py:|keyerror|valueerror|typeerror|satqueryerror/i;

function looksLikeInternalMessage(message: string | null | undefined): boolean {
  if (!message) return true;
  return INTERNAL_MESSAGE_PATTERN.test(message);
}

export function formatValidationDetail(detail: unknown): string {
  if (!Array.isArray(detail)) {
    return API_ERROR_MESSAGES.validation_error;
  }
  const parts = detail
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null;
      const loc = Array.isArray((entry as { loc?: unknown }).loc)
        ? (entry as { loc: unknown[] }).loc.filter((part) => part !== "body").join(".")
        : "";
      const msg =
        typeof (entry as { msg?: unknown }).msg === "string"
          ? (entry as { msg: string }).msg
          : "Invalid value";
      return loc ? `${loc}: ${msg}` : msg;
    })
    .filter(Boolean);
  if (parts.length === 0) {
    return API_ERROR_MESSAGES.validation_error;
  }
  return `${API_ERROR_MESSAGES.validation_error} (${parts.join("; ")})`;
}

export function messageForApiErrorCode(
  code: string,
  userMessage?: string | null,
  technicalMessage?: string | null,
): string {
  const mapped = API_ERROR_MESSAGES[code];
  if (mapped) return mapped;
  if (userMessage && !looksLikeInternalMessage(userMessage) && userMessage !== GENERIC_FALLBACK) {
    return userMessage;
  }
  if (
    technicalMessage &&
    !looksLikeInternalMessage(technicalMessage) &&
    technicalMessage !== GENERIC_FALLBACK
  ) {
    return technicalMessage;
  }
  return GENERIC_FALLBACK;
}

export function isNetworkError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  return (
    err.name === "TypeError" &&
    /fetch|network|load failed|failed to fetch|networkerror/i.test(err.message)
  );
}

export function isTimeoutError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  return err.name === "AbortError" || /timeout/i.test(err.message);
}

export function parseHttpErrorBody(status: number, body: unknown): ApiError {
  if (body && typeof body === "object" && "error" in body) {
    const payload = body as ErrorResponse;
    const code = payload.error?.code ?? "analysis_failed";
    const message = payload.error?.message ?? "Request failed";
    const userMessage = payload.error?.user_message ?? null;
    const normalized = messageForApiErrorCode(code, userMessage, message);
    return new ApiError(code, message, normalized);
  }

  if (status === 422 && body && typeof body === "object" && "detail" in body) {
    const formatted = formatValidationDetail((body as { detail?: unknown }).detail);
    return new ApiError("validation_error", "Validation failed", formatted);
  }

  if (status >= 500) {
    return new ApiError(
      "server_error",
      "Server error",
      API_ERROR_MESSAGES.server_error,
    );
  }

  return new ApiError(
    "analysis_failed",
    "Request failed",
    API_ERROR_MESSAGES.analysis_failed,
  );
}

/** Map backend / browser errors to operator-facing analysis messages. */
export function normalizeAnalysisError(err: unknown): string {
  if (isTimeoutError(err)) {
    return API_ERROR_MESSAGES.timeout_error;
  }

  if (isNetworkError(err)) {
    return API_ERROR_MESSAGES.network_error;
  }

  if (err instanceof ApiError) {
    return messageForApiErrorCode(err.code, err.userMessage, err.message);
  }

  if (err && typeof err === "object" && "code" in err && "userMessage" in err) {
    const apiErr = err as { code?: string; userMessage?: string; message?: string };
    return messageForApiErrorCode(
      apiErr.code ?? "analysis_failed",
      apiErr.userMessage,
      apiErr.message,
    );
  }

  const raw = err instanceof Error ? err.message : String(err);
  if (looksLikeInternalMessage(raw)) {
    return GENERIC_FALLBACK;
  }
  if (raw.trim()) {
    return raw;
  }

  return GENERIC_FALLBACK;
}
