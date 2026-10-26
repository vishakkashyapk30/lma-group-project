/**
 * Plan §13.6 flow 6: the batch desk (Pairokar). A legal-aid office uploads a zip; the triage board is sorted by urgency; each
 * case still needs its own approval, so there is no bulk export anywhere (plan §16).
 */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { expectNoUnmatched } from "./helpers";
import { fx } from "./fixtures";
import { TEXT, TID } from "./testids";

test("flow 6: zip upload -> triage board sorted by urgency -> open a case; no 'Export all'", async ({ page }) => {
  const mock = await MockBackend.install(page, { gate1Approved: true });
  await page.goto("/desk");

  await page.getByTestId(TID.deskUploadInput).setInputFiles({
    name: "legal_aid_batch.zip", mimeType: "application/zip", buffer: Buffer.from("PK\u0005\u0006" + "\0".repeat(18), "latin1"),
  });
  await expect.poll(() => mock.uploadCalls.length).toBe(1);
  expect(mock.uploadCalls[0].path).toBe("/api/desk/upload");
  expect(mock.uploadCalls[0].contentType).toMatch(/^multipart\/form-data/);

  const board = page.getByTestId(TID.deskBoard);
  await expect(board).toBeVisible();
  const cards = board.getByTestId(TID.triageCard);
  await expect(cards).toHaveCount(3);

  // Sorted by urgency_rank (the fixture is deliberately delivered unsorted).
  const sorted = [...fx.triageCards()].sort((a, b) => a.urgency_rank - b.urgency_rank);
  expect(sorted.map((c) => c.case_id)).toEqual(["case-0101", "case-0102", "case-0103"]);
  const order = await cards.evaluateAll((els) => els.map((e) => e.getAttribute("data-case-id")));
  expect(order).toEqual(sorted.map((c) => c.case_id));

  // RECONCILED: the redesign states the one-approval-per-case rule once for the whole desk (page description and the note under the
  // board) instead of on every card; the rule itself is still on screen.
  await expect(page.getByText(TEXT.needsOwnApproval).first()).toBeVisible();
  await expect(page.getByText(/no bulk export/i)).toBeVisible();

  // Each card: reasons, flags, missing docs and next step.
  for (const c of sorted) {
    const card = page.locator(`[data-testid=triage-card][data-case-id="${c.case_id}"]`);
    for (const r of c.reasons) await expect(card.getByTestId(TID.triageReason).filter({ hasText: r })).toHaveCount(1);
    for (const f of c.flags) await expect(card.getByTestId(TID.triageFlag).filter({ hasText: f })).toHaveCount(1);
    for (const d of c.missing_docs) await expect(card.getByTestId(TID.triageMissing).filter({ hasText: d })).toHaveCount(1);
    await expect(card.getByTestId(TID.triageNextStep)).toContainText(c.next_step!);
  }
  // A card without missing documents shows none.
  await expect(page.locator('[data-testid=triage-card][data-case-id="case-0101"]').getByTestId(TID.triageMissing)).toHaveCount(0);

  // No bulk export anywhere on the page (plan §16: no bulk export; one approval per case).
  await expect(page.getByRole("button", { name: TEXT.exportAll })).toHaveCount(0);
  await expect(page.getByRole("link", { name: TEXT.exportAll })).toHaveCount(0);
  await expect(page.getByText(TEXT.exportAll)).toHaveCount(0);
  await expect(page.getByTestId(TID.exportButton)).toHaveCount(0);

  // Opening the top case goes to its workspace.
  await cards.first().getByRole("link").first().click();
  await expect(page).toHaveURL(/\/case\/case-0101$/);
  // RECONCILED: the workspace opens on its stepper (the case file is a popover now, docs/handoff/workspace-redesign.md).
  await expect(page.getByTestId(TID.stageRail)).toBeVisible();
  await expectNoUnmatched(mock);
});

test("an empty board before any upload shows no cards", async ({ page }) => {
  await MockBackend.install(page);
  await page.goto("/desk");
  await expect(page.getByTestId(TID.triageCard)).toHaveCount(0);
  await expect(page.getByRole("button", { name: TEXT.exportAll })).toHaveCount(0);
});
