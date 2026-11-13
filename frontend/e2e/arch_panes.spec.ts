/**
 * The three panes of the chosen architecture (docs/handoff/team-todo-2026-11-02.md): dossier gaps by factor, objections grouped
 * under the ground they answer, and the brief read sentence by sentence. Backend mocked, as in the other specs.
 */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { expectNoUnmatched, seriousAxeViolations } from "./helpers";
import { TID } from "./testids";

test("Review facts: Gaps by factor lists every factor and leaves on the next tab", async ({ page }) => {
  const mock = await MockBackend.install(page, { gate1Approved: false, draft: "none", gate2Approved: false });
  await page.goto("/case/case-0007");
  await page.getByTestId("right-tab-gaps").click();
  const gaps = page.getByTestId("factor-gaps");
  await expect(gaps).toBeVisible();
  expect(await gaps.getByTestId("factor-gap").count()).toBeGreaterThan(0);
  expect(await seriousAxeViolations(page)).toEqual([]);
  await page.getByTestId("right-tab-dates").click();
  await expect(gaps).toBeHidden();
  await expectNoUnmatched(mock);
});

test("Draft grounds: By sentence shows a kind per sentence, and the switch is two pressed buttons", async ({ page }) => {
  const mock = await MockBackend.install(page, { gate1Approved: true, draft: "done", gate2Approved: false });
  await page.goto("/case/case-0007");
  await page.getByTestId(TID.stage("IV")).click();
  const draft = page.getByTestId("brief-view-draft");
  const sentences = page.getByTestId("brief-view-sentences");
  await expect(draft).toHaveAttribute("aria-pressed", "true");
  await sentences.click();
  await expect(sentences).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("sentence-summary")).toBeVisible();
  const kinds = await page.getByTestId("brief-sentence").evaluateAll((els) => els.map((e) => e.getAttribute("data-kind")));
  expect(kinds.length).toBeGreaterThan(0);
  expect(kinds.every((k) => k)).toBe(true);
  expect(await seriousAxeViolations(page)).toEqual([]);
  await draft.click();
  await expect(page.getByTestId("brief-sentence")).toHaveCount(0);
  await expectNoUnmatched(mock);
});

test("Likely objections are grouped by ground, and a ground links to its objections", async ({ page }) => {
  const mock = await MockBackend.install(page, { gate1Approved: true, draft: "done", gate2Approved: false });
  await page.goto("/case/case-0007");
  await page.getByTestId(TID.stage("IV")).click();
  const groups = page.getByTestId("spar-group");
  expect(await groups.count()).toBeGreaterThan(0);
  const link = page.getByTestId("ground-objections-link").first();
  await expect(link).toContainText("likely objection");
  await expectNoUnmatched(mock);
});
