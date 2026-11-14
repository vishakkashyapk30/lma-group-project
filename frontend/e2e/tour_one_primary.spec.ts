/**
 * One primary button at a time during a guided demo (docs/handoff/evaluator-demo.md): at each of the nine steps exactly one
 * visible maroon (primary) button is on screen, and it is the tour's Next; the step's own button and the top bar's New case are
 * secondary, and the Gate 2 button is not offered (Next approves). Outside a tour the step keeps its own primary button.
 * Runs on the sample case with the API unreachable (the demo backend answers).
 */
import { expect, test, type Page } from "@playwright/test";

const TOUR = "/case/case-0007?tour=00-sample-cheating-parity";
const STAGES = ["INTAKE", "DOSSIER", "GATE_1", "RIGHTS", "BRIEF", "SPAR", "HEARING_PREP", "GATE_2", "FILE"];
const MAROON = ["rgb(122, 22, 38)", "rgb(94, 16, 29)"]; // the primary fill and its hover fill (maroon-deep)

async function next(page: Page) {
  await page.getByTestId("tour-next").click();
  await page.waitForTimeout(350); // the step's slide settles
}

async function visiblePrimaries(page: Page): Promise<string[]> {
  return page.evaluate((maroon: string[]) => {
    const out: string[] = [];
    for (const el of Array.from(document.querySelectorAll<HTMLElement>("button, a, [role=button]"))) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const style = getComputedStyle(el);
      if (style.visibility === "hidden" || style.display === "none") continue;
      if (maroon.includes(style.backgroundColor)) out.push(el.getAttribute("data-testid") ?? (el.textContent ?? "").trim().slice(0, 40));
    }
    return out;
  }, MAROON);
}

for (const size of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test(`a tour shows one primary button at each of its nine steps, and it is Next (${size.width}x${size.height})`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.route("http://localhost:8000/**", (route) => route.abort());
    await page.setViewportSize(size);
    await page.goto(TOUR);
    const step = page.getByTestId("tour-step");
    for (const [i, stage] of STAGES.entries()) {
      await expect(step).toHaveAttribute("data-stage", stage);
      await page.waitForTimeout(350);
      expect(await visiblePrimaries(page), `primary buttons at ${stage}`).toEqual(["tour-next"]);
      if (stage === "GATE_2") {
        // The gate's own button is not offered; the tour's Next approves.
        await expect(page.getByTestId("approve-export-button")).toHaveCount(0);
        await expect(page.getByTestId("tour-gate-note")).toContainText("Next approves the draft");
        await expect(page.getByTestId("tour-next")).toHaveText(/Approve and continue/);
      }
      if (stage === "FILE") {
        // The export button is a secondary button now and still exports (allowed in a tour).
        await page.getByTestId("export-button").click();
        await expect(page.getByTestId("export-link").first()).toHaveAttribute("href", /\.docx$/);
        expect(await visiblePrimaries(page)).toEqual(["tour-next"]);
      }
      if (i < STAGES.length - 1) await next(page);
    }
  });
}

test("outside a tour the step keeps its own primary button", async ({ page }) => {
  await page.route("http://localhost:8000/**", (route) => route.abort());
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/case/case-0007");
  await page.getByTestId("stage-III").click();
  await page.waitForTimeout(350);
  expect(await visiblePrimaries(page)).toHaveLength(2); // the top bar's New case and the step's Continue
});
