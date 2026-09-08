import { execSync } from "node:child_process";
import path from "node:path";
import { test, expect } from "./fixtures";

const FIXTURE_DIR = path.join(__dirname, "fixtures");
const FIXTURE_BEFORE = path.join(FIXTURE_DIR, "bt_before.tif");
const FIXTURE_AFTER = path.join(FIXTURE_DIR, "bt_after.tif");

test.beforeAll(() => {
  execSync(
    `cd ../backend && .venv/bin/python -c "from pathlib import Path; from tests.fixtures.rasters import write_bi_temporal_scene; write_bi_temporal_scene(Path('${FIXTURE_BEFORE}'), role='earlier', scenario='vegetation_loss'); write_bi_temporal_scene(Path('${FIXTURE_AFTER}'), role='later', scenario='vegetation_loss')"`,
    { stdio: "inherit" },
  );
});

test("bi-temporal pair change flow shows trace, result, and regions", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/");

  await page.getByTestId("composer-mode-temporal-pair").click();
  await expect(page.getByTestId("composer-upload-earlier-trigger")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByTestId("composer-pair-date-from").fill("2023-01-01");
  await page.getByTestId("composer-pair-date-to").fill("2024-01-01");

  await page.getByTestId("composer-upload-earlier-trigger").click();
  const earlierUpload = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/imagery/upload") &&
      response.request().method() === "POST" &&
      response.ok(),
  );
  await page.getByTestId("composer-upload-earlier").setInputFiles(FIXTURE_BEFORE);
  await earlierUpload;
  await expect(page.getByTestId("composer-earlier-upload-status")).toContainText("Before", {
    timeout: 15_000,
  });

  await page.getByTestId("composer-upload-later-trigger").click();
  const laterUpload = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/imagery/upload") &&
      response.request().method() === "POST" &&
      response.ok(),
  );
  await page.getByTestId("composer-upload-later").setInputFiles(FIXTURE_AFTER);
  await laterUpload;
  await expect(page.getByTestId("composer-later-upload-status")).toContainText("After", {
    timeout: 15_000,
  });

  await page.getByTestId("composer-query").fill(
    "What changed between these two dates, and where did the change occur?",
  );
  await page.getByTestId("composer-run").click();

  await expect(page.getByTestId("composer-run")).toBeEnabled({
    timeout: 60_000,
  });
  await expect(page.getByTestId("inspector")).toBeVisible();
  await expect(page.getByTestId("trace")).toBeVisible();
  await expect(page.getByTestId("inspector-bitemporal-provenance")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByTestId("inspector-bitemporal-provenance")).toContainText(
    "uploaded_bi_temporal",
  );
  await expect(page.getByTestId("trace")).toContainText("uploaded_bi_temporal");
  await expect(page.getByTestId("inspector-change-summary")).not.toBeEmpty();
  await expect(page.getByTestId("region-row").first()).toBeVisible({ timeout: 15_000 });

  const firstRegion = page.getByTestId("region-row").first();
  await firstRegion.evaluate((node) => {
    (node as HTMLButtonElement).click();
  });
  await expect(firstRegion).toHaveAttribute("aria-selected", "true", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("before-after-evidence")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("before-after-preview-before")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("before-after-preview-after")).toBeVisible({ timeout: 15_000 });
  for (const testId of ["before-after-preview-before", "before-after-preview-after"] as const) {
    const brightRatio = await page.getByTestId(testId).evaluate((img: HTMLImageElement) => {
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx || canvas.width === 0 || canvas.height === 0) return 0;
      ctx.drawImage(img, 0, 0);
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      let bright = 0;
      for (let i = 0; i < data.length; i += 4) {
        if (data[i] > 10 || data[i + 1] > 10 || data[i + 2] > 10) bright += 1;
      }
      return bright / (canvas.width * canvas.height);
    });
    expect(brightRatio).toBeGreaterThan(0.5);
  }
  await expect(page.getByTestId("inspector-bitemporal-provenance")).toBeVisible();
  await expect(page.getByTestId("inspector-change-summary")).not.toBeEmpty();

  await expect(page.getByTestId("inspector-chat-drawer")).toHaveClass(/inspector-chat-drawer--collapsed/);
  await expect(page.getByTestId("region-chat-open")).toBeVisible();
  await expect(page.getByText("Ask GeoChat about this region")).toBeVisible();
  await expect(page.getByTestId("region-chat-message")).toHaveCount(0);
  await expect(page.getByTestId("before-after-evidence")).toBeVisible();

  await expect(page.getByTestId("region-deterministic-summary")).toBeVisible();
  await expect(page.getByTestId("region-deterministic-detection")).toBeVisible();
  await expect(page.getByTestId("region-chat-message")).toHaveCount(0);

  await page.getByTestId("region-chat-open").click();
  await expect(page.getByTestId("inspector-chat-drawer")).toHaveClass(/inspector-chat-drawer--expanded/);
  await expect(page.getByTestId("region-chat-message")).toBeVisible();
  await expect(page.getByTestId("region-chat-send")).toBeVisible();
  await expect(page.getByTestId("region-chat-resize-handle")).toBeVisible();
  await expect(page.getByTestId("before-after-evidence")).toBeVisible();

  const drawer = page.getByTestId("inspector-chat-drawer");
  const heightBeforeResize = await drawer.evaluate((node) => node.getBoundingClientRect().height);
  const resizeHandle = page.getByTestId("region-chat-resize-handle");
  const handleBox = await resizeHandle.boundingBox();
  if (!handleBox) throw new Error("Resize handle has no bounding box");

  await page.getByTestId("region-chat-message").fill("hello");
  const helloChatRequest = page.waitForResponse(
    (response) =>
      response.url().includes("/regions/") &&
      response.url().endsWith("/chat") &&
      response.request().method() === "POST" &&
      response.ok(),
  );
  await page.getByTestId("region-chat-send").evaluate((node) => {
    (node as HTMLButtonElement).click();
  });
  await helloChatRequest;
  await expect(page.getByTestId("region-chat-history")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("region-chat-turn")).toHaveCount(1);
  await expect(page.getByTestId("region-chat-turn").first()).toContainText("hello");
  await expect(page.getByTestId("region-chat-turn").first()).not.toContainText(
    "Found 3 significant spectral change regions",
  );
  await expect(page.getByTestId("region-chat-provider-badge")).toContainText("General AI · DEMO", {
    timeout: 30_000,
  });

  await page.getByTestId("region-chat-message").fill(
    "What visible change occurred between the two dates?",
  );
  await page.getByTestId("region-chat-send").evaluate((node) => {
    (node as HTMLButtonElement).click();
  });
  await expect(page.getByTestId("region-chat-loading")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("region-chat-history")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("region-chat-provider-badge")).toContainText("GeoChat · DEVELOPMENT MOCK");
  await expect(page.getByTestId("region-chat-route")).toHaveText("geo");

  await page.getByTestId("region-chat-message").fill("What is a binary search tree?");
  await page.getByTestId("region-chat-send").evaluate((node) => {
    (node as HTMLButtonElement).click();
  });
  await expect(page.getByTestId("region-chat-provider-badge")).toContainText("General AI · DEMO", {
    timeout: 30_000,
  });
  await expect(page.getByTestId("region-chat-route")).toHaveText("general");

  await page.getByTestId("region-chat-message").fill("Why do you think this is vegetation loss?");
  await page.getByTestId("region-chat-send").evaluate((node) => {
    (node as HTMLButtonElement).click();
  });
  await expect(page.getByTestId("region-chat-turn")).toHaveCount(3, { timeout: 30_000 });
  const turnAnswers = await page.getByTestId("region-chat-turn").locator(".region-chat__answer").allTextContents();
  expect(new Set(turnAnswers).size).toBeGreaterThan(1);
  await expect(page.getByTestId("inspector-chat-drawer")).toHaveClass(/inspector-chat-drawer--expanded/);

  await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y + handleBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y - 72, { steps: 10 });
  await page.mouse.up();
  const heightAfterExpand = await drawer.evaluate((node) => node.getBoundingClientRect().height);
  expect(heightAfterExpand).toBeGreaterThan(heightBeforeResize);

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
  await expect(page.getByTestId("before-after-evidence")).toBeVisible();

  await page.getByTestId("region-chat-message").fill("Find every changed area in the city.");
  await page.getByTestId("region-chat-send").evaluate((node) => {
    (node as HTMLButtonElement).click();
  });
  await expect(page.getByTestId("region-chat-scope-limited")).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("region-chat-collapse").click();
  await expect(page.getByTestId("inspector-chat-drawer")).toHaveClass(/inspector-chat-drawer--collapsed/);
  await expect(page.getByTestId("region-chat-open")).toBeVisible();
  await expect(page.getByTestId("region-chat-message")).toHaveCount(0);

  await page.getByTestId("region-chat-open").click();
  await expect(page.getByTestId("region-chat-history")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("region-chat-turn")).toHaveCount(5);
});
