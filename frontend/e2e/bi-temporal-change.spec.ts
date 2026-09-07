import { execSync } from "node:child_process";
import path from "node:path";
import { test, expect } from "./fixtures";

const FIXTURE_DIR = path.join(__dirname, "fixtures");
const FIXTURE_BEFORE = path.join(FIXTURE_DIR, "bt_before.tif");
const FIXTURE_AFTER = path.join(FIXTURE_DIR, "bt_after.tif");

test.beforeAll(() => {
  execSync(
    `cd ../backend && .venv/bin/python -c "from pathlib import Path; from tests.fixtures.rasters import write_geotiff; write_geotiff(Path('${FIXTURE_BEFORE}')); write_geotiff(Path('${FIXTURE_AFTER}'))"`,
    { stdio: "inherit" },
  );
});

test("bi-temporal pair change flow shows trace, result, and regions", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("composer-mode-temporal-pair").click();
  await page.getByTestId("composer-pair-date-from").fill("2023-01-01");
  await page.getByTestId("composer-pair-date-to").fill("2024-01-01");

  await page.getByTestId("composer-upload-earlier-trigger").click();
  await page.getByTestId("composer-upload-earlier").setInputFiles(FIXTURE_BEFORE);
  await expect(page.getByTestId("composer-earlier-upload-status")).toContainText("Before", {
    timeout: 15_000,
  });

  await page.getByTestId("composer-upload-later-trigger").click();
  await page.getByTestId("composer-upload-later").setInputFiles(FIXTURE_AFTER);
  await expect(page.getByTestId("composer-later-upload-status")).toContainText("After", {
    timeout: 15_000,
  });

  await page.getByTestId("composer-query").fill(
    "What changed between these two dates, and where did the change occur?",
  );
  await page.getByTestId("composer-run").click();

  await expect(page.getByTestId("inspector")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("trace")).toBeVisible();
  await expect(page.getByTestId("inspector-bitemporal-provenance")).toBeVisible();
  await expect(page.getByTestId("inspector-change-summary")).not.toBeEmpty();
  await expect(page.getByTestId("region-row").first()).toBeVisible();
});
