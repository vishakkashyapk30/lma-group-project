"use client";
// A ground read sentence by sentence (Draft grounds, "By sentence"): each sentence with its type (case fact, legal principle, not
// in the record) and what supports it. A cited fact shows its status in the facts and opens its page; a cited authority shows
// how later cases treat it and opens it. The type comes from the sentence's own markers (lib/factorGaps.ts), as in the M6a metric.
import type { ReactElement } from "react";
import { briefSentences, SENTENCE_KIND_LABELS, type BriefSentence, type SentenceKind } from "@/lib/factorGaps";
import { fieldLabel } from "@/lib/fields";
import { plural, stripCitationTokens } from "@/lib/format";
import { getStatusMeta } from "@/lib/status";
import type { Authority, BailBrief, DossierFieldName } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCaseData } from "@/lib/workspace";
import { useSourceOpener } from "./citations";

const KIND_TONE: Record<SentenceKind, string> = {
  case_fact: "text-ink-soft",
  legal: "text-indigo",
  not_in_record: "text-sindoor",
  absence: "text-haldi",
  note: "text-ink-muted",
};

function Support({ sentence, authorities }: { sentence: BriefSentence; authorities: Authority[] }): ReactElement {
  const { dossier } = useCaseData();
  const { openFact, openAuthority } = useSourceOpener(authorities);
  if (sentence.kind === "not_in_record") return <span>It cites no fact and no authority.</span>;
  if (sentence.kind === "note") return <span>A qualification added to the ground.</span>;
  return (
    <span className="inline-flex flex-wrap gap-x-3 gap-y-0.5">
      {sentence.facts.map((f) => {
        const status = dossier?.fields[f as DossierFieldName]?.status;
        return (
          <span key={`F:${f}`}>
            <button type="button" onClick={() => openFact(f)} className="rounded-sm text-maroon underline-offset-4 hover:underline" aria-label={`Fact: ${fieldLabel(f)}. Show its source`}>
              {fieldLabel(f)}
            </button>
            {status ? <span className="text-ink-muted"> ({getStatusMeta(status, "field").label.toLowerCase()})</span> : null}
          </span>
        );
      })}
      {sentence.authorities.map((a) => {
        const found = authorities.find((x) => x.doc_id === a.doc_id && (a.para === null || x.para === a.para));
        const name = `${found?.citation ?? a.doc_id}${a.para ? `, paragraph ${a.para}` : ""}`;
        return (
          <span key={`A:${a.doc_id}#${a.para ?? ""}`}>
            <button type="button" onClick={() => openAuthority(a.doc_id, a.para, name)} className="rounded-sm text-maroon underline-offset-4 hover:underline" aria-label={`Authority: ${name}. Open it`}>
              {name}
            </button>
            {found && found.good_law !== "OK" ? <span className="text-ink-muted"> ({getStatusMeta(found.good_law, "goodLaw").label.toLowerCase()})</span> : null}
          </span>
        );
      })}
    </span>
  );
}

export function SentenceList({ argument, authorities }: { argument: string; authorities: Authority[] }): ReactElement {
  const sentences = briefSentences(argument);
  return (
    <ol aria-label="Sentences" className="mt-3 list-none space-y-3 p-0">
      {sentences.map((s, i) => (
        <li key={i} data-testid="brief-sentence" data-kind={s.kind} className="border-l-2 border-line pl-3">
          <p className="doc-text m-0 text-ink">{stripCitationTokens(s.text)}</p>
          <p className="m-0 mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-sm">
            <span className={cn("font-medium", KIND_TONE[s.kind])}>{SENTENCE_KIND_LABELS[s.kind]}</span>
            <span className="text-ink-soft">
              <Support sentence={s} authorities={authorities} />
            </span>
          </p>
        </li>
      ))}
    </ol>
  );
}

/** One line counting the sentence types across the draft. */
export function sentenceSummary(brief: BailBrief): string {
  const all = brief.grounds.flatMap((g) => briefSentences(g.argument));
  const n = (k: SentenceKind) => all.filter((s) => s.kind === k).length;
  const parts = [
    plural(n("case_fact"), "case fact"),
    plural(n("legal"), "legal principle"),
    `${n("not_in_record")} not in the record`,
  ];
  if (n("absence")) parts.push(`${n("absence")} saying the record is silent`);
  return `${plural(all.length - n("note"), "sentence")}: ${parts.join(", ")}.`;
}

export default SentenceList;
