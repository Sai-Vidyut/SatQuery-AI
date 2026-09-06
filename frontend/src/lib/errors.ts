/** Map backend / browser errors to operator-facing analysis messages. */
export function normalizeAnalysisError(err: unknown): string {
  if (err && typeof err === "object" && "userMessage" in err) {
    const apiErr = err as { userMessage?: string; message?: string };
    if (apiErr.userMessage) return apiErr.userMessage;
  }

  const raw = err instanceof Error ? err.message : String(err);

  if (/no_imagery_found|no usable satellite imagery/i.test(raw)) {
    return "No usable satellite imagery was found for the requested dates and AOI.";
  }
  if (/no_imagery_after_cloud_filter|cloud filter/i.test(raw)) {
    return "All candidate scenes were rejected by cloud filtering.";
  }
  if (/invalid_date_range|unsupported_date/i.test(raw)) {
    return "Invalid or unsupported date range.";
  }
  if (/insufficient_valid_observations/i.test(raw)) {
    return "Not enough valid observations were available.";
  }
  if (/imagery_policy_unsupported|policy_rejection/i.test(raw)) {
    return "Imagery policy does not support this analysis.";
  }
  if (/expected pattern|invalid.*date|date/i.test(raw)) {
    return "Invalid date range.";
  }
  if (/earth.?engine|earthengine/i.test(raw)) {
    return "Earth Engine unavailable.";
  }
  if (/aoi|geometry|bbox|polygon/i.test(raw)) {
    return "AOI is invalid.";
  }
  if (/later.*earlier|date range/i.test(raw)) {
    return "Invalid date range.";
  }

  return "Analysis failed.";
}
