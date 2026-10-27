"use client";
// Check rights (plan §7.3, Appendix C): the Rights Radar as a short plain list. What may be open now comes first; the rest
// sit behind one line. "Why" shows the rule, its source and the dates used. Outputs are possible entitlements to check, never
// advice or a prediction.
import { ChevronDown } from "lucide-react";
import { useEffect, useState, type ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { RightsTimeline } from "@/components/rights/RightsTimeline";
import { timelineFromReport } from "@/lib/rightsTimeline";
import { fieldLabel } from "@/lib/fields";
import { daysBetween, formatCourtDate, plural } from "@/lib/format";
import { RIGHTS_CHECK_LABELS } from "@/lib/labels";
import { RIGHTS_URGENCY } from "@/lib/status";
import { DOSSIER_FIELD_NAMES, type RightsCheckResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCaseData, useEdits, useStageNav, useWorkspace } from "@/lib/workspace";
import { StepFooter, StepFrame } from "../StepFrame";
import { ChangedTag, focusClass, focusDomId, SectionTitle, stepState, useFocusItem } from "./shared";

/** Statuses that lead the list: something may be open, closed, flagged or unclear. */
const LEAD = new Set(["ELIGIBLE", "FLAG", "NOT_YET", "BAR_APPLIES", "CHECK", "UNKNOWN", "WINDOW_CLOSED"]);

const DATE_KEY_LABELS: Record<string, string> = {
  first_remand: "First remand",
  arrest_date: "Arrest",
  charge_sheet: "Charge sheet filed",
  as_of: "As of",
  one_third: "One-third of the maximum",
  one_half: "One-half of the maximum",
  day_60: "Day 60",
  day_90: "Day 90",
};

function dateKeyLabel(key: string): string {
  return DATE_KEY_LABELS[key] ?? key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

/** Days left for a NOT_YET check: from the dates it used when one is ahead of the as-of date, else from its own text. */
function daysLeft(check: RightsCheckResult, asOf: string): number | null {
  if (check.status !== "NOT_YET") return null;
  const ahead = Object.values(check.dates ?? {})
    .filter((d) => d > asOf)
    .sort();
  if (ahead.length) return daysBetween(asOf, ahead[0]);
  const m = /(\d[\d,]*)\s+days?\s+left/i.exec(check.detail ?? "");
  return m ? Number(m[1].replace(/,/g, "")) : null;
}

function CheckRow({ check, asOf, focusedId, changed }: { check: RightsCheckResult; asOf: string; focusedId: string | null; changed: boolean }): ReactElement {
  const { focusItem } = useStageNav();
  const [open, setOpen] = useState(false);
  const domId = focusDomId("rights", check.check);
  const label = RIGHTS_CHECK_LABELS[check.check] ?? check.check;
  const left = daysLeft(check, asOf);
  const dates = Object.entries(check.dates ?? {});
  const focused = focusedId === check.check;
  useEffect(() => {
    if (focused) setOpen(true);
  }, [focused]);

  return (
    <li
      id={domId}
      data-testid="rights-chip"
      data-check={check.check}
      data-status={check.status}
      data-changed={changed || undefined}
      tabIndex={-1}
      aria-labelledby={`${domId}-label`}
      className={cn("scroll-mt-4 py-4 outline-none focus-visible:ring-2 focus-visible:ring-maroon", focusClass(focusedId, check.check))}
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h4 id={`${domId}-label`} className="font-sans text-base font-semibold text-ink">{label}</h4>
        <StatusBadge status={check.status} kind="rights" size="sm" detail={left !== null ? `(${plural(left, "day")} left)` : undefined} />
        {changed ? <ChangedTag /> : null}
      </div>
      {check.detail ? <p className="mt-1 max-w-prose text-ink">{check.detail}</p> : null}
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`${domId}-why`}
        onClick={() => setOpen((v) => !v)}
        className="mt-1.5 inline-flex items-center gap-1 rounded-sm text-sm font-medium text-maroon underline-offset-4 hover:underline"
      >
        Why
        <ChevronDown aria-hidden className={cn("size-4 transition-transform duration-fast", open && "rotate-180")} />
        <span className="sr-only"> for {label}</span>
      </button>
      {open ? (
        <dl id={`${domId}-why`} className="mt-3 grid gap-x-4 gap-y-2 border-l-2 border-line pl-4 text-sm sm:grid-cols-[8rem_minmax(0,1fr)]">
          {check.rule ? (
            <>
              <dt className="text-ink-muted">Rule</dt>
              <dd className="m-0 text-ink"><span className="cite">{check.rule}</span>{check.rule_text ? <span className="block text-ink-soft">{check.rule_text}</span> : null}</dd>
            </>
          ) : null}
          {check.sources && check.sources.length > 0 ? (
            <>
              <dt className="text-ink-muted">Source</dt>
              <dd className="m-0 text-ink-soft">
                <ul className="m-0 list-none space-y-0.5 p-0">
                  {check.sources.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </dd>
            </>
          ) : null}
          {dates.length > 0 ? (
            <>
              <dt className="text-ink-muted">Dates used</dt>
              <dd className="m-0">
                <ul className="m-0 list-none space-y-0.5 p-0">
                  {dates.map(([k, v]) => (
                    <li key={k} className="text-ink">
                      <span className="text-ink-soft">{dateKeyLabel(k)}: </span>
                      <time dateTime={v} className="tabular">{formatCourtDate(v)}</time>
                    </li>
                  ))}
                </ul>
              </dd>
            </>
          ) : null}
          {check.uses.length > 0 ? (
            <>
              <dt className="text-ink-muted">Facts used</dt>
              <dd className="m-0 text-ink-soft">
                {check.uses.map((u, i) => {
                  const isField = (DOSSIER_FIELD_NAMES as readonly string[]).includes(u);
                  return (
                    <span key={u}>
                      {i > 0 ? ", " : ""}
                      {isField ? (
                        <button type="button" onClick={() => focusItem("dossier", u)} className="rounded-sm text-maroon underline-offset-4 hover:underline" aria-label={`Go to ${fieldLabel(u)} in the facts`}>
                          {fieldLabel(u)}
                        </button>
                      ) : (
                        u
                      )}
                    </span>
                  );
                })}
              </dd>
            </>
          ) : null}
          {check.last_verified ? (
            <>
              <dt className="text-ink-muted">Rule checked</dt>
              <dd className="m-0 text-ink-soft">{formatCourtDate(check.last_verified)}</dd>
            </>
          ) : null}
        </dl>
      ) : null}
    </li>
  );
}

export function RightsTab(): ReactElement {
  const ws = useWorkspace();
  const data = useCaseData();
  const rights = data.rights;
  const focused = useFocusItem("rights", Boolean(rights));
  const changedRights = useEdits().changes.changedRights;
  const [showRest, setShowRest] = useState(false);

  const state = stepState({
    resource: "rights", noun: "rights checks", loading: data.loading.rights, error: data.errors.rights, hasData: Boolean(rights),
    onRetry: () => void data.refresh(["rights"]),
    emptyTitle: "The rights checks have not run yet",
    emptyBody: "They need the arrest date, the first remand and the sections from the facts.",
  });
  const footer = <StepFooter label="Continue to Draft grounds" onClick={() => ws.setStage("BRIEF")} />;
  if (state || !rights) {
    return (
      <StepFrame title="Check rights" intro="Possible rights worked out from the dates in the file." footer={footer}>
        {state}
      </StepFrame>
    );
  }

  const sorted = rights.checks
    .map((c, i) => ({ c, i }))
    .sort((a, b) => RIGHTS_URGENCY[a.c.status] - RIGHTS_URGENCY[b.c.status] || a.i - b.i)
    .map(({ c }) => c);
  const lead = sorted.filter((c) => LEAD.has(c.status));
  const rest = sorted.filter((c) => !LEAD.has(c.status));
  const restOpen = showRest || rest.some((c) => c.check === focused?.id);

  // The calendar view of the same checks; the list below stays the full record (and the path for screen readers).
  const antecedents = data.dossier?.fields.antecedents;
  const fields = data.dossier?.fields;
  const cs = fields?.charge_sheet?.value as { filed?: boolean; date?: string | null } | null | undefined;
  const timeline = timelineFromReport(rights, Boolean(antecedents && antecedents.status !== "UNSUPPORTED" && antecedents.value != null), {
    arrest: typeof fields?.arrest_date?.value === "string" ? fields.arrest_date.value : null,
    firstRemand: typeof fields?.first_remand?.value === "string" ? fields.first_remand.value : null,
    chargeSheet: cs?.filed && cs.date ? cs.date : null,
  });
  const nextDate = (data.dates ?? []).map((e) => e.date).filter((d) => d > rights.as_of).sort()[0];

  return (
    <StepFrame
      title="Check rights"
      intro={`Possible rights worked out from the dates in the file as of ${formatCourtDate(rights.as_of)}. These are prompts to check, not advice or a prediction.`}
      footer={footer}
    >
      {timeline ? (
        <section aria-labelledby="rights-calendar" data-testid="rights-calendar">
          <SectionTitle id="rights-calendar">On the calendar</SectionTitle>
          <RightsTimeline
            input={timeline}
            initialDate={nextDate ?? rights.as_of}
            jumps={nextDate ? [{ label: "Next date in the file", date: nextDate }] : []}
            testId="workspace-rights-timeline"
            className="mt-2 border border-line"
          />
        </section>
      ) : null}

      {lead.length > 0 ? (
        <section aria-labelledby="rights-lead">
          <SectionTitle id="rights-lead">Worth checking now</SectionTitle>
          <ul className="mt-2 divide-y divide-line border-y border-line">
            {lead.map((c) => (
              <CheckRow key={c.check} check={c} asOf={rights.as_of} focusedId={focused?.id ?? null} changed={changedRights.includes(c.check)} />
            ))}
          </ul>
        </section>
      ) : (
        <p className="text-ink-soft">Nothing needs your attention. No right is open, flagged or close to a threshold as of {formatCourtDate(rights.as_of)}.</p>
      )}

      {rest.length > 0 ? (
        <section aria-labelledby="rights-rest">
          <h3 id="rights-rest" className="font-sans text-base">
            <button
              type="button"
              aria-expanded={restOpen}
              aria-controls="rights-rest-list"
              onClick={() => setShowRest((v) => !v)}
              className="inline-flex items-center gap-1 rounded-sm font-medium text-ink-soft hover:text-ink"
            >
              Other checks <span className="tabular font-normal">({rest.length})</span>
              <ChevronDown aria-hidden className={cn("size-4 transition-transform duration-fast", restOpen && "rotate-180")} />
            </button>
          </h3>
          {restOpen ? (
            <ul id="rights-rest-list" className="mt-2 divide-y divide-line border-y border-line">
              {rest.map((c) => (
                <CheckRow key={c.check} check={c} asOf={rights.as_of} focusedId={focused?.id ?? null} changed={changedRights.includes(c.check)} />
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      <p className="text-sm text-ink-muted">Drafting a default-bail application is outside this version. An opening is flagged here for you to act on.</p>
    </StepFrame>
  );
}

export default RightsTab;
