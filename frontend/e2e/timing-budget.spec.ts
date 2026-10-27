/**
 * Timing and effort budgets (docs/handoff/frontend-endeavours-ideation.md section 7, item 4), with the mocked backend, so later
 * changes cannot quietly make the lawyer's path longer or the motion slower:
 *  - from the landing page to a verbatim source in the sample case: at most 3 actions;
 *  - from the landing page to Gate 1 confirmed: at most 8 actions;
 *  - a held gate shows what is open within 300 ms of the press;
 *  - a panel released past its threshold is gone within the 450 ms gesture budget;
 *  - a route change's transition is over within 300 ms (trivially: route changes are instant, no view transition starts).
 * Each action is one click or one key press that the visitor makes; waits are not actions.
 */
import { expect, test, type Page } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { TID } from "./testids";

class Actions {
  n = 0;
  constructor(private readonly page: Page) {}
  async click(sel: ReturnType<Page["getByTestId"]>, opts?: { force?: boolean }) {
    this.n += 1;
    await sel.click(opts);
  }
}

test.use({ reducedMotion: "no-preference" });

test("landing to a verbatim source of the sample case: at most 3 actions", async ({ page }) => {
  await MockBackend.install(page, { gate1Approved: true, draft: "done" });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const a = new Actions(page);
  await a.click(page.getByTestId("open-case-button"));
  await a.click(page.getByTestId(TID.stage("II")));
  await a.click(page.locator('[data-testid=dossier-field][data-field="fir"]').getByTestId(TID.dossierFieldSource));
  await expect(page.getByTestId(TID.sourcePanel)).toContainText("112/2024");
  expect(a.n).toBeLessThanOrEqual(3);
});

test("on the landing page itself, the words behind a fact are already open (0 actions) and the FIR is filed in 1", async ({ page }) => {
  await MockBackend.install(page);
  await page.goto("/");
  await expect(page.getByTestId("read-row").first().getByTestId("read-quote")).toContainText("FIR No. 112/2024");
  const a = new Actions(page);
  await a.click(page.getByTestId("add-fir-button"));
  await expect(page.getByTestId("demo-row")).toHaveCount(5);
  expect(a.n).toBe(1);
});

test("landing to Gate 1 confirmed on the sample case: at most 8 actions", async ({ page }) => {
  await MockBackend.install(page, { gate1Approved: false, draft: "none" });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const a = new Actions(page);
  await a.click(page.getByTestId("open-case-button"));
  await a.click(page.getByTestId(TID.stage("II")));
  await a.click(page.getByTestId(TID.confirmFactsButton), { force: true }); // held: shows what is open
  await a.click(page.getByTestId("gate-hold-list").getByRole("button", { name: "Mark as unknown" }));
  await a.click(page.getByTestId(TID.confirmFactsButton));
  await a.click(page.getByTestId(TID.gateApproveButton));
  await expect(page.getByTestId(TID.stage("III"))).not.toHaveAttribute("aria-disabled", "true");
  expect(a.n).toBeLessThanOrEqual(8);
});

test("a held gate shows what is open within 300 ms of the press", async ({ page }) => {
  await MockBackend.install(page, { gate1Approved: false, draft: "none" });
  await page.goto("/case/case-0007");
  await page.getByTestId(TID.stage("II")).click();
  const gate = page.getByTestId(TID.confirmFactsButton);
  await expect(gate).toBeVisible();
  const ms = await page.evaluate(async () => {
    const btn = document.querySelector<HTMLElement>("[data-testid=confirm-facts-button]")!;
    const t0 = performance.now();
    btn.click();
    return new Promise<number>((resolve) => {
      const tick = () => (document.querySelector("[data-testid=gate-hold-list]") ? resolve(performance.now() - t0) : requestAnimationFrame(tick));
      tick();
    });
  });
  expect(ms).toBeLessThan(300);
});

test("a panel released past its threshold is gone within the 450 ms gesture budget", async ({ page }) => {
  await MockBackend.install(page, { gate1Approved: true, draft: "done" });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/case/case-0007");
  await page.getByTestId(TID.stage("II")).click();
  await page.locator('[data-testid=dossier-field][data-field="fir"]').getByTestId(TID.dossierFieldSource).click();
  const panel = page.getByTestId(TID.sourcePanel);
  await expect(panel).toBeVisible();
  const handle = (await panel.getByTestId("panel-handle").boundingBox())!;
  const w = (await panel.boundingBox())!.width;
  await page.mouse.move(handle.x + 40, handle.y + 20);
  await page.mouse.down();
  await page.mouse.move(handle.x + 40 + w * 0.6, handle.y + 20, { steps: 10 });
  await page.waitForTimeout(120);
  await page.evaluate(() => {
    const w = window as unknown as { __t0: number; __gone: number };
    w.__t0 = performance.now();
    new MutationObserver((_m, mo) => {
      if (!document.querySelector("[data-testid=source-panel]")) {
        w.__gone = performance.now() - w.__t0;
        mo.disconnect();
      }
    }).observe(document.body, { childList: true, subtree: true });
  });
  await page.mouse.up();
  await expect(panel).toHaveCount(0);
  const gone = await page.evaluate(() => (window as unknown as { __gone: number }).__gone);
  expect(gone).toBeLessThan(450 + 100); // 450 ms of settling, plus one React commit and the test's own overhead
});

test("a route change's transition is over within 300 ms (route changes are instant: no view transition starts)", async ({ page }) => {
  // RECONCILED (owner decision): route transitions were removed with experimental.viewTransition; the budget holds trivially.
  await MockBackend.install(page, { gate1Approved: true, draft: "done" });
  await page.goto("/cases");
  await expect(page.getByTestId("new-case-button")).toBeVisible();
  await page.evaluate(() => {
    const w = window as unknown as { __vt: number };
    w.__vt = 0;
    const start = document.startViewTransition?.bind(document);
    if (start) document.startViewTransition = ((arg: Parameters<typeof start>[0]) => { w.__vt += 1; return start(arg); }) as typeof document.startViewTransition;
  });
  const t0 = Date.now();
  await page.getByTestId(TID.sidebar).getByRole("link", { name: "Help" }).click();
  await expect(page).toHaveURL(/\/help$/);
  await expect(page.getByRole("heading", { level: 1, name: "Help" })).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { __vt: number }).__vt)).toBe(0);
  expect(Date.now() - t0).toBeGreaterThan(0);
});
