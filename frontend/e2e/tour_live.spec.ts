/**
 * Guided demos (docs/handoff/evaluator-demo.md) against the REAL API and the real recorded tour files: no page.route mocks.
 * Walks tours 01 and 04 from the Cases page's "Guided demos" list to Export with only the Next button, including the real
 * Gate 2 approval and the Word download. At every step the tour bar must show the title, the caption and the filled values of
 * the step as written in tour.json (read from GET /api/demo/tours/<slug>), and the page must log no console errors.
 *
 * Skipped unless E2E_LIVE_API=1. Start the backend (offline models; the six demo cases pre-load at start-up), then the frontend
 * built against it:
 *   VS_DATA_DIR=<scratch> VS_MODELS=offline VS_LLM_BACKEND=offline VS_CORS_ORIGINS=http://localhost:3031 \
 *     .venv/bin/python -m uvicorn vakeel_sahayak.api.asgi:app --port 8022
 *   cd frontend && NEXT_PUBLIC_API_BASE=http://localhost:8022 npm run build && npx next start -p 3031
 *   E2E_LIVE_API=1 E2E_LIVE_API_BASE=http://localhost:8022 E2E_PORT=3031 E2E_TOURLIVE_SHOTS=<dir> \
 *     npx playwright test e2e/tour_live.spec.ts --project=chromium
 * Each tour is reset first (POST /api/demo/tours/<slug>/reset), so the spec can be rerun on the same data directory.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { expectStepInsideBar } from "./helpers";

const API_BASE = (process.env.E2E_LIVE_API_BASE ?? "http://localhost:8000").replace(/\/+$/, "");
const SHOTS = process.env.E2E_TOURLIVE_SHOTS ?? path.resolve(__dirname, "../test-results/tourlive");
const SLUGS = ["01-cheating-parity", "04-ndps-commercial-scanned"];

test.skip(process.env.E2E_LIVE_API !== "1", "set E2E_LIVE_API=1 with the API and a frontend built against it running");

type Tour = { title: string; steps: { stage: string; title: string; caption: string; filled: { label: string; value: string }[] }[] };

async function shot(page: Page, slug: string, name: string) {
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: path.join(SHOTS, `${slug}-${name}.png`) });
}

for (const slug of SLUGS) {
  test(`live API: guided demo ${slug} walks to Export with Next only`, async ({ page, request }) => {
    test.setTimeout(3 * 60_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    const errors: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(`console: ${m.text()}`);
    });
    page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
    page.on("response", (r) => {
      if (r.url().startsWith(API_BASE) && r.status() >= 400 && r.status() !== 404) errors.push(`${r.status()} ${r.request().method()} ${r.url()}`);
    });

    expect((await request.post(`${API_BASE}/api/demo/tours/${slug}/reset`)).ok()).toBeTruthy();
    const tour = (await (await request.get(`${API_BASE}/api/demo/tours/${slug}`)).json()) as Tour;
    expect(tour.steps.length).toBe(9);

    await page.goto("/cases");
    const demos = page.getByTestId("guided-demos");
    await expect(demos.getByRole("heading", { name: "Guided demos" })).toBeVisible();
    const card = demos.getByTestId("guided-demo").filter({ hasText: tour.title });
    await expect(card).toHaveCount(1);
    await card.getByTestId("guided-demo-start").click();
    await expect(page).toHaveURL(new RegExp(`/case/demo-0\\d\\?tour=${slug}`));

    const bar = page.getByTestId("tour-bar");
    const middle = tour.steps.findIndex((s) => s.stage === "RIGHTS");
    for (const [i, step] of tour.steps.entries()) {
      await expect(bar.getByTestId("tour-step")).toHaveAttribute("data-stage", step.stage);
      await expect(bar.getByTestId("tour-progress")).toHaveText(`Step ${i + 1} of ${tour.steps.length}`);
      await expect(bar.locator("#tour-step-title")).toHaveText(step.title);
      await expect(bar.getByTestId("tour-caption")).toHaveText(step.caption);
      await expect(bar.getByTestId("tour-field")).toHaveCount(step.filled.length);
      if (step.filled.length) {
        await expect(bar.getByTestId("tour-field").first()).toContainText(step.filled[0].label);
        await expect(bar.getByTestId("tour-field").first()).toContainText(step.filled[0].value);
      }
      await page.waitForTimeout(400); // the step's slide settles before the picture
      await expectStepInsideBar(page);
      if (i === 0) await shot(page, slug, "step1");
      if (i === middle) await shot(page, slug, "middle-rights");
      if (step.stage === "GATE_1") await expect(bar.getByTestId("tour-gate")).toHaveAttribute("data-approved", "true");
      if (step.stage === "GATE_2") {
        await expect(bar.getByTestId("tour-gate")).toHaveAttribute("data-approved", "false");
        await expect(page.getByTestId("export-button")).toHaveCount(0);
        await shot(page, slug, "gate2");
      }
      if (i < tour.steps.length - 1) await bar.getByTestId("tour-next").click();
    }

    // Export: Gate 2 was approved by Next through the real route; the Word file comes out.
    await expect(bar.getByTestId("tour-next")).toHaveText(/Finish/);
    await page.getByTestId("export-button").click();
    const link = page.getByTestId("export-link").first();
    await expect(link).toHaveAttribute("href", /\.docx$/);
    await page.waitForTimeout(400);
    await shot(page, slug, "export");
    const [download] = await Promise.all([page.waitForEvent("download"), link.click()]);
    expect(download.suggestedFilename()).toMatch(/\.docx$/);
    const file = await download.path();
    expect(fs.statSync(file!).size).toBeGreaterThan(2000);
    expect(fs.readFileSync(file!).subarray(0, 2).toString()).toBe("PK"); // a DOCX is a zip

    expect(errors).toEqual([]);
  });
}

test("live API: the Hindi toggle keeps the tour bar readable and the step text as recorded", async ({ page, request }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const slug = SLUGS[0];
  await request.post(`${API_BASE}/api/demo/tours/${slug}/reset`);
  const tour = (await (await request.get(`${API_BASE}/api/demo/tours/${slug}`)).json()) as Tour;
  await page.goto(`/case/demo-01?tour=${slug}`);
  const bar = page.getByTestId("tour-bar");
  await bar.getByTestId("tour-next").click();
  await page.getByTestId("lang-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("lang", "hi");
  await expect(bar.locator("#tour-step-title")).toHaveText(tour.steps[1].title); // the recorded text is shown as written
  await expect(bar.getByTestId("tour-next")).toBeVisible();
  await expect(bar.getByTestId("tour-next")).not.toHaveText(/^Next$/);
  await page.waitForTimeout(400);
  await shot(page, slug, "hindi");
  await page.getByTestId("lang-toggle").click();
  await expect(bar.getByTestId("tour-next")).toHaveText(/Next/);
});
