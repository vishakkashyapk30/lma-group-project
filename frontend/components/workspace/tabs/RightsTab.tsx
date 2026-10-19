"use client";
// Rights tab (plan §7.3, Appendix C): the Rights Radar, one card per check. Outputs are possible entitlements to check,
// never advice. Every card shows the rule, its source and the dates it used; urgent flags come first.
import { ArrowUpRight, BookOpenCheck } from "lucide-react";
import type { ReactElement } from "react";
import { AgentSignature } from "@/components/agents/AgentSignature";
import { StatusBadge } from "@/components/common/StatusBadge";
import { fieldLabel } from "@/lib/fields";
import { daysBetween, formatCourtDate, plural } from "@/lib/format";
import { RIGHTS_CHECK_LABELS } from "@/lib/labels";
import { RIGHTS_URGENCY } from "@/lib/status";
import { DOSSIER_FIELD_NAMES, type RightsCheckResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAgentActivity, useCaseData, useEdits, useStageNav } from "@/lib/workspace";
import { ChangedTag, focusClass, focusDomId, SectionTitle, TabHeader, tabState, TabShell, useFocusItem } from "./shared";

export interface RightsTabProps {
  caseId: string;
  className?: string;
}

/** Statuses at the top of the list: something to look at now. */
const URGENT = new Set(["ELIGIBLE", "FLAG", "NOT_YET", "BAR_APPLIES"]);

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

function UsesLinks({ uses }: { uses: string[] }): ReactElement | null {
  const { focusItem } = useStageNav();
  if (uses.length === 0) return null;
  return (
    <ul aria-label="Dossier fields used" className="flex flex-wrap gap-1.5">
      {uses.map((u) => {
        const isField = (DOSSIER_FIELD_NAMES as readonly string[]).includes(u);
        return (
          <li key={u}>
            {isField ? (
              <button
                type="button"
                onClick={() => focusItem("dossier", u)}
                aria-label={`Go to ${fieldLabel(u)} in the dossier`}
                className="inline-flex items-center gap-1 rounded-sm border border-line-strong/50 bg-cream px-1.5 py-0.5 font-mono text-[11px] text-ink-soft transition-colors duration-fast hover:border-maroon hover:text-maroon"
              >
                {u} <ArrowUpRight aria-hidden className="size-3" />
              </button>
            ) : (
              <span className="inline-flex rounded-sm border border-line bg-cream px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">{u}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function CheckCard({ check, asOf, focusedId, changed }: { check: RightsCheckResult; asOf: string; focusedId: string | null; changed: boolean }): ReactElement {
  const domId = focusDomId("rights", check.check);
  const label = RIGHTS_CHECK_LABELS[check.check] ?? check.check;
  const left = daysLeft(check, asOf);
  const dates = Object.entries(check.dates ?? {});
  const urgent = URGENT.has(check.status);
  return (
    <article
      id={domId}
      data-testid="rights-chip"
      data-check={check.check}
      data-status={check.status}
      data-changed={changed || undefined}
      tabIndex={-1}
      aria-labelledby={`${domId}-label`}
      className={cn(
        "scroll-mt-4 rounded-lg border bg-cream p-4 shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-maroon",
        urgent ? "border-maroon/50 border-l-4" : "border-line",
        focusClass(focusedId, check.check),
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 id={`${domId}-label`} className="font-display text-base font-semibold text-maroon">{label}</h4>
        <div className="flex flex-wrap items-center gap-1.5">
          {changed ? <ChangedTag /> : null}
          <StatusBadge
            status={check.status}
            kind="rights"
            detail={left !== null ? `${plural(left, "day")} left` : undefined}
          />
        </div>
      </div>

      {check.detail ? <p className="mt-2 text-sm leading-relaxed text-ink">{check.detail}</p> : null}

      <dl className="mt-3 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[8rem_1fr]">
        {check.rule ? (
          <>
            <dt className="eyebrow pt-0.5">Rule</dt>
            <dd className="cite text-ink">{check.rule}</dd>
          </>
        ) : null}
        {check.rule_text ? (
          <>
            <dt className="eyebrow pt-0.5">As coded</dt>
            <dd className="text-ink-soft">{check.rule_text}</dd>
          </>
        ) : null}
        {check.sources && check.sources.length > 0 ? (
          <>
            <dt className="eyebrow pt-0.5">Sources</dt>
            <dd>
              <ul className="space-y-0.5 text-ink-soft">
                {check.sources.map((s) => (
                  <li key={s} className="flex gap-1.5">
                    <BookOpenCheck aria-hidden className="mt-1 size-3 shrink-0 text-gold-leaf" />
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </dd>
          </>
        ) : null}
        {dates.length > 0 ? (
          <>
            <dt className="eyebrow pt-0.5">Dates used</dt>
            <dd>
              <ul className="flex flex-wrap gap-x-4 gap-y-1">
                {dates.map(([k, v]) => (
                  <li key={k} className="text-ink">
                    <span className="text-ink-soft">{dateKeyLabel(k)}: </span>
                    <time dateTime={v} className="cite">{formatCourtDate(v)}</time>
                  </li>
                ))}
              </ul>
            </dd>
          </>
        ) : null}
        {check.uses.length > 0 ? (
          <>
            <dt className="eyebrow pt-0.5">Fields used</dt>
            <dd><UsesLinks uses={check.uses} /></dd>
          </>
        ) : null}
      </dl>
      {check.last_verified ? (
        <p className="mt-3 text-xs text-ink-muted">Rule last verified {formatCourtDate(check.last_verified)}.</p>
      ) : null}
    </article>
  );
}

export function RightsTab({ caseId, className }: RightsTabProps): ReactElement {
  void caseId;
  const data = useCaseData();
  const activity = useAgentActivity();
  const rights = data.rights;
  const focusedId = useFocusItem("rights", Boolean(rights));
  const changedRights = useEdits().changes.changedRights;

  const state = tabState({
    tab: "rights", resource: "rights", noun: "Rights Radar", loading: data.loading.rights, error: data.errors.rights, hasData: Boolean(rights),
    onRetry: () => void data.refresh(["rights"]),
    emptyTitle: "The Rights Radar has not run yet",
    emptyBody: "It runs on the dossier and the List of Dates, and needs the arrest, first remand and sections to compute its checks.",
  });
  if (state || !rights) return state ?? <></>;

  const sorted = rights.checks
    .map((c, i) => ({ c, i }))
    .sort((a, b) => RIGHTS_URGENCY[a.c.status] - RIGHTS_URGENCY[b.c.status] || a.i - b.i)
    .map(({ c }) => c);
  const urgent = sorted.filter((c) => URGENT.has(c.status));
  const rest = sorted.filter((c) => !URGENT.has(c.status));
  const working = activity.byAgent.PESHKAR.phase === "working";

  return (
    <TabShell label="Rights Radar" className={className}>
      <TabHeader
        agent="PESHKAR"
        title="Rights Radar"
        description={
          <>
            Possible entitlements to check, worked out by fixed rules from the dates in the file as of {formatCourtDate(rights.as_of)}.
            These are prompts for counsel, not advice or a prediction. Unsettled law returns CHECK.
          </>
        }
        signature={<AgentSignature agent="PESHKAR" mode="working" active={working} statusText={working ? activity.byAgent.PESHKAR.text : undefined} />}
      />

      {urgent.length > 0 ? (
        <section aria-labelledby="rights-urgent" className="space-y-3">
          <SectionTitle id="rights-urgent" aside={<span className="text-xs text-ink-soft">{urgent.length} to look at first</span>}>
            Look at first
          </SectionTitle>
          {urgent.map((c) => (
            <CheckCard key={c.check} check={c} asOf={rights.as_of} focusedId={focusedId} changed={changedRights.includes(c.check)} />
          ))}
        </section>
      ) : (
        <p className="rounded-md border border-line bg-parchment px-3 py-2 text-sm text-ink-soft">
          No check is ELIGIBLE, flagged or approaching a threshold as of {formatCourtDate(rights.as_of)}.
        </p>
      )}

      {rest.length > 0 ? (
        <section aria-labelledby="rights-others" className="space-y-3">
          <SectionTitle id="rights-others">{urgent.length > 0 ? "Other checks" : "All checks"}</SectionTitle>
          {rest.map((c) => (
            <CheckCard key={c.check} check={c} asOf={rights.as_of} focusedId={focusedId} changed={changedRights.includes(c.check)} />
          ))}
        </section>
      ) : null}

      <p className="text-xs text-ink-muted">
        Drafting a default-bail application is outside this version. An opening is flagged here for counsel to act on.
      </p>
    </TabShell>
  );
}

export default RightsTab;
