/**
 * The landing page's hands-on demos (docs/handoff/frontend-endeavours-ideation.md, Direction B "Walk the file"), all on the
 * sample case-0007 and with no backend: each one completes by pointer and by keyboard alone, and under reduced motion.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { seriousAxeViolations } from "./helpers";

/** Press Tab until `target` has focus (at most `max` presses); fails if it never does. */
export async function tabTo(page: Page, target: Locator, max = 80): Promise<number> {
  for (let i = 1; i <= max; i++) {
    await page.keyboard.press("Tab");
    if (await target.evaluate((el) => el === document.activeElement)) return i;
  }
  throw new Error("never reached by Tab");
}

async function dragTo(page: Page, from: Locator, to: Locator, steps = 14) {
  const a = (await from.boundingBox())!;
  const b = (await to.boundingBox())!;
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width / 2, b.y + Math.min(b.height / 2, 60), { steps });
  await page.waitForTimeout(120);
  await page.mouse.up();
}

for (const motion of ["no-preference", "reduce"] as const) {
  test.describe(`hero: put the FIR on the file (${motion})`, () => {
    test.use({ reducedMotion: motion });
    test.beforeEach(async ({ page }) => {
      await MockBackend.install(page);
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto("/");
    });

    test("dragging the FIR onto the dossier files it and shows what it gives and does not", async ({ page }) => {
      const demo = page.getByTestId("file-demo");
      await dragTo(page, demo.getByTestId("fir-card"), demo.getByTestId("dossier-drop"));
      await expect(demo).toHaveAttribute("data-added", "true");
      await expect(demo.getByTestId("demo-row")).toHaveCount(5);
      await expect(demo.locator("[data-testid=demo-row][data-status=UNSUPPORTED]")).toHaveCount(2);
      await expect(demo.getByTestId("demo-row").first()).toContainText("FIR p.1");
      await expect(demo.locator("[data-testid=demo-page][data-status=UNREADABLE]")).toContainText("unreadable");
    });

    test("dropped anywhere else, the card goes back and nothing is filed", async ({ page }) => {
      const demo = page.getByTestId("file-demo");
      const card = demo.getByTestId("fir-card");
      const home = (await card.boundingBox())!;
      await page.mouse.move(home.x + 20, home.y + 20);
      await page.mouse.down();
      await page.mouse.move(home.x + 20, home.y + 140, { steps: 8 });
      await page.waitForTimeout(120);
      await page.mouse.up();
      await expect.poll(async () => Math.round((await card.boundingBox())!.y), { timeout: 2000 }).toBe(Math.round(home.y));
      await expect(demo).not.toHaveAttribute("data-added", "true");
    });

    test("keyboard alone: Tab to 'Add this FIR' and press Enter", async ({ page }) => {
      const demo = page.getByTestId("file-demo");
      await tabTo(page, demo.getByTestId("add-fir-button"));
      await page.keyboard.press("Enter");
      await expect(demo.getByTestId("demo-row")).toHaveCount(5);
      await expect(page.getByRole("status").filter({ hasText: "FIR read" })).toBeAttached();
      await tabTo(page, demo.getByRole("button", { name: "Put the FIR back" }), 10);
      await page.keyboard.press("Enter");
      await expect(demo.getByTestId("fir-card")).toBeVisible();
    });
  });
}

test("hero demo at 390 px: a finger can still file the FIR with the button, and axe finds nothing serious", async ({ page }) => {
  await MockBackend.install(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const demo = page.getByTestId("file-demo");
  await demo.getByTestId("add-fir-button").click();
  await expect(demo.getByTestId("demo-row")).toHaveCount(5);
  const scrollsSideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(scrollsSideways).toBe(false);
  await page.waitForTimeout(500);
  expect(await seriousAxeViolations(page)).toEqual([]);
});

for (const motion of ["no-preference", "reduce"] as const) {
  test.describe(`read: open a fact and see the words behind it (${motion})`, () => {
    test.use({ reducedMotion: motion });
    test.beforeEach(async ({ page }) => {
      await MockBackend.install(page);
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto("/#read");
      await page.waitForTimeout(500);
    });

    test("the first fact is open on its Hindi sentence and English line, the value marked in both", async ({ page }) => {
      const first = page.getByTestId("read-row").first();
      await expect(first).toHaveAttribute("data-open", "true");
      const quote = first.getByTestId("read-quote");
      await expect(quote.locator("[lang=hi]")).toContainText("प्रथम सूचना रिपोर्ट");
      await expect(quote).toContainText("FIR No. 112/2024 dated 14.08.2024");
      await expect(quote.locator("mark")).toHaveCount(2);
    });

    test("pulling a row down with the pointer opens it; a short pull does not", async ({ page }) => {
      const row = page.getByTestId("read-row").nth(1);
      const head = row.getByRole("button");
      const b = (await head.boundingBox())!;
      await page.mouse.move(b.x + 100, b.y + b.height / 2);
      await page.mouse.down();
      await page.mouse.move(b.x + 100, b.y + b.height / 2 + 20, { steps: 4 });
      await page.waitForTimeout(120);
      await page.mouse.up();
      await expect(row).not.toHaveAttribute("data-open", "true");
      await page.mouse.move(b.x + 100, b.y + b.height / 2);
      await page.mouse.down();
      await page.mouse.move(b.x + 100, b.y + b.height / 2 + 120, { steps: 10 });
      await page.waitForTimeout(120);
      await page.mouse.up();
      await expect(row).toHaveAttribute("data-open", "true");
      await expect(row.getByTestId("read-quote")).toContainText("10.08.2024");
      await expect.poll(() => head.evaluate((el) => (el as HTMLElement).style.transform), { timeout: 2000 }).toBe("");
    });

    test("keyboard alone: Tab to a fact, Enter opens and closes it", async ({ page }) => {
      const row = page.getByTestId("read-row").nth(2);
      const head = row.getByRole("button");
      await tabTo(page, head);
      await page.keyboard.press("Enter");
      await expect(head).toHaveAttribute("aria-expanded", "true");
      await expect(row.getByTestId("read-quote")).toContainText("318(4), 316(2)");
      await page.keyboard.press("Space");
      await expect(head).toHaveAttribute("aria-expanded", "false");
    });
  });
}

for (const motion of ["no-preference", "reduce"] as const) {
  test.describe(`check: rights against the dates (${motion})`, () => {
    test.use({ reducedMotion: motion });
    test.beforeEach(async ({ page }) => {
      await MockBackend.install(page);
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto("/#check");
      await page.waitForTimeout(500); // the band's 250 ms reveal moves it 8 px
    });

    test("starts on the next hearing: default bail closed by the charge sheet, the undertrial limit not yet reached", async ({ page }) => {
      const demo = page.getByTestId("check-demo");
      await expect(demo.getByTestId("hearing-date")).toHaveText("18.02.2025");
      await expect(demo.getByTestId("custody-days")).toHaveText("182");
      await expect(demo.getByTestId("word-default-bail")).toHaveText("Closed.");
      await expect(demo.getByTestId("word-undertrial")).toHaveText("Not yet.");
      await expect(demo).not.toContainText(/eligible|will be granted|likely/i);
    });

    test("keyboard alone: the hearing-date slider moves by a day, by 30 days, and to the end", async ({ page }) => {
      const demo = page.getByTestId("check-demo");
      const handle = demo.getByTestId("hearing-handle");
      await tabTo(page, handle);
      await page.keyboard.press("ArrowRight");
      await expect(demo.getByTestId("hearing-date")).toHaveText("19.02.2025");
      await page.keyboard.press("Shift+ArrowRight");
      await expect(demo.getByTestId("hearing-date")).toHaveText("21.03.2025");
      await page.keyboard.press("End");
      await expect(demo.getByTestId("word-undertrial")).toHaveText("Check.");
      await expect(handle).toHaveAttribute("aria-valuetext", /days in custody/);
    });

    test("the threshold button moves the date to one-third, where the limit reads Check because antecedents are unknown", async ({ page }) => {
      const demo = page.getByTestId("check-demo");
      await demo.getByRole("button", { name: /One-third of the maximum/ }).click();
      await expect(demo.getByTestId("hearing-date")).toHaveText("20.12.2026", { timeout: 3000 });
      await expect(demo.getByTestId("custody-days")).toHaveText("852");
      await expect(demo.getByTestId("word-undertrial")).toHaveText("Check.");
      await expect(demo.getByTestId("lane-undertrial")).toContainText("only to a first-time offender");
    });

    test("pointer: dragging the handle moves the date; past the end it resists and settles on the last day", async ({ page }) => {
      const demo = page.getByTestId("check-demo");
      const handle = demo.getByTestId("hearing-handle");
      const h = (await handle.boundingBox())!;
      await page.mouse.move(h.x + h.width / 2, h.y + h.height / 2);
      await page.mouse.down();
      await page.mouse.move(h.x + h.width / 2 + 200, h.y + h.height / 2, { steps: 10 });
      await page.waitForTimeout(150);
      await page.mouse.up();
      const mid = await demo.getByTestId("hearing-date").innerText();
      expect(mid).not.toBe("18.02.2025");
      const box = (await handle.boundingBox())!;
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width / 2 + 1400, box.y + box.height / 2, { steps: 20 });
      const track = (await demo.locator("[data-testid=hearing-handle]").locator("xpath=../..").boundingBox())!;
      const pulled = (await handle.boundingBox())!;
      if (motion === "reduce") {
        expect(Math.round(pulled.x + pulled.width / 2)).toBe(Math.round(track.x + track.width)); // no rubber band: it stops at the end
      } else {
        expect(pulled.x + pulled.width / 2).toBeGreaterThan(track.x + track.width);
        expect(pulled.x + pulled.width / 2).toBeLessThan(track.x + track.width + 32);
      }
      await page.waitForTimeout(150);
      await page.mouse.up();
      await expect(demo.getByTestId("word-undertrial")).toHaveText("Check.");
      await expect.poll(async () => { const b = (await handle.boundingBox())!; return Math.round(b.x + b.width / 2 - (track.x + track.width)); }, { timeout: 2000 }).toBeLessThanOrEqual(1);
    });
  });
}

for (const motion of ["no-preference", "reduce"] as const) {
  test.describe(`hold: the gates (${motion})`, () => {
    test.use({ reducedMotion: motion });
    test.beforeEach(async ({ page }) => {
      await MockBackend.install(page);
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto("/#hold");
      await page.waitForTimeout(500);
    });

    test("pointer: pulling the held gate moves it at most 12 px (none under reduced motion) and lists what is open; resolve, confirm, then export holds", async ({ page }) => {
      const demo = page.getByTestId("hold-demo");
      const gate = demo.getByTestId("gate1-demo-button");
      await expect(gate).toContainText("(1 open)");
      const b = (await gate.boundingBox())!;
      await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
      await page.mouse.down();
      await page.mouse.move(b.x + b.width / 2 + 200, b.y + b.height / 2, { steps: 12 });
      const off = await gate.evaluate((el) => Number((el as HTMLElement).dataset.holdOffset ?? 0));
      if (motion === "reduce") expect(off).toBe(0);
      else { expect(off).toBeGreaterThan(3); expect(off).toBeLessThan(12); }
      await page.mouse.up();
      const list = demo.getByTestId("gate1-list");
      await expect(list).toBeVisible();
      await expect(list.getByTestId("gate1-item")).toHaveCount(1);
      await expect(list).toContainText("Antecedents");
      await list.getByRole("button", { name: "Mark as unknown" }).click();
      await expect(gate).toBeEnabled();
      await gate.click();
      await expect(demo.getByTestId("gate1-confirm")).toContainText("What this locks");
      await demo.getByTestId("gate1-confirm-button").click();
      await expect(demo.getByTestId("gate1-confirmed")).toBeVisible();
      const gate2 = demo.getByTestId("gate2-demo-button");
      await expect(gate2).toBeDisabled();
      await gate2.click({ force: true });
      await expect(demo.getByTestId("gate2-item")).toHaveCount(4);
      await expect(page.getByRole("button", { name: /export as/i })).toHaveCount(0);
    });

    test("keyboard alone: Enter on the held gate opens the list with focus on its action, and the whole flow completes", async ({ page }) => {
      const demo = page.getByTestId("hold-demo");
      await tabTo(page, demo.getByTestId("gate1-demo-button"));
      await page.keyboard.press("Enter");
      await expect(demo.getByTestId("gate1-list").getByRole("button", { name: "Mark as unknown" })).toBeFocused();
      await page.keyboard.press("Enter");
      await tabTo(page, demo.getByTestId("gate1-demo-button"), 10);
      await page.keyboard.press("Enter");
      await expect(demo.getByTestId("gate1-confirm-button")).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(demo.getByTestId("gate1-confirmed")).toBeVisible();
      await tabTo(page, demo.getByTestId("gate2-demo-button"), 10);
      await page.keyboard.press("Enter");
      await expect(demo.getByTestId("gate2-list").getByRole("link", { name: /sample case/ })).toBeFocused();
    });
  });
}
