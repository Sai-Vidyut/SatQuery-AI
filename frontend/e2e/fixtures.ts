import { test as base, expect } from "@playwright/test";

/** Matches WorkstationTour TOUR_STORAGE_KEY — set before navigation so auto-start is skipped. */
const TOUR_STORAGE_KEY = "satquery_tour_seen";

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.addInitScript((key) => {
      localStorage.setItem(key, "1");
    }, TOUR_STORAGE_KEY);
    await use(page);
  },
});

export { expect };
