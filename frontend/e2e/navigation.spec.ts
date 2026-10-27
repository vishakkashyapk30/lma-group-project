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

test.describe("continue the last case from the landing page", () => {
  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: true, draft: "done" });
    await page.setViewportSize({ width: 1440, height: 900 });
  });

  test("a first visit offers the workspace, not a case", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "Landing" }).getByRole("link", { name: "Open workspace" })).toBeVisible();
    await expect(page.getByTestId(TID.continueCase)).toHaveCount(0);
  });

  test("open a case, go home by the logo, and continue where you were", async ({ page }) => {
    await page.goto("/case/case-0007");
    await expect(page.getByTestId(TID.stageRail)).toBeVisible();
    await expect(page.getByTestId("topbar-stage")).toBeVisible();
    await page.getByTestId(TID.sidebar).getByTestId(TID.brandHome).click();
    await expect(page).toHaveURL(/\/$/);
    const cont = page.getByTestId(TID.continueCase);
    await expect(cont).toBeVisible();
    await expect(cont).toContainText("Continue: State v. Accused-1");
    await expect(cont).toHaveAttribute("href", "/case/case-0007");
    await expect(page.getByRole("link", { name: "All cases" })).toHaveAttribute("href", "/cases");
    await cont.click();
    await expect(page).toHaveURL(/\/case\/case-0007$/);
    await expect(page.getByTestId(TID.stageRail)).toBeVisible();
  });

  test("the header does not shift when the label changes", async ({ page }) => {
    await page.goto("/");
    const before = await page.getByRole("navigation", { name: "Landing" }).boundingBox();
    await page.evaluate(() => localStorage.setItem("vs:last-case", JSON.stringify({ id: "case-0007", title: "State v. Accused-1, FIR 112/2024, PS-1", stageLabel: "Draft grounds", at: "" })));
    await page.reload();
    await expect(page.getByTestId(TID.continueCase)).toBeVisible();
    const after = await page.getByRole("navigation", { name: "Landing" }).boundingBox();
    expect(Math.abs((after?.y ?? 0) - (before?.y ?? 0))).toBeLessThan(1);
    expect(after?.height).toBeCloseTo(before?.height ?? 0, 0);
  });
});
