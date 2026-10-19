"use client";
// One matter on the cause list (plan §13.5): numbered row, stage, Rights Radar chips (urgent first), items needing
// attention and last activity.
import Link from "next/link";
import { ArrowRight, BellRing, Clock } from "lucide-react";
import type { ReactElement } from "react";
import { Badge } from "@/components/ui";
import { StatusBadge } from "@/components/common/StatusBadge";
import { STAGE_BY_ID, stageIndex } from "@/lib/stages";
import { sortRightsChips } from "@/lib/status";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CaseSummary } from "@/lib/types";

/** CaseSummary plus an optional timestamp the API may add. */
export type CaseSummaryWithActivity = CaseSummary & { last_activity?: string | null };

export interface CaseCardProps {
  summary: CaseSummaryWithActivity;
  /** 1-based row number in the cause list (Fraunces numeral). */
  index?: number;
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

export function CaseCard({ summary, index, className }: CaseCardProps): ReactElement {
  const stage = STAGE_BY_ID[summary.stage];
  const chips = sortRightsChips(summary.rights_chips ?? []);
  const shown = chips.slice(0, MAX_CHIPS);
  const more = chips.length - shown.length;
  const n = summary.needs_attention;
  const titleId = `case-title-${summary.case_id}`;
  return (
    <article
      aria-labelledby={titleId}
      className={cn(
        "group relative grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 border-b border-line bg-cream px-4 py-4 transition-colors duration-fast hover:bg-parchment-deep/60 sm:grid-cols-[3.5rem_1fr_auto] sm:px-5",
        className,
      )}
    >
      <div className="font-display text-3xl font-semibold leading-none text-maroon/80 tabular sm:text-4xl" aria-hidden={index === undefined}>
        {index !== undefined ? <><span className="sr-only">Row </span>{index}</> : null}
      </div>
      <div className="min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h3 id={titleId} className="font-display text-lg font-semibold leading-snug text-ink">
            <Link href={`/case/${summary.case_id}`} className="rounded-sm no-underline after:absolute after:inset-0 after:content-[''] hover:text-maroon">
              {summary.title}
            </Link>
          </h3>
          <Badge variant="mono" size="sm">{summary.case_id}</Badge>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-ink-soft">
          <span className="inline-flex items-center gap-1.5 font-semibold text-ink">
            <span className="font-display text-base text-maroon" aria-hidden>{stage.numeral}</span>
            <span className="sr-only">Stage {stage.numeral}:</span> {stage.label}
          </span>
          <span aria-hidden className="text-gold">◆</span>
          <span className="text-xs">Stage {stageIndex(summary.stage) + 1} of 7</span>
          <span className="inline-flex items-center gap-1 text-xs"><Clock aria-hidden className="size-3.5" />{activityLabel(summary.last_activity)}</span>
        </div>
        {shown.length > 0 ? (
          <ul aria-label="Rights Radar" className="relative z-10 flex flex-wrap gap-1.5">
            {shown.map((c) => (
              <li key={c.raw}>
                {c.status ? <StatusBadge status={c.status} kind="rights" label={c.label} /> : <Badge variant="muted">{c.label}</Badge>}
              </li>
            ))}
            {more > 0 ? <li><Badge variant="outline" shape="pill">+{more} more</Badge></li> : null}
          </ul>
        ) : (
          <p className="text-xs text-ink-muted">No Rights Radar entries yet.</p>
        )}
      </div>
      <div className="col-span-2 flex items-center justify-between gap-3 sm:col-span-1 sm:flex-col sm:items-end sm:justify-center">
        {n > 0 ? (
          <span className="inline-flex items-center gap-1.5 rounded-pill border border-haldi/50 bg-haldi/[0.08] px-2.5 py-1 text-xs font-semibold text-haldi">
            <BellRing aria-hidden className="size-3.5" />
            {n} {n === 1 ? "item needs" : "items need"} attention
          </span>
        ) : (
          <span className="text-xs font-semibold text-neem">Nothing waiting on counsel</span>
        )}
        <span className="inline-flex items-center gap-1 text-sm font-semibold text-maroon">
          Open <ArrowRight aria-hidden className="size-4 transition-transform duration-fast group-hover:translate-x-0.5 motion-reduce:transition-none" />
        </span>
      </div>
    </article>
  );
}

export default CaseCard;
