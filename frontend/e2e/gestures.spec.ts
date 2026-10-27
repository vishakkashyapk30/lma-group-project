/**
 * Drag to close (DESIGN.md "Direct manipulation and springs"): the source panel, its phone sheet and the Details drawer follow
 * the pointer, resist with the rubber band when pulled the wrong way, spring back on a short drag, close past the threshold or
 * on a flick, and keep their keyboard and button paths (Escape, Close). Under reduced motion there is no rubber band and no
 * spring: the panel stops at its limit and closes or returns at once.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { seriousAxeViolations } from "./helpers";
import { MockBackend } from "./mockBackend";
import { TID } from "./testids";

const offset = (panel: Locator) => panel.evaluate((el) => Number((el as HTMLElement).dataset.dragOffset ?? 0));

async function openSource(page: Page): Promise<Locator> {
  await page.goto("/case/case-0007");
  await page.getByTestId(TID.stage("II")).click();
  await page.locator('[data-testid=dossier-field][data-field="fir"]').getByTestId(TID.dossierFieldSource).click();
  const panel = page.getByTestId(TID.sourcePanel);
  await expect(panel).toBeVisible();
  await page.waitForTimeout(300); // the sheet's entrance
  return panel;
}

/** Press on the handle, move by (dx, dy) in `steps`, optionally rest before releasing (so the release has no velocity). */
async function drag(page: Page, handle: Locator, dx: number, dy: number, o: { steps?: number; rest?: number; during?: () => Promise<void> } = {}) {
  const box = (await handle.boundingBox())!;
  const x = box.x + box.width * 0.4;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + dx, y + dy, { steps: o.steps ?? 12 });
  if (o.during) await o.during();
  if (o.rest) await page.waitForTimeout(o.rest);
  await page.mouse.up();
}

test.describe("drag to close, motion allowed", () => {
  test.use({ reducedMotion: "no-preference" });
  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: true, draft: "done" });
  });

  test.describe("side panel at 1440 px", () => {
    test.beforeEach(async ({ page }) => page.setViewportSize({ width: 1440, height: 900 }));

    test("a short drag springs back and the panel stays open", async ({ page }) => {
      const panel = await openSource(page);
      await drag(page, panel.getByTestId("panel-handle"), 60, 0, { rest: 150 });
      await expect(panel).toBeVisible();
      await expect.poll(() => offset(panel), { timeout: 2000 }).toBe(0);
    });

    test("pulled the wrong way it resists with the rubber band (never past 48 px) and springs back", async ({ page }) => {
      const panel = await openSource(page);
      let seen = 0;
      await drag(page, panel.getByTestId("panel-handle"), -400, 0, { steps: 20, during: async () => { seen = await offset(panel); } });
      expect(seen).toBeLessThan(-20);
      expect(seen).toBeGreaterThan(-48);
      await expect.poll(() => offset(panel), { timeout: 2000 }).toBe(0);
      await expect(panel).toBeVisible();
    });

    test("dragged past half its width it closes", async ({ page }) => {
      const panel = await openSource(page);
      const w = (await panel.boundingBox())!.width;
      await drag(page, panel.getByTestId("panel-handle"), w * 0.6, 0, { rest: 150 });
      await expect(panel).toHaveCount(0);
    });

    test("a quick flick closes it even when short", async ({ page }) => {
      const panel = await openSource(page);
      await drag(page, panel.getByTestId("panel-handle"), 90, 0, { steps: 3 });
      await expect(panel).toHaveCount(0);
    });

    test("a click on the handle is not a drag: Close and Escape still work", async ({ page }) => {
      let panel = await openSource(page);
      await panel.getByTestId("panel-handle").click({ position: { x: 40, y: 20 } });
      await expect(panel).toBeVisible();
      await panel.getByRole("button", { name: /close source/i }).focus();
      await page.keyboard.press("Escape");
      await expect(panel).toHaveCount(0);
      panel = await openSource(page);
      await panel.getByRole("button", { name: /close source/i }).click();
      await expect(panel).toHaveCount(0);
    });

    test("the Details drawer drags to the right to close", async ({ page }) => {
      await page.goto("/case/case-0007");
      await page.getByTestId(TID.detailsButton).click();
      const drawer = page.getByTestId(TID.traceDrawer);
      await expect(drawer).toBeVisible();
      await page.waitForTimeout(300);
      await drag(page, drawer.getByTestId("panel-handle"), 420, 0, { rest: 150 });
      await expect(drawer).toHaveCount(0);
      await expect(page.getByTestId(TID.detailsButton)).toHaveAttribute("aria-pressed", "false");
    });
  });

  test.describe("sheet at 390 px", () => {
    test.beforeEach(async ({ page }) => page.setViewportSize({ width: 390, height: 844 }));

    test("pulling the sheet down past a quarter of its height closes it", async ({ page }) => {
      const panel = await openSource(page);
      await expect(panel).toHaveAttribute("data-panel-mode", "sheet");
      await drag(page, panel.getByTestId("panel-handle"), 0, 300, { rest: 150 });
      await expect(panel).toHaveCount(0);
    });

    test("pulled up it resists (less than the pointer moved, never past 64 px) and settles back", async ({ page }) => {
      const panel = await openSource(page);
      let seen = 0;
      // The handle is at the top of the screen, so only a short pull upwards fits on it.
      await drag(page, panel.getByTestId("panel-handle"), 0, -20, { steps: 4, during: async () => { seen = await offset(panel); } });
      expect(seen).toBeLessThan(0);
      expect(seen).toBeGreaterThan(-20 + 6);
      await expect.poll(() => offset(panel), { timeout: 2000 }).toBe(0);
      await expect(panel).toBeVisible();
    });
  });
});

test.describe("drag to close with a finger (touch events through CDP)", () => {
  test.use({ hasTouch: true, isMobile: true, viewport: { width: 390, height: 844 }, reducedMotion: "no-preference" });

  test("a finger pulling the sheet down closes it; page scroll elsewhere stays native", async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: true, draft: "done" });
    const panel = await openSource(page);
    const box = (await panel.getByTestId("panel-handle").boundingBox())!;
    const cdp = await page.context().newCDPSession(page);
    const x = box.x + box.width / 2;
    let y = box.y + box.height / 2;
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
    for (let i = 0; i < 15; i++) {
      y += 20;
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y }] });
    }
    await page.waitForTimeout(150);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await expect(panel).toHaveCount(0);
    // Only the handle opts out of native panning.
    expect(await page.evaluate(() => getComputedStyle(document.querySelector("[data-testid=pane-main]")!).touchAction)).toBe("auto");
  });
});

test.describe("drag to close, prefers-reduced-motion: reduce", () => {
  test.use({ reducedMotion: "reduce" });
  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: true, draft: "done" });
    await page.setViewportSize({ width: 1440, height: 900 });
  });

  test("no rubber band: pulled the wrong way the panel stays at its limit", async ({ page }) => {
    const panel = await openSource(page);
    let seen = 1;
    await drag(page, panel.getByTestId("panel-handle"), -300, 0, { during: async () => { seen = await offset(panel); } });
    expect(seen).toBe(0);
  });

  test("past the threshold it closes at once; a short drag returns at once", async ({ page }) => {
    const panel = await openSource(page);
    await drag(page, panel.getByTestId("panel-handle"), 60, 0, { rest: 150 });
    expect(await offset(panel)).toBe(0);
    await drag(page, panel.getByTestId("panel-handle"), 400, 0, { rest: 150 });
    await expect(panel).toHaveCount(0, { timeout: 200 });
  });
});

test.describe("the gate that holds", () => {
  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: false, draft: "none" });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("II")).click();
  });

  const gate = (page: Page) => page.getByTestId(TID.confirmFactsButton);
  const holdOffset = (page: Page) => gate(page).evaluate((el) => Number((el as HTMLElement).dataset.holdOffset ?? 0));

  test("pressing it while items are open shows them instead of approving", async ({ page }) => {
    await expect(gate(page)).toBeDisabled(); // aria-disabled: unavailable to assistive technology, still pressable
    await expect(gate(page)).toContainText("(1 open)");
    await gate(page).click({ force: true });
    const list = page.getByTestId("gate-hold-list");
    await expect(list).toBeVisible();
    await expect(list.getByTestId("gate-hold-item")).toHaveCount(1);
    await expect(list.getByTestId("gate-hold-item").getByRole("button").first()).toBeFocused();
    await expect(page.getByTestId(TID.gateModal)).toHaveCount(0);
    await page.waitForTimeout(300);
    expect(await seriousAxeViolations(page)).toEqual([]);
  });

  test("dragged, it moves at most 12 px against the rubber band and springs back", async ({ page }) => {
    let seen = 0;
    await drag(page, gate(page), 240, 0, { steps: 16, during: async () => { seen = await holdOffset(page); } });
    expect(seen).toBeGreaterThan(4);
    expect(seen).toBeLessThan(12);
    await expect.poll(() => holdOffset(page), { timeout: 2000 }).toBe(0);
    await expect(page.getByTestId("gate-hold-list")).toBeVisible();
  });

  test("keyboard: Enter opens the list, Escape closes it and returns focus to the gate", async ({ page }) => {
    await gate(page).focus();
    await page.keyboard.press("Enter");
    const list = page.getByTestId("gate-hold-list");
    await expect(list).toBeVisible();
    await expect(list.getByRole("button", { name: "Mark as unknown" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(list).toHaveCount(0);
    await expect(gate(page)).toBeFocused();
  });

  test("resolving the open item from the list opens the gate, which then asks for confirmation", async ({ page }) => {
    await gate(page).click({ force: true });
    await page.getByTestId("gate-hold-list").getByRole("button", { name: "Mark as unknown" }).click();
    await expect(page.getByTestId("gate-hold-list")).toHaveCount(0);
    await expect(gate(page)).toBeEnabled();
    await expect(gate(page)).not.toContainText("open)");
    await gate(page).click();
    await expect(page.getByTestId(TID.gateModal)).toBeVisible();
  });
});

test.describe("the gate that holds, reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("it does not move, and the list still opens", async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: false, draft: "none" });
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("II")).click();
    const g = page.getByTestId(TID.confirmFactsButton);
    let seen = 1;
    await drag(page, g, 200, 0, { during: async () => { seen = await g.evaluate((el) => Number((el as HTMLElement).dataset.holdOffset ?? 0)); } });
    expect(seen).toBe(0);
    await expect(page.getByTestId("gate-hold-list")).toBeVisible();
  });
});

test.describe("rights timeline in the Check rights step", () => {
  test("it sits above the list, starts on the next date in the file, and the keyboard moves the hearing date", async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: true, draft: "done" });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("III")).click();
    const tl = page.getByTestId("workspace-rights-timeline");
    await expect(tl).toBeVisible();
    const before = await tl.getByTestId("hearing-date").innerText();
    await tl.getByTestId("hearing-handle").focus();
    await page.keyboard.press("Shift+ArrowRight");
    await expect(tl.getByTestId("hearing-date")).not.toHaveText(before);
    await expect(tl.getByTestId("word-default-bail")).not.toHaveText("Open.");
    // The list stays the full record.
    await expect(page.getByTestId(TID.rightsChip).first()).toBeVisible();
    const calendarFirst = await page.evaluate(() => {
      const cal = document.querySelector("[data-testid=rights-calendar]");
      const chip = document.querySelector("[data-testid=rights-chip]");
      return Boolean(cal && chip && cal.compareDocumentPosition(chip) & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    expect(calendarFirst).toBe(true);
    expect(await seriousAxeViolations(page)).toEqual([]);
  });
});
