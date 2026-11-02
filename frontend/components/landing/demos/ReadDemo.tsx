"use client";
// Read: every fact of the sample case carries the words it was read from. Open a row (tap, click, Enter or Space) or pull
// it down with the mouse or a pen: the row resists like a spring and, pulled far enough, opens on the Hindi sentence of
// the FIR beside its English line, with the value marked in both. On touch a vertical pull stays a page scroll (the
// browser cancels the drag), so a finger taps instead: no scroll is taken over.
import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";
import { SPRINGS, SpringValue, prefersReducedMotion, rubberband, useDrag } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { READ_FACTS } from "../sample";

/** The part of each quote to mark: the value as the FIR writes it. */
const MARK: Record<string, string> = { fir: "112/2024", offence_date: "10.08.2024", sections: "318(4), 316(2)", parties: "Accused-1" };

function marked(text: string, needle: string): ReactNode {
  const at = text.indexOf(needle);
  if (at < 0) return text;
  return (
    <>
      {text.slice(0, at)}
      <mark className="rounded-xs bg-indigo-pale px-0.5 text-ink">{needle}</mark>
      {text.slice(at + needle.length)}
    </>
  );
}

/** Pull distance (px, before resistance) that opens a row. */
const OPEN_AT = 56;

function Row({ fact, defaultOpen }: { fact: (typeof READ_FACTS)[number]; defaultOpen?: boolean }): ReactElement {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  const head = useRef<HTMLButtonElement>(null);
  const value = useRef<SpringValue | null>(null);
  const raw = useRef(0);
  useEffect(() => {
    value.current = new SpringValue(0, (y) => {
      const el = head.current;
      if (el) el.style.transform = y === 0 ? "" : `translateY(${y}px)`;
    });
    return () => value.current?.stop();
  }, []);
  useDrag(head, {
    axis: "y",
    onStart: () => value.current?.stop(),
    onMove: (d) => {
      raw.current = d;
      if (!prefersReducedMotion()) value.current?.set(rubberband(Math.max(0, d), 28));
    },
    onEnd: ({ velocity }) => {
      value.current?.to(0, { spring: SPRINGS.timeline, velocity, reduced: prefersReducedMotion() });
      if (raw.current > OPEN_AT || velocity > 600) setOpen(true);
      else if (raw.current < -OPEN_AT || velocity < -600) setOpen(false);
    },
  });
  const id = `read-${fact.key}`;
  return (
    <li data-testid="read-row" data-open={open || undefined} className="border-b border-line last:border-b-0">
      <button
        ref={head}
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full select-none items-baseline gap-3 py-3 text-left"
      >
        <span className="w-36 shrink-0 text-sm text-ink-soft">{fact.label}</span>
        <span className="min-w-0 flex-1 font-medium text-ink">{fact.value}</span>
        <span className="hidden shrink-0 rounded-sm bg-indigo-tint px-1 py-0.5 font-mono text-[11px] text-indigo sm:inline">FIR p.{fact.page}</span>
        <ChevronDown aria-hidden className={cn("size-4 shrink-0 self-center text-ink-muted transition-transform duration-base", open && "rotate-180")} />
        <span className="sr-only">{open ? "Hide the words" : "Show the words it was read from"}</span>
      </button>
      <div id={id} className="grid transition-[grid-template-rows] duration-base ease-standard" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}>
        <div className="overflow-hidden">
          <figure data-testid="read-quote" className="mb-3 border-l-2 border-indigo pl-3">
            <blockquote lang="hi" className="doc-text text-[16px] text-ink">{marked(fact.quote, MARK[fact.key] ?? "")}</blockquote>
            <p className="mt-1 text-sm text-ink-soft">{marked(fact.quoteEn, MARK[fact.key] ?? "")}</p>
            <figcaption className="mt-1 font-mono text-[11px] text-ink-muted">FIR No. 112/2024, page {fact.page}, read by OCR from a scan</figcaption>
          </figure>
        </div>
      </div>
    </li>
  );
}

export function ReadDemo({ className }: { className?: string }): ReactElement {
  return (
    <div data-testid="read-demo" className={cn("rounded-lg bg-cream p-4 text-ink sm:p-5", className)}>
      <p className="mb-1 text-sm font-semibold text-ink">Facts from the FIR</p>
      <ul aria-label="Facts from the FIR, each with its source">
        {READ_FACTS.map((f, i) => (
          <Row key={f.key} fact={f} defaultOpen={i === 0} />
        ))}
      </ul>
    </div>
  );
}
