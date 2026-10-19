"use client";
// Spar tab (plan §9): Abhiyojak's objections, each paired with Vakeel's reply, what grounds the objection, and the verdict.
// UNANSWERED objections go to counsel as NEEDS_REVIEW and must be resolved before Gate 2.
import { CheckCircle2, ScrollText, Undo2 } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement } from "react";
import { AgentSignature } from "@/components/agents/AgentSignature";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fieldLabel } from "@/lib/fields";
import { humanize, plural, toSelectedSource } from "@/lib/format";
import { FACTOR_LABELS } from "@/lib/labels";
import type { DossierFieldName, Factor, Objection, ObjectionGround } from "@/lib/types";
import { cn } from "@/lib/utils";
import { checklistKey, useAgentActivity, useCaseData, useGates, useSelectedSource, useStageNav } from "@/lib/workspace";
import { ArgumentText, AuthorityList } from "./citations";
import { focusClass, focusDomId, SectionTitle, TabHeader, tabState, TabShell, useFocusItem } from "./shared";

export interface SparTabProps {
  caseId: string;
  className?: string;
}

function GroundsChips({ grounds }: { grounds: ObjectionGround[] }): ReactElement | null {
  const data = useCaseData();
  const { selectSource } = useSelectedSource();
  const { focusItem } = useStageNav();
  if (grounds.length === 0) return null;
  return (
    <ul aria-label="What this objection rests on" className="flex flex-wrap gap-1.5">
      {grounds.map((g, i) => {
        if (g.fact) {
          const source = data.dossier?.fields[g.fact as DossierFieldName]?.source ?? null;
          return (
            <li key={i}>
              <button
                type="button"
                onClick={() => (toSelectedSource(source) ? selectSource(source, g.fact ?? undefined) : focusItem("dossier", g.fact ?? ""))}
                aria-label={`Dossier fact: ${fieldLabel(g.fact)}. Show its source`}
                className="inline-flex items-center gap-1 rounded-sm border border-maroon/40 bg-maroon/[0.06] px-1.5 py-0.5 font-mono text-[11px] text-maroon transition-colors duration-fast hover:bg-maroon hover:text-cream"
              >
                <ScrollText aria-hidden className="size-3" />F:{g.fact}
              </button>
            </li>
          );
        }
        const text = [g.store, g.doc_id, g.para != null ? `¶${g.para}` : null].filter(Boolean).join(" · ");
        return (
          <li key={i}>
            <span title="Objection bank, refusal reasoning or statute" className="inline-flex rounded-sm border border-indigo/45 bg-indigo/[0.06] px-1.5 py-0.5 font-mono text-[11px] text-indigo">
              {text}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function ResolveControls({ objection }: { objection: Objection }): ReactElement {
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
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-neem">
          <CheckCircle2 aria-hidden className="size-3.5" /> Resolved by counsel
          {resolution.note ? <span className="font-normal text-ink-soft">: {resolution.note}</span> : null}
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
        <label htmlFor={id} className="block text-xs font-semibold text-ink-soft">How will you meet {objection.id}?</label>
        <Input id={id} ref={noteRef} value={note} onChange={(e) => setNote(e.target.value)} placeholder="For example: will answer orally with the custody certificate" />
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => {
              resolveItem(key, note.trim() || "Accepted by counsel");
              setOpen(false);
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

function ObjectionCard({ objection, focusedId }: { objection: Objection; focusedId: string | null }): ReactElement {
  const { resolutions } = useGates();
  const { focusItem } = useStageNav();
  const domId = focusDomId("spar", objection.id);
  const unanswered = objection.verdict === "UNANSWERED";
  const resolved = Boolean(resolutions.resolved[checklistKey("UNANSWERED", objection.id)]);
  const factor = FACTOR_LABELS[objection.factor as Factor] ?? humanize(objection.factor);
  const general = objection.against === "general";

  return (
    <article
      id={domId}
      data-testid="spar-objection"
      data-objection={objection.id}
      tabIndex={-1}
      aria-labelledby={`${domId}-title`}
      className={cn(
        "scroll-mt-4 rounded-lg border bg-cream p-4 shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-maroon",
        unanswered && !resolved ? "border-sindoor/50" : "border-line",
        focusClass(focusedId, objection.id),
      )}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="eyebrow">Objection</p>
          <h4 id={`${domId}-title`} className="font-display text-base font-semibold text-maroon">
            <span className="numeral mr-2 text-gold-leaf">{objection.id}</span>
            {factor}
          </h4>
          <p className="mt-0.5 text-xs text-ink-soft">
            {general ? (
              "General objection"
            ) : (
              <>
                Against{" "}
                <button type="button" onClick={() => focusItem("brief", objection.against)} className="font-semibold text-maroon underline-offset-4 hover:underline" aria-label={`Go to ground ${objection.against} in the brief`}>
                  ground {objection.against}
                </button>
              </>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {objection.verdict ? <StatusBadge status={objection.verdict} kind="verdict" /> : <Badge variant="outline" size="md">Not judged yet</Badge>}
          {unanswered && !resolved ? <StatusBadge status="NEEDS_REVIEW" kind="claim" testId="aux-badge" /> : null}
        </div>
      </header>

      <blockquote className="mt-3 border-l-2 border-sindoor/60 pl-3 text-[0.95rem] leading-7 text-ink">{objection.objection}</blockquote>
      <div className="mt-2"><GroundsChips grounds={objection.grounds} /></div>

      <div className="mt-3 rounded-md border border-line bg-parchment/70 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="eyebrow">Vakeel&apos;s reply</p>
          {objection.reply ? <StatusBadge status={objection.reply.check} kind="claim" size="sm" testId="aux-badge" /> : null}
        </div>
        {objection.reply ? (
          <>
            <div className="mt-1.5">
              <ArgumentText argument={objection.reply.text} scope={objection.id} needsReview={objection.reply.check === "NEEDS_REVIEW"} />
            </div>
            <AuthorityList authorities={objection.reply.authorities} scope={objection.id} className="mt-2" />
          </>
        ) : (
          <p className="mt-1.5 text-sm italic text-ink-soft">No reply could be drafted that Vakeel could support from the file.</p>
        )}
      </div>

      {objection.reason ? (
        <p className="mt-2 text-sm text-ink">
          <span className="font-semibold">Abhiyojak&apos;s reason: </span>
          {objection.reason}
        </p>
      ) : null}

      {unanswered ? (
        <div className="mt-3 border-t border-line pt-3">
          <p className="mb-2 text-xs text-ink-soft">An unanswered objection goes to counsel and must be resolved before Gate 2.</p>
          <ResolveControls objection={objection} />
        </div>
      ) : null}
    </article>
  );
}

export function SparTab({ caseId, className }: SparTabProps): ReactElement {
  void caseId;
  const data = useCaseData();
  const activity = useAgentActivity();
  const { resolutions } = useGates();
  const spar = data.spar;
  const focusedId = useFocusItem("spar", Boolean(spar));

  const state = tabState({
    tab: "spar", resource: "spar", noun: "sparring record", loading: data.loading.spar, error: data.errors.spar, hasData: Boolean(spar),
    onRetry: () => void data.refresh(["spar"]),
    emptyTitle: "No sparring yet",
    emptyBody: "Abhiyojak argues the other side against each drafted ground, and Vakeel replies. It starts once the draft exists.",
  });
  if (state || !spar) return state ?? <></>;

  const objections = spar.objections;
  const count = (v: Objection["verdict"]) => objections.filter((o) => o.verdict === v).length;
  const unanswered = objections.filter((o) => o.verdict === "UNANSWERED");
  const open = unanswered.filter((o) => !resolutions.resolved[checklistKey("UNANSWERED", o.id)]).length;
  const working = activity.byAgent.ABHIYOJAK.phase === "working";

  return (
    <TabShell label="Prosecution sparring" className={className}>
      <TabHeader
        agent="ABHIYOJAK"
        title="Prosecution sparring"
        description={`Abhiyojak argues the other side from what prosecutors actually argue, then judges each reply. ${plural(spar.rounds, "round")}.`}
        signature={
          <AgentSignature
            agent="ABHIYOJAK"
            mode={working ? "working" : "full"}
            active={working}
            statusText={activity.byAgent.ABHIYOJAK.text}
            unanswered={open}
          />
        }
      />

      <div role="group" aria-label="Objections by verdict" className="flex flex-wrap items-center gap-1.5">
        <Badge variant="outline" size="lg">{plural(objections.length, "objection")}</Badge>
        <StatusBadge status="ANSWERED" kind="verdict" detail={`${count("ANSWERED")}`} />
        <StatusBadge status="PARTLY" kind="verdict" detail={`${count("PARTLY")}`} />
        <StatusBadge status="UNANSWERED" kind="verdict" detail={`${unanswered.length}`} />
      </div>
      <p className="text-sm text-ink-soft" aria-live="polite">
        {open > 0
          ? `${plural(open, "unanswered objection")} still ${open === 1 ? "needs" : "need"} counsel before Gate 2.`
          : unanswered.length > 0
            ? "Every unanswered objection has been resolved by counsel."
            : "No unanswered objections."}
      </p>

      <section aria-labelledby="spar-list" className="space-y-3">
        <SectionTitle id="spar-list">Objections and replies</SectionTitle>
        {objections.length === 0 ? (
          <p className="text-sm text-ink-soft">Abhiyojak raised no objection that it could ground in the objection bank, a refusal, a statute or a dossier fact.</p>
        ) : (
          objections.map((o) => <ObjectionCard key={o.id} objection={o} focusedId={focusedId} />)
        )}
      </section>

      {spar.discarded.length > 0 ? (
        <details className="rounded-md border border-line bg-parchment/60 p-3 text-sm">
          <summary className="cursor-pointer font-semibold text-ink">
            {plural(spar.discarded.length, "ungrounded objection")} discarded and logged
          </summary>
          <p className="mt-1 text-xs text-ink-soft">An objection must cite a bank paragraph, a refusal, a statute or a dossier fact. These did not.</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-soft">
            {spar.discarded.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </TabShell>
  );
}

export default SparTab;
