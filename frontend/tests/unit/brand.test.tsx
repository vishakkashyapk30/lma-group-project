/**
 * Brand and legal safety (plan §13.2 "What we avoid", §13.3 footer): no State Emblem / Lion Capital, national flag, court
 * logos or gavels anywhere in the frontend; the footer carries the disclaimer and NALSA 15100.
 */
import fs from "node:fs";
import path from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Footer } from "@/components/landing/Footer";
import { FRONTEND_ROOT } from "./_helpers";

const SKIP_DIRS = new Set(["node_modules", ".next", "tests", "e2e", "playwright-report", "test-results", "coverage", ".git"]);
const FORBIDDEN = /emblem|ashoka|\blion|lion[-_ ]?capital|gavel|tricolou?r|national[-_ ]?flag|\bflag\b|court[-_ ]?logo|supreme[-_ ]?court[-_ ]?(logo|seal)/i;
const ASSET_EXT = /\.(svg|png|jpe?g|gif|webp|avif|ico|bmp|tiff?)$/i;

function walk(dir: string, out: string[] = []): string[] {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(e.name) && dir === FRONTEND_ROOT) continue;
    if (e.name === "node_modules" || e.name === ".next") continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}
const files = walk(FRONTEND_ROOT).filter((f) => !/package-lock\.json$|tsconfig\.tsbuildinfo$/.test(f));
const rel = (f: string) => path.relative(FRONTEND_ROOT, f);
const sources = files.filter((f) => /\.(tsx?|css|mjs|json)$/.test(f) && !/(^|\/)(vitest|playwright)\.config\.ts$/.test(f));

describe("no restricted national symbols (plan §13.2 'What we avoid')", () => {
  it("no file name anywhere under frontend/ mentions emblem/ashoka/lion/gavel/flag/court logo", () => {
    const bad = files.map(rel).filter((f) => FORBIDDEN.test(path.basename(f)));
    expect(bad).toEqual([]);
  });

  it("every file under public/ is clean (names) and no raster/vector asset is named after a restricted symbol", () => {
    const pub = files.filter((f) => rel(f).startsWith("public" + path.sep));
    for (const f of pub) expect(rel(f)).not.toMatch(FORBIDDEN);
    expect(pub.filter((f) => ASSET_EXT.test(f)).map(rel).filter((n) => FORBIDDEN.test(n))).toEqual([]);
  });

  it("no source imports or references an asset path with a restricted name", () => {
    const refs: string[] = [];
    for (const f of sources) {
      const text = fs.readFileSync(f, "utf8");
      for (const m of text.matchAll(/["'`(]([^"'`()\s]+\.(?:svg|png|jpe?g|gif|webp|avif|ico))["'`)]/gi)) {
        if (FORBIDDEN.test(m[1])) refs.push(`${rel(f)}: ${m[1]}`);
      }
      for (const m of text.matchAll(/(?:import|require)[^;\n]*["']([^"']+)["']/g)) {
        if (FORBIDDEN.test(m[1])) refs.push(`${rel(f)}: import ${m[1]}`);
      }
    }
    expect(refs).toEqual([]);
  });

  it("no gavel / flag icon is imported from an icon library (lucide-react)", () => {
    const offenders: string[] = [];
    for (const f of sources.filter((x) => /\.tsx?$/.test(x))) {
      const text = fs.readFileSync(f, "utf8");
      for (const m of text.matchAll(/import\s*\{([^}]*)\}\s*from\s*["']lucide-react["']/g)) {
        if (/\b(Gavel|Flag\w*|Landmark)\b/.test(m[1])) offenders.push(`${rel(f)}: ${m[1].trim()}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("the scan is not vacuous: it sees the frontend sources", () => {
    expect(sources.length).toBeGreaterThan(20);
    expect(files.some((f) => rel(f) === path.join("lib", "stages.ts"))).toBe(true);
  });
});

describe("<Footer /> (fails until implemented)", () => {
  it("shows the Supreme Court motto in real Devanagari text", () => {
    const { container } = render(<Footer />);
    expect(container.textContent).toContain("यतो धर्मस्ततो जयः");
  });
  it("shows the AI-generated disclaimer verbatim", () => {
    const { container } = render(<Footer />);
    expect(container.textContent).toContain("AI-generated drafts for counsel. Not legal advice.");
  });
  it("points the public to NALSA 15100", () => {
    const { container } = render(<Footer />);
    expect(container.textContent).toMatch(/NALSA/);
    expect(container.textContent).toMatch(/15100/);
  });
  it("contains no <img> of an emblem or flag (art is our own inline SVG)", () => {
    const { container } = render(<Footer />);
    for (const img of container.querySelectorAll("img")) expect(img.getAttribute("src") ?? "").not.toMatch(FORBIDDEN);
  });
});
