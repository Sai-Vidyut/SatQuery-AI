import { describe, expect, it } from "vitest";
import { ApiError } from "@/types/domain";
import {
  API_ERROR_MESSAGES,
  formatValidationDetail,
  messageForApiErrorCode,
  normalizeAnalysisError,
  parseHttpErrorBody,
} from "./errors";

describe("messageForApiErrorCode", () => {
  it("maps known backend user error codes to operator messages", () => {
    const message = messageForApiErrorCode("catalog_sar_unsupported");
    expect(message).toContain("Cross-modal upload");
    expect(message).not.toBe("Analysis failed.");
  });

  it("does not expose internal exception text for analysis_failed", () => {
    const message = messageForApiErrorCode(
      "analysis_failed",
      "Analysis failed.",
      "ValueError: secret internal pipeline detail",
    );
    expect(message).toBe(API_ERROR_MESSAGES.analysis_failed);
    expect(message).not.toContain("ValueError");
  });
});

describe("parseHttpErrorBody", () => {
  it("parses structured backend error responses", () => {
    const err = parseHttpErrorBody(422, {
      success: false,
      error: {
        code: "catalog_sar_unsupported",
        message: "Catalog AOI optical+SAR fusion requires Earth Engine imagery.",
        user_message:
          "Catalog AOI optical+SAR fusion requires Earth Engine imagery. In development mode, use the Cross-modal upload workflow with separate optical and SAR images.",
      },
    });
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("catalog_sar_unsupported");
    expect(err.userMessage).toContain("Cross-modal upload");
  });

  it("formats FastAPI validation errors", () => {
    const err = parseHttpErrorBody(422, {
      detail: [{ loc: ["body", "aoi"], msg: "Field required", type: "missing" }],
    });
    expect(err.code).toBe("validation_error");
    expect(err.userMessage).toContain("aoi");
    expect(err.userMessage).toContain("Field required");
  });

  it("returns safe message for unknown 5xx responses", () => {
    const err = parseHttpErrorBody(500, { message: "Traceback (most recent call last)" });
    expect(err.code).toBe("server_error");
    expect(err.userMessage).toBe(API_ERROR_MESSAGES.server_error);
    expect(err.userMessage).not.toContain("Traceback");
  });

  it("handles malformed error payloads safely", () => {
    const err = parseHttpErrorBody(502, null);
    expect(err.code).toBe("server_error");
    expect(err.userMessage).toBe(API_ERROR_MESSAGES.server_error);
  });
});

describe("normalizeAnalysisError", () => {
  it("uses mapped message for known ApiError codes", () => {
    const err = new ApiError(
      "catalog_sar_unsupported",
      "internal technical message",
      "Analysis failed.",
    );
    const message = normalizeAnalysisError(err);
    expect(message).toContain("Cross-modal upload");
    expect(message).not.toContain("internal technical");
  });

  it("maps upload validation codes from ApiError", () => {
    const err = new ApiError("unsupported_format", "Unsupported file extension.", "Analysis failed.");
    expect(normalizeAnalysisError(err)).toBe(API_ERROR_MESSAGES.unsupported_format);
  });

  it("maps network failures clearly", () => {
    const message = normalizeAnalysisError(new TypeError("Failed to fetch"));
    expect(message).toBe(API_ERROR_MESSAGES.network_error);
  });

  it("maps timeout failures clearly", () => {
    const abortErr = new DOMException("The operation was aborted.", "AbortError");
    expect(normalizeAnalysisError(abortErr)).toBe(API_ERROR_MESSAGES.timeout_error);
  });

  it("does not leak internal exception strings from generic errors", () => {
    const message = normalizeAnalysisError(
      new Error("ValueError: unexpected scene metadata in detector.py"),
    );
    expect(message).toBe("Analysis failed.");
    expect(message).not.toContain(".py");
  });
});

describe("formatValidationDetail", () => {
  it("preserves useful field information", () => {
    const message = formatValidationDetail([
      { loc: ["body", "start_date"], msg: "Field required" },
    ]);
    expect(message).toContain("start_date");
    expect(message).toContain("Field required");
  });
});
