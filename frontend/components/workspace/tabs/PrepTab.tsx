"use client";
// Prep tab (plan §8.3): the one-page hearing-prep card. Likely concerns from the bench with short answers that link to
// grounds, three points to lead with, conditions courts often impose in similar grants, and open issues. It makes no
// outcome prediction and shows no grant rates. The card prints on its own.
import { ArrowUpRight, Download, Printer } from "lucide-react";
import { useRef, useState, type ReactElement } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatCourtDate, humanize } from "@/lib/format";
import { FACTOR_LABELS } from "@/lib/labels";
import { DRAFT_LABEL, type Factor, type PrepConcern } from "@/lib/types";
import { errorMessage } from "@/lib/errors";
import { useCaseData, useStageNav, useWorkspace } from "@/lib/workspace";
import { focusClass, focusDomId, InlineNote, printElement, SectionTitle, TabHeader, tabState, TabShell, useFocusItem } from "./shared";

export interface PrepTabProps {
  caseId: string;
  className?: string;
}

function GroundLink({ id, label }: { id: string; label?: string }): ReactElement {
  const { focusItem } = useStageNav();
  return (
    <button
      type="button"
      onClick={() => focusItem("brief", id)}
      aria-label={`Go to ground ${id} in the brief`}
      className="inline-flex items-center gap-0.5 rounded-sm border border-maroon/40 bg-maroon/[0.06] px-1.5 py-0.5 font-mono text-[11px] text-maroon transition-colors duration-fast hover:bg-maroon hover:text-cream print:border-0 print:bg-transparent print:p-0"
    >
      {label ?? id} <ArrowUpRight aria-hidden className="size-3 print:hidden" />
    </button>
  );
}

function Concern({ concern, index, focusedId }: { concern: PrepConcern; index: number; focusedId: string | null }): ReactElement {
  const id = `concern-${index}`;
  const factor = FACTOR_LABELS[concern.factor as Factor] ?? humanize(concern.factor);
  return (
    <li
      id={focusDomId("prep", id)}
      tabIndex={-1}
      className={`break-inside-avoid scroll-mt-4 rounded-md border border-line bg-cream p-3 outline-none focus-visible:ring-2 focus-visible:ring-maroon ${focusClass(focusedId, id)}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 font-display text-base font-semibold leading-snug text-ink">{concern.concern}</p>
        <Badge variant="outline" size="md">{factor}</Badge>
      </div>
      <p className="mt-1 text-xs text-ink-soft">{concern.basis}</p>
      <p className="mt-2 text-sm leading-relaxed text-ink">
        <span className="font-semibold text-maroon">Short answer: </span>
        {concern.answer}
      </p>
      {concern.ground_id || concern.authority ? (
        <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink-soft">
          {concern.ground_id ? <GroundLink id={concern.ground_id} label={`Ground ${concern.ground_id}`} /> : null}
          {concern.authority ? <span className="cite">{concern.authority}</span> : null}
        </p>
      ) : null}
    </li>
  );
}

/** Stage VII: export the application and the hearing card. It stays disabled, with the reason, until Gate 2 is approved (plan §16). */
function ExportPanel(): ReactElement {
  const ws = useWorkspace();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const run = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await ws.exportCase("DOCX");
    } catch (e) {
      setMessage(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section aria-labelledby="file-export" className="rounded-lg border border-maroon/40 bg-parchment p-4">
      <SectionTitle id="file-export">VII · File: export</SectionTitle>
      <p className="mt-1 text-sm text-ink-soft">
        {ws.canExport
          ? "Both gates are approved. The files carry the draft label; your court's rules still apply."
          : "Export unlocks only after counsel approves Gate 2 (the checked draft). Until then the server refuses it with a 403."}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button data-testid="export-button" onClick={() => void run()} disabled={!ws.canExport || busy}>
          <Download aria-hidden /> {busy ? "Exporting" : "Export"}
        </Button>
      </div>
      {message ? <InlineNote>{message}</InlineNote> : null}
      {ws.exports.length > 0 ? (
        <ul aria-label="Exported files" className="mt-3 space-y-1 text-sm">
          {ws.exports.map((f) => (
            <li key={f}>
              <a data-testid="export-link" href={f} download className="cite text-maroon underline underline-offset-4">
                {f.split("/").pop() || f}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

/** A hearing card in a shape the typed view does not know (the backend returns a plain mapping): show every string it carries. */
function GenericCard({ card }: { card: Record<string, unknown> }): ReactElement {
  const entries = Object.entries(card).filter(([, v]) => typeof v === "string" || (Array.isArray(v) && v.some((x) => typeof x === "string")));
  return (
    <article data-testid="prep-card" aria-label="Hearing-prep card" className="space-y-4 rounded-lg border-2 border-maroon/40 bg-cream p-5 shadow-sm">
      {entries.map(([key, value]) => (
        <section key={key} aria-label={humanize(key)}>
          <h4 className="eyebrow">{humanize(key)}</h4>
          {Array.isArray(value) ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
              {value.filter((x): x is string => typeof x === "string").map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-sm text-ink">{String(value)}</p>
          )}
        </section>
      ))}
      <p className="border-t border-line pt-3 text-xs text-ink-soft">This card makes no prediction of the outcome and shows no grant rates.</p>
    </article>
  );
}

export function PrepTab({ caseId, className }: PrepTabProps): ReactElement {
  void caseId;
  const ws = useWorkspace();
  const data = useCaseData();
  const prep = data.prep;
  const focusedId = useFocusItem("prep", Boolean(prep));
  const cardRef = useRef<HTMLElement | null>(null);

  const state = tabState({
    tab: "prep", resource: "prep", noun: "hearing-prep card", loading: data.loading.prep, error: data.errors.prep, hasData: Boolean(prep),
    onRetry: () => void data.refresh(["prep"]),
    emptyTitle: "No hearing-prep card yet",
    emptyBody: "The card is built from the checked brief and the sparring record. Draft the brief first.",
  });
  const exportPanel = ws.activeStage === "FILE" ? <ExportPanel /> : null;
  if (state || !prep) {
    return exportPanel ? (
      <TabShell label="File" className={className}>
        {exportPanel}
        {state}
      </TabShell>
    ) : (
      (state ?? <></>)
    );
  }
  if (!Array.isArray(prep.lead_points) || !Array.isArray(prep.likely_concerns)) {
    return (
      <TabShell label="Hearing preparation" className={className}>
        {exportPanel}
        <TabHeader agent="VAKEEL" title="Hearing-prep card" description="One page for the hearing." />
        <GenericCard card={prep as unknown as Record<string, unknown>} />
      </TabShell>
    );
  }

  const print = () => {
    if (cardRef.current) printElement(cardRef.current, `Hearing-prep card ${prep.case_id}`);
  };

  return (
    <TabShell label="Hearing preparation" className={className}>
      {exportPanel}
      <TabHeader
        agent="VAKEEL"
        title="Hearing-prep card"
        description="One page for the hearing: what the bench is likely to ask, three points to lead with, conditions to offer up front, and what to clear first."
        actions={
          <Button variant="secondary" size="sm" onClick={print}>
            <Printer aria-hidden /> Print the card
          </Button>
        }
      />

      <article
        ref={cardRef}
        data-testid="prep-card"
        aria-label="Hearing-prep card"
        className="space-y-5 rounded-lg border-2 border-maroon/40 bg-cream p-5 shadow-sm print:border print:shadow-none"
      >
        <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-gold/60 pb-3">
          <h3 className="font-display text-xl font-semibold text-maroon">Hearing-prep card</h3>
          <p className="text-sm text-ink-soft">
            Case <span className="cite">{prep.case_id}</span>
            {prep.hearing_date ? (
              <>
                {" "}· Hearing <time dateTime={prep.hearing_date} className="font-semibold text-ink">{formatCourtDate(prep.hearing_date)}</time>
              </>
            ) : null}
          </p>
        </header>

        <section aria-labelledby="prep-lead" className="break-inside-avoid">
          <h4 id="prep-lead" className="eyebrow">Three points to lead with</h4>
          <ol className="mt-2 space-y-2">
            {prep.lead_points.map((p, i) => (
              <li key={p.ground_id} className="flex gap-3 rounded-md border border-line bg-parchment/60 p-3">
                <span aria-hidden className="numeral grid size-7 shrink-0 place-items-center rounded-full bg-maroon text-sm font-semibold text-cream print:border print:border-ink print:bg-transparent print:text-ink">
                  {i + 1}
                </span>
                <div className="min-w-0 text-sm text-ink">
                  <p className="leading-relaxed">{p.point}</p>
                  <p className="mt-1"><GroundLink id={p.ground_id} label={`Ground ${p.ground_id}`} /></p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="prep-concerns">
          <h4 id="prep-concerns" className="eyebrow">Likely concerns from the bench</h4>
          {prep.likely_concerns.length === 0 ? (
            <p className="mt-2 text-sm text-ink-soft">No concern stood out in comparable orders.</p>
          ) : (
            <ul className="mt-2 space-y-3">
              {prep.likely_concerns.map((c, i) => (
                <Concern key={`${c.factor}-${i}`} concern={c} index={i} focusedId={focusedId} />
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="prep-conditions" className="break-inside-avoid">
          <h4 id="prep-conditions" className="eyebrow">Conditions courts often impose in similar grants</h4>
          <p className="mt-1 text-xs text-ink-soft">Taken from operative orders. Counsel can offer them up front. This is not a prediction.</p>
          {prep.conditions.length === 0 ? (
            <p className="mt-2 text-sm text-ink-soft">No conditions found in comparable operative orders.</p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {prep.conditions.map((c) => (
                <li key={c.condition} className="rounded-md border border-line bg-cream px-3 py-2 text-sm text-ink">
                  {c.condition}
                  {c.seen_in.length > 0 ? <span className="mt-0.5 block text-xs text-ink-soft">Seen in: <span className="cite">{c.seen_in.join(", ")}</span></span> : null}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="prep-issues" className="break-inside-avoid">
          <h4 id="prep-issues" className="eyebrow">Open issues to clear before the hearing</h4>
          {prep.open_issues.length === 0 ? (
            <p className="mt-2 text-sm text-ink-soft">None.</p>
          ) : (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
              {prep.open_issues.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          )}
        </section>

        <footer className="border-t border-line pt-3 text-xs text-ink-soft">
          <p className="font-semibold text-maroon">{prep.label || DRAFT_LABEL}</p>
          <p>This card makes no prediction of the outcome and shows no grant rates.</p>
        </footer>
      </article>
    </TabShell>
  );
}

export default PrepTab;
