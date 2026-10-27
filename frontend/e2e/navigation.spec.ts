/**
 * Navigation between the landing page and the app (docs/handoff/frontend-endeavours-ideation.md section 6): the logo goes to the
 * landing page from every route, and the landing page offers to continue the case that was open last.
 */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { TID } from "./testids";

test.describe("the logo goes to the landing page", () => {
  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: true, draft: "done" });
  });

  for (const path of ["/cases", "/case/case-0007", "/library", "/desk", "/help"]) {
    test(`from ${path} (desktop sidebar)`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(path);
      const logo = page.getByTestId(TID.sidebar).getByTestId(TID.brandHome);
      await expect(logo).toHaveAttribute("href", "/");
      await expect(logo).toHaveAccessibleName("Vakeel-Sahayak home");
      await logo.click();
      await expect(page).toHaveURL(/\/$/);
      await expect(page.getByRole("heading", { level: 1 })).toContainText("Prepare a bail application");
    });
  }

  test("from the mobile drawer", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/cases");
    await page.getByRole("button", { name: "Open menu" }).click();
    await page.getByRole("dialog").getByTestId(TID.brandHome).click();
    await expect(page).toHaveURL(/\/$/);
  });

  test("Cases stays one click away as the first sidebar item", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/library");
    const first = page.getByTestId(TID.sidebar).getByRole("navigation", { name: "Primary" }).getByRole("link").first();
    await expect(first).toHaveAttribute("href", "/cases");
  });
});
