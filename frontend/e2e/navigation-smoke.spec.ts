import { expect, test } from "./fixtures";

test("workstation root navigation smoke", async ({ page }) => {
  await page.goto("/workstation", { waitUntil: "domcontentloaded", timeout: 120_000 });
  await expect(page.getByTestId("composer-run")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("map")).toBeAttached();
});
