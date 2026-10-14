/**
 * Plan §13.6 flow 3: the brief and the spar. Counsel clicks "Draft bail brief"; Sutradhar plans (the trace is visible, driven by
 * SSE events), Vakeel drafts, Abhiyojak spars; counsel resolves NEEDS_REVIEW / UNANSWERED items, reads the hearing-prep card,
 * approves Gate 2 and exports the DOCX. SSE is mocked (text/event-stream).
 */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { expectNoUnmatched } from "./helpers";
import { TID } from "./testids";

test("flow 3: draft -> plan trace -> grounds with claim checks -> spar -> prep card -> Gate 2 -> DOCX", async ({ page }) => {
  const mock = await MockBackend.install(page, { gate1Approved: true, draft: "none", gate2Approved: false });
  await page.goto("/case/case-0007");

  // Counsel clicks "Draft bail brief"; nothing exists yet (404 from the mock).
  await page.getByTestId(TID.draftBriefButton).click();
  await expect.poll(() => mock.draftStarted).toBe(true);
  expect(mock.requests).toContain("POST /api/cases/case-0007/draft");

  // The trace drawer ("Show the plan") lists Sutradhar's steps from the SSE events.
  await page.getByTestId(TID.showPlanButton).click();
  const drawer = page.getByTestId(TID.traceDrawer);
  await expect(drawer).toBeVisible();
  const steps = drawer.getByTestId(TID.traceStep);
  await expect(steps).toHaveCount(4); // 4 Sutradhar TOOL_CALL events in e2e/fixtures/draft_events.json
  const tools = await steps.evaluateAll((els) => els.map((e) => e.getAttribute("data-tool")));
  expect(tools).toEqual(["get_fact", "search_reasoning", "similar_orders", "good_law_check"]);
  await page.keyboard.press("Escape");

  // Brief tab: grounds G1, G2 with SUPPORTED / REPAIRED, and the NEEDS_REVIEW underline marker on G3.
  await page.getByTestId(TID.rightTab("brief")).click();
  const g1 = page.locator('[data-testid=brief-ground][data-ground="G1"]');
  const g2 = page.locator('[data-testid=brief-ground][data-ground="G2"]');
  const g3 = page.locator('[data-testid=brief-ground][data-ground="G3"]');
  await expect(g1.getByTestId(TID.statusBadge)).toHaveAttribute("data-status", "SUPPORTED");
  await expect(g1.getByTestId(TID.statusBadge)).toContainText("✔");
  await expect(g2.getByTestId(TID.statusBadge)).toHaveAttribute("data-status", "REPAIRED");
  await expect(g3.getByTestId(TID.statusBadge)).toHaveAttribute("data-status", "NEEDS_REVIEW");
  const marker = g3.getByTestId(TID.needsReviewMarker);
  await expect(marker).toBeVisible();
  expect(await marker.evaluate((el) => getComputedStyle(el).textDecorationLine)).toContain("underline");
  await expect(g1.getByTestId(TID.needsReviewMarker)).toHaveCount(0);

  // Spar tab: objections with ANSWERED / PARTLY / UNANSWERED.
  await page.getByTestId(TID.rightTab("spar")).click();
  const verdict = async (id: string) =>
    page.locator(`[data-testid=spar-objection][data-objection="${id}"]`).getByTestId(TID.statusBadge).getAttribute("data-status");
  expect(await verdict("O1")).toBe("ANSWERED");
  expect(await verdict("O2")).toBe("PARTLY");
  expect(await verdict("O3")).toBe("UNANSWERED");
  await expect(page.locator('[data-testid=spar-objection][data-objection="O3"]').getByTestId(TID.statusBadge)).toContainText("✖");

  // Prep tab: the hearing-prep card is visible.
  await page.getByTestId(TID.rightTab("prep")).click();
  await expect(page.getByTestId(TID.prepCard)).toBeVisible();
  await expect(page.getByTestId(TID.prepCard)).toContainText("Why was the charge sheet filed on day 74?");

  // Gate 2 is blocked by G3 and O3 until counsel resolves them.
  await page.getByTestId(TID.gateDiamond(2)).click();
  await expect(page.getByTestId(TID.gateModal).getByTestId(TID.gateChecklistItem)).toHaveCount(2);
  await expect(page.getByTestId(TID.gateApproveButton)).toBeDisabled();
  await page.keyboard.press("Escape");
  mock.resolveGate2Items();
  await page.getByTestId(TID.gateDiamond(2)).click();
  await page.getByTestId(TID.gateApproveButton).click();
  expect(mock.approveCalls.map((c) => c.gate)).toEqual(["GATE_2_EXPORT"]);

  // Export -> DOCX link(s).
  await page.getByTestId(TID.stage("VII")).click();
  await page.getByTestId(TID.exportButton).click();
  const links = page.getByTestId(TID.exportLink);
  await expect(links).toHaveCount(2); // application + hearing-prep card
  const hrefs = await links.evaluateAll((els) => els.map((e) => e.getAttribute("href") ?? ""));
  expect(hrefs.some((h) => /application\.docx$/.test(h))).toBe(true);
  expect(mock.exportResults).toEqual([{ status: 200 }]);
  await expectNoUnmatched(mock);
});
