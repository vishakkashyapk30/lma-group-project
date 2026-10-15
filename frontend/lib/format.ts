// Formatting helpers shared by every view: court-style dates, doc ids, citation tokens in brief arguments.
import type { Box, SelectedSource, SourceRef } from "./types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Parse "YYYY-MM-DD" as a UTC date (no timezone drift). Returns null for anything else. */
export function parseIsoDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return null;
  return new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
}

/** "2024-08-20" -> "20.08.2024", the style Indian court records use. Unparseable input is returned unchanged. */
export function formatCourtDate(iso: string | null | undefined): string {
  const d = parseIsoDate(iso);
  if (!d) return iso ?? "";
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}.${d.getUTCFullYear()}`;
}

/** "2024-08-20" -> "20 Aug 2024". */
export function formatDateLong(iso: string | null | undefined): string {
  const d = parseIsoDate(iso);
  if (!d) return iso ?? "";
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** Whole days from `start` to `end` (end exclusive of start), both "YYYY-MM-DD". */
export function daysBetween(start: string, end: string): number | null {
  const a = parseIsoDate(start);
  const b = parseIsoDate(end);
  if (!a || !b) return null;
  return Math.round((b.getTime() - a.getTime()) / 86_400_000);
}

/** ISO timestamp -> "14:05:09" (local time) for the live trace. Deterministic on the server: returns "" there. */
export function formatClock(ts: string | null | undefined): string {
  if (!ts || typeof window === "undefined") return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-IN", { hour12: false });
}

/** Indian digit grouping: 150000 -> "1,50,000". */
export function formatNumberIN(n: number): string {
  return new Intl.NumberFormat("en-IN").format(n);
}

/** "d1 (FIR)" -> "d1"; "d2" -> "d2"; null -> null. SourceRef.doc carries a label in the plan's examples. */
export function parseDocId(doc: string | null | undefined): string | null {
  if (!doc) return null;
  const m = /^\s*([^\s(]+)/.exec(doc);
  return m ? m[1] : null;
}

/** The label part of "d1 (FIR)" -> "FIR", or null. */
export function parseDocLabel(doc: string | null | undefined): string | null {
  if (!doc) return null;
  const m = /\(([^)]+)\)/.exec(doc);
  return m ? m[1] : null;
}

/** Normalise a SourceRef into the viewer's SelectedSource; null when it has no document page to show. */
export function toSelectedSource(source: SourceRef | null | undefined, origin?: string): SelectedSource | null {
  if (!source) return null;
  const docId = parseDocId(source.doc);
  if (!docId || source.page == null) return null;
  const box = Array.isArray(source.box) && source.box.length === 4 ? (source.box as Box) : null;
  return {
    doc_id: docId,
    page: source.page,
    box,
    quote: source.quote ?? null,
    quote_en: source.quote_en ?? null,
    lang: source.lang ?? null,
    route: source.route ?? null,
    origin: origin ?? null,
  };
}

/** Short human label for a source: "d2 · p.4", "date_calc", "chat turn 3". */
export function sourceLabel(source: SourceRef | null | undefined): string {
  if (!source) return "no source";
  const docId = parseDocId(source.doc);
  if (docId) {
    const label = parseDocLabel(source.doc);
    const page = source.page != null ? ` · p.${source.page}` : "";
    return `${label ? `${docId} ${label}` : docId}${page}`;
  }
  if (source.tool) return source.tool;
  if (source.chat) return `chat ${source.chat}`;
  return "no source";
}

/** A piece of a brief argument: plain text, a [F:field] fact reference or an [A:doc#para] authority reference. */
export type ArgumentSegment =
  | { type: "text"; text: string }
  | { type: "fact"; field: string; raw: string }
  | { type: "authority"; doc_id: string; para: number | null; raw: string }
  | { type: "claim"; claim_id: string; raw: string };

const TOKEN_RE = /\[(F|A|C):([^\]]+)\]/g;

/** Split "Co-accused-1 ... on 05.12.2024 [F:co_accused_bail] ... [A:DLHC-2022-1187#14]" into segments (plan §8.1). */
export function parseArgument(argument: string): ArgumentSegment[] {
  const out: ArgumentSegment[] = [];
  let last = 0;
  for (const m of argument.matchAll(TOKEN_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) out.push({ type: "text", text: argument.slice(last, idx) });
    const kind = m[1];
    const body = m[2].trim();
    if (kind === "F") out.push({ type: "fact", field: body, raw: m[0] });
    else if (kind === "C") out.push({ type: "claim", claim_id: body, raw: m[0] });
    else {
      const [doc, para] = body.split("#");
      out.push({ type: "authority", doc_id: doc.trim(), para: para ? Number(para) : null, raw: m[0] });
    }
    last = idx + m[0].length;
  }
  if (last < argument.length) out.push({ type: "text", text: argument.slice(last) });
  return out;
}

/** Argument text with the citation tokens removed (for previews, aria labels and exports). */
export function stripCitationTokens(argument: string): string {
  return argument.replace(TOKEN_RE, "").replace(/\s{2,}/g, " ").replace(/\s+([.,;:])/g, "$1").trim();
}

/** "parity_with_co_accused" -> "Parity with co-accused". */
export function humanize(id: string): string {
  const s = id.replace(/_/g, " ").replace(/\bco accused\b/gi, "co-accused").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Pluralise: plural(3, "day") -> "3 days". */
export function plural(n: number, word: string, pluralWord?: string): string {
  return `${formatNumberIN(n)} ${n === 1 ? word : (pluralWord ?? `${word}s`)}`;
}
