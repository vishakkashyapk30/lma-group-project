"use client";
// Dates tab (plan §7.2): the List of Dates and Events, sorted by date. Every row carries its source; conflicting dates
// sit side by side; counsel can edit any row (it becomes USER_EDITED). Peshkar's calendar signature shows while it works.
import { Pencil, Undo2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { AgentSignature } from "@/components/agents/AgentSignature";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { daysBetween, formatCourtDate, parseIsoDate } from "@/lib/format";
import type { TimelineEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAgentActivity, useCaseData, useEdits } from "@/lib/workspace";
import {
  focusClass, focusDomId, InlineNote, SourceLine, SourceQuote, TabHeader, tabState, TabShell, useFocusItem,
} from "./shared";

export interface DatesTabProps {
  caseId: string;
  className?: string;
}

/** Group events that conflict with each other (directly or through a chain) so they can be shown side by side. */
function groupConflicts(events: TimelineEvent[]): TimelineEvent[][] {
  const byId = new Map(events.map((e) => [e.event_id, e]));
  const seen = new Set<string>();
  const groups: TimelineEvent[][] = [];
  for (const e of events) {
    if (seen.has(e.event_id)) continue;
    const group: TimelineEvent[] = [];
    const stack = [e.event_id];
    while (stack.length) {
      const id = stack.pop() as string;
      if (seen.has(id)) continue;
      seen.add(id);
      const ev = byId.get(id);
      if (!ev) continue;
      group.push(ev);
      for (const other of ev.conflicts_with) if (byId.has(other) && !seen.has(other)) stack.push(other);
      for (const o of events) if (o.conflicts_with.includes(id) && !seen.has(o.event_id)) stack.push(o.event_id);
    }
    group.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
    groups.push(group);
  }
  return groups;
}

interface EventCardProps {
  event: TimelineEvent;
  dayNumber: number | null;
  focusedId: string | null;
}

function EventCard({ event, dayNumber, focusedId }: EventCardProps): ReactElement {
  const { editDate, resetDate } = useEdits();
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState(event.date);
  const [label, setLabel] = useState(event.label);
  const [error, setError] = useState<string | null>(null);
  const dateRef = useRef<HTMLInputElement | null>(null);
  const editBtn = useRef<HTMLButtonElement | null>(null);
  const wasEditing = useRef(false);
  const domId = focusDomId("dates", event.event_id);

  useEffect(() => {
    if (editing) dateRef.current?.focus();
    else if (wasEditing.current) editBtn.current?.focus();
    wasEditing.current = editing;
  }, [editing]);

  const start = () => {
    setDate(event.date);
    setLabel(event.label);
    setError(null);
    setEditing(true);
  };

  const save = () => {
    if (!parseIsoDate(date)) {
      setError("Enter a valid date.");
      return;
    }
    if (!label.trim()) {
      setError("The row needs a description.");
      return;
    }
    editDate(event.event_id, { date, label: label.trim() });
    setEditing(false);
  };

  return (
    <article
      id={domId}
      tabIndex={-1}
      aria-labelledby={`${domId}-label`}
      className={cn(
        "scroll-mt-4 rounded-lg border bg-cream p-3 shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-maroon",
        event.status === "AMBIGUOUS" ? "border-haldi/60" : "border-line",
        focusClass(focusedId, event.event_id),
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-baseline gap-2">
          <time dateTime={event.date} className="numeral text-lg font-semibold text-maroon">{formatCourtDate(event.date)}</time>
          {dayNumber !== null ? <span className="cite text-xs text-ink-soft">day {dayNumber}</span> : null}
        </p>
        <StatusBadge status={event.status} kind="field" size="sm" />
      </div>

      {editing ? (
        <div className="mt-2 space-y-2">
          <div className="grid gap-2 sm:grid-cols-[10rem_1fr]">
            <div>
              <label htmlFor={`${domId}-date`} className="block text-xs font-semibold text-ink-soft">Date</label>
              <Input id={`${domId}-date`} type="date" ref={dateRef} value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div>
              <label htmlFor={`${domId}-text`} className="block text-xs font-semibold text-ink-soft">What happened</label>
              <Input
                id={`${domId}-text`}
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") save();
                  if (e.key === "Escape") setEditing(false);
                }}
              />
            </div>
          </div>
          {error ? <InlineNote>{error}</InlineNote> : null}
          <InlineNote tone="info">Saving marks this row as edited by counsel.</InlineNote>
          <div className="flex gap-2">
            <Button size="sm" onClick={save}>Save</Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <p id={`${domId}-label`} className="mt-1 text-sm text-ink">{event.label}</p>
      )}

      <div className="mt-2 space-y-2">
        <SourceLine source={event.source} />
        <SourceQuote source={event.source} />
      </div>

      {!editing ? (
        <div className="mt-2 flex flex-wrap gap-2" data-print-hide>
          <Button ref={editBtn} size="sm" variant="secondary" onClick={start} aria-label={`Edit row: ${event.label}`}>
            <Pencil aria-hidden /> Edit
          </Button>
          {event.status === "USER_EDITED" ? (
            <Button size="sm" variant="ghost" onClick={() => resetDate(event.event_id)} aria-label={`Restore the original of row: ${event.label}`}>
              <Undo2 aria-hidden /> Restore original
            </Button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

export function DatesTab({ caseId, className }: DatesTabProps): ReactElement {
  void caseId;
  const data = useCaseData();
  const activity = useAgentActivity();
  const dates = data.dates;
  const focusedId = useFocusItem("dates", Boolean(dates));

  const firstRemand = data.dossier?.fields.first_remand.value ?? null;
  const groups = useMemo(() => groupConflicts(dates ?? []), [dates]);

  const state = tabState({
    tab: "dates", resource: "dates", noun: "List of Dates", loading: data.loading.dates, error: data.errors.dates, hasData: Boolean(dates),
    onRetry: () => void data.refresh(["dates"]),
    emptyTitle: "No dates yet",
    emptyBody: "The List of Dates and Events is built from the dated events Munshi files from your documents.",
  });
  if (state || !dates) return state ?? <></>;

  const working = activity.byAgent.PESHKAR.phase === "working";
  const conflicts = groups.filter((g) => g.length > 1).length;
  const dayNumber = (e: TimelineEvent): number | null => {
    if (!firstRemand || e.date < firstRemand) return null;
    const d = daysBetween(firstRemand, e.date);
    return d === null ? null : d + 1;
  };

  // Keep the rows in date order: a conflict group sits where its earliest date falls.
  const ordered = [...groups].sort((a, b) => (a[0].date < b[0].date ? -1 : a[0].date > b[0].date ? 1 : 0));

  return (
    <TabShell label="List of Dates and Events" className={className}>
      <TabHeader
        agent="PESHKAR"
        title="List of Dates and Events"
        description="One row per dated event, sorted by date, each with its source. This list feeds the Rights Radar and the filed application. Edit any row; conflicting dates are shown side by side."
        signature={<AgentSignature agent="PESHKAR" mode="working" active={working} statusText={working ? activity.byAgent.PESHKAR.text : undefined} />}
      />

      <p className="text-sm text-ink-soft" aria-live="polite">
        {dates.length} event{dates.length === 1 ? "" : "s"}
        {conflicts > 0 ? `, ${conflicts} conflict${conflicts === 1 ? "" : "s"} for counsel to settle` : ", no conflicts"}.
        {firstRemand ? ` Day numbers count from the first remand, ${formatCourtDate(firstRemand)}, as day 1.` : ""}
      </p>

      <ol className="relative flex flex-col gap-4 border-l-2 border-gold/60 pl-5">
        {ordered.map((group) => {
          const first = group[0];
          return (
            <li key={group.map((g) => g.event_id).join("-")} className="relative">
              <span aria-hidden className="absolute -left-[1.72rem] top-4 size-2.5 rounded-full border-2 border-maroon bg-parchment" />
              {group.length === 1 ? (
                <EventCard event={first} dayNumber={dayNumber(first)} focusedId={focusedId} />
              ) : (
                <div role="group" aria-label={`Conflicting dates: ${first.label}`} className="rounded-lg border border-haldi bg-haldi/[0.06] p-3">
                  <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
                    <StatusBadge status="AMBIGUOUS" kind="field" size="sm" />
                    The documents give {group.length} different dates for this event. Compare and edit the one that is wrong.
                  </p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {group.map((e) => (
                      <EventCard key={e.event_id} event={e} dayNumber={dayNumber(e)} focusedId={focusedId} />
                    ))}
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </TabShell>
  );
}

export default DatesTab;
