"use client";
// Prepare for the hearing (plan §8.3): the one-page hearing-prep card. What the bench may ask with short answers that link to
// grounds, three points to lead with, conditions courts often impose in similar grants, and what to clear first. It makes no
// outcome prediction and shows no grant rates. The card prints on its own.
import { Printer } from "lucide-react";
import { useRef, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { formatCourtDate, humanize } from "@/lib/format";
import { FACTOR_LABELS } from "@/lib/labels";
import { DRAFT_LABEL, type Factor, type PrepConcern } from "@/lib/types";
import { useCaseData, useNeedsYou, useStageNav, useWorkspace } from "@/lib/workspace";
import { NeedsYou } from "../NeedsYou";
import { StepFooter, StepFrame } from "../StepFrame";
import { focusClass, focusDomId, printElement, SectionTitle, stepState, useFocusItem } from "./shared";

function GroundLink({ id }: { id: string }): ReactElement {
  const { focusItem } = useStageNav();
  return (
    <button
      type="button"
      onClick={() => focusItem("brief", id)}
      aria-label={`Go to ground ${id} in the draft`}
      className="rounded-sm text-maroon underline-offset-4 hover:underline print:text-ink print:no-underline"
    >
      Ground {id}
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
      className={`break-inside-avoid scroll-mt-4 py-4 outline-none focus-visible:ring-2 focus-visible:ring-maroon ${focusClass(focusedId, id)}`}
    >
      <p className="font-medium text-ink">{concern.concern}</p>
      <p className="mt-0.5 text-sm text-ink-muted">{factor}. {concern.basis}</p>
      <p className="mt-2 text-ink">
        <span className="text-ink-soft">Short answer: </span>
        {concern.answer}
      </p>
      {concern.ground_id || concern.authority ? (
        <p className="mt-1.5 flex flex-wrap items-center gap-x-3 text-sm text-ink-soft">
          {concern.ground_id ? <GroundLink id={concern.ground_id} /> : null}
          {concern.authority ? <span className="cite">{concern.authority}</span> : null}
        </p>
      ) : null}
    </li>
  );
}

/** A hearing card in a shape the typed view does not know (the backend returns a plain mapping): show every string it carries. */
function GenericCard({ card }: { card: Record<string, unknown> }): ReactElement {
  const entries = Object.entries(card).filter(([, v]) => typeof v === "string" || (Array.isArray(v) && v.some((x) => typeof x === "string")));
  return (
    <article data-testid="prep-card" aria-label="Hearing-prep card" className="space-y-6">
      {entries.map(([key, value]) => (
        <section key={key} aria-label={humanize(key)}>
          <h4 className="font-sans text-sm font-semibold text-ink-soft">{humanize(key)}</h4>
          {Array.isArray(value) ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-ink">
              {value.filter((x): x is string => typeof x === "string").map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-ink">{String(value)}</p>
          )}
        </section>
      ))}
      <p className="border-t border-line pt-3 text-sm text-ink-soft">This card makes no prediction of the outcome and shows no grant rates.</p>
    </article>
  );
}

export function PrepTab({ caseId }: { caseId: string }): ReactElement {
  void caseId;
  const ws = useWorkspace();
  const data = useCaseData();
  const needs = useNeedsYou("HEARING_PREP");
  const prep = data.prep;
  const focused = useFocusItem("prep", Boolean(prep));
  const cardRef = useRef<HTMLElement | null>(null);
  const footer = <StepFooter label="Continue to Export" onClick={() => ws.setStage("FILE")} />;
  const intro = "One page to take into the hearing.";

  const state = stepState({
    resource: "prep", noun: "hearing notes", loading: data.loading.prep, error: data.errors.prep, hasData: Boolean(prep),
    onRetry: () => void data.refresh(["prep"]),
    emptyTitle: "No hearing notes yet",
    emptyBody: "The notes are built from the checked draft and the likely objections. Draft the grounds first.",
    emptyAction: <Button variant="secondary" onClick={() => ws.setStage("BRIEF")}>Go to Draft grounds</Button>,
  });
  if (state || !prep) {
    return (
      <StepFrame title="Prepare for the hearing" intro={intro}>
        {state}
      </StepFrame>
    );
  }
  if (!Array.isArray(prep.lead_points) || !Array.isArray(prep.likely_concerns)) {
    return (
      <StepFrame title="Prepare for the hearing" intro={intro} footer={footer}>
        <GenericCard card={prep as unknown as Record<string, unknown>} />
      </StepFrame>
    );
  }

  const print = () => {
    if (cardRef.current) printElement(cardRef.current, `Hearing-prep card ${prep.case_id}`);
  };

  return (
    <StepFrame
      title="Prepare for the hearing"
      intro={intro}
      actions={
        <Button variant="secondary" size="sm" onClick={print}>
          <Printer aria-hidden /> Print
        </Button>
      }
      footer={footer}
    >
      <NeedsYou items={needs} empty="Nothing needs your attention before the hearing." />

      <article ref={cardRef} data-testid="prep-card" aria-label="Hearing-prep card" className="flex flex-col gap-8">
        <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-3">
          <h3 className="font-display text-xl font-semibold text-ink">Hearing-prep card</h3>
          <p className="text-sm text-ink-soft">
            Case <span className="cite">{prep.case_id}</span>
            {prep.hearing_date ? (
              <>
                , hearing on <time dateTime={prep.hearing_date} className="tabular font-medium text-ink">{formatCourtDate(prep.hearing_date)}</time>
              </>
            ) : null}
          </p>
        </header>

        <section aria-labelledby="prep-lead" className="break-inside-avoid">
          <SectionTitle id="prep-lead">Points to lead with</SectionTitle>
          <ol className="mt-3 list-decimal space-y-3 pl-5 marker:text-ink-muted">
            {prep.lead_points.map((p) => (
              <li key={p.ground_id} className="pl-1 text-ink">
                {p.point} <span className="text-sm text-ink-soft"><GroundLink id={p.ground_id} /></span>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="prep-concerns">
          <SectionTitle id="prep-concerns">What the bench may ask</SectionTitle>
          {prep.likely_concerns.length === 0 ? (
            <p className="mt-2 text-ink-soft">No concern stood out in comparable orders.</p>
          ) : (
            <ul className="mt-2 divide-y divide-line border-y border-line">
              {prep.likely_concerns.map((c, i) => (
                <Concern key={`${c.factor}-${i}`} concern={c} index={i} focusedId={focused?.id ?? null} />
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="prep-conditions" className="break-inside-avoid">
          <SectionTitle id="prep-conditions">Conditions you could offer up front</SectionTitle>
          <p className="mt-1 text-sm text-ink-soft">Taken from operative orders in similar grants. This is not a prediction.</p>
          {prep.conditions.length === 0 ? (
            <p className="mt-2 text-ink-soft">No conditions found in comparable operative orders.</p>
          ) : (
            <ul className="mt-2 divide-y divide-line border-y border-line">
              {prep.conditions.map((c) => (
                <li key={c.condition} className="py-2.5 text-ink">
                  {c.condition}
                  {c.seen_in.length > 0 ? <span className="mt-0.5 block text-sm text-ink-muted">Seen in <span className="cite">{c.seen_in.join(", ")}</span></span> : null}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="prep-issues" className="hidden break-inside-avoid print:block">
          <SectionTitle id="prep-issues">To clear before the hearing</SectionTitle>
          {prep.open_issues.length === 0 ? (
            <p className="mt-2">None.</p>
          ) : (
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {prep.open_issues.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          )}
        </section>

        <footer className="border-t border-line pt-3 text-sm text-ink-soft">
          <p className="font-medium text-maroon">{prep.label || DRAFT_LABEL}</p>
          <p>This card makes no prediction of the outcome and shows no grant rates.</p>
        </footer>
      </article>
    </StepFrame>
  );
}

export default PrepTab;
