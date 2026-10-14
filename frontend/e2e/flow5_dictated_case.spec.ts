/**
 * Plan §13.6 flow 5: a dictated case (plan §4.5). Counsel dictates in Hindi through the microphone; Munshi reads back the dates and sections it
 * heard and counsel confirms; the confirmed facts are USER_STATED and the brief labels them "per counsel, not on record".
 * Audio never leaves the laptop: the browser records with MediaRecorder (Chromium's fake audio device) and the mock backend stands in for the
 * laptop's /api/cases/{id}/audio route. The Hindi sentence itself is not played; what matters is the read-back and the status it produces.
 */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { expectNoUnmatched } from "./helpers";
import { fx } from "./fixtures";
import { TEXT, TID } from "./testids";

test.use({
  permissions: ["microphone"],
  launchOptions: { args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] },
});

async function dictate(page: import("@playwright/test").Page) {
  const mic = page.getByTestId(TID.micButton);
  await expect(mic).toHaveAttribute("aria-pressed", "false");
  await mic.click();
  await expect(mic).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId(TID.dictationStatus)).toContainText(/recording/i);
  await page.waitForTimeout(1200); // let the fake device produce some audio
  await mic.click();
  await expect(mic).toHaveAttribute("aria-pressed", "false");
}

test("flow 5: Hindi dictation via the mic -> read-back -> confirm -> USER_STATED facts -> the brief says 'per counsel, not on record'", async ({ page }) => {
  const mock = await MockBackend.install(page, { caseId: "case-0042", scenario: "dictation", fresh: true, gate1Approved: false, draft: "none" });
  await page.goto("/case/case-0042");
  await expect(page.getByTestId(TID.readbackCard)).toHaveCount(0);

  // 1. Counsel dictates; the recording goes to the laptop's audio route as multipart form data.
  await dictate(page);
  await expect.poll(() => mock.uploadCalls.length).toBe(1);
  expect(mock.uploadCalls[0].path).toBe("/api/cases/case-0042/audio");
  expect(mock.uploadCalls[0].contentType).toMatch(/^multipart\/form-data; boundary=/);
  expect(mock.uploadCalls[0].bytes).toBeGreaterThan(0);

  // 2. Munshi reads back the date and the section it heard, and asks for confirmation.
  const card = page.getByTestId(TID.readbackCard);
  await expect(card).toBeVisible();
  const items = card.getByTestId(TID.readbackItem);
  const lines = fx.dictationReadback().questions.filter((q) => /\d/.test(q));
  await expect(items).toHaveCount(lines.length);
  await expect(card).toContainText("20.08.2024");
  await expect(card).toContainText("318(4)");
  await expect(card).toContainText(/confirm/i);
  // nothing is filed before counsel confirms
  await page.getByTestId(TID.rightTab("dossier")).click();
  await expect(page.getByTestId(TID.dossierField)).toHaveCount(0);

  // 3. Counsel confirms: the chat carries the confirmation with the values.
  await card.getByTestId(TID.readbackConfirm).click();
  await expect.poll(() => mock.chatCalls.length).toBe(1);
  expect(mock.chatCalls[0]).toMatch(/confirm/i);
  expect(mock.chatCalls[0]).toContain("20.08.2024");
  expect(mock.chatCalls[0]).toContain("318(4)");
  expect(mock.dictationConfirmed).toBe(true);

  // 4. The dictated facts are USER_STATED ("Stated by counsel"), never VERIFIED.
  for (const field of ["arrest_date", "sections", "personal"]) {
    const row = page.locator(`[data-testid=dossier-field][data-field="${field}"]`);
    await expect(row.getByTestId(TID.statusBadge)).toHaveAttribute("data-status", "USER_STATED");
    await expect(row.getByTestId(TID.statusBadge)).toContainText(TEXT.statedByCounsel);
    await expect(row.getByTestId(TID.statusBadge)).toContainText("✎");
  }
  await expect(page.locator('[data-testid=status-badge][data-status="VERIFIED"]')).toHaveCount(0);

  // 5. Gate 1 (nothing unsupported), then the brief: the dictated fact is labelled "per counsel, not on record".
  await page.getByTestId(TID.gateDiamond(1)).click();
  const modal = page.getByTestId(TID.gateModal);
  await expect(modal.getByTestId(TID.gateChecklistItem)).toHaveCount(0);
  await modal.getByTestId(TID.gateApproveButton).click();
  expect(mock.approveCalls.map((c) => c.gate)).toEqual(["GATE_1_DOSSIER"]);

  await page.getByTestId(TID.draftBriefButton).click();
  await expect.poll(() => mock.draftStarted).toBe(true);
  await page.getByTestId(TID.rightTab("brief")).click();
  const g1 = page.locator('[data-testid=brief-ground][data-ground="G1"]');
  await expect(g1).toContainText(TEXT.perCounsel);
  await expect(g1.getByTestId(TID.perCounselLabel)).toBeVisible();
  await expect(g1.getByTestId(TID.perCounselLabel)).toContainText(TEXT.perCounsel);
  await expectNoUnmatched(mock);
});

test("flow 5: nothing is filed until counsel confirms the read-back", async ({ page }) => {
  const mock = await MockBackend.install(page, { caseId: "case-0042", scenario: "dictation", fresh: true, gate1Approved: false, draft: "none" });
  await page.goto("/case/case-0042");
  await dictate(page);
  await expect(page.getByTestId(TID.readbackCard)).toBeVisible();
  expect(mock.dictationConfirmed).toBe(false);
  expect(mock.chatCalls).toEqual([]);
  await page.getByTestId(TID.rightTab("dossier")).click();
  await expect(page.getByTestId(TID.dossierField)).toHaveCount(0);
  await expectNoUnmatched(mock);
});

test("flow 5: the microphone button is keyboard operable and labelled", async ({ page }) => {
  await MockBackend.install(page, { caseId: "case-0042", scenario: "dictation", fresh: true, gate1Approved: false, draft: "none" });
  await page.goto("/case/case-0042");
  const mic = page.getByTestId(TID.micButton);
  await expect(mic).toHaveAccessibleName(/dictat|record|mic/i);
  await mic.focus();
  await page.keyboard.press("Enter");
  await expect(mic).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Enter");
  await expect(mic).toHaveAttribute("aria-pressed", "false");
});
