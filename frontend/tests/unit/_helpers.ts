// Shared helpers for unit tests: parse lib/types.ts unions and the Python enums (read-only, no product logic).
import fs from "node:fs";
import path from "node:path";

export const FRONTEND_ROOT = path.resolve(__dirname, "../..");
export const REPO_ROOT = path.resolve(FRONTEND_ROOT, "..");

const read = (p: string) => fs.readFileSync(p, "utf8");

/** Members of `export type <name> = "A" | "B" ...;` in lib/types.ts. */
export function tsUnion(name: string): string[] {
  const src = read(path.join(FRONTEND_ROOT, "lib/types.ts"));
  const m = src.match(new RegExp(`export type ${name}\\s*=([^;]+);`));
  if (!m) throw new Error(`type ${name} not found in lib/types.ts`);
  // RECONCILED: lib/types.ts declares each union as `(typeof X_NAMES)[number]` over an `as const` array (so it is iterable);
  // the helper now resolves that form as well as a literal union. The member check itself is unchanged.
  const ref = m[1].match(/typeof\s+([A-Za-z0-9_]+)/);
  let body = m[1];
  if (ref) {
    const a = src.match(new RegExp(`export const ${ref[1]}\\s*(?::[^=]+)?=\\s*\\[([^\\]]*)\\]`));
    if (!a) throw new Error(`const ${ref[1]} not found in lib/types.ts`);
    body = a[1];
  }
  return [...body.matchAll(/"([^"]+)"/g)].map((x) => x[1]);
}

/** Values of `class <name>(str, Enum)` members in src/vakeel_sahayak/schemas/enums.py. */
export function pyEnum(name: string): string[] {
  const src = read(path.join(REPO_ROOT, "src/vakeel_sahayak/schemas/enums.py"));
  const lines = src.split("\n");
  const start = lines.findIndex((l) => new RegExp(`^class ${name}\\(`).test(l));
  if (start < 0) throw new Error(`enum ${name} not found in enums.py`);
  const out: string[] = [];
  for (let i = start + 1; i < lines.length; i++) {
    if (/^class /.test(lines[i])) break;
    const m = lines[i].match(/^\s+[A-Za-z0-9_]+\s*=\s*"([^"]*)"/);
    if (m) out.push(m[1]);
  }
  return out;
}
