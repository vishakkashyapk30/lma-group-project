"use client";
// Dossier tab (plan §7.1, §13.5): every field with its value, status, source (doc, page, route, language) and quote.
// Clicking a value selects its source in the case-file viewer; Edit marks the field USER_EDITED; AMBIGUOUS fields show
// the conflicting values side by side; changed fields are highlighted after a change set (plan §7.4); Gate 1 starts here.
import { CheckCircle2, HelpCircle, Pencil, ShieldCheck, Undo2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactElement, type ReactNode } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/lib/errors";
import {
  DATE_FIELDS, dossierEntries, fieldLabel, formatFieldValue, parseEditText, sectionDetails, STRING_LIST_FIELDS,
  valueToEditText,
} from "@/lib/fields";
import { formatCourtDate, toSelectedSource } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  CaseDossier, CoAccusedBail, DossierFieldName, FieldStatus, PreviousBail, SectionValue, SourceRef, TimelineEvent, TrackedField,
} from "@/lib/types";
import { checklistKey, useAgentActivity, useCaseData, useEdits, useGateChecklist, useGates, useSelectedSource } from "@/lib/workspace";
import { GateModal } from "../GateModal";
import {
  ChangedTag, focusClass, focusDomId, InlineNote, SectionTitle, SourceLine, SourceQuote, TabHeader, tabState, TabShell, useFocusItem,
} from "./shared";

export interface DossierTabProps {
  caseId: string;
  className?: string;
}

const STATUS_ORDER: FieldStatus[] = ["VERIFIED", "COMPUTED", "AMBIGUOUS", "UNSUPPORTED", "USER_STATED", "USER_EDITED"];

/** The value, one line per item, as spans so the whole block can sit inside a button. */
function FieldValue({ name, value }: { name: DossierFieldName; value: unknown }): ReactElement {
  if (value === null || value === undefined) {
    return <span className="block text-sm italic text-ink-soft">Not found in the file</span>;
  }
  const line = (key: string | number, text: ReactNode, sub?: ReactNode) => (
    <span key={key} className="block">
      <span className="block text-sm text-ink">{text}</span>
      {sub ? <span className="block text-xs text-ink-soft">{sub}</span> : null}
    </span>
  );
  if (name === "sections") {
    const list = value as SectionValue[];
    const details = sectionDetails(list);
    return (
      <span className="block space-y-1">
        {list.map((s, i) => line(i, <span className="cite font-medium">{s.as_written}{s.equivalent ? ` (≈ ${s.equivalent})` : ""}</span>, details[i]))}
      </span>
    );
  }
  if (name === "previous_bail") {
    const list = value as PreviousBail[];
    if (list.length === 0) return line("none", "None on record");
    return <span className="block space-y-1">{list.map((b, i) => line(i, `${b.court}: ${b.outcome}`, formatCourtDate(b.date)))}</span>;
  }
  if (name === "co_accused_bail") {
    const list = value as CoAccusedBail[];
    if (list.length === 0) return line("none", "None on record");
    return <span className="block space-y-1">{list.map((b, i) => line(i, `${b.id}: ${b.outcome}`, b.date ? formatCourtDate(b.date) : null))}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return line("none", "None");
    return <span className="block space-y-0.5">{value.map((v, i) => line(i, String(v)))}</span>;
  }
  return line("v", formatFieldValue(name, value));
}

/** Other values the documents give for a date this field uses, from the List of Dates' conflict links. */
function conflictAlternatives(value: unknown, dates: TimelineEvent[] | null): TimelineEvent[] {
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

interface FieldCardProps {
  name: DossierFieldName;
  field: TrackedField<unknown>;
  dates: TimelineEvent[] | null;
  changed: boolean;
  focusedId: string | null;
}

function FieldCard({ name, field, dates, changed, focusedId }: FieldCardProps): ReactElement {
  const { selectSource } = useSelectedSource();
  const { editField } = useEdits();
  const { resolutions, acknowledge, unacknowledge } = useGates();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement | HTMLInputElement | null>(null);
  const editBtnRef = useRef<HTMLButtonElement | null>(null);
  const wasEditing = useRef(false);

  const domId = focusDomId("dossier", name);
  const label = fieldLabel(name);
  const selectable = toSelectedSource(field.source) !== null;
  const ackKey = checklistKey("UNSUPPORTED", name);
  const acknowledged = field.status === "UNSUPPORTED" && (resolutions.acknowledged.includes(ackKey) || resolutions.acknowledged.includes(name));
  const alternatives = field.status === "AMBIGUOUS" ? conflictAlternatives(field.value, dates) : [];
  const isInput = DATE_FIELDS.has(name) || name === "custody_days" || name === "trial_stage";
  const hint = STRING_LIST_FIELDS.has(name)
    ? "One item per line."
    : DATE_FIELDS.has(name)
      ? "Use YYYY-MM-DD."
      : name === "custody_days"
        ? "A whole number of days."
        : name === "trial_stage"
          ? "A short phrase, for example: charges not framed."
          : "Structured field: edit as JSON.";

  useEffect(() => {
    if (editing) inputRef.current?.focus();
    else if (wasEditing.current) editBtnRef.current?.focus();
    wasEditing.current = editing;
  }, [editing]);

  const startEdit = () => {
    setText(valueToEditText(name, field.value));
    setError(null);
    setEditing(true);
  };

  const save = async () => {
    setError(null);
    let parsed;
    try {
      parsed = parseEditText(name, text);
    } catch (e) {
      setError(errorMessage(e));
      return;
    }
    setSaving(true);
    try {
      await editField(name, parsed);
      setEditing(false);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const editId = `${domId}-edit`;
  const hintId = `${domId}-hint`;
  const errId = `${domId}-error`;
  const verb = field.value === null || field.status === "UNSUPPORTED" ? "Enter value" : "Edit";

  return (
    <article
      id={domId}
      data-testid="dossier-field"
      data-field={name}
      tabIndex={-1}
      aria-labelledby={`${domId}-label`}
      data-changed={changed || undefined}
      className={cn(
        "scroll-mt-4 rounded-lg border bg-cream p-4 shadow-sm outline-none transition-shadow focus-visible:ring-2 focus-visible:ring-maroon",
        field.status === "UNSUPPORTED" && !acknowledged ? "border-sindoor/50" : "border-line",
        changed && "border-haldi bg-haldi/[0.08]",
        focusClass(focusedId, name),
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 id={`${domId}-label`} className="font-display text-base font-semibold text-maroon">{label}</h4>
        <div className="flex flex-wrap items-center gap-1.5">
          {changed ? <ChangedTag /> : null}
          <StatusBadge status={field.status} kind="field" />
        </div>
      </div>

      <div className="mt-2">
        {editing ? (
          <div className="space-y-2">
            <label htmlFor={editId} className="block text-xs font-semibold text-ink-soft">
              New value for {label}
            </label>
            {isInput ? (
              <Input
                id={editId}
                data-testid="dossier-field-input"
                ref={(el) => { inputRef.current = el; }}
                type={DATE_FIELDS.has(name) ? "date" : "text"}
                inputMode={name === "custody_days" ? "numeric" : undefined}
                value={text}
                onChange={(e) => setText(e.target.value)}
                aria-describedby={cn(hintId, error && errId)}
                aria-invalid={Boolean(error) || undefined}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void save();
                  if (e.key === "Escape") setEditing(false);
                }}
              />
            ) : (
              <Textarea
                id={editId}
                data-testid="dossier-field-input"
                ref={(el) => { inputRef.current = el; }}
                rows={STRING_LIST_FIELDS.has(name) ? 4 : 7}
                value={text}
                onChange={(e) => setText(e.target.value)}
                aria-describedby={cn(hintId, error && errId)}
                aria-invalid={Boolean(error) || undefined}
                className={cn(!STRING_LIST_FIELDS.has(name) && "font-mono text-xs")}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setEditing(false);
                }}
              />
            )}
            <InlineNote tone="info" id={hintId}>
              {hint} Saving marks this field as edited by counsel; it then has no court source behind it.
            </InlineNote>
            {error ? <InlineNote id={errId}>{error}</InlineNote> : null}
            <div className="flex gap-2">
              <Button size="sm" data-testid="dossier-field-save" onClick={() => void save()} disabled={saving}>
                {saving ? "Saving" : "Save"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)} disabled={saving}>
                Cancel
              </Button>
            </div>
          </div>
        ) : selectable ? (
          <button
            type="button"
            data-testid="dossier-field-source"
            onClick={() => selectSource(field.source, name)}
            aria-label={`${label}: show the source in the case file`}
            title="Show this in the case file"
            className="-mx-2 block w-[calc(100%+1rem)] rounded-md px-2 py-1 text-left transition-colors duration-fast hover:bg-parchment"
          >
            <FieldValue name={name} value={field.value} />
          </button>
        ) : (
          <div className="py-1">
            <FieldValue name={name} value={field.value} />
          </div>
        )}
      </div>

      {field.status === "AMBIGUOUS" ? (
        <div className="mt-3 rounded-md border border-haldi/50 bg-haldi/[0.06] p-3" role="group" aria-label={`Conflicting values for ${label}`}>
          <p className="text-xs font-semibold text-ink">The documents disagree. Counsel decides which value stands.</p>
          {alternatives.length > 0 ? (
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <div className="rounded-md border border-line bg-cream p-2">
                <p className="eyebrow">Used in this field</p>
                <div className="mt-1"><FieldValue name={name} value={field.value} /></div>
                <SourceLine source={field.source} className="mt-1" />
              </div>
              {alternatives.map((alt) => (
                <div key={alt.event_id} className="rounded-md border border-haldi/50 bg-cream p-2">
                  <p className="eyebrow">Another document says</p>
                  <p className="mt-1 text-sm text-ink">{formatCourtDate(alt.date)}</p>
                  <p className="text-xs text-ink-soft">{alt.label}</p>
                  <SourceLine source={alt.source} className="mt-1" />
                </div>
              ))}
            </div>
          ) : name === "sections" && Array.isArray(field.value) ? (
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {(field.value as SectionValue[]).map((s, i) => (
                <div key={i} className="rounded-md border border-line bg-cream p-2 text-sm">
                  <p className="eyebrow">As written</p>
                  <p className="cite">{s.as_written}</p>
                  <p className="eyebrow mt-1">Mapped to</p>
                  <p className="cite">{s.equivalent ?? "No single equivalent"}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-1 text-xs text-ink-soft">The other value is on the Dates tab, marked as a conflict.</p>
          )}
        </div>
      ) : null}

      <div className="mt-3 space-y-2">
        <SourceLine source={field.source as SourceRef | null} />
        <SourceQuote source={field.source} />
        {field.status === "USER_EDITED" ? <p className="text-xs text-ink-soft">Corrected by counsel. No court record backs this value.</p> : null}
        {field.status === "USER_STATED" && !field.source?.quote ? <p className="text-xs text-ink-soft">Stated by counsel. No court record backs this value.</p> : null}
      </div>

      {!editing ? (
        <div className="mt-3 flex flex-wrap items-center gap-2" data-print-hide>
          <Button ref={editBtnRef} size="sm" variant="secondary" data-testid="dossier-field-edit" onClick={startEdit} aria-label={`${verb} ${label}`}>
            <Pencil aria-hidden /> {verb}
          </Button>
          {field.status === "UNSUPPORTED" ? (
            acknowledged ? (
              <>
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-neem">
                  <CheckCircle2 aria-hidden className="size-3.5" /> Acknowledged: stays unsupported
                </span>
                <Button size="sm" variant="ghost" onClick={() => unacknowledge(ackKey)} aria-label={`Undo acknowledging ${label}`}>
                  <Undo2 aria-hidden /> Undo
                </Button>
              </>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => acknowledge(ackKey)} aria-label={`Acknowledge that ${label} stays unsupported`}>
                <CheckCircle2 aria-hidden /> Acknowledge as unsupported
              </Button>
            )
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

export function DossierTab({ caseId, className }: DossierTabProps): ReactElement {
  const data = useCaseData();
  const { changedFields } = useEdits();
  const checklist = useGateChecklist("GATE_1_DOSSIER");
  const activity = useAgentActivity();
  const [gateOpen, setGateOpen] = useState(false);
  const dossier: CaseDossier | null = data.dossier;
  const focusedId = useFocusItem("dossier", Boolean(dossier));

  const counts = useMemo(() => {
    const c = new Map<FieldStatus, number>();
    if (dossier) for (const [, f] of dossierEntries(dossier)) c.set(f.status, (c.get(f.status) ?? 0) + 1);
    return c;
  }, [dossier]);

  const state = tabState({
    tab: "dossier", resource: "dossier", noun: "dossier", loading: data.loading.dossier, error: data.errors.dossier, hasData: Boolean(dossier),
    onRetry: () => void data.refresh(["dossier"]),
    emptyTitle: "No dossier yet",
    emptyBody: "Peshkar builds the dossier once Munshi has filed the case papers. Upload the file in the case-file pane to begin.",
  });
  if (state || !dossier) return state ?? <></>;

  const peshkar = activity.byAgent.PESHKAR;
  const changed = new Set<string>(changedFields);
  const unsupported = checklist.items.filter((i) => i.kind === "UNSUPPORTED");

  return (
    <TabShell label="Dossier" className={className}>
      <TabHeader
        agent="PESHKAR"
        title="Case dossier"
        description={
          <>
            Each value below was read from the file or computed by a tool, and shows where it came from.
            {dossier.court ? ` ${dossier.court}.` : ""}
            {dossier.as_of ? ` As of ${formatCourtDate(dossier.as_of)}.` : ""}
          </>
        }
      />
      <p className="sr-only" aria-live="polite">
        {peshkar.phase === "working" ? "Peshkar is updating the dossier." : ""}
      </p>

      <div role="group" aria-label="Fields by status" className="flex flex-wrap gap-1.5">
        {STATUS_ORDER.filter((s) => counts.get(s)).map((s) => (
          <StatusBadge key={s} status={s} kind="field" detail={`${counts.get(s)}`} size="sm" />
        ))}
      </div>

      <div className="flex flex-col gap-3">
        {dossierEntries(dossier).map(([name, field]) => (
          <FieldCard key={name} name={name} field={field} dates={data.dates} changed={changed.has(name)} focusedId={focusedId} />
        ))}
      </div>

      <section aria-labelledby="dossier-questions" className="space-y-2">
        <SectionTitle id="dossier-questions">Open questions</SectionTitle>
        {dossier.open_questions.length === 0 ? (
          <p className="text-sm text-ink-soft">None. Nothing in the file needs a question to counsel.</p>
        ) : (
          <ul className="space-y-2">
            {dossier.open_questions.map((q) => (
              <li key={q} className="flex items-start gap-2 rounded-md border border-line bg-cream px-3 py-2 text-sm text-ink">
                <HelpCircle aria-hidden className="mt-0.5 size-4 shrink-0 text-haldi" />
                <span>{q} <span className="text-ink-soft">Answer in the chat, or enter the value in the field above.</span></span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="dossier-gate" className="rounded-lg border border-maroon/40 bg-parchment p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h3 id="dossier-gate" className="flex items-center gap-2 font-display text-lg font-semibold text-maroon">
              <ShieldCheck aria-hidden className="size-5" /> Gate 1: approve the dossier
            </h3>
            <p className="mt-1 text-sm text-ink-soft">
              {checklist.approved
                ? "Counsel approved this dossier. Drafting is unlocked."
                : unsupported.length > 0 && checklist.blocking.length > 0
                  ? `${checklist.blocking.length} unsupported field${checklist.blocking.length === 1 ? "" : "s"} to edit, state or acknowledge before approval.`
                  : checklist.summary}{" "}
              Only counsel can approve; the system never does.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={checklist.uiStatus} kind="gate" />
            <Button onClick={() => setGateOpen(true)} data-print-hide>
              {checklist.approved ? "View approval" : "Review and approve"}
            </Button>
          </div>
        </div>
      </section>
      <GateModal gate="GATE_1_DOSSIER" caseId={caseId} open={gateOpen} onClose={() => setGateOpen(false)} />
    </TabShell>
  );
}

export default DossierTab;
