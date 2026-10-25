"use client";
// Brief and reply text with its citations as small numbered footnotes (plan §8.1): [F:field] facts, [A:doc#para] authorities and
// [C:id] claims. A number is a button: it opens the source in the side panel. The notes are listed under the text, and the
// citation text comes from corpus metadata; the model only wrote ids.
import { useMemo, type ReactElement } from "react";
import { fieldLabel } from "@/lib/fields";
import { parseArgument, toSelectedSource } from "@/lib/format";
import { sourceLabel } from "@/components/common/SourceChip";
import type { Authority, DossierFieldName, SourceRef } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

type Note =
  | { key: string; kind: "fact"; field: string; label: string }
  | { key: string; kind: "authority"; doc_id: string; para: number | null; label: string }
  | { key: string; kind: "claim"; claim_id: string; label: string };

type Part = { n: number; text?: undefined } | { text: string; n?: undefined };

export interface CitedProps {
  text: string;
  /** Authorities the text may cite, for their rendered citations. */
  authorities: Authority[];
  className?: string;
}

export function Cited({ text, authorities, className }: CitedProps): ReactElement {
  const ws = useWorkspace();
  const dossier = ws.data.dossier;
  const caseDocs = useMemo(() => new Set((ws.data.ingestion?.documents ?? []).map((d) => d.doc_id)), [ws.data.ingestion]);

  const { parts, notes } = useMemo(() => {
    const notes: Note[] = [];
    const indexOf = (note: Note): number => {
      const at = notes.findIndex((n) => n.key === note.key);
      if (at >= 0) return at + 1;
      notes.push(note);
      return notes.length;
    };
    const parts: Part[] = parseArgument(text).map((seg): Part => {
      if (seg.type === "text") return { text: seg.text };
      if (seg.type === "fact") {
        const source = dossier?.fields[seg.field as DossierFieldName]?.source ?? null;
        const where = source?.doc ? `, ${sourceLabel(source as SourceRef)}` : "";
        return { n: indexOf({ key: `F:${seg.field}`, kind: "fact", field: seg.field, label: `${fieldLabel(seg.field)}${where}` }) };
      }
      if (seg.type === "authority") {
        const found = authorities.find((a) => a.doc_id === seg.doc_id && (seg.para === null || a.para === seg.para));
        const label = `${found?.citation ?? seg.doc_id}${seg.para ? `, paragraph ${seg.para}` : ""}`;
        return { n: indexOf({ key: `A:${seg.doc_id}#${seg.para ?? ""}`, kind: "authority", doc_id: seg.doc_id, para: seg.para, label }) };
      }
      return { n: indexOf({ key: `C:${seg.claim_id}`, kind: "claim", claim_id: seg.claim_id, label: `Ground ${seg.claim_id}` }) };
    });
    return { parts, notes };
  }, [text, authorities, dossier]);

  const open = (note: Note) => {
    if (note.kind === "claim") {
      ws.focusItem("brief", note.claim_id);
      return;
    }
    ws.clearSource();
    if (note.kind === "fact") {
      const source = dossier?.fields[note.field as DossierFieldName]?.source ?? null;
      ws.openDetail({ kind: "field", name: note.field as DossierFieldName });
      if (toSelectedSource(source)) ws.selectSource(source, note.field);
      return;
    }
    const found = authorities.find((a) => a.doc_id === note.doc_id && (note.para === null || a.para === note.para));
    ws.openDetail({ kind: "authority", authority: found ?? { doc_id: note.doc_id, para: note.para ?? 0, good_law: "UNKNOWN" } });
    if (caseDocs.has(note.doc_id)) ws.selectSource({ doc_id: note.doc_id, page: note.para ?? 1, origin: note.label });
  };

  return (
    <div className={className}>
      <p className="doc-text text-ink">
        {parts.map((p, i) =>
          p.n !== undefined ? (
            <sup key={i} className="ml-px mr-0.5">
              <button
                type="button"
                onClick={() => open(notes[p.n - 1])}
                title={notes[p.n - 1].label}
                aria-label={`Source ${p.n}: ${notes[p.n - 1].label}`}
                className="rounded-sm px-0.5 font-sans text-xs font-semibold text-maroon hover:bg-maroon/[0.08]"
              >
                {p.n}
              </button>
            </sup>
          ) : (
            <span key={i}>{p.text}</span>
          ),
        )}
      </p>
      {notes.length > 0 ? (
        <ol aria-label="Sources" className={cn("mt-3 list-decimal space-y-0.5 pl-5 text-sm text-ink-soft marker:text-ink-muted")}>
          {notes.map((n) => (
            <li key={n.key}>
              <button type="button" onClick={() => open(n)} className="rounded-sm text-left underline-offset-4 hover:text-maroon hover:underline">
                {n.label}
              </button>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

export default Cited;
