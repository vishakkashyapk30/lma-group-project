/**
 * Plan §13.6 flow 4: the case moves on. The charge sheet is filed and counsel uploads the order; Peshkar highlights the changed fields and
 * counsel re-approves; only the affected grounds are redrafted, highlighted, and the rest stay word for word (plan §7.4, §10).
 * The backend is the "change" scenario of e2e/mockBackend.ts: the upload yields a change set (SSE) and a pending Gate 1; approving it
 * redrafts G2 (charge_sheet_filed) only. The duplicate-document control mirrors T3's no-op controls.
 *
 * RECONCILED (docs/handoff/workspace-redesign.md): documents are added on the Add documents step; Gate 1 pending again shows as the
 * change banner's "Review and confirm again" and the Review facts step's confirm button (in place of a grey gate diamond); the
 * changed marker reads "Changed since you confirmed"; brief, rights and facts are steps, not right-pane tabs.
 */
import { expect, test, type Page } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { expectNoUnmatched, tinyPdf } from "./helpers";
import { TEXT, TID } from "./testids";

const ground = (page: Page, id: string) => page.locator(`[data-testid=brief-ground][data-ground="${id}"]`);
const step = (page: Page, key: string) => page.getByTestId(TID.stage(key)).click();
async function uploadOrder(page: Page) {
  await step(page, "I");
  await page.getByTestId(TID.uploadInput).setInputFiles({ name: "order_sheet_2.pdf", mimeType: "application/pdf", buffer: tinyPdf(2) });
}

test("flow 4: new charge-sheet order -> changed fields highlighted -> re-approve -> only G2 redrafted and highlighted", async ({ page }) => {
  const mock = await MockBackend.install(page, { scenario: "change", gate1Approved: true, draft: "done" });
  await page.goto("/case/case-0007");

  // Before: the approved brief says the charge sheet is not filed. Remember G1 and G3 word for word.
  await step(page, "IV");
  await expect(ground(page, "G2")).toContainText(/not been filed/i);
  const g1Before = await ground(page, "G1").innerText();
  const g3Before = await ground(page, "G3").innerText();
  await expect(page.getByTestId(TID.changeBanner)).toHaveCount(0);

  // 1. Counsel uploads the order.
  await uploadOrder(page);
  await expect.poll(() => mock.uploadCalls.length).toBe(1);
  expect(mock.uploadCalls[0].path).toBe("/api/cases/case-0007/upload");

  // 2. Peshkar highlights the changed fields: only charge_sheet (dossier) and default_bail (rights), with a visible marker, not colour alone.
  const banner = page.getByTestId(TID.changeBanner);
  await expect(banner).toBeVisible();
  await expect(banner.locator('[data-testid=change-item][data-kind="field"]')).toHaveCount(1);
  await expect(banner.locator('[data-testid=change-item][data-kind="field"][data-name="charge_sheet"]')).toBeVisible();
  await expect(banner.locator('[data-testid=change-item][data-kind="right"][data-name="default_bail"]')).toBeVisible();
  await expect(banner.getByRole("button", { name: /confirm again/i })).toBeVisible();

  await step(page, "II");
  await expect(page.locator("[data-testid=dossier-field][data-changed=true]")).toHaveCount(1);
  const charge = page.locator('[data-testid=dossier-field][data-field="charge_sheet"]');
  await expect(charge).toHaveAttribute("data-changed", "true");
  await expect(charge.getByTestId(TID.changedMarker)).toContainText(TEXT.changed);
  // RECONCILED: the UI shows court-style dates (02.11.2024, as in the plan's prose examples); the stored value stays ISO 2024-11-02.
  await expect(charge).toContainText(/02\.11\.2024|2024-11-02/);
  await expect(page.locator('[data-testid=dossier-field][data-field="arrest_date"]')).not.toHaveAttribute("data-changed", "true");

  await step(page, "III");
  await expect(page.locator("[data-testid=rights-chip][data-changed=true]")).toHaveCount(1);
  await expect(page.locator('[data-testid=rights-chip][data-check="default_bail"]')).toHaveAttribute("data-changed", "true");

  // 3. Counsel re-approves on Review facts: the confirm button is back, with nothing to deal with.
  await step(page, "II");
  await expect(page.getByTestId(TID.confirmFactsButton)).toBeEnabled();
  await page.getByTestId(TID.confirmFactsButton).click();
  const modal = page.getByTestId(TID.gateModal);
  await expect(modal.getByTestId(TID.gateChecklistItem)).toHaveCount(0);
  await expect(modal.getByTestId(TID.gateApproveButton)).toBeEnabled();
  await modal.getByTestId(TID.gateApproveButton).click();
  expect(mock.approveCalls).toEqual([{ gate: "GATE_1_DOSSIER", body: { acknowledged_fields: [] } }]);
  await expect(page.getByTestId(TID.confirmFactsButton)).toHaveCount(0);

  // 4. Only the affected ground is redrafted and highlighted, with the reason; G1 and G3 are word for word the same.
  await step(page, "IV");
  await expect(ground(page, "G2")).toContainText("02.11.2024");
  await expect(ground(page, "G2")).not.toContainText(/not been filed/i);
  await expect(ground(page, "G2")).toHaveAttribute("data-changed", "true");
  await expect(ground(page, "G2").getByTestId(TID.changeReason)).toContainText(/charge sheet/i);
  await expect(page.locator("[data-testid=brief-ground][data-changed=true]")).toHaveCount(1);
  await expect(ground(page, "G2")).toHaveAttribute("data-state", "CURRENT");
  expect(await ground(page, "G1").innerText()).toBe(g1Before);
  expect(await ground(page, "G3").innerText()).toBe(g3Before);
  await expect(ground(page, "G1")).not.toHaveAttribute("data-changed", "true");
  await expect(ground(page, "G3")).not.toHaveAttribute("data-changed", "true");

  // The re-draft was triggered by the approval, not by a new "Draft bail brief" click, and no endpoint outside the routers was needed.
  expect(mock.requests).not.toContain("POST /api/cases/case-0007/draft");
  await expectNoUnmatched(mock);
});

test("flow 4 control: a duplicate of a document already filed changes nothing (T3 no-op control)", async ({ page }) => {
  const mock = await MockBackend.install(page, { scenario: "change", duplicateUpload: true, gate1Approved: true, draft: "done" });
  await page.goto("/case/case-0007");
  await step(page, "IV");
  const before = await page.getByTestId(TID.briefGround).allInnerTexts();

  await uploadOrder(page);
  await expect.poll(() => mock.uploadCalls.length).toBe(1);

  await expect(page.getByTestId(TID.changeBanner)).toHaveCount(0);
  await step(page, "II");
  await expect(page.locator("[data-testid=dossier-field][data-changed=true]")).toHaveCount(0);
  await expect(page.getByTestId(TID.confirmFactsButton)).toHaveCount(0); // still confirmed
  await step(page, "IV");
  await expect(page.locator("[data-testid=brief-ground][data-changed=true]")).toHaveCount(0);
  expect(await page.getByTestId(TID.briefGround).allInnerTexts()).toEqual(before);
  expect(mock.approveCalls).toEqual([]);
  await expectNoUnmatched(mock);
});

test("flow 4: the change banner and the changed marker carry text, not colour alone (plan §13.2)", async ({ page }) => {
  await MockBackend.install(page, { scenario: "change", gate1Approved: true, draft: "done" });
  await page.goto("/case/case-0007");
  await uploadOrder(page);
  const banner = page.getByTestId(TID.changeBanner);
  await expect(banner).toBeVisible();
  expect((await banner.innerText()).trim().length).toBeGreaterThan(0);
  await step(page, "II");
  const marker = page.locator('[data-testid=dossier-field][data-field="charge_sheet"]').getByTestId(TID.changedMarker);
  expect((await marker.innerText()).trim()).toMatch(/changed/i);
});
