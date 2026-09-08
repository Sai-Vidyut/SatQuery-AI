import { test, expect } from "./fixtures";

async function drawAoiOnMap(page: import("@playwright/test").Page) {
  await expect(page.getByTestId("map")).toBeAttached({ timeout: 30_000 });
  await expect(page.locator(".maplibregl-canvas")).toBeVisible({ timeout: 30_000 });
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
  await expect(page.getByTestId("map")).toHaveAttribute("data-ground-view-point-count", /^[1-9]/, {
    timeout: 15_000,
  });
}

async function readMapSnapshot(page: import("@playwright/test").Page) {
  return page.evaluate(() => {
    const map = (window as unknown as {
      __satqueryMap?: {
        getCenter: () => { lng: number; lat: number };
        getZoom: () => number;
        getBearing: () => number;
        getPitch: () => number;
      };
    }).__satqueryMap;
    if (!map) return null;
    const center = map.getCenter();
    return {
      center: [center.lng, center.lat],
      zoom: map.getZoom(),
      bearing: map.getBearing(),
      pitch: map.getPitch(),
    };
  });
}

async function snapshotsRoughlyEqual(
  a: { center: number[]; zoom: number; bearing: number; pitch: number } | null,
  b: { center: number[]; zoom: number; bearing: number; pitch: number } | null,
): Promise<boolean> {
  if (!a || !b) return a === b;
  return (
    Math.abs(a.center[0] - b.center[0]) < 0.002 &&
    Math.abs(a.center[1] - b.center[1]) < 0.002 &&
    Math.abs(a.zoom - b.zoom) < 1.0 &&
    Math.abs(a.bearing - b.bearing) < 0.5 &&
    Math.abs(a.pitch - b.pitch) < 0.5
  );
}

test.describe("Ground View immersive preview", () => {
  test.describe.configure({ mode: "serial" });
  test("AOI markers open full-screen mock preview and restore map state", async ({ page }) => {
    let submitCount = 0;
    page.on("request", (request) => {
      if (request.url().includes("/api/v1/query/submit") && request.method() === "POST") {
        submitCount += 1;
      }
    });

    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 120_000 });

    await drawAoiOnMap(page);

    const marker = page.locator(".ground-view-marker").first();
    await expect(marker).toBeVisible({ timeout: 15_000 });

    const snapshotBefore = await readMapSnapshot(page);
    const bboxBefore = await page.getByTestId("aoi-status").textContent();

    await marker.click();
    await expect(page.getByTestId("ground-view-overlay")).toBeVisible();
    await expect(page.getByTestId("ground-view-image")).toBeVisible();
    await expect(page.getByTestId("ground-view-demo-badge")).toContainText("DEMO DATA");
    await expect(page.getByTestId("ground-view-disclosure")).toContainText("Demonstration imagery");
    await expect(page.getByTestId("ground-view-panorama-hint")).toContainText("Drag horizontally");
    await expect(page.getByTestId("ground-view-image")).toHaveAttribute(
      "src",
      /\/mock-ground\/panorama-/,
    );
    await expect(page.getByTestId("ground-view-close")).toBeVisible();
    await expect(page.getByTestId("ground-view-title")).not.toBeEmpty();

    expect(submitCount).toBe(0);

    await page.getByTestId("ground-view-close").click();
    await expect(page.getByTestId("ground-view-overlay")).toHaveCount(0);
    await expect(page.locator(".ground-view-marker").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("aoi-status")).toHaveText(bboxBefore ?? "");
    if (snapshotBefore) {
      await expect
        .poll(async () => snapshotsRoughlyEqual(snapshotBefore, await readMapSnapshot(page)))
        .toBe(true);
    }
  });

  test("Escape closes Ground View without changing AOI", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 120_000 });
    await drawAoiOnMap(page);
    await expect(page.locator(".ground-view-marker").first()).toBeVisible({ timeout: 15_000 });

    const bboxBefore = await page.getByTestId("aoi-status").textContent();
    await page.locator(".ground-view-marker").first().click();
    await expect(page.getByTestId("ground-view-overlay")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("ground-view-overlay")).toHaveCount(0);
    await expect(page.getByTestId("aoi-status")).toHaveText(bboxBefore ?? "");
  });

  test("switching between two Ground View points updates metadata", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 120_000 });
    await drawAoiOnMap(page);

    const markers = page.locator(".ground-view-marker");
    await expect(markers.first()).toBeVisible({ timeout: 15_000 });
    const markerCount = await markers.count();
    test.skip(markerCount < 2, "AOI fixture produced fewer than two Ground View points");

    await markers.nth(0).click();
    const firstTitle = await page.getByTestId("ground-view-title").textContent();
    await page.getByTestId("ground-view-close").click();

    await markers.nth(1).click();
    const secondTitle = await page.getByTestId("ground-view-title").textContent();
    expect(firstTitle).not.toEqual(secondTitle);
  });
});
