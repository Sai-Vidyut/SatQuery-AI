import { test, expect } from "./fixtures";

async function drawAoiOnMap(page: import("@playwright/test").Page) {
  await page.getByTestId("rail-draw-aoi").click();
  await expect(page.getByTestId("map")).toHaveAttribute("data-draw-active", "true");

  const canvas = page.locator(".maplibregl-canvas");
  await expect(canvas).toBeVisible({ timeout: 20_000 });
  const box = await canvas.boundingBox();
  if (!box) throw new Error("Map canvas has no bounding box");

  const startX = box.x + box.width * 0.35;
  const startY = box.y + box.height * 0.35;
  const endX = box.x + box.width * 0.55;
  const endY = box.y + box.height * 0.55;

  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(endX, endY, { steps: 12 });
  await page.mouse.up();

  await expect(page.getByTestId("aoi-status")).toContainText("km²", { timeout: 10_000 });
  await expect(page.getByTestId("map")).toHaveAttribute("data-draw-active", "false");
}

test.describe("SatQuery flagship flow", () => {
  test("AOI draw, dates, query, trace, regions, confidence, map visible", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByTestId("map")).toBeAttached();
    await expect(page.getByTestId("inspector")).toHaveCount(0);
    await expect(page.getByTestId("composer-validation-error")).toHaveCount(0);

    await drawAoiOnMap(page);

    await page.getByTestId("composer-date-from").fill("2024-12-01");
    await page.getByTestId("composer-date-to").fill("2025-03-01");
    await expect(page.getByTestId("composer-date-from")).toHaveValue("2024-12-01");
    await expect(page.getByTestId("composer-date-to")).toHaveValue("2025-03-01");

    await page.getByTestId("composer-query").fill("Show me significant new construction.");
    await page.getByTestId("composer-run").click();

    await expect(page.getByTestId("composer-run")).toBeEnabled({
      timeout: 60_000,
    });
    await expect(page.getByTestId("inspector")).toBeVisible();
    await expect(page.getByTestId("trace")).toBeVisible();

    const inspector = page.getByTestId("inspector");
    const regions = inspector.getByTestId("region-row");
    await expect(regions.first()).toBeVisible({ timeout: 15_000 });
    expect(await regions.count()).toBeGreaterThanOrEqual(1);

    await expect(inspector.getByText(/Regions \(\d+\)/)).toBeVisible();
    await expect(page.locator(".inspector-answer")).toContainText(/separability/i);
    await expect(page.getByTestId("map")).toBeVisible();
  });

  test("bbox keyboard fallback sets AOI", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".maplibregl-canvas")).toBeVisible({ timeout: 20_000 });

    await page.getByTestId("aoi-status").click();
    await page.getByTestId("aoi-bbox").fill("77.59, 12.97, 77.61, 12.99");
    await page.getByRole("button", { name: "Set AOI" }).click();

    await expect(page.getByTestId("aoi-status")).toContainText("km²");
  });

  test("validation errors stay in composer only", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("composer-run").click();
    await expect(page.getByTestId("composer-validation-error")).toBeVisible();
    await expect(page.getByTestId("inspector")).toHaveCount(0);
  });

  test("keyboard focus on run control", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("composer-run").focus();
    await expect(page.getByTestId("composer-run")).toBeFocused();
  });
});
