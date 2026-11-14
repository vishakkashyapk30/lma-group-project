/**
 * Guided demo for an evaluator (docs/handoff/evaluator-demo.md), on the built-in sample data: the API at localhost:8000 is
 * made unreachable, so the client answers from the demo backend (lib/mock/server.ts), which serves one tour over case-0007.
 * The evaluator starts the tour from the cases page and presses only Next: the workspace walks every step, Gate 2 is approved
 * through the approve route on the way, and the tour ends at Export with the export buttons open.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { expectStepInsideBar, seriousAxeViolations } from "./helpers";
import { TID } from "./testids";

const STAGES = ["INTAKE", "DOSSIER", "GATE_1", "RIGHTS", "BRIEF", "SPAR", "HEARING_PREP", "GATE_2", "FILE"];
// The stepper step on screen for each tour step (the gates live inside Review facts and Export; objections in Draft grounds).
const RAIL = { INTAKE: "I", DOSSIER: "II", GATE_1: "II", RIGHTS: "III", BRIEF: "IV", SPAR: "IV", HEARING_PREP: "VI", GATE_2: "VII", FILE: "VII" } as const;

test.beforeEach(async ({ page }) => {
  await page.route("http://localhost:8000/**", (route) => route.abort());
});

test("a guided demo walks the sample case from the papers to Export with Next only", async ({ page }) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/cases");
  const demos = page.getByTestId("guided-demos");
  await expect(demos.getByRole("heading", { name: "Guided demos" })).toBeVisible();
  const card = demos.getByTestId("guided-demo").first();
  await expect(card).toContainText("Offence and law:");
  await expect(card).toContainText("Parity and history:");
  expect(await seriousAxeViolations(page)).toEqual([]);
  await card.getByTestId("guided-demo-start").click();
  await expect(page).toHaveURL(/\/case\/case-0007\?tour=/);

  const bar = page.getByTestId("tour-bar");
  const step = bar.getByTestId("tour-step");
  for (const [i, stage] of STAGES.entries()) {
    await expect(step).toHaveAttribute("data-stage", stage);
    await expect(bar.getByTestId("tour-progress")).toHaveText(`Step ${i + 1} of ${STAGES.length}`);
    await expect(page.getByTestId(TID.stage(RAIL[stage as keyof typeof RAIL]))).toHaveAttribute("aria-current", "step");
    await expect(bar.getByTestId("tour-caption")).not.toBeEmpty();
    await page.waitForTimeout(350); // the step's slide settles before the layout is measured
    await expectStepInsideBar(page);
    if (stage === "DOSSIER") {
      await expect(bar.getByTestId("tour-field").first()).toBeVisible();
      expect(await seriousAxeViolations(page)).toEqual([]);
    }
    if (stage === "GATE_1") await expect(bar.getByTestId("tour-gate")).toHaveAttribute("data-approved", "true");
    if (stage === "GATE_2") {
      await expect(bar.getByTestId("tour-gate")).toHaveAttribute("data-approved", "false");
      await expect(page.getByTestId("export-button")).toHaveCount(0);
    }
    if (i < STAGES.length - 1) await bar.getByTestId("tour-next").click();
  }

  // Export, with the draft approved: the export buttons exist and the Word file comes out.
  await expect(bar.getByTestId("tour-next")).toHaveText(/Finish/);
  await page.getByTestId("export-button").click();
  await expect(page.getByTestId("export-link").first()).toHaveAttribute("href", /\.docx$/);
  expect(await seriousAxeViolations(page)).toEqual([]);

  // Back to the gate: it reads approved, and Next goes straight on.
  await bar.getByTestId("tour-back").click();
  await expect(bar.getByTestId("tour-gate")).toHaveAttribute("data-approved", "true");
  await bar.getByTestId("tour-next").click();
  await expect(step).toHaveAttribute("data-stage", "FILE");
});

test("the tour moves with the keyboard and Escape leaves it in the case", async ({ page }) => {
  await page.goto("/case/case-0007?tour=00-sample-cheating-parity");
  const bar = page.getByTestId("tour-bar");
  await expect(bar.getByTestId("tour-next")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(bar.getByTestId("tour-progress")).toHaveText("Step 2 of 9");
  await page.keyboard.press("ArrowRight");
  await expect(bar.getByTestId("tour-progress")).toHaveText("Step 3 of 9");
  await page.keyboard.press("ArrowLeft");
  await expect(bar.getByTestId("tour-progress")).toHaveText("Step 2 of 9");
  await page.keyboard.press("Escape");
  await expect(bar).toHaveCount(0);
  await expect(page).toHaveURL(/\/case\/case-0007$/);
  await expect(page.getByTestId(TID.stage("II"))).toHaveAttribute("aria-current", "step");
});

test("an unknown tour says so and offers a way out", async ({ page }) => {
  await page.goto("/case/case-0007?tour=no-such-tour");
  await expect(page.getByTestId("tour-missing")).toContainText("This guided demo was not found.");
  await page.getByTestId("tour-exit").click();
  await expect(page).toHaveURL(/\/case\/case-0007$/);
});

/** Walks the tour with Next only, up to (and including) the last step. `each` runs once the step has settled. */
async function walkToEnd(page: Page, each?: (stage: string) => Promise<void>) {
  const bar = page.getByTestId("tour-bar");
  for (const [i, stage] of STAGES.entries()) {
    await expect(bar.getByTestId("tour-step")).toHaveAttribute("data-stage", stage);
    await page.waitForTimeout(350);
    await each?.(stage);
    if (i < STAGES.length - 1) await bar.getByTestId("tour-next").click();
  }
}

async function box(l: Locator) {
  const b = await l.boundingBox();
  expect(b).toBeTruthy();
  return b!;
}

type Box = { x: number; y: number; width: number; height: number };
function overlap(a: Box, b: Box) {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

for (const size of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test(`the export toast never covers the export button or Next at ${size.width}x${size.height}`, async ({ page }) => {
    test.setTimeout(90_000);
    await page.route("http://localhost:8000/**", (route) => route.abort());
    await page.setViewportSize(size);
    await page.goto("/case/case-0007?tour=00-sample-cheating-parity");
    await walkToEnd(page);
    await page.getByTestId("export-button").click();
    const toast = page.getByRole("status").filter({ hasText: /Exported \d+ files?/ });
    await expect(toast).toBeVisible();
    await page.waitForTimeout(350); // the toast's fade settles
    const t = await box(toast);
    expect(t.x).toBeGreaterThanOrEqual(0);
    expect(t.x + t.width).toBeLessThanOrEqual(size.width);
    for (const id of ["export-button", "export-link"]) {
      const target = page.getByTestId(id).first();
      if (await target.count()) expect(overlap(t, await box(target)), `${id} is covered by the toast`).toBe(false);
    }
    expect(overlap(t, await box(page.getByTestId("tour-next"))), "Next is covered by the toast").toBe(false);
    expect(overlap(t, await box(page.getByTestId("tour-bar"))), "the tour bar is covered by the toast").toBe(false);
  });
}

for (const size of [{ width: 768, height: 1024 }, { width: 390, height: 844 }]) {
  test(`the tour fits a ${size.width}x${size.height} screen: no sideways scroll, buttons reachable, step inside the bar`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.route("http://localhost:8000/**", (route) => route.abort());
    await page.setViewportSize(size);
    await page.goto("/cases");
    const start = page.getByTestId("guided-demo-start").first();
    await expect(start).toBeVisible();
    expect((await box(start)).height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await start.click();
    const bar = page.getByTestId("tour-bar");
    await walkToEnd(page, async () => {
      await expectStepInsideBar(page);
      const b = await box(bar);
      expect(b.y + b.height).toBeLessThanOrEqual(size.height + 1);
      expect(b.height).toBeLessThanOrEqual(size.height * 0.45);
      for (const id of ["tour-exit", "tour-back", "tour-next"]) {
        const r = await box(bar.getByTestId(id));
        expect(r.x, id).toBeGreaterThanOrEqual(0);
        expect(r.x + r.width, id).toBeLessThanOrEqual(size.width);
        expect(r.y + r.height, id).toBeLessThanOrEqual(size.height);
        expect(r.height, `${id} touch target`).toBeGreaterThanOrEqual(44);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), "horizontal overflow").toBe(true);
    });
    // Fold the bar to its title and buttons, then open it again.
    const fold = bar.getByTestId("tour-fold");
    await expect(fold).toBeVisible();
    expect((await box(fold)).height).toBeGreaterThanOrEqual(44);
    const open = (await box(bar)).height;
    await fold.click();
    await expect(bar.getByTestId("tour-caption")).toBeHidden();
    expect((await box(bar)).height).toBeLessThan(open);
    await expect(bar.getByTestId("tour-next")).toBeVisible();
    await fold.click();
    await expect(bar.getByTestId("tour-caption")).toBeVisible();
  });
}
