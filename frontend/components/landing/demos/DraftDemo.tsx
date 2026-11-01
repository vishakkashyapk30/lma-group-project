"use client";
// Draft: two grounds of the sample application as they read in the draft. A numbered authority opens the paragraph of
// the judgment it relies on, word for word, with whether it is still good law. A ground whose check failed stays in
// the draft, marked "Needs your check" with the reason, instead of being dropped or smoothed over.
import { X } from "lucide-react";
import { useState, type ReactElement, type ReactNode } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { cn } from "@/lib/utils";
import { GROUNDS } from "../sample";

/** Why G5 needs counsel, from the sample brief's open issues and the authority's good-law flag. */
const G5_REASON = "Its authority was found only after widening the search to all cheating offences, and a later judgment distinguished it. Read it before you rely on it.";

type Ground = (typeof GROUNDS)[number];

function GroundText({ g, open, onOpen }: { g: Ground; open: string | null; onOpen: (key: string) => void }): ReactNode {
  // "... [1] ... [2]." -> text with superscript buttons
  const parts = g.text.split(/\s\[(\d+)\]/);
  return parts.map((p, i) => {
    if (i % 2 === 0) return <span key={i}>{p}</span>;
    const n = Number(p);
    const key = `${g.id}-${n}`;
    const a = g.authorities[n - 1]!;
    return (
      <sup key={i} className="ml-0.5">
        <button
          type="button"
          aria-expanded={open === key}
          aria-controls="draft-source"
          aria-label={`Authority ${n}: ${a.citation}`}
          data-testid="draft-cite"
          onClick={() => onOpen(key)}
          className={cn("press inline-block min-w-[1.5rem] rounded-sm px-0.5 text-center font-mono text-[11px] font-medium leading-5 text-indigo underline-offset-2 hover:underline", open === key && "bg-indigo-tint")}
        >
          [{n}]
        </button>
      </sup>
    );
  });
}

export function DraftDemo({ className }: { className?: string }): ReactElement {
  const [open, setOpen] = useState<string | null>("G1-1");
  const [g, n] = open ? [GROUNDS.find((x) => open.startsWith(`${x.id}-`))!, Number(open.split("-")[1])] : [null, 0];
  const a = g ? g.authorities[n - 1]! : null;
  return (
    <div data-testid="draft-demo" className={cn("grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)]", className)}>
      <ol aria-label="Grounds from the sample draft" className="space-y-4 rounded-lg border border-line bg-cream p-4 sm:p-5">
        {GROUNDS.map((ground, i) => (
          <li
            key={ground.id}
            data-testid="draft-ground"
            data-check={ground.check}
            className={cn("relative", ground.check === "NEEDS_REVIEW" && "border-l-2 border-saffron pl-3")}
          >
            <p className="flex flex-wrap items-baseline gap-x-3 text-sm">
              <span className="font-semibold text-ink">Ground {i === 0 ? "A" : "B"}</span>
              {ground.check === "NEEDS_REVIEW" ? (
                <StatusBadge status="NEEDS_REVIEW" kind="openIssue" size="sm" testId="draft-needs-check" />
              ) : (
                <StatusBadge status="SUPPORTED" kind="claim" size="sm" label="Checked against its sources" testId="draft-checked" />
              )}
            </p>
            <p className="doc-text mt-1 text-[16px]"><GroundText g={ground} open={open} onOpen={(k) => setOpen((o) => (o === k ? null : k))} /></p>
            {ground.check === "NEEDS_REVIEW" ? <p className="mt-1 text-sm text-saffron-ink">{G5_REASON}</p> : null}
          </li>
        ))}
      </ol>
      <div id="draft-source" role="region" aria-label="Authority" aria-live="polite" className="min-h-[12rem] rounded-lg border border-line bg-cream p-4 sm:p-5">
        {a ? (
          <figure data-testid="draft-paragraph">
            <div className="flex items-start justify-between gap-3">
              <figcaption className="font-mono text-xs text-indigo">[{n}] {a.citation}</figcaption>
              <button type="button" onClick={() => setOpen(null)} aria-label="Close the authority" className="press grid size-7 shrink-0 place-items-center rounded-md text-ink-soft hover:bg-ink/[0.06]">
                <X aria-hidden className="size-4" />
              </button>
            </div>
            <blockquote className="doc-text mt-2 text-[16px] text-ink">{a.paragraph ?? "The paragraph is in the precedent library."}</blockquote>
            <p className="mt-2 text-sm"><StatusBadge status={a.goodLaw} kind="goodLaw" size="sm" testId="draft-good-law" /> <span className="text-ink-soft">{a.court}</span></p>
          </figure>
        ) : (
          <p className="text-sm text-ink-soft">Open a numbered authority to read its paragraph.</p>
        )}
      </div>
    </div>
  );
}
