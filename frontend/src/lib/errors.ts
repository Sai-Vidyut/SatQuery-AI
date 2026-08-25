/** Map backend / browser errors to operator-facing analysis messages. */
export function normalizeAnalysisError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err);

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
