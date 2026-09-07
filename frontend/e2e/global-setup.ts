import { request } from "@playwright/test";
import { waitForWorkstationReady } from "./wait-for-workstation";

const API_URL = process.env.SATQUERY_API_URL ?? "http://127.0.0.1:8001";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3002";

async function assertSatQueryBackend(url: string): Promise<void> {
  const ctx = await request.newContext();
  try {
    const res = await ctx.get(`${url}/health`, { timeout: 5_000 });
    if (!res.ok()) {
      throw new Error(
        `E2E backend port ${url} is occupied but /health returned HTTP ${res.status()}. ` +
          "Stop the conflicting process or set SATQUERY_API_URL to a free port.",
      );
    }
    const body = await res.json();
    const provider = body?.data?.imagery_provider;
    if (provider !== "development") {
      throw new Error(
        `E2E backend port ${url} is occupied by a non-E2E server ` +
          `(imagery_provider=${String(provider)}). Stop the conflicting process before running Playwright.`,
      );
    }
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("E2E backend port")) {
      throw error;
    }
    // Connection refused — Playwright webServer will start the backend.
  } finally {
    await ctx.dispose();
  }
}

async function assertSatQueryFrontend(url: string): Promise<void> {
  const ctx = await request.newContext();
  try {
    const res = await ctx.get(url, { timeout: 5_000 });
    if (!res.ok()) {
      throw new Error(
        `E2E frontend port ${url} is occupied but returned HTTP ${res.status()}. ` +
          "Stop the conflicting process or set PLAYWRIGHT_BASE_URL to a free port.",
      );
    }
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("E2E frontend port")) {
      throw error;
    }
    // Connection refused — Playwright webServer will start the frontend.
    return;
  } finally {
    await ctx.dispose();
  }

  await waitForWorkstationReady(url);
}

export default async function globalSetup(): Promise<void> {
  await assertSatQueryBackend(API_URL);
  await assertSatQueryFrontend(BASE_URL);
}
