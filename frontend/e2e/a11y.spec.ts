/**
 * Accessibility across the app (plan §13.7: zero serious axe violations; SA-07). axe-core on every page and every workspace step,
 * drawer and dialog at desktop and phone widths; the keyboard shortcuts the Help page documents; and Hindi text marked lang="hi"
 * so screen readers and fonts treat it as Hindi.
 */
import { expect, test, type Page } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { seriousAxeViolations } from "./helpers";
import { TID } from "./testids";

async function audit(page: Page, where: string, found: string[]) {
  await page.waitForTimeout(300);
  for (const v of await seriousAxeViolations(page)) found.push(`${where}: ${v}`);
}

for (const width of [1440, 390]) {
  test(`axe: zero serious or critical violations on every page, step, drawer and dialog at ${width} px`, async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width, height: 900 });
    await MockBackend.install(page, { gate1Approved: true, draft: "done", gate2Approved: false });
    const found: string[] = [];
    for (const path of ["/cases", "/desk", "/library", "/help", "/about", "/settings"]) {
      await page.goto(path);
      await audit(page, path, found);
    }
    await page.goto("/cases");
    await page.getByTestId("new-case-button").click();
    await audit(page, "new case dialog", found);
    await page.keyboard.press("Escape");

    await page.goto("/case/case-0007");
    await expect(page.getByTestId(TID.stageRail)).toBeVisible();
    for (const key of ["I", "II", "III", "IV", "VI", "VII"]) {
      await page.getByTestId(TID.stage(key)).click();
      await audit(page, `step ${key}`, found);
    }
    await page.getByTestId(TID.stage("II")).click();
    await page.getByTestId(TID.rightTab("dates")).click();
    await audit(page, "List of dates", found);
    await page.getByTestId(TID.rightTab("dossier")).click();
    await page.locator('[data-testid=dossier-field][data-field="fir"]').getByTestId(TID.dossierFieldSource).click();
    await audit(page, "source panel", found);
    await page.keyboard.press("Escape");
    for (const [id, name] of [[TID.chatButton, "chat"], [TID.detailsButton, "Details"], [TID.documentsButton, "Documents"]] as const) {
      await page.getByTestId(id).click();
      await audit(page, name, found);
      await page.keyboard.press("Escape");
    }
    expect(found).toEqual([]);
  });
}

test("axe: a fresh case and an empty cause list have no serious violations", async ({ page }) => {
  await MockBackend.install(page, { caseId: "case-0042", fresh: true, gate1Approved: false, draft: "none" });
  const found: string[] = [];
  await page.goto("/case/case-0042");
  await expect(page.getByTestId(TID.stageRail)).toBeVisible();
  await audit(page, "fresh case", found);
  await page.route("**/api/cases", (r) =>
    r.request().method() === "GET" ? r.fulfill({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: "[]" }) : r.fallback());
  await page.goto("/cases");
  await expect(page.getByText("No cases yet")).toBeVisible();
  await audit(page, "empty cause list", found);
  expect(found).toEqual([]);
});

test("a fresh case offers no fact confirmation before any paper is read", async ({ page }) => {
  await MockBackend.install(page, { caseId: "case-0042", fresh: true, gate1Approved: false, draft: "none" });
  await page.goto("/case/case-0042");
  await page.getByTestId(TID.stage("II")).click();
  await expect(page.getByText("No facts yet")).toBeVisible();
  await expect(page.getByTestId(TID.confirmFactsButton)).toHaveCount(0);
});

test.describe("keyboard shortcuts documented on the Help page", () => {
  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: true, draft: "done" });
  });

  test("Ctrl+K opens search, arrows and Enter open a result, Esc closes it", async ({ page }) => {
    await page.goto("/cases");
    await expect(page.getByTestId("new-case-button")).toBeVisible();
    const box = page.getByRole("combobox", { name: "Search cases, pages and actions" });
    await page.keyboard.press("Control+k");
    await expect(box).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(box).toHaveCount(0);
    await page.keyboard.press("Control+k");
    await box.fill("Help");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/help$/);
  });

  test("Left and Right move between steps when the step list has focus", async ({ page }) => {
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("II")).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId(TID.stage("III"))).toBeFocused();
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByTestId(TID.stage("II"))).toBeFocused();
  });
});

test("Hindi text on screen is marked lang=hi", async ({ page }) => {
  await MockBackend.install(page, { gate1Approved: true, draft: "done" });
  const unmarked = async () =>
    page.evaluate(() => {
      const out: string[] = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        const el = n.parentElement;
        if (!el || el.closest("script,style") || !/[ऀ-ॿ]/.test(n.textContent ?? "")) continue;
        if (!el.closest("[lang^=hi]")) out.push((n.textContent ?? "").trim().slice(0, 40));
      }
      return out;
    });
  await page.goto("/");
  expect(await unmarked()).toEqual([]);
  await page.goto("/case/case-0007");
  await page.getByTestId(TID.stage("II")).click();
  await page.locator('[data-testid=dossier-field][data-field="fir"]').getByTestId(TID.dossierFieldSource).click();
  await expect(page.getByTestId(TID.sourcePanel)).toBeVisible();
  expect(await unmarked()).toEqual([]);
});

test.describe("focus and loading after a navigation", () => {
  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: true, draft: "done" });
    await page.setViewportSize({ width: 1440, height: 900 });
  });

  test("a sidebar link moves focus to the new page's heading", async ({ page }) => {
    await page.goto("/cases");
    await expect(page.getByTestId("new-case-button")).toBeVisible();
    await page.getByTestId(TID.sidebar).getByRole("link", { name: "Batch desk" }).click();
    await expect(page).toHaveURL(/\/desk$/);
    await expect(page.getByRole("heading", { level: 1, name: "Batch desk" })).toBeFocused();
  });

  test("the command palette moves focus to the new page's heading, keyboard only", async ({ page }) => {
    await page.goto("/cases");
    await expect(page.getByTestId("new-case-button")).toBeVisible();
    await page.keyboard.press("Control+k");
    await page.keyboard.type("Precedent");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/library$/);
    await expect(page.getByRole("heading", { level: 1, name: "Precedent library" })).toBeFocused();
  });

  test("opening a case from the sidebar's Cases list keeps the stepper's arrow keys working", async ({ page }) => {
    await page.goto("/desk");
    await page.getByTestId(TID.sidebar).getByRole("link", { name: "Cases" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Cases" })).toBeFocused();
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("II")).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId(TID.stage("III"))).toBeFocused();
  });

  test("while the workspace loads, its skeleton has the real layout and appears only after 150 ms", async ({ page }) => {
    await page.goto("/cases");
    await expect(page.getByTestId("new-case-button")).toBeVisible();
    // Hold the workspace's code so the skeleton stays up long enough to measure.
    await page.route(/WorkspaceShell/, async (route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.fallback();
    });
    await page.goto("/case/case-0007");
    const skel = page.getByTestId("workspace-skeleton");
    await expect(skel).toBeAttached();
    await page.waitForTimeout(400);
    expect(Number(await skel.evaluate((el) => getComputedStyle(el).opacity))).toBe(1);
    const skelRow = (await skel.locator("> div").first().boundingBox())!;
    const skelCol = (await skel.locator("> div").nth(1).boundingBox())!;
    await expect(page.getByTestId(TID.stageRail)).toBeVisible({ timeout: 15_000 });
    const rail = (await page.getByTestId(TID.stageRail).boundingBox())!;
    const col = (await page.locator("section[aria-labelledby=step-title]").boundingBox())!;
    expect(Math.abs(rail.y - skelRow.y)).toBeLessThan(4);
    expect(Math.abs(col.x - skelCol.x)).toBeLessThan(2);
    expect(Math.abs(col.width - skelCol.width)).toBeLessThan(2);
  });
});
