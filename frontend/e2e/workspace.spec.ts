/**
 * Case workspace (plan §13.5): the stepper, one step at a time, status badges that always carry icon + label, Rights Radar
 * chips, the source panel with the page highlight, axe-core and the keyboard path. Runs in both the chromium and
 * reduced-motion projects.
 *
 * RECONCILED (docs/handoff/workspace-redesign.md, "Old test expectations that will fail"): the three panes, the seven-stage
 * rail with gate diamonds and the right-pane tabs were replaced by a six-step stepper that shows one step at a time. The case
 * file moved into the Documents popover, chat into a drawer, the gates into confirm buttons inside their steps, and Likely
 * objections into Draft grounds. Status labels are plain language. Each test below keeps what the old one protected.
 */
import { expect, test, type Page } from "@playwright/test";
import { MockBackend } from "./mockBackend";
import { renderedStageIds, seriousAxeViolations, expectNoUnmatched } from "./helpers";
import { STEPS, TID } from "./testids";
import { fx } from "./fixtures";

let mock: MockBackend;
test.beforeEach(async ({ page }) => {
  mock = await MockBackend.install(page, { caseId: "case-0007", gate1Approved: true, draft: "done" });
  await page.goto("/case/case-0007");
  await expect(page.getByTestId(TID.stageRail)).toBeVisible();
});

const field = (page: Page, key: string) => page.locator(`[data-testid=dossier-field][data-field="${key}"]`);
const step = (page: Page, key: string) => page.getByTestId(TID.stage(key)).click();

test("shows one step, the stepper and the case controls; the case file and chat open on demand", async ({ page }) => {
  await expect(page.getByTestId(TID.paneMain)).toBeVisible();
  for (const id of [TID.documentsButton, TID.chatButton, TID.detailsButton]) await expect(page.getByTestId(id)).toBeVisible();
  await page.getByTestId(TID.documentsButton).click();
  await expect(page.getByTestId(TID.paneCaseFile)).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByTestId(TID.chatButton).click();
  await expect(page.getByTestId(TID.paneChat)).toBeVisible();
});

test("the stepper has six steps in order with plain labels, and no separate gate controls", async ({ page }) => {
  expect(await renderedStageIds(page)).toEqual(STEPS.map((s) => `stage-${s.key}`));
  for (const s of STEPS) await expect(page.getByTestId(TID.stage(s.key))).toContainText(s.label);
  await expect(page.locator("[data-testid^='gate-diamond-']")).toHaveCount(0);
});

test("each step shows its own content and becomes the current step", async ({ page }) => {
  const shows: Record<string, string> = { II: TID.dossierField, III: TID.rightsChip, IV: TID.briefGround, VI: TID.prepCard, VII: TID.approveExportButton };
  for (const [key, id] of Object.entries(shows)) {
    await step(page, key);
    await expect(page.getByTestId(TID.stage(key))).toHaveAttribute("aria-current", "step");
    await expect(page.getByTestId(TID.paneMain).getByTestId(id).first()).toBeVisible();
  }
  // Likely objections (stage SPAR) are shown inside Draft grounds.
  await step(page, "IV");
  await expect(page.getByTestId(TID.sparObjection).first()).toBeVisible();
});

test.describe("Review facts", () => {
  test.beforeEach(async ({ page }) => {
    await step(page, "II");
  });

  test("lists every case-0007 dossier field", async ({ page }) => {
    const keys = Object.keys(fx.dossier().fields);
    await expect(page.getByTestId(TID.dossierField)).toHaveCount(keys.length);
    for (const k of keys) await expect(field(page, k)).toBeVisible();
  });

  test("antecedents shows the cross icon and the words Not found", async ({ page }) => {
    const badge = field(page, "antecedents").getByTestId(TID.statusBadge);
    await expect(badge).toContainText("✖");
    await expect(badge).toContainText("Not found");
    await expect(badge).toHaveAttribute("data-status", "UNSUPPORTED");
  });

  test("every status badge shows an icon AND a text label (never colour alone)", async ({ page }) => {
    const texts = await page.getByTestId(TID.dossierField).getByTestId(TID.statusBadge).allTextContents();
    expect(texts.length).toBe(Object.keys(fx.dossier().fields).length);
    for (const t of texts) {
      const trimmed = t.replace(/\s+/g, " ").trim();
      expect(trimmed, "badge text").toMatch(/^\S+\s+\S.*$/); // glyph, then a label
      expect(trimmed.replace(/^\S+\s+/, "").length).toBeGreaterThan(1);
    }
  });

  test("COMPUTED, VERIFIED and USER_STATED fields use the plan's icons with plain labels", async ({ page }) => {
    const badge = (k: string) => field(page, k).getByTestId(TID.statusBadge);
    await expect(badge("custody_days")).toContainText("ƒ");
    await expect(badge("custody_days")).toContainText("Calculated");
    await expect(badge("fir")).toContainText("✔");
    await expect(badge("fir")).toContainText("Confirmed from the documents");
    await expect(badge("personal")).toContainText("✎");
    await expect(badge("personal")).toContainText("Entered by you");
  });

  test("opening a field's source shows the quote and highlights its box on the page (data-box)", async ({ page }) => {
    await field(page, "fir").getByTestId(TID.dossierFieldSource).click();
    const panel = page.getByTestId(TID.sourcePanel);
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("FIR No. 112/2024 dated 14.08.2024");
    const hl = panel.getByTestId(TID.pdfViewer).getByTestId(TID.pdfHighlight);
    await expect(hl).toHaveCount(1);
    await expect(hl).toHaveAttribute("data-box", /^\s*64\s*,\s*120\s*,\s*540\s*,\s*152\s*$/);
    await expect(hl).toBeInViewport();
  });

  test("the List of dates shows the seven timeline events", async ({ page }) => {
    await page.getByTestId(TID.rightTab("dates")).click();
    await expect(page.getByTestId(TID.rightTab("dates"))).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId(TID.dateRow)).toHaveCount(fx.timeline().length);
    const main = page.getByTestId(TID.paneMain);
    for (const e of fx.timeline()) await expect(main).toContainText(String(e.label));
  });
});

test("Check rights shows one chip per Rights Radar check; default bail is WINDOW_CLOSED", async ({ page }) => {
  await step(page, "III");
  await page.getByTestId(TID.paneMain).getByRole("button", { name: /Other checks/ }).click();
  await expect(page.getByTestId(TID.rightsChip)).toHaveCount(fx.rights().checks.length);
  const dflt = page.locator('[data-testid=rights-chip][data-check="default_bail"]');
  await expect(dflt).toContainText(/default bail/i);
  await expect(dflt).toHaveAttribute("data-status", "WINDOW_CLOSED");
  await expect(dflt.getByTestId(TID.statusBadge)).toContainText(/window closed/i);
  for (const c of fx.rights().checks) {
    await expect(page.locator(`[data-testid=rights-chip][data-check="${c.check}"]`)).toHaveAttribute("data-status", c.status);
  }
});

test("axe-core: zero serious or critical violations on the workspace", async ({ page }) => {
  await step(page, "II");
  expect(await seriousAxeViolations(page)).toEqual([]);
});

test("keyboard: Tab reaches the stepper and a step shows a visible focus ring", async ({ page }) => {
  let focusedStage: string | null = null;
  for (let i = 0; i < 60 && !focusedStage; i++) {
    await page.keyboard.press("Tab");
    focusedStage = await page.evaluate(() => {
      const id = document.activeElement?.getAttribute("data-testid") ?? "";
      return /^stage-[IVX]+$/.test(id) ? id : null;
    });
  }
  expect(focusedStage, "Tab never reached a step of the stepper").not.toBeNull();
  const ring = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement;
    const cs = getComputedStyle(el);
    return { matches: el.matches(":focus-visible"), outline: cs.outlineStyle, outlineWidth: parseFloat(cs.outlineWidth), shadow: cs.boxShadow };
  });
  expect(ring.matches).toBe(true);
  // A focus ring may be drawn as an outline or as a ring shadow (Tailwind focus-visible:ring).
  expect(ring.outline !== "none" && ring.outlineWidth > 0 || (ring.shadow !== "none" && ring.shadow !== "")).toBe(true);
});

test("the workspace only calls endpoints the backend defines", async ({ page }) => {
  for (const key of ["II", "III", "IV", "VI", "VII"]) await step(page, key);
  await expectNoUnmatched(mock);
});

test.describe("layout by width (frontend/DESIGN.md, Workspace principles 7)", () => {
  for (const width of [390, 768, 1024, 1280, 1440]) {
    test(`no sideways page scroll at ${width} px; the stepper is whole from 1024 px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/case/case-0007");
      await expect(page.getByTestId(TID.stageRail)).toBeVisible();
      const m = await page.evaluate(() => {
        const ol = document.querySelector("[data-testid=stage-rail] ol") as HTMLElement;
        return { doc: document.documentElement.scrollWidth, olClient: ol.clientWidth, olScroll: ol.scrollWidth };
      });
      expect(m.doc).toBeLessThanOrEqual(width);
      if (width >= 1024) expect(m.olScroll).toBeLessThanOrEqual(m.olClient);
      await expect(page.getByTestId(TID.stage("VII"))).toBeAttached();
    });
  }

  test("on a phone the source sheet takes focus and Escape closes it", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/case/case-0007");
    await step(page, "II");
    await field(page, "fir").getByTestId(TID.dossierFieldSource).click();
    await expect(page.getByTestId(TID.sourcePanel)).toBeVisible();
    await expect(page.getByRole("button", { name: "Close source" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId(TID.sourcePanel)).toHaveCount(0);
  });

  test("compact case controls keep their full names for screen readers", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/case/case-0007");
    await expect(page.getByTestId(TID.chatButton)).toHaveAccessibleName("Ask about this case");
    await expect(page.getByTestId(TID.documentsButton)).toHaveAccessibleName(/Documents/);
  });
});
