import { defineConfig, devices } from "@playwright/test";

const API_URL = process.env.SATQUERY_API_URL ?? "http://127.0.0.1:8001";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3002";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  timeout: 60_000,
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "setup",
      testMatch: /global\.setup\.spec\.ts/,
    },
    {
      name: "chromium",
      testMatch: /.*\.spec\.ts/,
      testIgnore: /global\.setup\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },
  ],
  webServer: [
    {
      command:
        "cd ../backend && IMAGERY_PROVIDER=development CHANGE_DETECTOR=development SEMANTIC_ANALYZER=development SAR_CHANGE_DETECTOR=development QUERY_PLANNER=deterministic GEOCHAT_VQA_PROVIDER=development UPLOAD_CHANGE_DETECTOR=bi_temporal PYTHONPATH=.:.pip_packages /opt/homebrew/bin/python3.11 -m uvicorn app.main:app --host 127.0.0.1 --port 8001",
      url: `${API_URL}/health`,
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: `SATQUERY_BACKEND_URL=${API_URL} npm run dev -- --port 3002`,
      url: BASE_URL,
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
