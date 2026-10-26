/**
 * Plan §13.6 flow 3: the brief and the spar. Counsel clicks "Draft bail brief"; Sutradhar plans (the trace is visible, driven by
 * SSE events), Vakeel drafts, Abhiyojak spars; counsel resolves NEEDS_REVIEW / UNANSWERED items, reads the hearing-prep card,
 * approves Gate 2 and exports the DOCX. SSE is mocked (text/event-stream).
 *
 * RECONCILED (docs/handoff/workspace-redesign.md): "Draft bail brief" lives on the Draft grounds step; "Show the plan" is the
 * Details drawer (details-button) that holds the trace; Likely objections are shown inside Draft grounds; the hearing card is the
 * Prepare for the hearing step; Gate 2 is the Export step's approve button and confirm dialog.
 */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { expectNoUnmatched } from "./helpers";
import { TID } from "./testids";

test("flow 3: draft -> plan trace -> grounds with claim checks -> spar -> prep card -> Gate 2 -> DOCX", async ({ page }) => {
  const mock = await MockBackend.install(page, { gate1Approved: true, draft: "none", gate2Approved: false });
  await page.goto("/case/case-0007");

  // Counsel opens Draft grounds and clicks "Draft bail brief"; nothing exists yet (404 from the mock).
  await page.getByTestId(TID.stage("IV")).click();
  await page.getByTestId(TID.draftBriefButton).click();
  await expect.poll(() => mock.draftStarted).toBe(true);
  expect(mock.requests).toContain("POST /api/cases/case-0007/draft");

  // The Details drawer lists Sutradhar's steps from the SSE events.
  await page.getByTestId(TID.detailsButton).click();
  const drawer = page.getByTestId(TID.traceDrawer);
  await expect(drawer).toBeVisible();
  const steps = drawer.getByTestId(TID.traceStep);
  await expect(steps).toHaveCount(4); // 4 Sutradhar TOOL_CALL events in e2e/fixtures/draft_events.json
  const tools = await steps.evaluateAll((els) => els.map((e) => e.getAttribute("data-tool")));
  expect(tools).toEqual(["get_fact", "search_reasoning", "similar_orders", "good_law_check"]);
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();

  // Draft grounds: G1, G2 with SUPPORTED / REPAIRED, and the NEEDS_REVIEW marker on G3.
  const g1 = page.locator('[data-testid=brief-ground][data-ground="G1"]');
  const g2 = page.locator('[data-testid=brief-ground][data-ground="G2"]');
  const g3 = page.locator('[data-testid=brief-ground][data-ground="G3"]');
  // RECONCILED: a ground shows one "Needs check" mark only when it needs review; its claim check is under Details.
  const check = async (g: import("@playwright/test").Locator) => {
    await g.locator("summary", { hasText: "Details" }).click();
    return g.locator("details").getByTestId(TID.auxBadge).first().getAttribute("data-status");
  };
  await expect(g1).toBeVisible();
  expect(await check(g1)).toBe("SUPPORTED");
  expect(await check(g2)).toBe("REPAIRED");
  expect(await check(g3)).toBe("NEEDS_REVIEW");
  await expect(g3.getByTestId(TID.needsReviewMarker)).toBeVisible();
  await expect(g3.getByTestId(TID.needsReviewMarker).getByTestId(TID.auxBadge)).toHaveAttribute("data-status", "NEEDS_REVIEW");
  await expect(g1.getByTestId(TID.needsReviewMarker)).toHaveCount(0);

  // Likely objections (inside Draft grounds): ANSWERED / PARTLY / UNANSWERED.
  const verdict = (id: string) =>
    page.locator(`[data-testid=spar-objection][data-objection="${id}"]`).getByTestId(TID.statusBadge).first().getAttribute("data-status");
  expect(await verdict("O1")).toBe("ANSWERED");
  expect(await verdict("O2")).toBe("PARTLY");
  expect(await verdict("O3")).toBe("UNANSWERED");
  await expect(page.locator('[data-testid=spar-objection][data-objection="O3"]').getByTestId(TID.statusBadge).first()).toContainText("✖");

  // Prepare for the hearing: the hearing-prep card.
  await page.getByTestId(TID.stage("VI")).click();
  await expect(page.getByTestId(TID.prepCard)).toBeVisible();
  await expect(page.getByTestId(TID.prepCard)).toContainText("Why was the charge sheet filed on day 74?");

  // Gate 2 is blocked by G3 and O3 until counsel resolves them.
  await page.getByTestId(TID.stage("VII")).click();
  await expect(page.getByTestId(TID.needsYouItem)).toHaveCount(2);
  await expect(page.getByTestId(TID.approveExportButton)).toBeDisabled();
  mock.resolveGate2Items();
  await page.reload();
  await page.getByTestId(TID.stage("VII")).click();
  await page.getByTestId(TID.approveExportButton).click();
  await page.getByTestId(TID.gateModal).getByTestId(TID.gateApproveButton).click();
  expect(mock.approveCalls.map((c) => c.gate)).toEqual(["GATE_2_EXPORT"]);

  // Export -> DOCX link(s).
  await page.getByTestId(TID.exportButton).click();
  const links = page.getByTestId(TID.exportLink);
  await expect(links).toHaveCount(2); // application + hearing-prep card
  const hrefs = await links.evaluateAll((els) => els.map((e) => e.getAttribute("href") ?? ""));
  expect(hrefs.some((h) => /application\.docx$/.test(h))).toBe(true);
  expect(mock.exportResults).toEqual([{ status: 200 }]);
  await expectNoUnmatched(mock);
});
