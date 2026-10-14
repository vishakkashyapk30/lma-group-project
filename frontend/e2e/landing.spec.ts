/**
 * Landing page (plan §13.3, §13.7): scenes 0-6 in order, the scene indicator (a row of six dots, one lit), the footer, the
 * reduced-motion static storyboard with captions, and axe-core in both modes. See e2e/testids.ts for the DOM contract.
 */
import { expect, test, type Page } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { seriousAxeViolations } from "./helpers";
import { TEXT, TID } from "./testids";

const SCENES = [0, 1, 2, 3, 4, 5, 6];

async function goToScene(page: Page, n: number) {
  await page.getByTestId(TID.scene(n)).evaluate((el) => el.scrollIntoView({ block: "start" }));
}
async function litDots(page: Page): Promise<number[]> {
  return page.getByTestId(TID.sceneDot).evaluateAll((els) =>
    els.map((e, i) => (e.getAttribute("aria-current") === "true" ? i : -1)).filter((i) => i >= 0),
  );
}

test.describe("landing, motion allowed", () => {
  test.use({ reducedMotion: "no-preference" });

  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page);
    await page.goto("/");
  });

  test("renders scenes 0-6 in document order", async ({ page }) => {
    for (const n of SCENES) await expect(page.getByTestId(TID.scene(n))).toBeAttached();
    const order = await page.locator("[data-testid^='scene-']").evaluateAll((els) =>
      els.map((e) => e.getAttribute("data-testid") ?? "").filter((t) => /^scene-\d$/.test(t)),
    );
    expect(order).toEqual(SCENES.map((n) => `scene-${n}`));
  });

  test("scene 0 has the headline, both controls and the stats band", async ({ page }) => {
    const hero = page.getByTestId(TID.scene(0));
    await expect(hero).toContainText(TEXT.headlineA);
    await expect(hero).toContainText(TEXT.headlineB);
    await expect(hero.getByTestId(TID.openCaseButton)).toBeVisible();
    await expect(hero.getByRole("link", { name: TEXT.openCase }).or(hero.getByRole("button", { name: TEXT.openCase })).first()).toBeVisible();
    await expect(hero.getByTestId(TID.watchJourneyButton)).toBeVisible();
    await expect(hero.getByRole("button", { name: TEXT.watchJourney }).or(hero.getByRole("link", { name: TEXT.watchJourney })).first()).toBeVisible();
    await expect(hero.getByTestId(TID.statsBand)).toContainText(TEXT.stat);
  });

  test("scene 0 credits Krishna Iyer J. (1977)", async ({ page }) => {
    await expect(page.getByTestId(TID.scene(0))).toContainText(/Krishna Iyer/);
    await expect(page.getByTestId(TID.scene(0))).toContainText(/1977/);
  });

  test("scene 6 shows Article 21 and Article 39A", async ({ page }) => {
    await goToScene(page, 6);
    const s6 = page.getByTestId(TID.scene(6));
    await expect(s6).toContainText(TEXT.article21);
    await expect(s6).toContainText(TEXT.article39A);
  });

  test("footer shows the motto, the disclaimer and NALSA 15100", async ({ page }) => {
    const footer = page.getByTestId(TID.siteFooter);
    await footer.scrollIntoViewIfNeeded();
    await expect(footer).toContainText(TEXT.motto);
    await expect(footer).toContainText(TEXT.disclaimer);
    await expect(footer).toContainText(TEXT.nalsa);
    await expect(footer).toContainText(TEXT.nalsaNumber);
  });

  test("scene indicator is a row of six dots with exactly one lit while scrolling", async ({ page }) => {
    await expect(page.getByTestId(TID.sceneDot)).toHaveCount(6);
    for (const n of [1, 2, 3, 4, 5, 6]) {
      await goToScene(page, n);
      await expect.poll(() => litDots(page), { message: `scene ${n}` }).toEqual([n - 1]);
    }
  });

  test("'Watch the journey' moves the visitor to scene 1", async ({ page }) => {
    await page.getByTestId(TID.watchJourneyButton).click();
    await expect.poll(() => litDots(page)).toEqual([0]);
  });

  test("the static storyboard is not shown when motion is allowed, scenes are animated", async ({ page }) => {
    await expect(page.getByTestId(TID.staticStoryboard)).toHaveCount(0);
    for (const n of SCENES) await expect(page.getByTestId(TID.scene(n))).toHaveAttribute("data-motion", "animated");
  });

  test("axe-core: zero serious or critical violations", async ({ page }) => {
    expect(await seriousAxeViolations(page)).toEqual([]);
  });
});

test.describe("landing, prefers-reduced-motion: reduce", () => {
  test.use({ reducedMotion: "reduce" });

  test.beforeEach(async ({ page }) => {
    await MockBackend.install(page);
    await page.goto("/");
  });

  test("renders the static storyboard with a caption for each scene", async ({ page }) => {
    const board = page.getByTestId(TID.staticStoryboard);
    await expect(board).toBeVisible();
    for (const n of SCENES) {
      const scene = board.getByTestId(TID.scene(n));
      await expect(scene).toBeAttached();
      await expect(scene.getByTestId(TID.sceneCaption)).not.toBeEmpty();
    }
    await expect(board.getByTestId(TID.sceneCaption)).toHaveCount(SCENES.length);
  });

  test("keeps the hero text, controls and footer (content is the same, motion is not)", async ({ page }) => {
    const hero = page.getByTestId(TID.scene(0));
    await expect(hero).toContainText(TEXT.headlineA);
    await expect(hero.getByTestId(TID.openCaseButton)).toBeVisible();
    await expect(page.getByTestId(TID.siteFooter)).toContainText(TEXT.disclaimer);
  });

  test("every scene is static: data-motion=static and no running animation inside it", async ({ page }) => {
    await page.waitForTimeout(500); // let any entrance transition settle
    for (const n of SCENES) {
      const scene = page.getByTestId(TID.scene(n));
      await expect(scene).toHaveAttribute("data-motion", "static");
      const running = await scene.evaluate((el) =>
        el.getAnimations({ subtree: true }).filter((a) => a.playState === "running").length,
      );
      expect(running, `scene ${n} has running animations`).toBe(0);
    }
  });

  test("no infinite CSS animation anywhere on the page (working-loop cap is 0s)", async ({ page }) => {
    const infinite = await page.evaluate(() =>
      document.getAnimations().filter((a) => (a.effect?.getComputedTiming().iterations ?? 1) === Infinity).length,
    );
    expect(infinite).toBe(0);
  });

  test("axe-core: zero serious or critical violations", async ({ page }) => {
    expect(await seriousAxeViolations(page)).toEqual([]);
  });
});
