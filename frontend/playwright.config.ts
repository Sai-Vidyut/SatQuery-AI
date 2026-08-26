import { defineConfig, devices } from "@playwright/test";

const API_URL = process.env.SATQUERY_API_URL ?? "http://127.0.0.1:8001";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3002",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "cd ../backend && IMAGERY_PROVIDER=development CHANGE_DETECTOR=development SEMANTIC_ANALYZER=development SAR_CHANGE_DETECTOR=development QUERY_PLANNER=deterministic GEOCHAT_VQA_PROVIDER=development PYTHONPATH=.:.pip_packages /opt/homebrew/bin/python3.11 -m uvicorn app.main:app --host 127.0.0.1 --port 8001",
      url: `${API_URL}/health`,
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: `SATQUERY_BACKEND_URL=${API_URL} npm run dev -- --port 3002`,
      url: "http://127.0.0.1:3002",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
