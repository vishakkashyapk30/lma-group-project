/**
 * The workspace header at phone, tablet and laptop widths (390, 768, 820, 1024, 1280, 1440), on the sample case with the API
 * unreachable (the demo backend answers). Checks: the top bar's breadcrumb and search never overlap, nothing in the top bar
 * leaves the screen, the page never scrolls sideways, every step of the stepper is reachable (on a phone through one
 * "Step k of 6: <name>" control that opens the list, with 44 px rows), and each step selected shows as the current one.
 * Screenshots of the header on each step go to E2E_HEADER_SHOTS when it is set.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { TID } from "./testids";

const SIZES = [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 820, height: 1180 },
  { width: 1024, height: 768 },
  { width: 1280, height: 800 },
  { width: 1440, height: 900 },
];
const STEPS = [
  { numeral: "I", name: "Add documents" },
  { numeral: "II", name: "Review facts" },
  { numeral: "III", name: "Check rights" },
  { numeral: "IV", name: "Draft grounds" },
  { numeral: "VI", name: "Prepare for the hearing" },
  { numeral: "VII", name: "Export" },
];
const SHOTS = process.env.E2E_HEADER_SHOTS;

type Box = { x: number; y: number; width: number; height: number };
const overlap = (a: Box, b: Box) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

async function box(l: Locator): Promise<Box> {
  const b = await l.boundingBox();
  expect(b, "element has a box").toBeTruthy();
  return b!;
}

async function openList(page: Page, phone: boolean) {
  if (!phone) return;
  const toggle = page.getByTestId("stage-rail-toggle");
  if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();
}

async function expectTopBarFits(page: Page, width: number) {
  const header = page.locator("header[data-print-hide]").first();
  const kids = header.locator(":scope > *:visible");
  const n = await kids.count();
  for (let i = 0; i < n; i++) {
    const b = await box(kids.nth(i));
    expect(b.x, `top bar item ${i} starts on screen`).toBeGreaterThanOrEqual(-0.5);
    expect(b.x + b.width, `top bar item ${i} ends on screen`).toBeLessThanOrEqual(width + 0.5);
  }
  const crumbs = await box(page.getByTestId("topbar-crumbs"));
  const search = page.getByTestId("search-trigger");
  const searchBox = (await search.isVisible()) ? await box(search) : await box(page.getByTestId("search-icon"));
  expect(overlap(crumbs, searchBox), "breadcrumb and search overlap").toBe(false);
  // The breadcrumb's own text stays inside its container (it truncates, never spills under the search).
  const spill = await page.evaluate(() => {
    const c = document.querySelector('[data-testid="topbar-crumbs"]') as HTMLElement | null;
    if (!c) return 0;
    const r = c.getBoundingClientRect();
    return Math.max(0, ...Array.from(c.querySelectorAll("*")).map((e) => (e as HTMLElement).getBoundingClientRect()).filter((b) => b.width > 0).map((b) => b.right - r.right));
  });
  expect(spill, "breadcrumb content spills past its box").toBeLessThanOrEqual(0.5);
}

for (const size of SIZES) {
  test(`the workspace header fits at ${size.width}x${size.height} on every step`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.route("http://localhost:8000/**", (route) => route.abort());
    await page.setViewportSize(size);
    await page.goto("/case/case-0007");
    await expect(page.getByTestId(TID.stageRail)).toBeVisible();
    const phone = size.width < 1024;
    if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });

    for (const [i, step] of STEPS.entries()) {
      await openList(page, phone);
      const button = page.getByTestId(TID.stage(step.numeral));
      await expect(button).toBeVisible();
      if (phone) {
        const b = await box(button);
        expect(b.height, `${step.name} touch target`).toBeGreaterThanOrEqual(44);
        expect(b.x + b.width, `${step.name} inside the screen`).toBeLessThanOrEqual(size.width);
      }
      await button.click();
      await page.waitForTimeout(350); // the step's slide settles
      await expect(button).toHaveAttribute("aria-current", "step");
      if (phone) {
        // Chosen: the list closes and the control names the step.
        await expect(page.getByTestId("stage-rail-toggle")).toHaveAttribute("aria-expanded", "false");
        await expect(page.getByTestId("stage-rail-toggle")).toContainText(`Step ${i + 1} of ${STEPS.length}: ${step.name}`);
        await expect(button).toBeHidden();
      } else {
        await expect(page.getByTestId("stage-rail-toggle")).toBeHidden();
        // Reachable: the current step is inside the viewport (the rail scrolls it into view).
        const b = await box(button);
        expect(b.x).toBeGreaterThanOrEqual(-0.5);
        expect(b.x + b.width, `${step.name} inside the screen`).toBeLessThanOrEqual(size.width + 0.5);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), "horizontal overflow").toBe(true);
      await expectTopBarFits(page, size.width);
      if (SHOTS) {
        const head = page.locator("header[data-print-hide]").first();
        const rail = page.getByTestId(TID.stageRail);
        const top = await box(head);
        const r = await box(rail);
        await page.screenshot({
          path: path.join(SHOTS, `header-${size.width}x${size.height}-${i + 1}-${step.name.replace(/\s+/g, "-")}.png`),
          clip: { x: 0, y: 0, width: size.width, height: Math.min(size.height, Math.max(top.y + top.height, r.y + r.height) + 56) },
        });
        if (phone) {
          await openList(page, phone);
          await page.screenshot({
            path: path.join(SHOTS, `header-${size.width}x${size.height}-${i + 1}-list-open.png`),
            clip: { x: 0, y: 0, width: size.width, height: Math.min(size.height, 480) },
          });
          await page.getByTestId("stage-rail-toggle").click();
        }
      }
    }
  });
}

test("on a phone the step list opens from one control, keeps keyboard and screen-reader semantics, and closes with Escape", async ({ page }) => {
  await page.route("http://localhost:8000/**", (route) => route.abort());
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/case/case-0007");
  const nav = page.getByRole("navigation", { name: "Case steps" });
  await expect(nav).toBeVisible();
  const toggle = nav.getByTestId("stage-rail-toggle");
  expect((await box(toggle)).height).toBeGreaterThanOrEqual(44);
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(nav.getByRole("list", { name: "Steps" })).toBeHidden();
  await toggle.click();
  const list = nav.getByRole("list", { name: "Steps" });
  await expect(list).toBeVisible();
  // Each step still reads its state as a word, and the current one is marked.
  await expect(list.getByRole("button", { name: /Step Add documents\s*, Done/ })).toHaveCount(1);
  await expect(list.locator('[aria-current="step"]')).toHaveCount(1);
  // Arrow keys move between the steps.
  await list.getByRole("button").first().focus();
  await page.keyboard.press("ArrowDown");
  await expect(list.getByRole("button").nth(1)).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toBeFocused();
});

test("below lg the search is an icon button and Ctrl K still opens the palette", async ({ page }) => {
  await page.route("http://localhost:8000/**", (route) => route.abort());
  for (const width of [768, 820]) {
    await page.setViewportSize({ width, height: 1024 });
    await page.goto("/case/case-0007");
    await expect(page.getByTestId("search-trigger")).toBeHidden();
    await expect(page.getByTestId("search-icon")).toBeVisible();
    await page.keyboard.press("Control+k");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
  }
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto("/case/case-0007");
  await expect(page.getByTestId("search-trigger")).toBeVisible();
});
