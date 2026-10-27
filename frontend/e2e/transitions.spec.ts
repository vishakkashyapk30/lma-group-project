/**
 * Route and step transitions (DESIGN.md "Route transitions"; docs/handoff/frontend-endeavours-ideation.md section 6): a step
 * change slides from the side it comes from; the tab indicator follows the chosen tab; the case title carries over.
 *
 * RECONCILED (owner decision, 2026-10-27): route changes are instant. The crossfade needed Next's experimental.viewTransition
 * (the experimental React channel and about 12 kB on every route), so the flag was removed. What the crossfade tests protected
 * is kept: the sidebar and the top bar do not move during a navigation, nothing animates under reduced motion; and the tests
 * now also assert that no view transition is started at all.
 */
import { expect, test, type Page } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { TID } from "./testids";

/** Record every view transition: its pseudo-element animations and their durations. */
async function recordTransitions(page: Page) {
  await page.evaluate(() => {
    const w = window as unknown as { __vt: { anims: { pseudo: string; ms: number }[] }[] };
    w.__vt = [];
    const start = document.startViewTransition?.bind(document);
    if (!start) return;
    document.startViewTransition = ((arg: Parameters<typeof start>[0]) => {
      const t = start(arg);
      const entry = { anims: [] as { pseudo: string; ms: number }[] };
      w.__vt.push(entry);
      void t.ready.then(() => {
        for (const a of document.getAnimations()) {
          const eff = a.effect as KeyframeEffect | null;
          if (eff?.pseudoElement?.startsWith("::view-transition")) entry.anims.push({ pseudo: eff.pseudoElement, ms: Number(eff.getComputedTiming().endTime ?? 0) });
        }
      });
      return t;
    }) as typeof document.startViewTransition;
  });
}
const transitions = (page: Page) => page.evaluate(() => (window as unknown as { __vt: { anims: { pseudo: string; ms: number }[] }[] }).__vt);

test.describe("route transitions, motion allowed", () => {
  test.use({ reducedMotion: "no-preference" });
  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: true, draft: "done" });
    await page.setViewportSize({ width: 1440, height: 900 });
  });

  test("navigating swaps the page at once: no view transition, and the sidebar and top bar do not move", async ({ page }) => {
    await page.goto("/cases");
    await expect(page.getByTestId("new-case-button")).toBeVisible();
    await recordTransitions(page);
    const sidebar = page.getByTestId(TID.sidebar);
    const topbar = page.locator("header").first();
    const s0 = await sidebar.boundingBox();
    const t0 = await topbar.boundingBox();
    await sidebar.getByRole("link", { name: "Batch desk" }).click();
    for (let i = 0; i < 6; i++) {
      expect(await sidebar.boundingBox()).toEqual(s0);
      expect(await topbar.boundingBox()).toEqual(t0);
      await page.waitForTimeout(40);
    }
    await expect(page).toHaveURL(/\/desk$/);
    await page.waitForTimeout(300);
    expect(await transitions(page)).toEqual([]);
  });

  test("a step change slides from the side it comes from", async ({ page }) => {
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("II")).click();
    await page.getByTestId(TID.stage("III")).click();
    await expect(page.locator("[data-step-enter]")).toHaveAttribute("data-step-enter", "forward");
    await page.getByTestId(TID.stage("II")).click();
    await expect(page.locator("[data-step-enter]")).toHaveAttribute("data-step-enter", "back");
    // The stepper does not move while the step slides.
    const rail = await page.getByTestId(TID.stageRail).boundingBox();
    await page.getByTestId(TID.stage("IV")).click();
    expect(await page.getByTestId(TID.stageRail).boundingBox()).toEqual(rail);
  });

  test("the case title carries over: from the card it moves into the top bar's breadcrumb", async ({ page }) => {
    await page.goto("/cases");
    const link = page.locator("article h3 a").first();
    await expect(link).toBeVisible();
    const href = (await link.getAttribute("href"))!;
    const id = href.split("/").pop()!;
    const title = (await link.innerText()).trim();
    await page.evaluate(() => {
      const w = window as unknown as { __morph: string[] };
      w.__morph = [];
      new MutationObserver(() => {
        const el = document.querySelector<HTMLElement>("[data-morph][data-morphing]");
        if (el) w.__morph.push(getComputedStyle(el).transform);
      }).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["data-morphing"] });
    });
    await link.click();
    await expect(page).toHaveURL(new RegExp(`${href}$`));
    const crumb = page.locator(`nav[aria-label=Breadcrumb] [data-morph='case-title-${id}']`);
    await expect(crumb).toContainText(title);
    const seen = await page.evaluate(() => (window as unknown as { __morph: string[] }).__morph);
    expect(seen.length).toBeGreaterThan(0);
    const ty = Number(/matrix\(([^)]+)\)/.exec(seen[0]!)?.[1]?.split(",")[5] ?? 0);
    expect(ty).toBeGreaterThan(100); // it starts down where the card was
    await page.waitForTimeout(400);
    expect(await crumb.evaluate((el) => el.getAnimations().length)).toBe(0);
  });

  test("the tab indicator sits under the chosen tab", async ({ page }) => {
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("II")).click();
    const dates = page.getByTestId(TID.rightTab("dates"));
    await dates.click();
    await page.waitForTimeout(350);
    const bar = await page.getByTestId("tab-indicator").first().boundingBox();
    const tab = await dates.boundingBox();
    expect(Math.abs(bar!.x - tab!.x)).toBeLessThan(1.5);
    expect(Math.abs(bar!.width - tab!.width)).toBeLessThan(1.5);
  });
});

test.describe("route transitions, prefers-reduced-motion: reduce", () => {
  test.use({ reducedMotion: "reduce" });

  test("navigation and step changes do not animate", async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: true, draft: "done" });
    await page.goto("/cases");
    await expect(page.getByTestId("new-case-button")).toBeVisible();
    await recordTransitions(page);
    await page.getByTestId(TID.sidebar).getByRole("link", { name: "Precedent library" }).click();
    await expect(page).toHaveURL(/\/library$/);
    await page.waitForTimeout(200);
    expect(await transitions(page)).toEqual([]);
    await page.goto("/cases");
    await page.locator("article a").first().click();
    await expect(page).toHaveURL(/\/case\//);
    expect(await page.locator("[data-morphing]").count()).toBe(0);
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("III")).click();
    const running = await page.evaluate(() => document.querySelector(".step-enter")?.getAnimations().filter((a) => a.playState === "running").length ?? 0);
    expect(running).toBe(0);
  });
});
