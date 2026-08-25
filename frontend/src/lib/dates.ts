const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Parse and validate YYYY-MM-DD (calendar-correct). Returns null if invalid. */
export function parseIsoDate(value: string | null | undefined): string | null {
  if (!value || !ISO_DATE_RE.test(value)) return null;
  const [year, month, day] = value.split("-").map((part) => Number.parseInt(part, 10));
  const probe = new Date(Date.UTC(year, month - 1, day));
  if (
    probe.getUTCFullYear() !== year ||
    probe.getUTCMonth() !== month - 1 ||
    probe.getUTCDate() !== day
  ) {
    return null;
  }
  return value;
}

export function validateDateRange(earlier: string, later: string): string | null {
  if (!parseIsoDate(earlier)) {
    return "Earlier date must use YYYY-MM-DD format.";
  }
  if (!parseIsoDate(later)) {
    return "Later date must use YYYY-MM-DD format.";
  }
  if (later <= earlier) {
    return "Invalid date range. Later date must be after earlier date.";
  }
  return null;
}
