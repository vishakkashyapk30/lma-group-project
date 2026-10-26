/**
 * Landing page (plan §13.3, §13.7; frontend/DESIGN.md "Landing"): the hero with its one primary action, the colour bands in
 * DESIGN.md's order, the footer, the hero product loop that plays once and rests, the reduced-motion path (final frame, no
 * animation, Replay hidden), no endless animation, and axe-core in both modes.
 *
 * RECONCILED: the earlier landing (seven scroll "scenes", a scene indicator of six dots, a static storyboard, a stats band and
 * "Watch the journey") was replaced by the colour-band page of docs/handoff/landing-colour-motion.md; DESIGN.md bans pinned
 * scenes, scroll-driven indicators and hero stat counters. What the old spec protected is kept: the hero and its action, the
 * order of the content, the footer's disclaimer and legal-aid number, the reduced-motion path, and zero serious axe findings.
 */
import { expect, test, type Page } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { seriousAxeViolations } from "./helpers";
import { TEXT, TID } from "./testids";

/** The band headings of DESIGN.md "Landing band order", top to bottom. */
const BANDS = ["How it works", "Open a fact and see the words behind it", "What you stay in control of", "Justice, social, economic and political."];

const hero = (page: Page) => page.locator("section[aria-labelledby='hero-heading']");
const heroLoop = (page: Page) => page.getByRole("img", { name: /Product preview/ }).or(page.locator("[aria-label^='Product preview']")).first();

async function runningAnimations(page: Page, scope?: string): Promise<number> {
  return page.evaluate((sel) => {
    const root = sel ? document.querySelector(sel) : document.documentElement;
    if (!root) return 0;
    return root.getAnimations({ subtree: true }).filter((a) => a.playState === "running").length;
  }, scope ?? null);
}

test.describe("landing, motion allowed", () => {
  test.use({ reducedMotion: "no-preference" });

  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page);
    await page.goto("/");
  });

  test("the hero states what the product does and offers one way in", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toContainText(TEXT.headline);
    const open = hero(page).getByTestId(TID.openCaseButton);
    await expect(open).toBeVisible();
    await expect(open).toHaveAttribute("href", "/cases");
    await expect(hero(page).getByRole("link", { name: TEXT.seeHow })).toBeVisible();
  });

  test("the bands follow DESIGN.md's order, with the footer last", async ({ page }) => {
    const order = await page.locator("h2").evaluateAll((els) => els.map((e) => (e.textContent ?? "").trim()));
    expect(order).toEqual(BANDS);
    const footerLast = await page.getByTestId(TID.siteFooter).evaluate((f) => {
      const headings = [...document.querySelectorAll("h2")];
      return headings.every((h) => h.compareDocumentPosition(f) & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    expect(footerLast).toBe(true);
  });

  test("footer shows the motto, the disclaimer and NALSA 15100", async ({ page }) => {
    const footer = page.getByTestId(TID.siteFooter);
    await footer.scrollIntoViewIfNeeded();
    await expect(footer).toContainText(TEXT.motto);
    await expect(footer).toContainText(TEXT.disclaimer);
    await expect(footer).toContainText(TEXT.nalsa);
    await expect(footer).toContainText(TEXT.nalsaNumber);
  });

  test("'See how it works' moves the visitor to the How it works band", async ({ page }) => {
    await hero(page).getByRole("link", { name: TEXT.seeHow }).click();
    await expect(page).toHaveURL(/#how$/);
    await expect(page.getByRole("heading", { name: "How it works" })).toBeInViewport();
  });

  test("the hero loop plays once and comes to rest on 'Approved for export'", async ({ page }) => {
    await expect(heroLoop(page)).toBeVisible();
    // One run of about 8.55 s, then nothing moves inside the loop (DESIGN.md: "plays once, then rests").
    await expect.poll(() => runningAnimations(page, "[aria-label^='Product preview']"), { timeout: 15_000, intervals: [500] }).toBe(0);
    await expect(heroLoop(page)).toContainText("Approved for export");
    await expect(page.getByRole("button", { name: "Replay" })).toBeVisible();
  });

  test("no animation runs forever (only short loops, no scroll-driven scenes)", async ({ page }) => {
    const infinite = await page.evaluate(() =>
      document.getAnimations().filter((a) => (a.effect?.getComputedTiming().iterations ?? 1) === Infinity).length,
    );
    expect(infinite).toBe(0);
  });

  test("axe-core: zero serious or critical violations once the hero loop is at rest", async ({ page }) => {
    // Mid-fade frames of the loop are not what a reader sees for long; audit the page at rest (as under reduced motion).
    await expect.poll(() => runningAnimations(page, "[aria-label^='Product preview']"), { timeout: 15_000, intervals: [500] }).toBe(0);
    expect(await seriousAxeViolations(page)).toEqual([]);
  });
});

test.describe("landing, prefers-reduced-motion: reduce", () => {
  test.use({ reducedMotion: "reduce" });

  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page);
    await page.goto("/");
  });

  test("shows the loop's final frame at once, with nothing running and Replay hidden", async ({ page }) => {
    await page.waitForTimeout(500); // let the 250 ms entrance settle, if any
    await expect(heroLoop(page)).toContainText("Approved for export");
    expect(await runningAnimations(page, "[aria-label^='Product preview']")).toBe(0);
    await expect(page.getByRole("button", { name: "Replay" })).toBeHidden();
  });

  test("keeps the hero text, the action and the footer (content is the same, motion is not)", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toContainText(TEXT.headline);
    await expect(hero(page).getByTestId(TID.openCaseButton)).toBeVisible();
    await expect(page.getByTestId(TID.siteFooter)).toContainText(TEXT.disclaimer);
    for (const band of BANDS) await expect(page.getByRole("heading", { name: band })).toBeAttached();
  });

  test("no running animation anywhere after the first paint", async ({ page }) => {
    await page.waitForTimeout(500);
    expect(await runningAnimations(page)).toBe(0);
  });

  test("axe-core: zero serious or critical violations", async ({ page }) => {
    expect(await seriousAxeViolations(page)).toEqual([]);
  });
});
