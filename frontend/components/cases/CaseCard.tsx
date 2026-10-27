"use client";
// One matter on the Cases page: title, stage, rights to check (urgent first), items needing attention, last activity.
import Link from "next/link";
import { ArrowRight, BellRing, Clock } from "lucide-react";
import type { ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { STAGE_BY_ID, STEPPER_STAGES, stepOf } from "@/lib/stages";
import { sortRightsChips } from "@/lib/status";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CaseSummary } from "@/lib/types";

/** CaseSummary plus an optional timestamp the API may add. */
export type CaseSummaryWithActivity = CaseSummary & { last_activity?: string | null };

export interface CaseCardProps {
  summary: CaseSummaryWithActivity;
  className?: string;
}

const MAX_CHIPS = 3;

function activityLabel(iso: string | null | undefined): string {
  if (!iso) return "No activity recorded yet";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "No activity recorded yet";
  const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (mins < 1) return "Last activity just now";
  if (mins < 60) return `Last activity ${plural(mins, "minute")} ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `Last activity ${plural(hrs, "hour")} ago`;
  return `Last activity ${plural(Math.round(hrs / 24), "day")} ago`;
}

export function CaseCard({ summary, className }: CaseCardProps): ReactElement {
  // The stepper has six steps; Likely objections (SPAR) is shown inside Draft grounds, so a case there reads "Draft grounds".
  const step = stepOf(summary.stage);
  const stage = STAGE_BY_ID[step];
  const stepNo = STEPPER_STAGES.findIndex((s) => s.id === step) + 1;
  const chips = sortRightsChips(summary.rights_chips ?? []);
  const shown = chips.slice(0, MAX_CHIPS);
  const more = chips.length - shown.length;
  const n = summary.needs_attention;
  const titleId = `case-title-${summary.case_id}`;
  return (
    <article
      aria-labelledby={titleId}
      className={cn(
        "group relative grid grid-cols-1 gap-x-6 gap-y-2 border-b border-line px-4 py-3.5 transition-colors duration-fast last:border-b-0 hover:bg-parchment sm:grid-cols-[minmax(0,1fr)_auto] sm:px-5",
        className,
      )}
    >
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <h3 id={titleId} className="font-display text-[1.0625rem] font-semibold leading-snug text-ink">
            <Link href={`/case/${summary.case_id}`} className="rounded-sm text-ink no-underline after:absolute after:inset-0 after:content-[''] group-hover:text-maroon">
              {summary.title}
            </Link>
          </h3>
          <span className="font-mono text-xs text-ink-muted">{summary.case_id}</span>
        </div>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm text-ink-soft">
          <span className="font-medium text-ink">{stage.label}</span>
          <span className="tabular text-xs">Step {stepNo} of {STEPPER_STAGES.length}</span>
          <span className="inline-flex items-center gap-1 text-xs"><Clock aria-hidden className="size-3.5" />{activityLabel(summary.last_activity)}</span>
        </p>
        {shown.length > 0 ? (
          <ul aria-label="Rights to check" className="relative z-10 flex flex-wrap gap-x-4 gap-y-1">
            {shown.map((c) => (
              <li key={c.raw}>
                {c.status ? <StatusBadge status={c.status} kind="rights" label={c.label} /> : <span className="text-[13px] text-ink-soft">{c.label}</span>}
              </li>
            ))}
            {more > 0 ? <li className="text-[13px] text-ink-muted">+{more} more</li> : null}
          </ul>
        ) : (
          <p className="text-xs text-ink-muted">No rights checked yet.</p>
        )}
      </div>
      <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end sm:justify-center sm:gap-1.5">
        {n > 0 ? (
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-haldi">
            <BellRing aria-hidden className="size-3.5" />
            {n} {n === 1 ? "item needs" : "items need"} attention
          </span>
        ) : (
          <span className="text-sm text-ink-muted">Nothing waiting</span>
        )}
        <span className="inline-flex items-center gap-1 text-sm font-medium text-maroon">
          Open <ArrowRight aria-hidden className="size-4 transition-transform duration-fast group-hover:translate-x-0.5" />
        </span>
      </div>
    </article>
  );
}

export default CaseCard;
