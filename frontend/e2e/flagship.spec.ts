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
    await expect(page.getByTestId("inspector-chat-drawer")).toHaveClass(/inspector-chat-drawer--collapsed/);
    await expect(page.getByTestId("region-chat-open")).toBeVisible();

    await page.getByTestId("region-chat-open").click();
    await expect(page.getByTestId("region-chat-message")).toBeVisible();
    await expect(page.getByTestId("region-chat-send")).toBeVisible();
    await expect(page.getByTestId("region-chat-resize-handle")).toBeVisible();

    const drawer = page.getByTestId("inspector-chat-drawer");
    const heightBeforeResize = await drawer.evaluate((node) => node.getBoundingClientRect().height);
    const resizeHandle = page.getByTestId("region-chat-resize-handle");
    const handleBox = await resizeHandle.boundingBox();
    if (!handleBox) throw new Error("Resize handle has no bounding box");
    await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y + handleBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y - 72, { steps: 10 });
    await page.mouse.up();
    const heightAfterExpand = await drawer.evaluate((node) => node.getBoundingClientRect().height);
    expect(heightAfterExpand).toBeGreaterThan(heightBeforeResize);

    await page.getByTestId("region-chat-message").fill("hello");
    const chatRequest = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/query/") &&
        response.url().endsWith("/chat") &&
        response.request().method() === "POST" &&
        response.ok(),
    );
    await page.getByTestId("region-chat-send").click();
    await chatRequest;
    await expect(page.getByTestId("region-chat-history")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("region-chat-turn")).toHaveCount(1);
    await expect(page.getByTestId("region-chat-turn").first()).toContainText("hello");
    await expect(page.getByTestId("region-chat-turn").first()).not.toContainText(
      "Found 3 significant spectral change regions",
    );

    await page.getByTestId("region-chat-message").fill("On what basis are you finding the differences?");
    await page.getByTestId("region-chat-send").click();
    await expect(page.getByTestId("region-chat-turn")).toHaveCount(2, { timeout: 60_000 });
    await expect(page.getByTestId("inspector-chat-drawer")).toHaveClass(/inspector-chat-drawer--expanded/);

    await page.getByTestId("region-chat-message").fill("Summarize the strongest change signal.");
    await page.getByTestId("region-chat-send").click();
    await expect(page.getByTestId("region-chat-turn")).toHaveCount(3, { timeout: 60_000 });
    const turnAnswers = await page.getByTestId("region-chat-turn").locator(".region-chat__answer").allTextContents();
    expect(new Set(turnAnswers).size).toBeGreaterThan(1);

    await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y + handleBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y + 72, { steps: 10 });
    await page.mouse.up();
    const heightAfterShrink = await drawer.evaluate((node) => node.getBoundingClientRect().height);
    expect(heightAfterShrink).toBeLessThanOrEqual(heightAfterExpand);
    if (heightAfterExpand > 260) {
      await resizeHandle.focus();
      await page.keyboard.press("ArrowDown");
      await page.keyboard.press("ArrowDown");
      await page.keyboard.press("ArrowDown");
      const heightAfterKeyboardShrink = await drawer.evaluate((node) => node.getBoundingClientRect().height);
      expect(heightAfterKeyboardShrink).toBeLessThan(heightAfterExpand);
    }

    await page.getByTestId("region-chat-collapse").click();
    await expect(page.getByTestId("inspector-chat-drawer")).toHaveClass(/inspector-chat-drawer--collapsed/);
    await expect(page.getByTestId("region-chat-message")).toHaveCount(0);
    await expect(page.locator(".inspector-answer")).toContainText(/separability/i);
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
