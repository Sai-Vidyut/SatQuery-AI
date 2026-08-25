import { describe, expect, it } from "vitest";
import { parseIsoDate, validateDateRange } from "@/lib/dates";

describe("parseIsoDate", () => {
  it("accepts valid ISO dates", () => {
    expect(parseIsoDate("2024-12-01")).toBe("2024-12-01");
    expect(parseIsoDate("2025-03-01")).toBe("2025-03-01");
  });

  it("rejects locale-style and invalid dates", () => {
    expect(parseIsoDate("01/12/2024")).toBeNull();
    expect(parseIsoDate("2024-13-01")).toBeNull();
    expect(parseIsoDate("2024-02-30")).toBeNull();
    expect(parseIsoDate("")).toBeNull();
  });
});

describe("validateDateRange", () => {
  it("accepts valid ordered ranges", () => {
    expect(validateDateRange("2024-12-01", "2025-03-01")).toBeNull();
  });

  it("rejects invalid or reversed ranges", () => {
    expect(validateDateRange("01/12/2024", "2025-03-01")).not.toBeNull();
    expect(validateDateRange("2025-03-01", "2024-12-01")).not.toBeNull();
  });
});
