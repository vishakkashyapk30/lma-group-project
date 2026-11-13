/**
 * Plan §13.6 flows 1 and 3 against the REAL API (no page.route mocks): create a case, upload a bundle, review and confirm the facts,
 * check rights, draft, resolve what Gate 2 needs, read the hearing card, approve, export and download the application.
 *
 * Skipped unless E2E_LIVE_API=1. Start the backend first (offline models are enough), then the frontend built against it:
 *   VS_DATA_DIR=<scratch> VS_MODELS=offline VS_LLM_BACKEND=offline .venv/bin/python -m uvicorn vakeel_sahayak.api.asgi:app --port 8000
 *   NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build && npx next start -p 3000
 *   E2E_LIVE_API=1 npx playwright test e2e/live_flow.spec.ts --project=chromium
 * E2E_LIVE_API_BASE (default http://localhost:8000) is the API the frontend was built against; E2E_PORT picks the frontend's port.
 * The bundle defaults to a born-digital T2 bundle from `make data` (E2E_LIVE_PDF overrides it); without it the test is skipped. The
 * numbers of facts, grounds and objections depend on the models, so the test checks the flow and its gates, not the counts.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { TID } from "./testids";

const API_BASE = (process.env.E2E_LIVE_API_BASE ?? "http://localhost:8000").replace(/\/+$/, "");
const PDF = process.env.E2E_LIVE_PDF ?? path.resolve(__dirname, "../../data/testsets/t2/bundles/t1-003_K1.pdf");

test.skip(process.env.E2E_LIVE_API !== "1", "set E2E_LIVE_API=1 with the API and a frontend built against it running");
test.skip(!fs.existsSync(PDF), `no bundle at ${PDF} (run make data, or set E2E_LIVE_PDF)`);

async function clickAll(page: Page, name: RegExp, then?: string) {
  for (let i = 0; i < 60; i++) {
    const button = page.getByRole("button", { name }).first();
    if (!(await button.count())) return;
    await button.click();
    if (then) await page.getByRole("button", { name: then }).first().click();
  }
}

test("live API: upload -> facts -> Gate 1 -> rights -> draft -> resolve -> hearing card -> Gate 2 -> export and download", async ({ page }) => {
  test.setTimeout(15 * 60_000);
  const failures: string[] = [];
  page.on("response", (r) => {
    if (r.url().includes("/api/") && r.status() >= 500) failures.push(`${r.status()} ${r.request().method()} ${r.url()}`);
  });

  await page.goto("/cases");
  await page.getByTestId("new-case-button").click();
  await page.getByRole("dialog").getByRole("textbox").first().fill("Live flow (e2e)");
  await page.getByRole("dialog").getByRole("button", { name: /create/i }).click();
  await page.waitForURL(/\/case\/[^/]+$/);
  await expect(page.getByTestId(TID.stageRail)).toBeVisible();
  await expect(page.getByTestId("mode-chip")).toContainText("Connected");

  // Flow 1: upload; Munshi files the documents and Peshkar builds the facts and the rights report.
  const uploaded = page.waitForResponse((r) => r.url().endsWith("/upload") && r.request().method() === "POST", { timeout: 300_000 });
  await page.getByTestId(TID.uploadInput).setInputFiles(PDF);
  expect((await uploaded).status()).toBe(200);
  await expect(page.getByTestId(TID.paneMain).getByTestId(TID.documentItem).first()).toBeVisible();

  await page.getByTestId(TID.stage("II")).click();
  await expect(page.getByTestId(TID.dossierField).first()).toBeVisible();
  await clickAll(page, /^Mark .* as unknown$/);
  await page.getByTestId(TID.confirmFactsButton).click();
  await page.getByTestId(TID.gateModal).getByTestId(TID.gateApproveButton).click();
  await expect(page.getByTestId(TID.stage("III"))).not.toHaveAttribute("aria-disabled", "true");

  await page.getByTestId(TID.stage("III")).click();
  await expect(page.getByTestId(TID.rightsChip).first()).toBeVisible();

  // Flow 3: draft, then resolve every ground that needs review and every unanswered objection.
  await page.getByTestId(TID.stage("IV")).click();
  const drafted = page.waitForResponse((r) => r.url().endsWith("/draft") && r.request().method() === "POST", { timeout: 600_000 });
  await page.getByTestId(TID.draftBriefButton).click();
  expect((await drafted).status()).toBe(200);
  await expect(page.getByTestId(TID.briefGround).first()).toBeVisible();

  // What the draft left out: every sentence the API reports as withheld is listed under its ground (closed until opened), and a
  // ground that lost every sentence is listed under "Grounds left for you to draft". The offline models usually withhold some
  // sentences, but how many depends on the models, so only agreement between the API and the screen is checked.
  const caseId = new URL(page.url()).pathname.split("/").pop();
  const brief = await (await page.request.get(`${API_BASE}/api/cases/${caseId}/brief`)).json();
  const withheld: Array<{ ground: string; sentences: unknown[]; dropped?: boolean }> = (brief.withheld ?? []).filter((w: { sentences: unknown[] }) => w.sentences.length > 0);
  const present = new Set((brief.grounds ?? []).map((g: { id: string }) => g.id));
  const inBrief = withheld.filter((w) => present.has(w.ground) && !w.dropped);
  const left = withheld.filter((w) => !present.has(w.ground) || w.dropped);
  await expect(page.getByTestId("withheld-list")).toHaveCount(inBrief.length);
  await expect(page.getByTestId("dropped-ground")).toHaveCount(left.length);
  if (inBrief.length > 0) {
    const first = page.getByTestId("withheld-list").first();
    await expect(first.getByTestId("withheld-sentence").first()).toBeHidden(); // closed until counsel opens it
    await first.locator("summary").click();
    await expect(first.getByTestId("withheld-sentence")).toHaveCount(inBrief[0]!.sentences.length);
    await expect(first.getByTestId("withheld-sentence").first()).toBeVisible();
  }
  await clickAll(page, /^Accept .* with a note$/, "Mark as reviewed");
  await clickAll(page, /^Resolve unanswered objection/, "Mark as resolved");

  await page.getByTestId(TID.stage("VI")).click();
  await expect(page.getByTestId(TID.prepCard)).toBeVisible();
  await expect(page.getByTestId(TID.prepCard)).toContainText(/no prediction/i);

  // Gate 2 and export: the server records counsel's resolutions with the approval, then the files can be downloaded.
  await page.getByTestId(TID.stage("VII")).click();
  await expect(page.getByTestId(TID.exportButton)).toHaveCount(0);
  await page.getByTestId(TID.approveExportButton).click();
  await page.getByTestId(TID.gateModal).getByTestId(TID.gateApproveButton).click();
  await expect(page.getByTestId(TID.errorBanner)).toHaveCount(0);
  await page.getByTestId(TID.exportButton).click();
  const links = page.getByTestId(TID.exportLink);
  await expect(links).toHaveCount(4, { timeout: 120_000 });
  const href = (await links.first().getAttribute("href")) ?? "";
  expect(href).toMatch(/\/export\/files\/application\.docx$/);
  const download = await page.request.get(href);
  expect(download.status()).toBe(200);
  expect(download.headers()["content-type"]).toContain("wordprocessingml");
  expect(failures, "server errors during the flow").toEqual([]);
});
