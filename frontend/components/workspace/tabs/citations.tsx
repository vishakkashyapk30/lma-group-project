"use client";
// Brief and sparring text with its citations: [F:field] fact chips, [A:doc#para] authority chips and [C:id] claim chips
// (plan §8.1), plus the list of authorities with transfer and good-law badges (plan §5.3, §5.4). Citation text comes from
// corpus metadata; the model only wrote IDs.
import { BookMarked, Link2, ScrollText } from "lucide-react";
import type { ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { fieldLabel } from "@/lib/fields";
import { parseArgument, toSelectedSource } from "@/lib/format";
import type { Authority, DossierFieldName } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCaseData, useSelectedSource, useStageNav } from "@/lib/workspace";

/** Id of an authority row, so a chip in the text can scroll to it. */
export function authorityDomId(scope: string, docId: string, para: number | null): string {
  return `ws-authority-${scope}-${docId}-${para ?? 0}`;
}

const chipBase =
  "mx-0.5 inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 align-baseline font-mono text-[11px] leading-tight transition-colors duration-fast";

export interface ArgumentTextProps {
  argument: string;
  /** Scope for authority row ids: a ground id or an objection id. */
  scope: string;
  /** Underline the text in maroon: the claim needs counsel's review. */
  needsReview?: boolean;
  className?: string;
}

export function ArgumentText({ argument, scope, needsReview = false, className }: ArgumentTextProps): ReactElement {
  const data = useCaseData();
  const { selectSource } = useSelectedSource();
  const { focusItem } = useStageNav();
  const caseDocs = new Set((data.ingestion?.documents ?? []).map((d) => d.doc_id));

  const onFact = (field: string) => {
    const source = data.dossier?.fields[field as DossierFieldName]?.source ?? null;
    if (toSelectedSource(source)) selectSource(source, field);
    else focusItem("dossier", field);
  };

  const onAuthority = (docId: string, para: number | null) => {
    if (caseDocs.has(docId)) {
      selectSource({ doc_id: docId, page: para ?? 1, origin: `${docId}#${para ?? ""}` });
      return;
    }
    const el = document.getElementById(authorityDomId(scope, docId, para));
    if (el) {
      el.scrollIntoView({ block: "nearest", behavior: "auto" });
      el.focus({ preventScroll: true });
    }
  };

  return (
    <p
      data-testid={needsReview ? "needs-review-marker" : undefined}
      className={cn(
        "text-[0.95rem] leading-7 text-ink",
        needsReview && "underline decoration-maroon decoration-2 underline-offset-[5px]",
        className,
      )}
    >
      {parseArgument(argument).map((seg, i) => {
        if (seg.type === "text") return <span key={i}>{seg.text}</span>;
        if (seg.type === "fact") {
          return (
            <button
              key={i}
              type="button"
              onClick={() => onFact(seg.field)}
              aria-label={`Fact: ${fieldLabel(seg.field)}. Show its source`}
              className={cn(chipBase, "border-maroon/40 bg-maroon/[0.06] text-maroon no-underline hover:bg-maroon hover:text-cream")}
            >
              <ScrollText aria-hidden className="size-3" />F:{seg.field}
            </button>
          );
        }
        if (seg.type === "authority") {
          return (
            <button
              key={i}
              type="button"
              onClick={() => onAuthority(seg.doc_id, seg.para)}
              aria-label={`Authority ${seg.doc_id}${seg.para ? `, paragraph ${seg.para}` : ""}. Show the citation`}
              className={cn(chipBase, "border-indigo/45 bg-indigo/[0.06] text-indigo no-underline hover:bg-indigo hover:text-cream")}
            >
              <BookMarked aria-hidden className="size-3" />A:{seg.doc_id}{seg.para ? `#${seg.para}` : ""}
            </button>
          );
        }
        return (
          <button
            key={i}
            type="button"
            onClick={() => focusItem("brief", seg.claim_id)}
            aria-label={`Claim ${seg.claim_id}. Go to it`}
            className={cn(chipBase, "border-line-strong/60 bg-cream text-ink-soft no-underline hover:border-maroon hover:text-maroon")}
          >
            <Link2 aria-hidden className="size-3" />C:{seg.claim_id}
          </button>
        );
      })}
    </p>
  );
}

export interface AuthorityListProps {
  authorities: Authority[];
  scope: string;
  className?: string;
}

/** The cited authorities: rendered citation, transfer flag, good-law flag. */
export function AuthorityList({ authorities, scope, className }: AuthorityListProps): ReactElement | null {
  if (authorities.length === 0) return null;
  return (
    <ul aria-label="Authorities cited" className={cn("space-y-1.5", className)}>
      {authorities.map((a) => (
        <li
          key={`${a.doc_id}#${a.para}`}
          id={authorityDomId(scope, a.doc_id, a.para)}
          tabIndex={-1}
          className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-line bg-parchment/60 px-2 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-maroon"
        >
          <span className="min-w-0 flex-1 text-ink">
            {a.citation ?? a.doc_id} <span className="cite text-ink-soft">¶{a.para}</span>
            {a.sc_root ? <span className="block text-xs text-ink-muted">Rooted in {a.sc_root}</span> : null}
          </span>
          {a.transfer ? <StatusBadge status={a.transfer} kind="transfer" size="sm" testId="authority-badge" /> : null}
          <StatusBadge status={a.good_law} kind="goodLaw" size="sm" testId="authority-badge" />
        </li>
      ))}
    </ul>
  );
}
