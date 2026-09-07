/**
 * Monotonic guard for overlapping analysis submit requests.
 * Only the latest request id may commit result/error/loading state.
 */
export type AnalysisRequestSequence = {
  begin: () => number;
  isLatest: (requestId: number) => boolean;
};

export function createAnalysisRequestSequence(): AnalysisRequestSequence {
  let latestRequestId = 0;
  return {
    begin: () => ++latestRequestId,
    isLatest: (requestId: number) => requestId === latestRequestId,
  };
}

export type AnalysisRunCommitHandlers<T> = {
  onSuccess: (value: T) => void;
  onError: (message: string) => void;
  onComplete: () => void;
};

/**
 * Apply async analysis outcome only when requestId is still the latest run.
 */
export async function runGuardedAnalysisRequest<T>(
  sequence: AnalysisRequestSequence,
  requestId: number,
  task: () => Promise<T>,
  handlers: AnalysisRunCommitHandlers<T>,
): Promise<void> {
  try {
    const value = await task();
    if (!sequence.isLatest(requestId)) return;
    handlers.onSuccess(value);
  } catch (err) {
    if (!sequence.isLatest(requestId)) return;
    handlers.onError(err instanceof Error ? err.message : String(err));
  } finally {
    if (sequence.isLatest(requestId)) {
      handlers.onComplete();
    }
  }
}
