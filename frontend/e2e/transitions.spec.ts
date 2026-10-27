/**
 * Route and step transitions (DESIGN.md "Route transitions"; docs/handoff/frontend-endeavours-ideation.md section 6): page
 * content crossfades in at most 250 ms while the sidebar and the top bar stay put; nothing animates under reduced motion; a
 * step change slides from the side it comes from; the tab indicator follows the chosen tab.
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

  test("navigating crossfades the content within 250 ms and the sidebar and top bar do not move", async ({ page }) => {
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
    await expect.poll(async () => (await transitions(page)).length).toBeGreaterThan(0);
    await expect.poll(async () => (await transitions(page))[0]!.anims.length).toBeGreaterThan(0);
    const [first] = await transitions(page);
    const longest = Math.max(...first!.anims.map((a) => a.ms));
    expect(longest).toBeLessThanOrEqual(250);
    expect(first!.anims.some((a) => a.pseudo.startsWith("::view-transition-new"))).toBe(true);
    // Nothing of the transition is left running shortly after.
    await page.waitForTimeout(300);
    const left = await page.evaluate(() => document.getAnimations().filter((a) => (a.effect as KeyframeEffect | null)?.pseudoElement?.startsWith("::view-transition") && a.playState === "running").length);
    expect(left).toBe(0);
  });

  test("clicks during a transition are not lost (the transition layer ignores the pointer)", async ({ page }) => {
    await page.goto("/cases");
    const pe = await page.evaluate(() => {
      for (const sheet of [...document.styleSheets]) {
        try {
          for (const r of [...sheet.cssRules]) if (r.cssText.startsWith("::view-transition {") && r.cssText.includes("pointer-events: none")) return true;
        } catch { /* cross-origin sheet */ }
      }
      return false;
    });
    expect(pe).toBe(true);
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
    for (const t of await transitions(page)) for (const a of t.anims) expect(a.ms, a.pseudo).toBe(0);
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("III")).click();
    const running = await page.evaluate(() => document.querySelector(".step-enter")?.getAnimations().filter((a) => a.playState === "running").length ?? 0);
    expect(running).toBe(0);
  });
});
