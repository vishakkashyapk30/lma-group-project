/**
 * Plan §13.6 flow 1: a new case from a messy bundle. Counsel drops one 14-page PDF (scanned Hindi FIR, two remand orders, the
 * Sessions Court bail rejection); Munshi splits and labels it, shows route badges and asks about one unreadable page; counsel
 * fixes the red fields and approves Gate 1. IngestionReport comes from e2e/fixtures/ingestion_bundle.json.
 *
 * RECONCILED (docs/handoff/workspace-redesign.md): the documents are listed on the Add documents step (pane-main) and each
 * document's route badges sit under its "Reading details" expander; Munshi's question appears in the step's "Needs your
 * attention" list and once in the chat drawer; the edited field reads "Corrected by you"; Gate 1 is the Review facts step's
 * confirm button, and the remaining UNSUPPORTED field is dealt with by "Mark unknown" (still sent as acknowledged_fields).
 */
import { expect, test, type Locator } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { expectNoUnmatched, tinyPdf } from "./helpers";
import { fx } from "./fixtures";
import { TID } from "./testids";

async function routesOf(doc: Locator): Promise<string[]> {
  await doc.getByRole("button", { name: /Reading details/ }).click();
  const routes = (await doc.getByTestId(TID.routeBadge).allTextContents()).map((t) => t.trim().toUpperCase());
  await doc.getByRole("button", { name: /Reading details/ }).click();
  return routes;
}

test("flow 1: messy 14-page bundle -> route badges, stamps, one question, edit red fields, approve Gate 1", async ({ page }) => {
  const mock = await MockBackend.install(page, { caseId: "case-0042", fresh: true, gate1Approved: false, draft: "none" });
  await page.goto("/case/case-0042");
  const main = page.getByTestId(TID.paneMain);

  // Intake: nothing yet, and the case opens on Add documents.
  await expect(page.getByTestId(TID.stage("I"))).toHaveAttribute("aria-current", "step");
  await expect(main.getByTestId(TID.documentItem)).toHaveCount(0);

  // 1. Counsel drops in one 14-page PDF.
  await page.getByTestId(TID.uploadInput).setInputFiles({ name: "bundle_14pp.pdf", mimeType: "application/pdf", buffer: tinyPdf(14) });
  await expect.poll(() => mock.uploadCalls.length).toBe(1);
  expect(mock.uploadCalls[0].path).toBe("/api/cases/case-0042/upload");
  expect(mock.uploadCalls[0].contentType).toMatch(/^multipart\/form-data; boundary=/);

  // 2. Munshi splits and labels: four documents with type stamps...
  const docs = main.getByTestId(TID.documentItem);
  await expect(docs).toHaveCount(4);
  const stampTexts = (await main.getByTestId(TID.docTypeStamp).allTextContents()).map((t) => t.toUpperCase().replace(/[\s_]+/g, " "));
  expect(stampTexts).toHaveLength(4);
  expect(stampTexts.filter((t) => t.includes("FIR"))).toHaveLength(1);
  expect(stampTexts.filter((t) => t.includes("REMAND"))).toHaveLength(2);
  expect(stampTexts.filter((t) => t.includes("BAIL"))).toHaveLength(1);

  // ...and route badges: TEXT, LAYOUT, OCR and VISION all appear across the documents.
  const d1 = main.locator('[data-testid=document-item][data-doc-id="d1"]');
  const d4 = main.locator('[data-testid=document-item][data-doc-id="d4"]');
  const all = new Set<string>();
  for (let i = 0; i < 4; i++) for (const r of await routesOf(docs.nth(i))) all.add(r);
  for (const route of ["TEXT", "LAYOUT", "OCR", "VISION"]) expect([...all], `route badge ${route}`).toContain(route);
  // the scanned Hindi FIR (d1) carries OCR and the VISION fallback; the born-digital bail order (d4) is TEXT only
  expect(await routesOf(d1)).toEqual(expect.arrayContaining(["OCR", "VISION"]));
  expect(await routesOf(d4)).toEqual(["TEXT"]);
  await d1.getByRole("button", { name: /Reading details/ }).click();
  await expect(d1).toContainText(/hi|hindi/i); // the FIR is Hindi

  // 3. Munshi asks ONE question, about the unreadable page: on the step, and once in the chat.
  const question = fx.ingestionBundle().questions[0];
  expect(question).toMatch(/unreadable/);
  await expect(main.getByTestId(TID.needsYouItem).filter({ hasText: /Page 3 of the FIR is unreadable/ })).toBeVisible();
  await page.getByTestId(TID.chatButton).click();
  const munshiMsgs = page.getByTestId(TID.paneChat).locator(`[data-testid=chat-message][data-agent="MUNSHI"]`);
  await expect(munshiMsgs).toHaveCount(1);
  await expect(munshiMsgs.first()).toContainText(/page 3/i);
  await expect(munshiMsgs.first()).toContainText(/unreadable/i);
  await page.keyboard.press("Escape");

  // 4. Peshkar's dossier: red fields. Counsel edits antecedents.
  await page.getByTestId(TID.stage("II")).click();
  const antecedents = page.locator('[data-testid=dossier-field][data-field="antecedents"]');
  await expect(antecedents.getByTestId(TID.statusBadge)).toHaveAttribute("data-status", "UNSUPPORTED");
  await antecedents.getByTestId(TID.dossierFieldEdit).click();
  await antecedents.getByTestId(TID.dossierFieldInput).fill("No prior cases");
  await antecedents.getByTestId(TID.dossierFieldSave).click();
  // RECONCILED: DossierFields.antecedents is TrackedField[list[str]] (schemas/dossier.py), so the PATCH carries the one typed line as a list.
  expect(mock.patchCalls).toEqual([{ field: "antecedents", value: ["No prior cases"] }]);
  await expect(antecedents.getByTestId(TID.statusBadge)).toHaveAttribute("data-status", "USER_EDITED");
  await expect(antecedents.getByTestId(TID.statusBadge)).toContainText("Corrected by you");
  await expect(antecedents.getByTestId(TID.statusBadge)).toContainText("✎");
  await expect(antecedents).toContainText("No prior cases");

  // 5. Gate 1: trial_stage is still UNSUPPORTED; it must be dealt with, then the facts are confirmed.
  await expect(page.getByTestId(TID.stage("III"))).toHaveAttribute("aria-disabled", "true");
  await expect(page.getByTestId(TID.confirmFactsButton)).toBeDisabled();
  await page.getByRole("button", { name: "Mark Trial stage as unknown" }).click();
  await page.getByTestId(TID.confirmFactsButton).click();
  const modal = page.getByTestId(TID.gateModal);
  await expect(modal.locator('[data-testid=gate-checklist-item][data-kind="unsupported"][data-item="trial_stage"]')).toBeVisible();
  await modal.getByTestId(TID.gateApproveButton).click();
  expect(mock.approveCalls).toEqual([{ gate: "GATE_1_DOSSIER", body: { acknowledged_fields: ["trial_stage"] } }]);
  await expect(page.getByTestId(TID.stage("III"))).not.toHaveAttribute("aria-disabled", "true");
  await expectNoUnmatched(mock);
});
