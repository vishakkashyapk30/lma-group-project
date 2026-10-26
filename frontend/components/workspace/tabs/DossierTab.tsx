"use client";
// Review facts (plan §7.1, §13.5): a short list of what needs you, then every fact as label, value and one plain status
// word. A fact opens in the side panel with its page, quote and how it was read. Edit changes a value in place. Confirming
// the facts is Gate 1; it asks first, and says what it locks.
import { Pencil } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/errors";
import { DATE_FIELDS, dossierEntries, fieldLabel, parseEditText, STRING_LIST_FIELDS, valueToEditText } from "@/lib/fields";
import { formatCourtDate, plural, toSelectedSource } from "@/lib/format";
import type { CaseDossier, DossierFieldName, SourceRef, TrackedField } from "@/lib/types";
import { cn } from "@/lib/utils";
import { checklistKey, useCaseData, useEdits, useGateChecklist, useGates, useNeedsYou, useWorkspace } from "@/lib/workspace";
import { GateModal } from "../GateModal";
import { NeedsYou } from "../NeedsYou";
import { StepFooter, StepFrame } from "../StepFrame";
import { DatesTab } from "./DatesTab";
import { FieldValue } from "./FieldValue";
import { ChangedTag, focusClass, focusDomId, InlineNote, stepState, useFocusItem, type FocusedItem } from "./shared";

export interface DossierTabProps {
  caseId: string;
}

interface FactRowProps {
  name: DossierFieldName;
  field: TrackedField<unknown>;
  changed: boolean;
  focused: FocusedItem | null;
}

function FactRow({ name, field, changed, focused }: FactRowProps): ReactElement {
  const ws = useWorkspace();
  const toast = useToast();
  const { editField } = useEdits();
  const { resolutions, acknowledge, unacknowledge } = useGates();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement | HTMLInputElement | null>(null);
  const editBtnRef = useRef<HTMLButtonElement | null>(null);
  const wasEditing = useRef(false);
  const asked = useRef(0);

  const domId = focusDomId("dossier", name);
  const label = fieldLabel(name);
  const selectable = toSelectedSource(field.source) !== null;
  const ackKey = checklistKey("UNSUPPORTED", name);
  const markedUnknown = field.status === "UNSUPPORTED" && (resolutions.acknowledged.includes(ackKey) || resolutions.acknowledged.includes(name));
  const isInput = DATE_FIELDS.has(name) || name === "custody_days" || name === "trial_stage";
  const hint = STRING_LIST_FIELDS.has(name)
    ? "One item per line."
    : DATE_FIELDS.has(name)
      ? "Use the date picker."
      : name === "custody_days"
        ? "A whole number of days."
        : name === "trial_stage"
          ? "A short phrase, for example: charges not framed."
          : "Structured value: edit as JSON.";

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

  // "Add value" in the needs-you list jumps here and opens the editor.
  useEffect(() => {
    if (focused?.id === name && focused.intent === "edit" && !editing && asked.current !== ws.focusTarget?.nonce) {
      asked.current = ws.focusTarget?.nonce ?? 0;
      setText(valueToEditText(name, field.value));
      setError(null);
      setEditing(true);
    }
  }, [focused, name, editing, ws.focusTarget?.nonce, field.value]);

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

  const show = () => {
    ws.clearSource();
    ws.openDetail({ kind: "field", name });
    if (selectable) ws.selectSource(field.source as SourceRef, name);
  };

  const editId = `${domId}-edit`;
  const hintId = `${domId}-hint`;
  const errId = `${domId}-error`;
  const verb = field.value === null || field.status === "UNSUPPORTED" ? "Add value" : "Edit";

  return (
    <li
      id={domId}
      data-testid="dossier-field"
      data-field={name}
      data-status={field.status}
      tabIndex={-1}
      aria-labelledby={`${domId}-label`}
      data-changed={changed || undefined}
      className={cn(
        "group scroll-mt-4 py-3.5 outline-none focus-visible:ring-2 focus-visible:ring-maroon",
        changed && "border-l-2 border-haldi pl-3",
        focusClass(focused?.id ?? null, name),
      )}
    >
      {editing ? (
        <div className="space-y-3">
          <label htmlFor={editId} id={`${domId}-label`} className="block font-medium text-ink">
            {label}
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
            {hint} It will show as entered by you, with no court record behind it.
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
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 sm:grid-cols-[9.5rem_minmax(0,1fr)_auto]">
          <h4 id={`${domId}-label`} className="col-span-2 font-sans text-sm font-medium text-ink-soft sm:col-span-1 sm:pt-0.5">
            {label}
          </h4>
          <div className="min-w-0">
            <button
              type="button"
              data-testid="dossier-field-source"
              onClick={show}
              aria-label={`${label}: show the source`}
              title="Show the source"
              className="-mx-1.5 block w-[calc(100%+0.75rem)] rounded-md px-1.5 py-0.5 text-left transition-colors duration-fast hover:bg-parchment-deep/70"
            >
              <FieldValue name={name} value={field.value} />
            </button>
            {changed ? <ChangedTag /> : null}
            {markedUnknown ? <p className="mt-1 text-sm text-ink-soft">Marked as unknown.</p> : null}
          </div>
          <div className="flex flex-col items-end gap-1 text-right" data-print-hide>
            <StatusBadge status={field.status} kind="field" size="sm" className={field.status === "VERIFIED" ? "text-ink-muted" : undefined} />
            <div className="flex items-center gap-1 lg:opacity-0 lg:transition-opacity lg:duration-fast lg:group-focus-within:opacity-100 lg:group-hover:opacity-100">
              {field.status === "AMBIGUOUS" ? (
                <Button size="sm" variant="secondary" onClick={show} aria-label={`Check ${label}`}>
                  Check
                </Button>
              ) : null}
              {field.status === "UNSUPPORTED" && !markedUnknown ? (
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Mark ${label} as unknown`}
                  onClick={() => {
                    acknowledge(ackKey);
                    toast({ title: `${label} marked as unknown`, action: { label: "Undo", onClick: () => unacknowledge(ackKey) } });
                  }}
                >
                  Mark unknown
                </Button>
              ) : null}
              {markedUnknown ? (
                <Button size="sm" variant="ghost" onClick={() => unacknowledge(ackKey)} aria-label={`Undo marking ${label} as unknown`}>
                  Undo
                </Button>
              ) : null}
              <Button ref={editBtnRef} size="sm" variant="ghost" data-testid="dossier-field-edit" onClick={startEdit} aria-label={`${verb} ${label}`}>
                <Pencil aria-hidden /> {verb}
              </Button>
            </div>
          </div>
        </div>
      )}
    </li>
  );
}

export function DossierTab({ caseId }: DossierTabProps): ReactElement {
  const ws = useWorkspace();
  const data = useCaseData();
  const { changedFields } = useEdits();
  const checklist = useGateChecklist("GATE_1_DOSSIER");
  const needs = useNeedsYou("DOSSIER");
  const [gateOpen, setGateOpen] = useState(false);
  const dossier: CaseDossier | null = data.dossier;
  const focused = useFocusItem("dossier", Boolean(dossier));
  const section = ws.activeTab === "dates" ? "dates" : "facts";

  const state = stepState({
    // A dossier with no fields yet (no papers read) is empty too: there is nothing to confirm, so Gate 1 is not offered.
    resource: "dossier", noun: "facts", loading: data.loading.dossier, error: data.errors.dossier, hasData: dossier !== null && dossierEntries(dossier).length > 0,
    onRetry: () => void data.refresh(["dossier"]),
    emptyTitle: "No facts yet",
    emptyBody: "The facts are drawn from your documents. Add the case papers first.",
    emptyAction: <Button variant="secondary" onClick={() => ws.setStage("INTAKE")}>Add documents</Button>,
  });
  if (state || !dossier) {
    return (
      <StepFrame title="Review facts" intro="Check each fact against the page it came from.">
        {state}
      </StepFrame>
    );
  }

  const changed = new Set<string>(changedFields);
  const entries = dossierEntries(dossier);
  const confirmed = checklist.approved;
  const blocked = checklist.blocking.length > 0;

  return (
    <StepFrame
      title="Review facts"
      intro={
        <>
          Check each fact against the page it came from.
          {dossier.court ? ` ${dossier.court}.` : ""}
          {dossier.as_of ? ` As of ${formatCourtDate(dossier.as_of)}.` : ""}
        </>
      }
      footer={
        confirmed ? (
          <StepFooter label="Continue to Check rights" onClick={() => ws.setStage("RIGHTS")} hint="You confirmed these facts." />
        ) : (
          <StepFooter
            label="Confirm facts and continue"
            onClick={() => setGateOpen(true)}
            disabled={blocked}
            hint={blocked ? `${plural(checklist.blocking.length, "item")} above ${checklist.blocking.length === 1 ? "needs" : "need"} you before you can confirm.` : undefined}
            testId="confirm-facts-button"
          />
        )
      }
    >
      <NeedsYou items={needs} empty="Nothing needs your attention. Look through the facts, then confirm." />

      <Tabs value={section} onValueChange={(v) => ws.setTab(v === "dates" ? "dates" : "dossier")}>
        <TabsList aria-label="Facts and dates" className="mb-5">
          <TabsTrigger value="facts" data-testid="right-tab-dossier">
            Facts <span className="tabular font-normal text-ink-muted">({entries.length})</span>
          </TabsTrigger>
          <TabsTrigger value="dates" data-testid="right-tab-dates">
            List of dates {data.dates ? <span className="tabular font-normal text-ink-muted">({data.dates.length})</span> : null}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="facts">
          <ul aria-label="Facts" className="divide-y divide-line border-y border-line">
            {entries.map(([name, field]) => (
              <FactRow key={name} name={name} field={field} changed={changed.has(name)} focused={focused} />
            ))}
          </ul>
        </TabsContent>
        <TabsContent value="dates">
          <DatesTab />
        </TabsContent>
      </Tabs>
      <GateModal gate="GATE_1_DOSSIER" caseId={caseId} open={gateOpen} onClose={() => setGateOpen(false)} />
    </StepFrame>
  );
}

export default DossierTab;
