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
