"use client";
// Likely objections (plan §9): what the prosecution is likely to say, each with Vakeel's reply, as question and answer pairs
// in an accordion. Only the ones with no answer yet start open. An objection with no answer must be resolved with a note before
// the draft can be approved for export.
import { CheckCircle2, ChevronDown, Undo2 } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { fieldLabel } from "@/lib/fields";
import { humanize, plural, toSelectedSource } from "@/lib/format";
import { FACTOR_LABELS } from "@/lib/labels";
import type { DossierFieldName, Factor, Objection, ObjectionGround } from "@/lib/types";
import { cn } from "@/lib/utils";
import { checklistKey, useCaseData, useGates, useStageNav, useWorkspace } from "@/lib/workspace";
import { Cited } from "./citations";
import { focusClass, focusDomId, SectionTitle, stepState, useFocusItem } from "./shared";

/** What an objection rests on: dossier facts open their page; bank paragraphs and statutes are named. */
function RestsOn({ grounds }: { grounds: ObjectionGround[] }): ReactElement | null {
  const ws = useWorkspace();
  if (grounds.length === 0) return null;
  return (
    <ul aria-label="What this objection rests on" className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-sm text-ink-soft">
      {grounds.map((g, i) => {
        if (g.fact) {
          const name = g.fact as DossierFieldName;
          const source = ws.data.dossier?.fields[name]?.source ?? null;
          return (
            <li key={i}>
              <button
                type="button"
                onClick={() => {
                  ws.clearSource();
                  ws.openDetail({ kind: "field", name });
                  if (toSelectedSource(source)) ws.selectSource(source, name);
                }}
                aria-label={`Fact: ${fieldLabel(name)}. Show its source`}
                className="rounded-sm text-maroon underline-offset-4 hover:underline"
              >
                {fieldLabel(name)}
              </button>
            </li>
          );
        }
        return <li key={i}>{[g.store, g.doc_id, g.para != null ? `¶${g.para}` : null].filter(Boolean).join(" ")}</li>;
      })}
    </ul>
  );
}

function ResolveControls({ objection }: { objection: Objection }): ReactElement {
  const toast = useToast();
  const { resolutions, resolveItem, unresolveItem } = useGates();
  const key = checklistKey("UNANSWERED", objection.id);
  const resolution = resolutions.resolved[key];
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const noteRef = useRef<HTMLInputElement | null>(null);
  const openerRef = useRef<HTMLButtonElement | null>(null);
  const was = useRef(false);

  useEffect(() => {
    if (open) noteRef.current?.focus();
    else if (was.current) openerRef.current?.focus();
    was.current = open;
  }, [open]);

  if (resolution) {
    return (
      <div className="flex flex-wrap items-center gap-2" data-print-hide>
        <span className="inline-flex items-center gap-1 text-sm font-medium text-neem">
          <CheckCircle2 aria-hidden className="size-4" /> Resolved by you
          {resolution.note && resolution.note !== "Accepted by counsel" ? <span className="font-normal text-ink-soft">: {resolution.note}</span> : null}
        </span>
        <Button size="sm" variant="ghost" onClick={() => unresolveItem(key)} aria-label={`Undo resolving ${objection.id}`}>
          <Undo2 aria-hidden /> Undo
        </Button>
      </div>
    );
  }
  if (open) {
    const id = `spar-${objection.id}-note`;
    return (
      <div className="space-y-2" data-print-hide>
        <label htmlFor={id} className="block text-sm font-medium text-ink-soft">How will you meet this objection?</label>
        <Input id={id} ref={noteRef} value={note} onChange={(e) => setNote(e.target.value)} placeholder="For example: will answer orally with the custody certificate" />
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => {
              resolveItem(key, note.trim() || "Accepted by counsel");
              setOpen(false);
              toast({ title: "Marked as resolved", action: { label: "Undo", onClick: () => unresolveItem(key) } });
            }}
          >
            Mark as resolved
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
        </div>
      </div>
    );
  }
  return (
    <div data-print-hide>
      <Button ref={openerRef} size="sm" variant="secondary" onClick={() => setOpen(true)} aria-label={`Resolve unanswered objection ${objection.id}`}>
        <CheckCircle2 aria-hidden /> Resolve with a note
      </Button>
    </div>
  );
}

function ObjectionItem({ objection, focusedId }: { objection: Objection; focusedId: string | null }): ReactElement {
  const { resolutions } = useGates();
  const { focusItem } = useStageNav();
  const domId = focusDomId("spar", objection.id);
  const unanswered = objection.verdict === "UNANSWERED";
  const resolved = Boolean(resolutions.resolved[checklistKey("UNANSWERED", objection.id)]);
  const [open, setOpen] = useState(unanswered && !resolved);
  const factor = FACTOR_LABELS[objection.factor as Factor] ?? humanize(objection.factor);
  const general = objection.against === "general";
  const focused = focusedId === objection.id;
  useEffect(() => {
    if (focused) setOpen(true);
  }, [focused]);

  return (
    <li
      id={domId}
      data-testid="spar-objection"
      data-objection={objection.id}
      data-verdict={objection.verdict ?? undefined}
      tabIndex={-1}
      aria-labelledby={`${domId}-title`}
      className={cn("scroll-mt-4 outline-none focus-visible:ring-2 focus-visible:ring-maroon", focusClass(focusedId, objection.id))}
    >
      <h4 className="font-sans text-base font-normal">
        <button
          type="button"
          id={`${domId}-title`}
          aria-expanded={open}
          aria-controls={`${domId}-body`}
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-start gap-3 py-3.5 text-left"
        >
          <span className="min-w-0 flex-1">
            <span className="sr-only">{objection.id}: </span>
            <span className="block text-ink">{objection.objection}</span>
            <span className="mt-0.5 block text-sm text-ink-muted">{factor}</span>
          </span>
          <span className="shrink-0 pt-0.5">
            {objection.verdict ? <StatusBadge status={objection.verdict} kind="verdict" size="sm" /> : <span className="text-sm text-ink-muted">Not judged yet</span>}
          </span>
          <ChevronDown aria-hidden className={cn("mt-1 size-4 shrink-0 text-ink-soft transition-transform duration-fast", open && "rotate-180")} />
        </button>
      </h4>
      {open ? (
        <div id={`${domId}-body`} className="space-y-4 pb-5">
          <p className="text-sm text-ink-muted">
            {general ? (
              "General objection."
            ) : (
              <>
                Against{" "}
                <button type="button" onClick={() => focusItem("brief", objection.against)} className="rounded-sm text-maroon underline-offset-4 hover:underline" aria-label={`Go to ground ${objection.against}`}>
                  ground {objection.against}
                </button>
                .
              </>
            )}
          </p>
          <div className="border-l-2 border-line-strong pl-4">
            <p className="text-sm font-medium text-ink-soft">Reply</p>
            {objection.reply ? (
              <Cited text={objection.reply.text} authorities={objection.reply.authorities} className="mt-1" />
            ) : (
              <p className="mt-1 text-ink-soft">No reply could be drafted that the record supports.</p>
            )}
          </div>
          {objection.reason ? <p className="text-sm text-ink-soft">{objection.reason}</p> : null}
          <RestsOn grounds={objection.grounds} />
          {unanswered ? <ResolveControls objection={objection} /> : null}
        </div>
      ) : null}
    </li>
  );
}

export function ObjectionsSection(): ReactElement | null {
  const data = useCaseData();
  const spar = data.spar;
  const focused = useFocusItem("spar", Boolean(spar));

  const state = stepState({
    resource: "spar", noun: "likely objections", loading: data.loading.spar, error: data.errors.spar, hasData: Boolean(spar),
    onRetry: () => void data.refresh(["spar"]),
    emptyTitle: "No likely objections yet",
    emptyBody: "They are worked out once the draft exists.",
  });
  if (state || !spar) return data.loading.spar || data.errors.spar ? (
    <section aria-labelledby="spar-list">
      <SectionTitle id="spar-list">Likely objections</SectionTitle>
      <div className="mt-3">{state}</div>
    </section>
  ) : null;

  const objections = spar.objections;
  const count = (v: Objection["verdict"]) => objections.filter((o) => o.verdict === v).length;

  return (
    <section aria-labelledby="spar-list">
      <SectionTitle id="spar-list">Likely objections</SectionTitle>
      {objections.length === 0 ? (
        <p className="mt-2 text-ink-soft">No objection came up that could be tied to the record, a statute or a fact.</p>
      ) : (
        <>
          <p className="mt-1 text-ink-soft" aria-live="polite">
            {plural(objections.length, "objection")}: {count("ANSWERED")} answered, {count("PARTLY")} partly answered, {count("UNANSWERED")} not answered yet.
          </p>
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {objections.map((o) => (
              <ObjectionItem key={o.id} objection={o} focusedId={focused?.id ?? null} />
            ))}
          </ul>
        </>
      )}
      {spar.discarded.length > 0 ? (
        <details className="mt-4 text-sm">
          <summary className="inline-flex cursor-pointer select-none rounded-sm font-medium text-ink-soft underline-offset-4 hover:text-ink hover:underline">
            {plural(spar.discarded.length, "objection")} left out
          </summary>
          <p className="mt-2 text-ink-soft">These could not be tied to a source, so they were left out.</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-soft">
            {spar.discarded.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

export default ObjectionsSection;
