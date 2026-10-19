/**
 * Plan §13.6 flow 1: a new case from a messy bundle. Counsel drops one 14-page PDF (scanned Hindi FIR, two remand orders, the
 * Sessions Court bail rejection); Munshi splits and labels it, shows route badges and asks about one unreadable page; counsel
 * fixes the red fields and approves Gate 1. IngestionReport comes from e2e/fixtures/ingestion_bundle.json.
 */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { expectNoUnmatched, tinyPdf } from "./helpers";
import { fx } from "./fixtures";
import { TID } from "./testids";

test("flow 1: messy 14-page bundle -> route badges, stamps, one question, edit red fields, approve Gate 1", async ({ page }) => {
  const mock = await MockBackend.install(page, { caseId: "case-0042", fresh: true, gate1Approved: false, draft: "none" });
  await page.goto("/case/case-0042");

  // Intake: nothing yet.
  await expect(page.getByTestId(TID.documentItem)).toHaveCount(0);

  // 1. Counsel drops in one 14-page PDF.
  await page.getByTestId(TID.uploadInput).setInputFiles({ name: "bundle_14pp.pdf", mimeType: "application/pdf", buffer: tinyPdf(14) });
  await expect.poll(() => mock.uploadCalls.length).toBe(1);
  expect(mock.uploadCalls[0].path).toBe("/api/cases/case-0042/upload");
  expect(mock.uploadCalls[0].contentType).toMatch(/^multipart\/form-data; boundary=/);

  // 2. Munshi splits and labels: four documents with type stamps...
  const caseFile = page.getByTestId(TID.paneCaseFile);
  const docs = caseFile.getByTestId(TID.documentItem);
  await expect(docs).toHaveCount(4);
  const stamps = caseFile.getByTestId(TID.docTypeStamp);
  await expect(stamps).toHaveCount(4);
  const stampTexts = (await stamps.allTextContents()).map((t) => t.toUpperCase().replace(/[\s_]+/g, " "));
  expect(stampTexts.filter((t) => t.includes("FIR"))).toHaveLength(1);
  expect(stampTexts.filter((t) => t.includes("REMAND"))).toHaveLength(2);
  expect(stampTexts.filter((t) => t.includes("BAIL"))).toHaveLength(1);
  await expect(docs.first()).toContainText(/hi|hindi/i); // the FIR is Hindi

  // ...and route badges: TEXT, LAYOUT, OCR and VISION all appear.
  const badgeTexts = await caseFile.getByTestId(TID.routeBadge).allTextContents();
  for (const route of ["TEXT", "LAYOUT", "OCR", "VISION"]) {
    expect(badgeTexts.map((t) => t.trim().toUpperCase()), `route badge ${route}`).toContain(route);
  }
  // the scanned FIR (d1) carries OCR and the VISION fallback; the born-digital bail order (d4) is TEXT only
  const d1 = caseFile.locator('[data-testid=document-item][data-doc-id="d1"]');
  expect((await d1.getByTestId(TID.routeBadge).allTextContents()).map((t) => t.trim().toUpperCase())).toEqual(expect.arrayContaining(["OCR", "VISION"]));
  const d4 = caseFile.locator('[data-testid=document-item][data-doc-id="d4"]');
  expect((await d4.getByTestId(TID.routeBadge).allTextContents()).map((t) => t.trim().toUpperCase())).toEqual(["TEXT"]);

  // 3. Munshi asks ONE question, about the unreadable page.
  const question = fx.ingestionBundle().questions[0];
  const munshiMsgs = page.getByTestId(TID.paneChat).locator(`[data-testid=chat-message][data-agent="MUNSHI"]`);
  await expect(munshiMsgs).toHaveCount(1);
  await expect(munshiMsgs.first()).toContainText(/page 3/i);
  await expect(munshiMsgs.first()).toContainText(/unreadable/i);
  expect(question).toMatch(/unreadable/);

  // 4. Peshkar's dossier: red fields. Counsel edits antecedents.
  await page.getByTestId(TID.rightTab("dossier")).click();
  const antecedents = page.locator('[data-testid=dossier-field][data-field="antecedents"]');
  await expect(antecedents.getByTestId(TID.statusBadge)).toHaveAttribute("data-status", "UNSUPPORTED");
  await antecedents.getByTestId(TID.dossierFieldEdit).click();
  await antecedents.getByTestId(TID.dossierFieldInput).fill("No prior cases");
  await antecedents.getByTestId(TID.dossierFieldSave).click();
  // RECONCILED: DossierFields.antecedents is TrackedField[list[str]] (schemas/dossier.py), so the PATCH carries the one typed line as a list.
  expect(mock.patchCalls).toEqual([{ field: "antecedents", value: ["No prior cases"] }]);
  await expect(antecedents.getByTestId(TID.statusBadge)).toHaveAttribute("data-status", "USER_EDITED");
  await expect(antecedents.getByTestId(TID.statusBadge)).toContainText("Edited by counsel");
  await expect(antecedents.getByTestId(TID.statusBadge)).toContainText("✎");
  await expect(antecedents).toContainText("No prior cases");

  // 5. Gate 1: trial_stage is still UNSUPPORTED; it must be acknowledged, then Gate 1 is approved.
  await expect(page.getByTestId(TID.stage("III"))).toHaveAttribute("aria-disabled", "true");
  await page.getByTestId(TID.gateDiamond(1)).click();
  const modal = page.getByTestId(TID.gateModal);
  await expect(modal.getByTestId(TID.gateChecklistItem)).toHaveCount(1);
  const item = modal.locator('[data-kind="unsupported"][data-item="trial_stage"]');
  await expect(modal.getByTestId(TID.gateApproveButton)).toBeDisabled();
  await item.getByRole("checkbox").check();
  await modal.getByTestId(TID.gateApproveButton).click();
  expect(mock.approveCalls).toEqual([{ gate: "GATE_1_DOSSIER", body: { acknowledged_fields: ["trial_stage"] } }]);
  await expect(page.getByTestId(TID.gateDiamond(1))).toHaveAttribute("data-approved", "true");
  await expect(page.getByTestId(TID.stage("III"))).not.toHaveAttribute("aria-disabled", "true");
  await expectNoUnmatched(mock);
});
