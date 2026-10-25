// Conflicting dates (plan §7.2): rows of the List of Dates that disagree with each other, and the other values the documents
// give for a date a dossier field uses. Pure.
import type { TimelineEvent } from "../types";

/** Group events that conflict with each other (directly or through a chain) so they can be shown together. */
export function groupConflicts(events: TimelineEvent[]): TimelineEvent[][] {
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

/** Other values the documents give for a date this field uses, from the List of Dates' conflict links. */
export function conflictAlternatives(value: unknown, dates: TimelineEvent[] | null): TimelineEvent[] {
  if (!dates || value === null || value === undefined) return [];
  const isoDates = new Set(JSON.stringify(value).match(/\d{4}-\d{2}-\d{2}/g) ?? []);
  if (isoDates.size === 0) return [];
  const byId = new Map(dates.map((e) => [e.event_id, e]));
  const out = new Map<string, TimelineEvent>();
  for (const e of dates) {
    if (!isoDates.has(e.date) || e.conflicts_with.length === 0) continue;
    for (const id of e.conflicts_with) {
      const other = byId.get(id);
      if (other && !isoDates.has(other.date)) out.set(other.event_id, other);
    }
  }
  return [...out.values()];
}
