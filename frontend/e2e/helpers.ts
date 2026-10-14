import AxeBuilder from "@axe-core/playwright";
import { expect, type Locator, type Page } from "@playwright/test";
import { STAGE_NUMERALS, TID } from "./testids";

/** axe-core serious/critical violations (plan §13.7: zero serious violations). Returns a readable list. */
export async function seriousAxeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.impact}: ${v.id} (${v.nodes.length} nodes) ${v.help}`);
}

export const byId = (page: Page, id: string): Locator => page.getByTestId(id);

/** Minimal valid-looking PDF buffer (the mock backend never parses it). */
export function tinyPdf(pages = 1): Buffer {
  const objs: string[] = ["<< /Type /Catalog /Pages 2 0 R >>"];
  const kids = Array.from({ length: pages }, (_, i) => `${3 + i} 0 R`).join(" ");
  objs.push(`<< /Type /Pages /Kids [${kids}] /Count ${pages} >>`);
  for (let i = 0; i < pages; i++) objs.push("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>");
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  objs.forEach((o, i) => { offsets.push(out.length); out += `${i + 1} 0 obj\n${o}\nendobj\n`; });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n` + offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1");
}

/** Stage numerals actually rendered in the rail, in DOM order. */
export async function renderedStageIds(page: Page): Promise<string[]> {
  const ids = await page.getByTestId(TID.stageRail).locator("[data-testid^='stage-']").evaluateAll(
    (els) => els.map((e) => e.getAttribute("data-testid") ?? ""),
  );
  return ids.filter((i) => (STAGE_NUMERALS as readonly string[]).includes(i.replace("stage-", "")));
}

export async function expectNoUnmatched(mock: { unmatched: string[] }): Promise<void> {
  expect(mock.unmatched, "UI called endpoints that the backend routers do not define").toEqual([]);
}
