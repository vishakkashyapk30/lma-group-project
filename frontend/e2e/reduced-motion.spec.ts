/**
 * Reduced motion (plan §13.4, §13.7): "With prefers-reduced-motion, every animation becomes a static icon with a text status."
 *
 * RECONCILED (docs/handoff/workspace-redesign.md, commit "Replace the large agent animations with quiet status indicators"): the
 * six always-on agent animations became one quiet indicator (agent-signature: a small glyph that breathes, and a text status) that
 * appears only while an agent works: the progress line of the current step (Munshi reading an upload) and Pairokar on the desk. The
 * rule is unchanged: under reduced motion the glyph does not move and the status is real text. Slow mock responses keep the work
 * running long enough to look at it.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { tinyPdf } from "./helpers";
import { TID } from "./testids";

test.use({ reducedMotion: "reduce" });

async function expectStatic(sig: Locator, label: string) {
  await expect(sig, `${label} indicator`).toBeVisible();
  await expect(sig.getByTestId(TID.agentStatus)).not.toBeEmpty();
  const running = await sig.evaluate((el) => el.getAnimations({ subtree: true }).filter((a) => a.playState === "running").length);
  expect(running, `${label} runs animations under reduced motion`).toBe(0);
}

/** Hold matching requests for `ms` before the mock answers them. */
async function slow(page: Page, pattern: string, ms: number) {
  await page.route(pattern, async (route) => {
    await new Promise((r) => setTimeout(r, ms));
    await route.fallback();
  });
}

test("Munshi's progress line while reading an upload is a static icon with a text status", async ({ page }) => {
  await MockBackend.install(page, { caseId: "case-0042", fresh: true, gate1Approved: false, draft: "none" });
  await slow(page, "**/api/cases/*/upload", 4000);
  await page.goto("/case/case-0042");
  await page.getByTestId(TID.uploadInput).setInputFiles({ name: "bundle.pdf", mimeType: "application/pdf", buffer: tinyPdf(2) });
  const sig = page.getByTestId(TID.paneMain).locator('[data-testid=agent-signature][data-agent="MUNSHI"]').first();
  await expectStatic(sig, "MUNSHI");
});

test("Pairokar's indicator on /desk is static with a text status, idle and while scoring", async ({ page }) => {
  await MockBackend.install(page);
  await slow(page, "**/api/desk/upload", 4000);
  await page.goto("/desk");
  const sig = page.locator('[data-testid=agent-signature][data-agent="PAIROKAR"]').first();
  await expectStatic(sig, "PAIROKAR idle");
  await page.getByTestId(TID.deskUploadInput).setInputFiles({
    name: "legal_aid_batch.zip", mimeType: "application/zip", buffer: Buffer.from("PK\u0005\u0006" + "\0".repeat(18), "latin1"),
  });
  await expect(sig.getByTestId(TID.agentStatus)).toContainText(/scoring/i);
  await expectStatic(sig, "PAIROKAR scoring");
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

/**
 * Added with the hands-on landing and the drag physics (frontend-endeavours): under reduced motion nothing keeps running after
 * the visitor uses a demo, a panel or a gate, and every result is still reached.
 */
// Animations the reduced-motion CSS collapses to 0.01 ms may be caught mid-tick; they move nothing, so they do not count.
const running = (page: Page) =>
  page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running" && Number(a.effect?.getComputedTiming().duration ?? 0) > 1).length);

test("landing demos under reduced motion: every result is reached and nothing keeps moving", async ({ page }) => {
  await MockBackend.install(page);
  await page.goto("/");
  await page.getByTestId("add-fir-button").click();
  await expect(page.getByTestId("demo-row")).toHaveCount(5);
  await page.getByTestId("read-row").nth(1).getByRole("button").click();
  await expect(page.getByTestId("read-row").nth(1)).toHaveAttribute("data-open", "true");
  await page.getByTestId("hearing-handle").focus();
  await page.keyboard.press("End");
  await expect(page.getByTestId("word-undertrial")).toHaveText("Check.");
  await page.getByTestId("gate1-demo-button").click({ force: true });
  await expect(page.getByTestId("gate1-list")).toBeVisible();
  await page.getByTestId("draft-cite").nth(1).click();
  await expect(page.getByTestId("draft-paragraph")).toContainText("SC-2014-0463");
  await page.waitForTimeout(150);
  expect(await running(page)).toBe(0);
});

test("panels and gates under reduced motion: nothing keeps moving after opening, holding or closing", async ({ page }) => {
  await MockBackend.install(page, { gate1Approved: false, draft: "none" });
  await page.goto("/case/case-0007");
  await page.getByTestId(TID.stage("II")).click();
  await page.getByTestId(TID.confirmFactsButton).click({ force: true });
  await expect(page.getByTestId("gate-hold-list")).toBeVisible();
  await page.locator('[data-testid=dossier-field][data-field="fir"]').getByTestId(TID.dossierFieldSource).click();
  await expect(page.getByTestId(TID.sourcePanel)).toBeVisible();
  await page.waitForTimeout(150);
  expect(await running(page)).toBe(0);
  await page.getByTestId(TID.sourcePanel).getByRole("button", { name: /close source/i }).click();
  await expect(page.getByTestId(TID.sourcePanel)).toHaveCount(0);
  expect(await running(page)).toBe(0);
});
