/**
 * "Manuscript" design tokens (plan §13.2) and WCAG contrast (plan §13.7: "WCAG 2.1 AA, using the text pairs in the
 * palette table"). Parses styles/tokens.css and tailwind.config.ts; no component code involved.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import tailwindConfig from "../../tailwind.config";

const root = path.resolve(__dirname, "../..");
const css = fs.readFileSync(path.join(root, "styles/tokens.css"), "utf8");

/** Value of a custom property declared in :root (first declaration wins). */
function cssVar(name: string): string {
  const m = css.match(new RegExp(`${name}\\s*:\\s*([^;]+);`));
  if (!m) throw new Error(`token ${name} missing from tokens.css`);
  return m[1].trim();
}

function luminance(hex: string): number {
  const ch = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = ch.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
/** WCAG 2.x contrast ratio between two #RRGGBB colours. */
function contrast(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

const PALETTE: Record<string, string> = {
  "--color-parchment": "#F6EEDC",
  "--color-cream": "#FBF7EE",
  "--color-maroon": "#7A1626",
  "--color-oxblood": "#4A0E17",
  "--color-gold-leaf": "#B08D57",
  "--color-ink": "#231A16",
};
const STATUS: Record<string, string> = {
  "--color-neem": "#3D6B45",
  "--color-indigo": "#2E3A6B",
  "--color-sindoor": "#B3261E",
  "--color-haldi": "#8C5A0B",
  "--color-clay": "#6B5E55",
};

describe("Manuscript palette (plan §13.2)", () => {
  it.each(Object.entries(PALETTE))("%s is %s", (name, hex) => {
    expect(cssVar(name).toUpperCase()).toBe(hex);
  });
  it.each(Object.entries(STATUS))("status colour %s is %s", (name, hex) => {
    expect(cssVar(name).toUpperCase()).toBe(hex);
  });
});

describe("fonts (plan §13.2 Type)", () => {
  it.each([
    ["--font-display", "Fraunces"],
    ["--font-devanagari-display", "Tiro Devanagari Hindi"],
    ["--font-devanagari-body", "Noto Sans Devanagari"],
    ["--font-ui", "DM Sans"],
    ["--font-mono", "IBM Plex Mono"],
  ])("%s starts with %s", (name, family) => {
    expect(cssVar(name)).toContain(`"${family}"`);
  });
});

describe("motion tokens (plan §13.4, §13.7)", () => {
  it("working loops are capped at 2s by default", () => {
    expect(cssVar("--motion-working-loop-max")).toBe("2s");
  });
  it("the prefers-reduced-motion block sets --motion-working-loop-max to 0s", () => {
    const block = css.match(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{([\s\S]*?\})\s*\}/);
    expect(block, "reduced-motion media block missing").not.toBeNull();
    expect(block![1]).toMatch(/--motion-working-loop-max\s*:\s*0s\s*;/);
  });
});

describe("tailwind.config.ts references the CSS variables", () => {
  // RECONCILED: colours are declared as `rgb(var(--rgb-x) / <alpha-value>)` (the channel twin of --color-x in tokens.css) so
  // Tailwind opacity modifiers (bg-neem/10) work; a `{ DEFAULT, ... }` object is a colour family. The test still requires
  // every colour to resolve to the token's variable, never to a hex.
  type ColorValue = string | { DEFAULT?: string; [k: string]: string | undefined };
  const colors = (tailwindConfig.theme?.extend?.colors ?? {}) as Record<string, ColorValue>;
  const flat = (v: ColorValue | undefined): string => (typeof v === "string" ? v : (v?.DEFAULT ?? ""));
  const resolves = (v: string, variable: string) =>
    v === `var(${variable})` || v === `rgb(var(${variable.replace("--color-", "--rgb-")}) / <alpha-value>)`;
  it.each([
    ["parchment", "--color-parchment"],
    ["cream", "--color-cream"],
    ["maroon", "--color-maroon"],
    ["oxblood", "--color-oxblood"],
    ["gold", "--color-gold-leaf"],
    ["ink", "--color-ink"],
    ["neem", "--color-neem"],
    ["indigo", "--color-indigo"],
    ["sindoor", "--color-sindoor"],
    ["haldi", "--color-haldi"],
    ["clay", "--color-clay"],
  ])("colour key %s -> var(%s)", (key, variable) => {
    expect(resolves(flat(colors[key]), variable), `${key}: ${flat(colors[key])}`).toBe(true);
  });
  it("never hard-codes a hex colour (single source of truth is tokens.css)", () => {
    for (const v of Object.values(colors)) expect(JSON.stringify(v)).not.toMatch(/#[0-9a-f]{3,8}/i);
  });
  it("font families reference the font variables", () => {
    const fam = (tailwindConfig.theme?.extend?.fontFamily ?? {}) as Record<string, string[]>;
    expect(fam.display).toEqual(["var(--font-display)"]);
    expect(fam.sans).toEqual(["var(--font-ui)"]);
    expect(fam.mono).toEqual(["var(--font-mono)"]);
    expect(fam.devanagari).toEqual(["var(--font-devanagari-display)"]);
    expect(fam["devanagari-body"]).toEqual(["var(--font-devanagari-body)"]);
  });
});

describe("WCAG contrast of the palette text pairs (plan §13.2; tolerance 0.1 for the plan's rounding)", () => {
  const TOL = 0.1;
  const c = (name: string) => cssVar(name);
  it.each([
    ["cream on oxblood", "--color-cream", "--color-oxblood", 14.4],
    ["maroon on parchment", "--color-maroon", "--color-parchment", 9.2],
    ["ink on parchment", "--color-ink", "--color-parchment", 14.8],
    ["gold leaf on oxblood", "--color-gold-leaf", "--color-oxblood", 5.0],
    ["neem on cream", "--color-neem", "--color-cream", 5.8],
    ["indigo on cream", "--color-indigo", "--color-cream", 10.2],
    ["sindoor on cream", "--color-sindoor", "--color-cream", 6.1],
    ["haldi on cream", "--color-haldi", "--color-cream", 5.5],
    ["clay on cream", "--color-clay", "--color-cream", 5.9],
  ])("%s >= %s", (_label, fg, bg, planned) => {
    expect(contrast(c(fg as string), c(bg as string))).toBeGreaterThanOrEqual((planned as number) - TOL);
  });

  it.each(Object.keys(STATUS))("%s on cream meets WCAG AA for normal text (4.5:1)", (name) => {
    expect(contrast(c(name), c("--color-cream"))).toBeGreaterThanOrEqual(4.5);
  });
  it("body pairs meet AA 4.5:1", () => {
    expect(contrast(c("--color-ink"), c("--color-parchment"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(c("--color-cream"), c("--color-oxblood"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(c("--color-maroon"), c("--color-parchment"))).toBeGreaterThanOrEqual(4.5);
  });

  it("gold leaf on parchment is 2.7:1 (fails AA text) and is documented as decoration only in tokens.css", () => {
    const ratio = contrast(c("--color-gold-leaf"), c("--color-parchment"));
    expect(ratio).toBeGreaterThan(2.6);
    expect(ratio).toBeLessThan(2.8);
    expect(ratio).toBeLessThan(4.5); // therefore never legal as text
    const goldLine = css.split("\n").find((l) => l.includes("--color-gold-leaf:"))!;
    expect(goldLine).toMatch(/decoration only/i);
    expect(goldLine).toMatch(/text only on oxblood/i);
  });
});
