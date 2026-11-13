// What the draft left out (strict abstention, X4 of the chosen architecture): the brief's `withheld` list, per ground, read out in
// plain words. The checker's reasons come from PROBLEM_WORDS in src/vakeel_sahayak/agents/vakeel/work.py; scores in brackets are dropped.
import { FACTOR_LABELS } from "./labels";
import type { BailBrief, Factor, WithheldGround } from "./types";

/** The checker's phrase (agents/vakeel/work.py PROBLEM_WORDS) and how counsel reads it. */
const PLAIN: Array<[string, string]> = [
  ["not supported by the dossier quote", "not supported by the record"],
  ["not supported by the cited paragraph", "the cited paragraph does not say this"],
  ["not supported by its sources", "not supported by the record or the cited judgment"],
  ["cites an overruled authority", "relies on a judgment that has been overruled"],
  ["cites an authority that was not retrieved", "cites a judgment that was not among the sources found"],
  ["cites a document the corpus does not know", "cites a judgment that is not in the library"],
  ["cites no fact or authority", "cites no fact or authority"],
  ["has a malformed [f:...] or [a:...] reference", "its reference to a source could not be read"],
  ["predicts an outcome", "predicts the outcome"],
  ["names a case or a citation instead of an id marker", "names a case that could not be matched to the library"],
  ["could not be checked", "could not be checked"],
  ["flagged by the model's own re-reading (no outside check)", "flagged on re-reading, with no outside check"],
  ["is not a span of the facts text", "is not in the words of the record"],
  ["mixes a case fact and a legal principle", "mixes a fact of the case with a legal principle"],
];

const SILENT = "only says the record is silent";

/** The factor's name for a sentence ("parity with co-accused"), or null for an unknown factor. */
function factorWords(factor: string | null | undefined): string | null {
  const label = factor ? FACTOR_LABELS[factor as Factor] : undefined;
  return label ? label.charAt(0).toLowerCase() + label.slice(1) : null;
}

/**
 * Why a sentence was left out, in plain words: "not supported by the record", "the record is silent on trial delay".
 * Several problems are joined with "; ". A reason the table does not know is returned as it came, without its bracketed scores.
 */
export function plainReason(reason: string, factor?: string | null): string {
  const text = reason.trim();
  if (text.toLowerCase().startsWith(SILENT)) {
    const on = factorWords(factor);
    return on ? `the record is silent on ${on}` : "the record is silent on this point";
  }
  let rest = text;
  const parts: string[] = [];
  while (rest) {
    if (rest.startsWith("(")) break; // the checker's detail: scores and ids in brackets, "(fact support 0.31; ...)"
    const lower = rest.toLowerCase();
    const hit = PLAIN.find(([raw]) => lower.startsWith(raw));
    if (!hit) {
      parts.push(rest.replace(/\s*\(.*$/, "").trim() || rest);
      break;
    }
    parts.push(hit[1]);
    rest = rest.slice(hit[0].length).replace(/^\s*,\s*/, "").trim();
  }
  return parts.length ? [...new Set(parts)].join("; ") : text;
}

/** "Not supported by the record." for display under a sentence. */
export function reasonSentence(reason: string, factor?: string | null): string {
  const p = plainReason(reason, factor);
  return `${p.charAt(0).toUpperCase()}${p.slice(1)}${/[.!?]$/.test(p) ? "" : "."}`;
}

/** The withheld sentences of one ground that is in the brief (empty when nothing was left out). */
export function withheldFor(brief: BailBrief, groundId: string): WithheldGround | null {
  const group = (brief.withheld ?? []).find((w) => w.ground === groundId && w.sentences.length > 0);
  return group ?? null;
}

/** Grounds that lost every sentence, so they are not in the brief: counsel drafts them. */
export function droppedGrounds(brief: BailBrief): WithheldGround[] {
  const present = new Set(brief.grounds.map((g) => g.id));
  return (brief.withheld ?? []).filter((w) => w.sentences.length > 0 && (w.dropped || !present.has(w.ground)));
}
