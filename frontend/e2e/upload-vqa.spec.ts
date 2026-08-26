import { execSync } from "node:child_process";
import path from "node:path";
import { test, expect } from "@playwright/test";

const FIXTURE_DIR = path.join(__dirname, "fixtures");
const FIXTURE_TIF = path.join(FIXTURE_DIR, "vqa_smoke.tif");

test.beforeAll(() => {
  execSync(
    `cd ../backend && .venv/bin/python -c "from pathlib import Path; from tests.fixtures.rasters import write_geotiff; write_geotiff(Path('${FIXTURE_TIF}'))"`,
    { stdio: "inherit" },
  );
});

test("upload image VQA flow shows trace and answer", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("composer-mode-upload").click();

  await page.getByTestId("composer-upload-trigger").click();
  await page.getByTestId("composer-upload").setInputFiles(FIXTURE_TIF);

  await expect(page.getByTestId("composer-upload-status")).toContainText("Validated", {
    timeout: 15_000,
  });

  await page.getByTestId("composer-query").fill(
    "Describe the land-cover and major objects visible in this image.",
  );
  await page.getByTestId("composer-run").click();

  await expect(page.getByTestId("inspector")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("trace")).toBeVisible();
  await expect(page.getByTestId("inspector-vqa-provenance")).toBeVisible();
  await expect(page.locator(".inspector-answer")).not.toBeEmpty();
});
