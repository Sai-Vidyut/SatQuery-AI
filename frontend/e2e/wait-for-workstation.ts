import { request } from "@playwright/test";

const WORKSTATION_MARKERS = ["SatQuery", "__next"];

/** Poll until the workstation HTML shell responds consistently. */
export async function waitForWorkstationReady(
  baseURL: string,
  timeoutMs = 120_000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  const ctx = await request.newContext();
  let lastStatus: number | "unreachable" = "unreachable";

  try {
    while (Date.now() < deadline) {
      try {
        const res = await ctx.get(baseURL, { timeout: 10_000 });
        lastStatus = res.status();
        if (res.ok()) {
          const html = await res.text();
          if (WORKSTATION_MARKERS.every((marker) => html.includes(marker))) {
            return;
          }
        }
      } catch {
        lastStatus = "unreachable";
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    throw new Error(
      `Workstation page not ready at ${baseURL} (last status: ${String(lastStatus)})`,
    );
  } finally {
    await ctx.dispose();
  }
}
