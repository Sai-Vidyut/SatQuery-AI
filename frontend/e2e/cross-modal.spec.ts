import { execSync } from "node:child_process";
import path from "node:path";
import { test, expect } from "@playwright/test";

const FIXTURE_DIR = path.join(__dirname, "fixtures");
const FIXTURE_OPTICAL = path.join(FIXTURE_DIR, "cm_optical.tif");
const FIXTURE_SAR = path.join(FIXTURE_DIR, "cm_sar.tif");

test.beforeAll(() => {
  execSync(
    `cd ../backend && uv run python -c "from pathlib import Path; from tests.fixtures.rasters import write_geotiff; write_geotiff(Path('${FIXTURE_OPTICAL}')); write_geotiff(Path('${FIXTURE_SAR}'))"`,
    { stdio: "inherit" },
  );
});

test("cross-modal optical+SAR flow shows trace and joint analysis", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("composer-mode-cross-modal").click();

  await page.getByTestId("composer-upload-optical-trigger").click();
  await page.getByTestId("composer-upload-optical").setInputFiles(FIXTURE_OPTICAL);
  await expect(page.getByTestId("composer-optical-upload-status")).toBeVisible({
    timeout: 15_000,
  });

  await page.getByTestId("composer-upload-sar-trigger").click();
  await page.getByTestId("composer-upload-sar").setInputFiles(FIXTURE_SAR);
  await expect(page.getByTestId("composer-sar-upload-status")).toBeVisible({
    timeout: 15_000,
  });

  await expect(page.getByTestId("composer-cross-modal-validation-status")).toBeVisible();

  await page.getByTestId("composer-query").fill(
    "Use the optical and SAR images together to identify built-up and water-covered regions.",
  );
  await page.getByTestId("composer-run").click();

  await expect(page.getByTestId("inspector")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("trace")).toBeVisible();
  await expect(page.getByTestId("inspector-optical-analysis")).toBeVisible();
  await expect(page.getByTestId("inspector-sar-analysis")).toBeVisible();
  await expect(page.getByTestId("inspector-joint-analysis")).toBeVisible();
  await expect(page.getByText("Validate input")).toBeVisible();
  await expect(page.getByTestId("trace").getByText("Cross-modal fusion", { exact: true })).toBeVisible();
});
