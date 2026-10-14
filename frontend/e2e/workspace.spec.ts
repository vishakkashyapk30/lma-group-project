/**
 * Case workspace (plan §13.5): three panes, stage rail with seven stages and two gate diamonds, right-pane tabs synced with the
 * rail, status badges that always carry icon + label, Rights Radar chips, PDF highlights, axe-core and the keyboard path.
 * Runs in both the chromium and reduced-motion projects.
 */
import { expect, test } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { renderedStageIds, seriousAxeViolations, expectNoUnmatched } from "./helpers";
import { RIGHT_TABS, STAGE_NUMERALS, STAGE_TAB, TID } from "./testids";
import { fx } from "./fixtures";

let mock: MockBackend;
test.beforeEach(async ({ page }) => {
  mock = await MockBackend.install(page, { caseId: "case-0007", gate1Approved: true, draft: "done" });
  await page.goto("/case/case-0007");
});

test("shows the three panes", async ({ page }) => {
  await expect(page.getByTestId(TID.paneCaseFile)).toBeVisible();
  await expect(page.getByTestId(TID.paneChat)).toBeVisible();
  await expect(page.getByTestId(TID.paneRight)).toBeVisible();
});

test("stage rail has seven stages I..VII in order and two gate diamonds", async ({ page }) => {
  await expect(page.getByTestId(TID.stageRail)).toBeVisible();
  expect(await renderedStageIds(page)).toEqual(STAGE_NUMERALS.map((n) => `stage-${n}`));
  const labels = ["Intake", "Dossier", "Rights", "Brief", "Spar", "Hearing prep", "File"];
  for (const [i, n] of STAGE_NUMERALS.entries()) {
    await expect(page.getByTestId(TID.stage(n))).toContainText(labels[i]);
  }
  await expect(page.getByTestId(TID.gateDiamond(1))).toBeVisible();
  await expect(page.getByTestId(TID.gateDiamond(2))).toBeVisible();
  await expect(page.locator("[data-testid^='gate-diamond-']")).toHaveCount(2);
});

test("right pane offers Dossier, Dates, Rights, Brief, Spar and Prep tabs", async ({ page }) => {
  for (const t of RIGHT_TABS) await expect(page.getByTestId(TID.rightTab(t))).toBeVisible();
});

test("rail and right-pane tabs are synced in both directions", async ({ page }) => {
  for (const [numeral, tab] of Object.entries(STAGE_TAB)) {
    await page.getByTestId(TID.stage(numeral)).click();
    await expect(page.getByTestId(TID.rightTab(tab))).toHaveAttribute("aria-selected", "true");
  }
  for (const [numeral, tab] of Object.entries(STAGE_TAB)) {
    await page.getByTestId(TID.rightTab(tab)).click();
    await expect(page.getByTestId(TID.stage(numeral))).toHaveAttribute("aria-current", "step");
  }
});

test.describe("Dossier tab", () => {
  test.beforeEach(async ({ page }) => {
    await page.getByTestId(TID.rightTab("dossier")).click();
  });

  test("lists every case-0007 dossier field", async ({ page }) => {
    const keys = Object.keys(fx.dossier().fields);
    await expect(page.getByTestId(TID.dossierField)).toHaveCount(keys.length);
    for (const k of keys) await expect(page.locator(`[data-testid=dossier-field][data-field="${k}"]`)).toBeVisible();
  });

  test("antecedents shows the cross icon and the word Unsupported", async ({ page }) => {
    const badge = page.locator('[data-testid=dossier-field][data-field="antecedents"]').getByTestId(TID.statusBadge);
    await expect(badge).toContainText("✖");
    await expect(badge).toContainText("Unsupported");
    await expect(badge).toHaveAttribute("data-status", "UNSUPPORTED");
  });

  test("every status badge shows an icon AND a text label (never colour alone)", async ({ page }) => {
    const badges = page.getByTestId(TID.dossierField).getByTestId(TID.statusBadge);
    const texts = await badges.allTextContents();
    expect(texts.length).toBe(Object.keys(fx.dossier().fields).length);
    for (const t of texts) {
      const trimmed = t.replace(/\s+/g, " ").trim();
      expect(trimmed, "badge text").toMatch(/^\S+\s+\S.*$/); // glyph, then a label
      expect(trimmed.replace(/^\S+\s+/, "").length).toBeGreaterThan(1);
    }
  });

  test("COMPUTED, VERIFIED and USER_STATED fields use the plan's icons", async ({ page }) => {
    const row = (k: string) => page.locator(`[data-testid=dossier-field][data-field="${k}"]`).getByTestId(TID.statusBadge);
    await expect(row("custody_days")).toContainText("ƒ");
    await expect(row("custody_days")).toContainText("Computed");
    await expect(row("fir")).toContainText("✔");
    await expect(row("fir")).toContainText("Verified");
    await expect(row("personal")).toContainText("✎");
    await expect(row("personal")).toContainText("Stated by counsel");
  });

  test("clicking a field's source highlights its box on the page (data-box)", async ({ page }) => {
    await page.locator('[data-testid=dossier-field][data-field="fir"]').getByTestId(TID.dossierFieldSource).click();
    const hl = page.getByTestId(TID.pdfViewer).getByTestId(TID.pdfHighlight);
    await expect(hl).toHaveCount(1);
    await expect(hl).toHaveAttribute("data-box", /^\s*64\s*,\s*120\s*,\s*540\s*,\s*152\s*$/);
    await expect(hl).toBeInViewport();
  });
});

test("Rights tab shows one chip per Rights Radar check; default bail is WINDOW_CLOSED", async ({ page }) => {
  await page.getByTestId(TID.rightTab("rights")).click();
  await expect(page.getByTestId(TID.rightsChip)).toHaveCount(7);
  const dflt = page.locator('[data-testid=rights-chip][data-check="default_bail"]');
  await expect(dflt).toContainText(/default bail/i);
  await expect(dflt).toHaveAttribute("data-status", "WINDOW_CLOSED");
  await expect(dflt.getByTestId(TID.statusBadge)).toContainText(/window closed/i);
  const expected = fx.rights().checks.map((c) => [c.check, c.status] as const);
  for (const [check, status] of expected) {
    await expect(page.locator(`[data-testid=rights-chip][data-check="${check}"]`)).toHaveAttribute("data-status", status);
  }
});

test("Dates tab lists the seven timeline events", async ({ page }) => {
  await page.getByTestId(TID.rightTab("dates")).click();
  const pane = page.getByTestId(TID.paneRight);
  for (const e of fx.timeline()) await expect(pane).toContainText(String(e.label));
});

test("axe-core: zero serious or critical violations on the workspace", async ({ page }) => {
  await page.getByTestId(TID.rightTab("dossier")).click();
  expect(await seriousAxeViolations(page)).toEqual([]);
});

test("keyboard: Tab reaches the stage rail and a stage item shows a visible focus ring", async ({ page }) => {
  let focusedStage: string | null = null;
  for (let i = 0; i < 60 && !focusedStage; i++) {
    await page.keyboard.press("Tab");
    focusedStage = await page.evaluate(() => {
      const id = document.activeElement?.getAttribute("data-testid") ?? "";
      return /^stage-[IVX]+$/.test(id) ? id : null;
    });
  }
  expect(focusedStage, "Tab never reached a stage-rail item").not.toBeNull();
  const ring = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement;
    const cs = getComputedStyle(el);
    return { matches: el.matches(":focus-visible"), style: cs.outlineStyle, width: parseFloat(cs.outlineWidth) };
  });
  expect(ring.matches).toBe(true);
  expect(ring.style).not.toBe("none");
  expect(ring.width).toBeGreaterThan(0);
});

test("the workspace only calls endpoints the backend defines", async ({ page }) => {
  await page.getByTestId(TID.rightTab("brief")).click();
  await page.getByTestId(TID.rightTab("spar")).click();
  await page.getByTestId(TID.rightTab("prep")).click();
  await expectNoUnmatched(mock);
});
