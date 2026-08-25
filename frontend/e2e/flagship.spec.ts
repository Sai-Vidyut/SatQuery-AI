import { test, expect } from "@playwright/test";

test.describe("SatQuery flagship flow", () => {
  test("AOI, dates, query, trace, regions, confidence, map visible", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByTestId("map")).toBeAttached();
    await expect(page.locator(".maplibregl-canvas")).toBeVisible({ timeout: 20_000 });

    // Set AOI via bounding box (keyboard-accessible fallback)
    await page.getByTestId("aoi-status").click();
    await page.getByTestId("aoi-bbox").fill("77.59, 12.97, 77.61, 12.99");
    await page.getByRole("button", { name: "Set AOI" }).click();

    await page.getByTestId("composer-date-from").fill("2024-12-01");
    await page.getByTestId("composer-date-to").fill("2025-03-01");
    await page.getByTestId("composer-query").fill("Show me significant new construction.");
    await page.getByTestId("composer-run").click();

    await expect(page.getByTestId("composer-run")).toHaveText("Run Analysis", {
      timeout: 60_000,
    });
    await expect(page.getByTestId("inspector")).toBeVisible();
    await expect(page.getByTestId("trace")).toBeVisible();

    const regions = page.getByTestId("region-row");
    await expect(regions.first()).toBeVisible({ timeout: 15_000 });
    expect(await regions.count()).toBeGreaterThanOrEqual(1);

    await regions.first().click();
    await expect(page.getByTestId("confidence").first()).toBeVisible();
    await expect(page.getByTestId("map")).toBeVisible();
  });

  test("keyboard focus on run control", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("composer-run").focus();
    await expect(page.getByTestId("composer-run")).toBeFocused();
  });
});
