"use client";
// List of Dates and Events (plan §7.2): a plain timeline, one row per dated event in date order. Choosing a row shows its page
// in the side panel. Rows that disagree sit together with a single "Check" action. Any row can be edited.
import { Pencil } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { daysBetween, formatCourtDate, parseIsoDate, plural } from "@/lib/format";
import type { SourceRef, TimelineEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { groupConflicts, useCaseData, useEdits, useWorkspace } from "@/lib/workspace";
import { focusClass, focusDomId, InlineNote, stepState, useFocusItem, type FocusedItem } from "./shared";

interface EventRowProps {
  event: TimelineEvent;
  dayNumber: number | null;
  focused: FocusedItem | null;
}

function EventRow({ event, dayNumber, focused }: EventRowProps): ReactElement {
  const ws = useWorkspace();
  const toast = useToast();
  const { editDate, resetDate } = useEdits();
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState(event.date);
  const [label, setLabel] = useState(event.label);
  const [error, setError] = useState<string | null>(null);
  const dateRef = useRef<HTMLInputElement | null>(null);
  const editBtn = useRef<HTMLButtonElement | null>(null);
  const wasEditing = useRef(false);
  const domId = focusDomId("dates", event.event_id);
  const hasSource = Boolean(event.source?.doc && event.source.page != null);

  useEffect(() => {
    if (editing) dateRef.current?.focus();
    else if (wasEditing.current) editBtn.current?.focus();
    wasEditing.current = editing;
  }, [editing]);

  const show = () => {
    ws.clearSource();
    ws.openDetail({ kind: "date", label: event.label, date: event.date, status: event.status });
    if (hasSource) ws.selectSource(event.source as SourceRef, event.label);
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
    const before = { date: event.date, label: event.label };
    const wasEdited = event.status === "USER_EDITED";
    editDate(event.event_id, { date, label: label.trim() });
    setEditing(false);
    toast({ title: "Date saved", action: { label: "Undo", onClick: () => (wasEdited ? editDate(event.event_id, before) : resetDate(event.event_id)) } });
  };

  return (
    <li
      id={domId}
      data-testid="date-row"
      data-status={event.status}
      tabIndex={-1}
      aria-labelledby={`${domId}-label`}
      className={cn("group scroll-mt-4 py-3 outline-none focus-visible:ring-2 focus-visible:ring-maroon", focusClass(focused?.id ?? null, event.event_id))}
    >
      {editing ? (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
            <div>
              <label htmlFor={`${domId}-date`} className="block text-sm font-medium text-ink-soft">Date</label>
              <Input id={`${domId}-date`} type="date" ref={dateRef} value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div>
              <label htmlFor={`${domId}-text`} className="block text-sm font-medium text-ink-soft">What happened</label>
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
          <div className="flex gap-2">
            <Button size="sm" onClick={save}>Save</Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-[6.5rem_minmax(0,1fr)_auto] items-baseline gap-x-4 sm:grid-cols-[7.5rem_minmax(0,1fr)_auto]">
          <time dateTime={event.date} className="tabular text-ink">{formatCourtDate(event.date)}</time>
          <div className="min-w-0">
            <button
              type="button"
              id={`${domId}-label`}
              onClick={show}
              title="Show the page this came from"
              className="rounded-sm text-left text-ink underline-offset-4 hover:underline"
            >
              {event.label}
            </button>
            <p className="mt-0.5 text-sm text-ink-muted">
              {dayNumber !== null ? <span className="tabular">Day {dayNumber}</span> : null}
              {dayNumber !== null && event.status === "USER_EDITED" ? ", " : null}
              {event.status === "USER_EDITED" ? "edited by you" : null}
            </p>
          </div>
          <div className="flex gap-1 lg:opacity-0 lg:transition-opacity lg:duration-fast lg:group-focus-within:opacity-100 lg:group-hover:opacity-100" data-print-hide>
            <Button
              ref={editBtn}
              size="sm"
              variant="ghost"
              onClick={() => {
                setDate(event.date);
                setLabel(event.label);
                setError(null);
                setEditing(true);
              }}
              aria-label={`Edit row: ${event.label}`}
            >
              <Pencil aria-hidden /> Edit
            </Button>
            {event.status === "USER_EDITED" ? (
              <Button size="sm" variant="ghost" onClick={() => resetDate(event.event_id)} aria-label={`Restore the original of row: ${event.label}`}>
                Restore
              </Button>
            ) : null}
          </div>
        </div>
      )}
    </li>
  );
}

export function DatesTab(): ReactElement {
  const ws = useWorkspace();
  const data = useCaseData();
  const dates = data.dates;
  const focused = useFocusItem("dates", Boolean(dates));
  const firstRemand = data.dossier?.fields.first_remand.value ?? null;
  const groups = useMemo(() => groupConflicts(dates ?? []), [dates]);

  const state = stepState({
    resource: "dates", noun: "List of Dates", loading: data.loading.dates, error: data.errors.dates, hasData: Boolean(dates),
    onRetry: () => void data.refresh(["dates"]),
    emptyTitle: "No dates yet",
    emptyBody: "The list is built from the dated events found in your documents.",
  });
  if (state || !dates) return state ?? <></>;

  const conflicts = groups.filter((g) => g.length > 1).length;
  const dayNumber = (e: TimelineEvent): number | null => {
    if (!firstRemand || e.date < firstRemand) return null;
    const d = daysBetween(firstRemand, e.date);
    return d === null ? null : d + 1;
  };
  const ordered = [...groups].sort((a, b) => (a[0].date < b[0].date ? -1 : a[0].date > b[0].date ? 1 : 0));

  return (
    <div>
      <p className="text-ink-soft" aria-live="polite">
        {plural(dates.length, "event")}
        {conflicts > 0 ? `, ${plural(conflicts, "conflict")} to check` : ""}.
        {firstRemand ? ` Days count from the first remand, ${formatCourtDate(firstRemand)}, as day 1.` : ""}
      </p>
      <ol className="mt-3 divide-y divide-line border-y border-line">
        {ordered.map((group) => {
          const first = group[0];
          if (group.length === 1) return <EventRow key={first.event_id} event={first} dayNumber={dayNumber(first)} focused={focused} />;
          return (
            <li key={group.map((g) => g.event_id).join("-")} role="group" aria-label={`Conflicting dates: ${first.label}`} className="border-l-2 border-haldi pl-4">
              <div className="flex flex-wrap items-center justify-between gap-2 pt-3">
                <p className="text-sm font-medium text-haldi">The documents give different dates for this event</p>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    ws.clearSource();
                    ws.openDetail({ kind: "date", label: first.label, date: first.date, status: first.status });
                    if (first.source?.doc) ws.selectSource(first.source as SourceRef, first.label);
                  }}
                >
                  Check
                </Button>
              </div>
              <ol className="divide-y divide-line">
                {group.map((e) => (
                  <EventRow key={e.event_id} event={e} dayNumber={dayNumber(e)} focused={focused} />
                ))}
              </ol>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default DatesTab;
