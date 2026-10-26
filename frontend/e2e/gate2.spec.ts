/**
 * Approval gates (plan §13.5, §16): Gate 2 blocks export until the checklist is cleared and approved; Gate 1 requires counsel to
 * deal with every UNSUPPORTED field. The mock backend enforces the same rules as the real routers (409 on a partly cleared
 * checklist, 403 on export before approval).
 *
 * RECONCILED (docs/handoff/workspace-redesign.md): the gate diamonds and the checklist modal were replaced by the steps
 * themselves. What still needs counsel is listed under "Needs your attention" (needs-you) on Review facts and Export; the step's
 * one button (confirm-facts-button, approve-export-button) stays disabled until that list is clear and then opens a confirm
 * dialog (gate-modal) that lists what the approval locks. "Acknowledge an UNSUPPORTED field" is now "Mark unknown" on the field,
 * and the approval still sends it in acknowledged_fields. The export button exists only after Gate 2.
 */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { expectNoUnmatched } from "./helpers";
import { TID } from "./testids";

test.describe("Gate 2 (export)", () => {
  let mock: MockBackend;
  test.beforeEach(async ({ page }) => {
    mock = await MockBackend.install(page, { gate1Approved: true, draft: "done", gate2Approved: false });
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("VII")).click();
  });

  test("the unresolved NEEDS_REVIEW and UNANSWERED items are listed and approval is disabled", async ({ page }) => {
    const needs = page.getByTestId(TID.needsYouItem);
    await expect(needs).toHaveCount(2);
    await expect(needs.filter({ hasText: "G3" })).toBeVisible();
    await expect(needs.filter({ hasText: "O3" })).toBeVisible();
    await expect(page.getByTestId(TID.approveExportButton)).toBeDisabled();
    expect(mock.approveCalls).toEqual([]);
  });

  test("export is impossible before approval: no export button, no file link, no export request", async ({ page }) => {
    await expect(page.getByTestId(TID.approveExportButton)).toBeVisible();
    await expect(page.getByTestId(TID.exportButton)).toHaveCount(0);
    await expect(page.getByTestId(TID.exportLink)).toHaveCount(0);
    expect(mock.exportResults).toEqual([]);
  });

  test("resolving every item enables approval; after approval the export succeeds and shows file links", async ({ page }) => {
    await expect(page.getByTestId(TID.approveExportButton)).toBeDisabled();
    mock.resolveGate2Items(); // the items are resolved on the server (e.g. in another window); a fresh load reads the checklist
    await page.reload();
    await page.getByTestId(TID.stage("VII")).click();
    await expect(page.getByTestId(TID.needsYouItem)).toHaveCount(0);
    await expect(page.getByTestId(TID.approveExportButton)).toBeEnabled();

    await page.getByTestId(TID.approveExportButton).click();
    const modal = page.getByTestId(TID.gateModal);
    await expect(modal).toBeVisible();
    await expect(modal).toContainText(/What this locks/);
    await modal.getByTestId(TID.gateApproveButton).click();
    await expect(page.getByTestId(TID.gateModal)).toHaveCount(0);
    expect(mock.approveCalls.map((c) => c.gate)).toEqual(["GATE_2_EXPORT"]);

    await expect(page.getByTestId(TID.exportButton)).toBeEnabled();
    await page.getByTestId(TID.exportButton).click();
    const links = page.getByTestId(TID.exportLink);
    await expect(links.first()).toBeVisible();
    await expect(links.first()).toHaveAttribute("href", /application\.docx$/);
    expect(mock.exportResults).toEqual([{ status: 200 }]);
    await expect(page.getByTestId(TID.errorBanner)).toHaveCount(0);
    await expectNoUnmatched(mock);
  });

  test("a server-side refusal (409) of an approval is shown, and the gate stays closed", async ({ page }) => {
    mock.resolveGate2Items(); // the step sees a cleared checklist...
    await page.reload();
    await page.getByTestId(TID.stage("VII")).click();
    await page.getByTestId(TID.approveExportButton).click();
    mock.gate2 = { ...mock.gate2, unresolved_unanswered: ["O3"] }; // ...but the server state changed before approve
    await page.getByTestId(TID.gateModal).getByTestId(TID.gateApproveButton).click();
    await expect(page.getByTestId(TID.errorBanner).or(page.getByTestId(TID.gateModal).getByRole("alert")).first()).toBeVisible();
    await expect(page.getByTestId(TID.exportButton)).toHaveCount(0);
    expect(mock.exportResults).toEqual([]);
  });
});

test.describe("Gate 1 (dossier)", () => {
  test("every UNSUPPORTED field (antecedents) must be dealt with before the facts can be confirmed", async ({ page }) => {
    const mock = await MockBackend.install(page, { gate1Approved: false, draft: "none" });
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.stage("II")).click();
    await expect(page.getByTestId(TID.needsYouItem).filter({ hasText: /Antecedents not found/ })).toBeVisible();
    await expect(page.getByTestId(TID.confirmFactsButton)).toBeDisabled();

    await page.getByRole("button", { name: "Mark Antecedents as unknown" }).click();
    await expect(page.getByTestId(TID.confirmFactsButton)).toBeEnabled();
    await page.getByRole("button", { name: "Undo marking Antecedents as unknown" }).click();
    await expect(page.getByTestId(TID.confirmFactsButton)).toBeDisabled();

    await page.getByRole("button", { name: "Mark Antecedents as unknown" }).click();
    await page.getByTestId(TID.confirmFactsButton).click();
    const modal = page.getByTestId(TID.gateModal);
    await expect(modal.locator('[data-testid=gate-checklist-item][data-kind="unsupported"][data-item="antecedents"]')).toBeVisible();
    await modal.getByTestId(TID.gateApproveButton).click();
    expect(mock.approveCalls).toEqual([{ gate: "GATE_1_DOSSIER", body: { acknowledged_fields: ["antecedents"] } }]);
  });

  test("later steps are locked until Gate 1 is approved, then unlock", async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: false, draft: "none" });
    await page.goto("/case/case-0007");
    const later = ["III", "IV", "VI", "VII"];
    for (const n of later) await expect(page.getByTestId(TID.stage(n))).toHaveAttribute("aria-disabled", "true");
    await page.getByTestId(TID.stage("II")).click();
    await page.getByRole("button", { name: "Mark Antecedents as unknown" }).click();
    await page.getByTestId(TID.confirmFactsButton).click();
    await page.getByTestId(TID.gateModal).getByTestId(TID.gateApproveButton).click();
    for (const n of later) await expect(page.getByTestId(TID.stage(n))).not.toHaveAttribute("aria-disabled", "true");
  });
});
