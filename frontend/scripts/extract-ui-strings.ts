// Lists the interface strings to translate: the text in the label tables plus every literal passed to `t("...")` in the
// components. Writes lib/i18n/source.en.json (sorted, unique). Run: npx vite-node --config vitest.config.ts scripts/extract-ui-strings.ts
import fs from "node:fs";
import path from "node:path";
import { NAV_ITEMS } from "../components/shell/nav";
import * as labels from "../lib/labels";
import * as stages from "../lib/stages";
import * as status from "../lib/status";

const out = new Set<string>();
const add = (v: unknown) => {
  if (typeof v === "string" && v.trim()) out.add(v);
};

// Label tables: every string value of an exported *_LABELS record, and the label and description of each status meta.
for (const [name, value] of Object.entries(labels)) {
  if (name.endsWith("_LABELS") && value && typeof value === "object") Object.values(value as Record<string, unknown>).forEach(add);
}
for (const [name, value] of Object.entries(status)) {
  if (name.endsWith("_META") && value && typeof value === "object") {
    for (const m of Object.values(value as Record<string, { label?: string; description?: string }>)) {
      add(m.label);
      add(m.description);
    }
  }
}
Object.values(stages.TAB_LABELS).forEach(add);
for (const s of stages.STAGES) {
  add(s.label);
  add(s.description);
}
for (const g of Object.values(stages.GATE_LABELS)) {
  add(g.short);
  add(g.label);
  add(g.description);
}
for (const n of NAV_ITEMS) {
  add(n.label);
  add(n.hint);
}

// Literals passed to t("...") in the components and lib.
const T_CALL = /\bt\(\s*"((?:[^"\\\n]|\\.)*)"\s*\)/g;
// Literals given as title, intro, hint or label props (StepFrame, StepFooter and GateFooter translate those props themselves),
// including both branches of `label={busy ? "Exporting" : "Export as Word file"}`.
const PROP_STRING = /\b(?:title|intro|hint|label)="((?:[^"\\\n]|\\.)*)"/g;
const PROP_EXPR = /\b(?:title|intro|hint|label)=\{([^{}\n]*)\}/g;
const QUOTED = /"((?:[^"\\\n]|\\.)+)"/g;
function propStrings(file: string, text: string): void {
  if (!file.includes(`${path.sep}workspace${path.sep}`)) return;
  for (const m of text.matchAll(PROP_STRING)) add(JSON.parse(`"${m[1]}"`));
  for (const m of text.matchAll(PROP_EXPR)) for (const q of m[1].matchAll(QUOTED)) add(JSON.parse(`"${q[1]}"`));
}
function walk(dir: string): void {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "node_modules" || e.name.startsWith(".")) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(ts|tsx)$/.test(e.name)) {
      const text = fs.readFileSync(p, "utf8");
      for (const m of text.matchAll(T_CALL)) add(JSON.parse(`"${m[1]}"`));
      propStrings(p, text);
    }
  }
}
const root = path.resolve(__dirname, "..");
for (const d of ["components", "lib", "app"]) walk(path.join(root, d));

const list = [...out].sort();
fs.writeFileSync(path.join(root, "lib/i18n/source.en.json"), JSON.stringify(list, null, 2) + "\n");
console.log(`${list.length} interface strings -> lib/i18n/source.en.json`);
