/**
 * Reduced motion (plan §13.4, §13.7): "With prefers-reduced-motion, every animation becomes a static icon with a text status."
 * Checks all six agent signatures on the workspace and the desk.
 */
import { expect, test, type Page } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { AGENTS, TID, type RightTab } from "./testids";

test.use({ reducedMotion: "reduce" });

const signature = (page: Page, agent: string) =>
  page.locator(`[data-testid=agent-signature][data-agent="${agent}"]`).first();

async function expectStatic(page: Page, agent: string) {
  const sig = signature(page, agent);
  await expect(sig, `${agent} signature`).toBeVisible();
  await expect(sig).toHaveAttribute("data-motion", "static");
  await expect(sig.getByTestId(TID.agentStatus)).toBeVisible();
  await expect(sig.getByTestId(TID.agentStatus)).not.toBeEmpty();
  const running = await sig.evaluate((el) => el.getAnimations({ subtree: true }).filter((a) => a.playState === "running").length);
  expect(running, `${agent} runs animations under reduced motion`).toBe(0);
}

test("every in-app agent animation is a static icon with a text status", async ({ page }) => {
  await MockBackend.install(page, { gate1Approved: true, draft: "done" });
  await page.goto("/case/case-0007");

  const where: [string, RightTab | null][] = [
    ["MUNSHI", null], // case-file pane
    ["SUTRADHAR", null], // chat header
    ["PESHKAR", "rights"],
    ["VAKEEL", "brief"],
    ["ABHIYOJAK", "spar"],
  ];
  for (const [agent, tab] of where) {
    if (tab) await page.getByTestId(TID.rightTab(tab)).click();
    await expectStatic(page, agent);
  }
  expect(AGENTS).toContain("PAIROKAR");
});

test("Pairokar's cause-list bars are static with a text status on /desk", async ({ page }) => {
  await MockBackend.install(page);
  await page.goto("/desk");
  await expectStatic(page, "PAIROKAR");
});

test("no infinite animation runs anywhere in the workspace", async ({ page }) => {
  await MockBackend.install(page, { gate1Approved: true, draft: "done" });
  await page.goto("/case/case-0007");
  await page.waitForTimeout(500);
  const infinite = await page.evaluate(() =>
    document.getAnimations().filter((a) => (a.effect?.getComputedTiming().iterations ?? 1) === Infinity).length,
  );
  expect(infinite).toBe(0);
});
