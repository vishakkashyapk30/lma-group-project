/**
 * Approval gates (plan §13.5, §16): Gate 2 blocks export until the checklist is cleared and approved; Gate 1 requires counsel to
 * acknowledge every UNSUPPORTED field. The mock backend enforces the same rules as the real routers (409 on a partly cleared
 * checklist, 403 on export before approval).
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

  test("the checklist lists the unresolved NEEDS_REVIEW and UNANSWERED items and approval is disabled", async ({ page }) => {
    await page.getByTestId(TID.gateDiamond(2)).click();
    const modal = page.getByTestId(TID.gateModal);
    await expect(modal).toBeVisible();
    await expect(modal.getByTestId(TID.gateChecklistItem)).toHaveCount(2);
    await expect(modal.locator('[data-kind="needs_review"][data-item="G3"]')).toBeVisible();
    await expect(modal.locator('[data-kind="unanswered"][data-item="O3"]')).toBeVisible();
    await expect(modal.getByTestId(TID.gateApproveButton)).toBeDisabled();
    expect(mock.approveCalls).toEqual([]);
  });

  test("export is blocked before approval: disabled, or the 403 is shown as an error and no file link appears", async ({ page }) => {
    const exportButton = page.getByTestId(TID.exportButton);
    await expect(exportButton).toBeVisible();
    if (await exportButton.isEnabled()) {
      await exportButton.click();
      await expect(page.getByTestId(TID.errorBanner)).toBeVisible();
      await expect(page.getByTestId(TID.errorBanner)).toContainText(/403|Gate 2|approv/i);
      expect(mock.exportResults).toEqual([{ status: 403 }]);
    }
    await expect(page.getByTestId(TID.exportLink)).toHaveCount(0);
    expect(mock.exportResults.filter((r) => r.status === 200)).toEqual([]);
  });

  test("resolving every item enables approval; after approval the export succeeds and shows file links", async ({ page }) => {
    // Counsel resolves the items elsewhere (Brief/Spar tabs); the modal re-fetches the checklist each time it opens.
    await page.getByTestId(TID.gateDiamond(2)).click();
    await expect(page.getByTestId(TID.gateApproveButton)).toBeDisabled();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId(TID.gateModal)).toHaveCount(0);

    mock.resolveGate2Items();

    await page.getByTestId(TID.gateDiamond(2)).click();
    const modal = page.getByTestId(TID.gateModal);
    await expect(modal.getByTestId(TID.gateChecklistItem)).toHaveCount(0);
    await expect(modal.getByTestId(TID.gateApproveButton)).toBeEnabled();
    await modal.getByTestId(TID.gateApproveButton).click();
    await expect(page.getByTestId(TID.gateModal)).toHaveCount(0);
    expect(mock.approveCalls.map((c) => c.gate)).toEqual(["GATE_2_EXPORT"]);
    await expect(page.getByTestId(TID.gateDiamond(2))).toHaveAttribute("data-approved", "true");

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
    mock.gate2 = { ...mock.gate2, unresolved_needs_review: [], unresolved_unanswered: [] }; // UI sees a cleared checklist...
    await page.getByTestId(TID.gateDiamond(2)).click();
    mock.gate2 = { ...mock.gate2, unresolved_unanswered: ["O3"] }; // ...but the server state changed before approve
    await page.getByTestId(TID.gateModal).getByTestId(TID.gateApproveButton).click();
    await expect(page.getByTestId(TID.errorBanner)).toBeVisible();
    await expect(page.getByTestId(TID.gateDiamond(2))).toHaveAttribute("data-approved", "false");
  });
});

test.describe("Gate 1 (dossier)", () => {
  test("every UNSUPPORTED field (antecedents) must be acknowledged before approval is enabled", async ({ page }) => {
    const mock = await MockBackend.install(page, { gate1Approved: false, draft: "none" });
    await page.goto("/case/case-0007");
    await page.getByTestId(TID.gateDiamond(1)).click();
    const modal = page.getByTestId(TID.gateModal);
    const item = modal.locator('[data-testid=gate-checklist-item][data-kind="unsupported"][data-item="antecedents"]');
    await expect(item).toBeVisible();
    await expect(modal.getByTestId(TID.gateApproveButton)).toBeDisabled();

    await item.getByRole("checkbox").check();
    await expect(modal.getByTestId(TID.gateApproveButton)).toBeEnabled();
    await item.getByRole("checkbox").uncheck();
    await expect(modal.getByTestId(TID.gateApproveButton)).toBeDisabled();

    await item.getByRole("checkbox").check();
    await modal.getByTestId(TID.gateApproveButton).click();
    expect(mock.approveCalls).toEqual([{ gate: "GATE_1_DOSSIER", body: { acknowledged_fields: ["antecedents"] } }]);
    await expect(page.getByTestId(TID.gateDiamond(1))).toHaveAttribute("data-approved", "true");
  });

  test("later stages are locked until Gate 1 is approved, then unlock", async ({ page }) => {
    await MockBackend.install(page, { gate1Approved: false, draft: "none" });
    await page.goto("/case/case-0007");
    for (const n of ["III", "IV", "V", "VI", "VII"]) await expect(page.getByTestId(TID.stage(n))).toHaveAttribute("aria-disabled", "true");
    await page.getByTestId(TID.gateDiamond(1)).click();
    await page.getByTestId(TID.gateModal).getByRole("checkbox").first().check();
    await page.getByTestId(TID.gateApproveButton).click();
    for (const n of ["III", "IV", "V", "VI", "VII"]) await expect(page.getByTestId(TID.stage(n))).not.toHaveAttribute("aria-disabled", "true");
  });
});
