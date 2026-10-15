// Word-level text diff (LCS) for the IPC<->BNS bridge (plan §5.4). Statute sections are short, so O(n*m) is fine.
import type { DiffSegment } from "./types";

function tokenize(text: string): string[] {
  // Keep whitespace attached so that joining the segments reproduces the text.
  return text.match(/\S+\s*/g) ?? [];
}

/** Diff `oldText` -> `newText` into equal / delete / insert segments (adjacent segments of one kind are merged). */
export function diffWords(oldText: string, newText: string): DiffSegment[] {
  const a = tokenize(oldText);
  const b = tokenize(newText);
  const n = a.length;
  const m = b.length;
  const norm = (s: string) => s.trim().toLowerCase();
  // lcs[i][j] = LCS length of a[i..] and b[j..]
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] = norm(a[i]) === norm(b[j]) ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const out: DiffSegment[] = [];
  const push = (op: DiffSegment["op"], text: string) => {
    const last = out[out.length - 1];
    if (last && last.op === op) last.text += text;
    else out.push({ op, text });
  };
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (norm(a[i]) === norm(b[j])) {
      push("equal", b[j]);
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      push("delete", a[i++]);
    } else {
      push("insert", b[j++]);
    }
  }
  while (i < n) push("delete", a[i++]);
  while (j < m) push("insert", b[j++]);
  return out;
}

/** True when the diff has no insertions or deletions. */
export function isSameText(segments: readonly DiffSegment[]): boolean {
  return segments.every((s) => s.op === "equal");
}

/** A unified-diff style string ("- old" / "+ new" lines) for the concordance edge's text_diff field. */
export function toUnifiedDiff(oldRef: string, newRef: string, segments: readonly DiffSegment[]): string {
  const removed = segments.filter((s) => s.op === "delete").map((s) => s.text.trim()).filter(Boolean);
  const added = segments.filter((s) => s.op === "insert").map((s) => s.text.trim()).filter(Boolean);
  if (!removed.length && !added.length) return `--- ${oldRef}\n+++ ${newRef}\n(no textual change)`;
  return [`--- ${oldRef}`, `+++ ${newRef}`, ...removed.map((r) => `- ${r}`), ...added.map((a) => `+ ${a}`)].join("\n");
}
