import type {
  AnalysisResult,
  ApiResponse,
  ImageryRequest,
  ImageryResult,
  ImageModality,
  QueryRequest,
  SubmitQueryData,
  TraceStep,
  UploadImageResponse,
} from "@/types/domain";
import { parseHttpErrorBody, API_ERROR_MESSAGES } from "@/lib/errors";
import { ApiError } from "@/types/domain";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function readJsonBody(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    if (res.ok) {
      throw new ApiError(
        "invalid_response",
        "Invalid JSON",
        API_ERROR_MESSAGES.invalid_response,
      );
    }
    throw parseHttpErrorBody(res.status, null);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch (err) {
    throw err;
  }

  const body = await readJsonBody(res);
  if (!res.ok) {
    throw parseHttpErrorBody(res.status, body);
  }
  return (body as ApiResponse<T>).data;
}

export const api = {
  health: () => request<{ status: string; imagery_provider: string; mode: string }>("/health"),

  fetchImagery: (payload: ImageryRequest) =>
    request<ImageryResult>("/api/v1/imagery/fetch", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  submitQuery: (payload: QueryRequest) =>
    request<SubmitQueryData>("/api/v1/query/submit", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  uploadImagery: async (
    file: File,
    options?: {
      modality?: ImageModality;
      benchmarkDataset?: boolean;
      acquisitionDatetime?: string;
      coRegisteredBenchmarkPair?: boolean;
      benchmarkPairId?: string;
    },
  ): Promise<UploadImageResponse> => {
    const form = new FormData();
    form.append("file", file);
    if (options?.modality) form.append("modality", options.modality);
    form.append("benchmark_dataset", String(options?.benchmarkDataset ?? false));
    if (options?.acquisitionDatetime) {
      form.append("acquisition_datetime", options.acquisitionDatetime);
    }
    if (options?.coRegisteredBenchmarkPair) {
      form.append("co_registered_benchmark_pair", "true");
    }
    if (options?.benchmarkPairId) {
      form.append("benchmark_pair_id", options.benchmarkPairId);
    }

    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/v1/imagery/upload`, {
        method: "POST",
        body: form,
      });
    } catch (err) {
      throw err;
    }

    const body = await readJsonBody(res);
    if (!res.ok) {
      throw parseHttpErrorBody(res.status, body);
    }
    return (body as ApiResponse<UploadImageResponse>).data;
  },

  getTrace: (sessionId: string) =>
    request<TraceStep[]>(`/api/v1/query/${sessionId}/trace`),

  getResult: (sessionId: string) =>
    request<AnalysisResult>(`/api/v1/query/${sessionId}/result`),
};
