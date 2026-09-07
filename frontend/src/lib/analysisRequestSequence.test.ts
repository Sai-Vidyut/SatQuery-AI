import { describe, expect, it } from "vitest";
import {
  createAnalysisRequestSequence,
  runGuardedAnalysisRequest,
} from "./analysisRequestSequence";

describe("analysisRequestSequence", () => {
  it("ignores stale success when a newer request resolves first", async () => {
    const sequence = createAnalysisRequestSequence();
    const resolveQueue: Array<(value: string) => void> = [];
    const defer = () =>
      new Promise<string>((resolve) => {
        resolveQueue.push(resolve);
      });

    let result: string | null = null;
    let error: string | null = null;
    let running = false;

    const requestA = sequence.begin();
    running = true;
    const promiseA = defer();
    void runGuardedAnalysisRequest(sequence, requestA, () => promiseA, {
      onSuccess: (value) => {
        result = value;
      },
      onError: (message) => {
        error = message;
      },
      onComplete: () => {
        running = false;
      },
    });

    const requestB = sequence.begin();
    running = true;
    const promiseB = defer();
    void runGuardedAnalysisRequest(sequence, requestB, () => promiseB, {
      onSuccess: (value) => {
        result = value;
      },
      onError: (message) => {
        error = message;
      },
      onComplete: () => {
        running = false;
      },
    });

    resolveQueue[1]("result-B");
    await Promise.resolve();
    expect(result).toBe("result-B");

    resolveQueue[0]("result-A");
    await Promise.resolve();

    expect(result).toBe("result-B");
    expect(error).toBeNull();
    expect(running).toBe(false);
  });

  it("ignores stale error after newer request succeeds", async () => {
    const sequence = createAnalysisRequestSequence();
    const resolveQueue: Array<(value: string) => void> = [];
    const rejectQueue: Array<(reason: Error) => void> = [];
    const deferSuccess = () =>
      new Promise<string>((resolve) => {
        resolveQueue.push(resolve);
      });
    const deferFailure = () =>
      new Promise<string>((_, reject) => {
        rejectQueue.push(reject);
      });

    let result: string | null = null;
    let error: string | null = null;

    const requestA = sequence.begin();
    void runGuardedAnalysisRequest(sequence, requestA, () => deferFailure(), {
      onSuccess: (value) => {
        result = value;
      },
      onError: (message) => {
        error = message;
      },
      onComplete: () => {},
    });

    const requestB = sequence.begin();
    void runGuardedAnalysisRequest(sequence, requestB, () => deferSuccess(), {
      onSuccess: (value) => {
        result = value;
      },
      onError: (message) => {
        error = message;
      },
      onComplete: () => {},
    });

    resolveQueue[0]("result-B");
    await Promise.resolve();
    expect(result).toBe("result-B");

    rejectQueue[0](new Error("stale-A-failed"));
    await Promise.resolve();

    expect(result).toBe("result-B");
    expect(error).toBeNull();
  });
});
