import { expect, test as setup } from "./fixtures";

setup("warm up workstation dev page", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded", timeout: 120_000 });
  await expect(page.getByTestId("composer-run")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("map")).toBeAttached({ timeout: 30_000 });
});
