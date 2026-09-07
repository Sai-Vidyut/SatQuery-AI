import { execSync } from "node:child_process";
import path from "node:path";
import { test, expect } from "./fixtures";

const FIXTURE_DIR = path.join(__dirname, "fixtures");
const FIXTURE_TIF = path.join(FIXTURE_DIR, "caption_smoke.tif");

test.beforeAll(() => {
  execSync(
    `cd ../backend && .venv/bin/python -c "from pathlib import Path; from tests.fixtures.rasters import write_geotiff; write_geotiff(Path('${FIXTURE_TIF}'))"`,
    { stdio: "inherit" },
  );
});

test("upload image scene description flow shows trace and caption", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("composer-mode-upload").click();

  await page.getByTestId("composer-upload-trigger").click();
  await page.getByTestId("composer-upload").setInputFiles(FIXTURE_TIF);

  await expect(page.getByTestId("composer-upload-status")).toContainText("Validated", {
    timeout: 15_000,
  });

  await page.getByTestId("composer-query").fill("Describe this satellite scene.");
  await page.getByTestId("composer-run").click();

  await expect(page.getByTestId("inspector")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("trace")).toBeVisible();
  await expect(page.getByTestId("inspector-caption-provenance")).toBeVisible();
  await expect(page.getByTestId("inspector-scene-description")).not.toBeEmpty();
  await expect(
    page.getByTestId("inspector-caption-provenance").locator("dd", { hasText: "Scene Description" }),
  ).toBeVisible();
});
