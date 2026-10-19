"use client";
// Brief tab (plan §8.1, §10): the statutory position and one manuscript-style card per ground, with [F:field] and
// [A:doc#para] citation chips, transfer and good-law badges, check status, CURRENT/STALE state and highlights of what
// changed since the last approval. Open issues, the draft label, the Gate 2 entry point and the gated export live here.
import { CheckCircle2, Download, FileText, Pencil, ShieldCheck, Undo2 } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement } from "react";
import { AgentSignature } from "@/components/agents/AgentSignature";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/lib/errors";
import { fieldLabel } from "@/lib/fields";
import { diffWords } from "@/lib/diff";
import { formatCourtDate } from "@/lib/format";
import { FACTOR_LABELS } from "@/lib/labels";
import { checklistKey, useAgentActivity, useCaseData, useEdits, useGateChecklist, useGates, useStageNav, useWorkspace } from "@/lib/workspace";
import { DRAFT_LABEL, type DossierFieldName, type ExportFormat, type Ground, type GroundRevision, type OpenIssue } from "@/lib/types";
import { cn } from "@/lib/utils";
import { GateModal } from "../GateModal";
import { ArgumentText, AuthorityList } from "./citations";
import {
  ChangedTag, focusClass, focusDomId, InlineNote, SectionTitle, TabHeader, tabState, TabShell, useFocusItem,
} from "./shared";

export interface BriefTabProps {
  caseId: string;
  className?: string;
}

const STANCE: Record<Ground["stance"], string> = { favourable: "Favourable", adverse: "Adverse", not_applicable: "Not applicable" };

function latestRevision(revisions: GroundRevision[], groundId: string): GroundRevision | null {
  return revisions.filter((r) => r.ground_id === groundId).sort((a, b) => (a.at < b.at ? 1 : -1))[0] ?? null;
}

function WhatChanged({ before, after }: { before: string; after: string }): ReactElement {
  const segments = diffWords(before, after);
  return (
    <p className="rounded-md border border-line bg-cream p-3 text-sm leading-7 text-ink">
      {segments.map((s, i) =>
        s.op === "equal" ? (
          <span key={i}>{s.text}</span>
        ) : s.op === "insert" ? (
          <ins key={i} className="bg-neem/15 font-medium text-ink underline decoration-neem decoration-2 underline-offset-2">
            <span className="sr-only">[added] </span>
            {s.text}
          </ins>
        ) : (
          <del key={i} className="text-ink-soft line-through decoration-sindoor decoration-2">
            <span className="sr-only">[removed] </span>
            {s.text}
          </del>
        ),
      )}
    </p>
  );
}

interface ReviewControlsProps {
  itemKey: string;
  label: string;
  /** Present for grounds: counsel can reword the argument. */
  ground?: Ground;
}

/** Reword, accept with a note, or undo: how counsel clears a NEEDS_REVIEW item (Gate 2 needs every one resolved). */
function ReviewControls({ itemKey, label, ground }: ReviewControlsProps): ReactElement {
  const { resolutions, resolveItem, unresolveItem } = useGates();
  const { editGround, resetGround, editedGrounds } = useEdits();
  const [mode, setMode] = useState<"idle" | "reword" | "accept">("idle");
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const areaRef = useRef<HTMLTextAreaElement | null>(null);
  const noteRef = useRef<HTMLInputElement | null>(null);
  const openerRef = useRef<HTMLButtonElement | null>(null);
  const was = useRef<"idle" | "reword" | "accept">("idle");
  const resolution = resolutions.resolved[itemKey];
  const reworded = ground ? editedGrounds.includes(ground.id) : false;

  useEffect(() => {
    if (mode === "reword") areaRef.current?.focus();
    if (mode === "accept") noteRef.current?.focus();
    if (mode === "idle" && was.current !== "idle") openerRef.current?.focus();
    was.current = mode;
  }, [mode]);

  if (resolution) {
    return (
      <div className="flex flex-wrap items-center gap-2" data-print-hide>
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-neem">
          <CheckCircle2 aria-hidden className="size-3.5" /> {reworded ? "Reworded by counsel" : "Reviewed by counsel"}
          {resolution.note ? <span className="font-normal text-ink-soft">: {resolution.note}</span> : null}
        </span>
        <Button
          size="sm"
          variant="ghost"
          aria-label={`Undo review of ${label}`}
          onClick={() => (ground && reworded ? resetGround(ground.id) : unresolveItem(itemKey))}
        >
          <Undo2 aria-hidden /> Undo
        </Button>
      </div>
    );
  }

  const base = `${itemKey.replace(/[^A-Za-z0-9]/g, "-")}`;
  if (mode === "reword" && ground) {
    return (
      <div className="space-y-2" data-print-hide>
        <label htmlFor={`${base}-text`} className="block text-xs font-semibold text-ink-soft">Reworded argument for {ground.id}</label>
        <Textarea id={`${base}-text`} ref={areaRef} rows={6} value={text} onChange={(e) => setText(e.target.value)} aria-describedby={`${base}-hint`} />
        <InlineNote tone="info" id={`${base}-hint`}>
          Keep the [F:field] and [A:doc#para] markers so every statement stays tied to a fact or an authority.
        </InlineNote>
        {error ? <InlineNote>{error}</InlineNote> : null}
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => {
              if (!text.trim()) {
                setError("The argument cannot be empty.");
                return;
              }
              editGround(ground.id, text.trim(), "Reworded by counsel");
              setMode("idle");
            }}
          >
            Save wording
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setMode("idle")}>Cancel</Button>
        </div>
      </div>
    );
  }
  if (mode === "accept") {
    return (
      <div className="space-y-2" data-print-hide>
        <label htmlFor={`${base}-note`} className="block text-xs font-semibold text-ink-soft">Your note (optional)</label>
        <Input id={`${base}-note`} ref={noteRef} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why this stands, or what you checked" />
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => {
              resolveItem(itemKey, note.trim() || "Accepted by counsel");
              setMode("idle");
            }}
          >
            Mark as reviewed
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setMode("idle")}>Cancel</Button>
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap gap-2" data-print-hide>
      {ground ? (
        <Button
          ref={openerRef}
          size="sm"
          variant="secondary"
          onClick={() => {
            setText(ground.argument);
            setError(null);
            setMode("reword");
          }}
          aria-label={`Reword ${label}`}
        >
          <Pencil aria-hidden /> Reword
        </Button>
      ) : null}
      <Button size="sm" variant={ground ? "ghost" : "secondary"} ref={ground ? undefined : openerRef} onClick={() => setMode("accept")} aria-label={`Accept ${label} with a note`}>
        <CheckCircle2 aria-hidden /> Accept with a note
      </Button>
    </div>
  );
}

function GroundCard({ ground, revision, focusedId }: { ground: Ground; revision: GroundRevision | null; focusedId: string | null }): ReactElement {
  const { resolutions } = useGates();
  const { dossier } = useCaseData();
  const { changes } = useEdits();
  const { focusItem } = useStageNav();
  const domId = focusDomId("brief", ground.id);
  const key = checklistKey("NEEDS_REVIEW", ground.id);
  const resolved = Boolean(resolutions.resolved[key]);
  const needsReview = ground.check === "NEEDS_REVIEW" && !resolved;
  const stale = ground.state === "STALE" || changes.staleClaims.includes(ground.id);
  const redrafted = changes.redrafted.includes(ground.id);
  const changeReason = revision?.reason ?? changes.reasons[ground.id] ?? null;
  const facts = Object.keys(ground.depends_on.facts);
  // Facts that counsel stated (dictated or typed) have no court record behind them: the brief says so (plan §4.5, flow 5).
  const stated = facts.filter((f) => dossier?.fields[f as DossierFieldName]?.status === "USER_STATED");

  return (
    <article
      id={domId}
      data-testid="brief-ground"
      data-ground={ground.id}
      tabIndex={-1}
      aria-labelledby={`${domId}-title`}
      data-state={stale ? "STALE" : "CURRENT"}
      data-changed={redrafted || Boolean(revision) || undefined}
      className={cn(
        "scroll-mt-4 rounded-lg border border-line border-l-[5px] bg-cream p-4 shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-maroon",
        needsReview ? "border-l-haldi" : stale || revision ? "border-l-haldi" : "border-l-gold",
        (stale || revision) && "bg-haldi/[0.06]",
        focusClass(focusedId, ground.id),
      )}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="eyebrow">Ground</p>
          <h4 id={`${domId}-title`} className="font-display text-lg font-semibold leading-snug text-maroon">
            <span className="numeral mr-2 text-gold-leaf" aria-hidden>{ground.id}</span>
            <span className="sr-only">{ground.id}: </span>
            {FACTOR_LABELS[ground.factor] ?? ground.factor}
          </h4>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="outline" size="md">{STANCE[ground.stance]}</Badge>
          <StatusBadge status={ground.check} kind="claim" />
          {stale ? <StatusBadge status="STALE" kind="state" testId="state-badge" /> : null}
        </div>
      </header>

      {(stale || revision || redrafted) ? (
        <div className="mt-3 space-y-2 rounded-md border border-haldi/60 bg-haldi/[0.1] p-3" role="group" aria-label={`Changes to ${ground.id}`}>
          <div className="flex flex-wrap items-center gap-2">
            {revision || redrafted ? <ChangedTag /> : <StatusBadge status="STALE" kind="state" size="sm" testId="state-badge" />}
            {revision ? <time dateTime={revision.at} className="text-xs text-ink-soft">{formatCourtDate(revision.at)}</time> : null}
          </div>
          <p data-testid={redrafted || revision ? "change-reason" : undefined} className="text-sm text-ink">
            {redrafted || revision ? "Redrafted: " : ""}
            {changeReason ?? "A dependency changed. This ground is being redrafted; unchanged grounds stay word for word."}
          </p>
          {revision && revision.changed.length > 0 ? (
            <p className="flex flex-wrap items-center gap-1.5 text-xs text-ink-soft">
              Changed:
              {revision.changed.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => focusItem("dossier", c)}
                  className="cite rounded-sm border border-line-strong/50 bg-cream px-1.5 py-0.5 hover:border-maroon hover:text-maroon"
                  aria-label={`Go to ${fieldLabel(c)} in the dossier`}
                >
                  {c}
                </button>
              ))}
            </p>
          ) : null}
          {revision?.previous_argument ? (
            <details className="group">
              <summary className="cursor-pointer text-sm font-semibold text-maroon underline-offset-4 hover:underline">Show what changed</summary>
              <div className="mt-2">
                <WhatChanged before={revision.previous_argument} after={ground.argument} />
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

      {stated.length > 0 ? (
        <p data-testid="per-counsel-label" className="mt-3 rounded-md border border-clay/50 bg-clay/[0.07] px-2.5 py-1.5 text-xs font-semibold text-ink">
          <span aria-hidden>✎ </span>
          Stated by counsel, so the brief says it is per counsel, not on record: {stated.map((f) => fieldLabel(f)).join(", ")}.
        </p>
      ) : null}

      <div className="mt-3">
        <ArgumentText argument={ground.argument} scope={ground.id} needsReview={needsReview} />
        {needsReview ? (
          <p className="mt-1 text-xs font-semibold text-ink">
            This claim did not pass its check after two repair rounds. Review it before export.
          </p>
        ) : null}
      </div>

      <div className="mt-3">
        <AuthorityList authorities={ground.authorities} scope={ground.id} />
      </div>

      {facts.length > 0 || ground.depends_on.events.length > 0 ? (
        <details className="mt-3 text-xs text-ink-soft">
          <summary className="cursor-pointer font-semibold text-ink-soft hover:text-maroon">What this ground depends on</summary>
          <p className="mt-1">
            Facts: {facts.length ? facts.map(fieldLabel).join(", ") : "none"}.
            {ground.depends_on.events.length ? ` Events: ${ground.depends_on.events.join(", ")}.` : ""}
            {ground.depends_on.rights.length ? ` Rights checks: ${ground.depends_on.rights.join(", ")}.` : ""}
          </p>
        </details>
      ) : null}

      {ground.check === "NEEDS_REVIEW" ? (
        <div className="mt-3 border-t border-line pt-3">
          <ReviewControls itemKey={key} label={`ground ${ground.id}`} ground={ground} />
        </div>
      ) : null}
    </article>
  );
}

function IssueRow({ issue, index, focusedId }: { issue: OpenIssue; index: number; focusedId: string | null }): ReactElement {
  const id = `issue-${index}`;
  const key = checklistKey("NEEDS_REVIEW", id);
  return (
    <li
      id={focusDomId("brief", id)}
      tabIndex={-1}
      className={cn("scroll-mt-4 space-y-2 rounded-md border border-line bg-cream p-3 outline-none focus-visible:ring-2 focus-visible:ring-maroon", focusClass(focusedId, id))}
    >
      <div className="flex flex-wrap items-start gap-2">
        <StatusBadge status={issue.type} kind="openIssue" size="sm" />
        <p className="min-w-0 flex-1 text-sm text-ink">{issue.item}</p>
      </div>
      {issue.type === "NEEDS_REVIEW" ? <ReviewControls itemKey={key} label={`open issue ${index + 1}`} /> : null}
    </li>
  );
}

export function BriefTab({ caseId, className }: BriefTabProps): ReactElement {
  const ws = useWorkspace();
  const data = useCaseData();
  const activity = useAgentActivity();
  const gate2 = useGateChecklist("GATE_2_EXPORT");
  const [gateOpen, setGateOpen] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [exportMsg, setExportMsg] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const brief = data.brief;
  const focusedId = useFocusItem("brief", Boolean(brief));

  const canDraft = ws.gates.approvals.gate1;
  const drafting = ws.drafting || activity.byAgent.VAKEEL.phase === "working";

  const state = tabState({
    tab: "brief", resource: "brief", noun: "brief", loading: data.loading.brief, error: data.errors.brief, hasData: Boolean(brief),
    onRetry: () => void data.refresh(["brief", "revisions"]),
    emptyTitle: drafting ? "Vakeel is drafting" : "No draft yet",
    emptyBody: canDraft
      ? "The dossier is approved. Vakeel drafts one ground per applicable factor, then checks every claim against its source."
      : "Approve the dossier at Gate 1 first. Drafting starts from the approved dossier.",
    emptyAction: drafting ? (
      <AgentSignature agent="VAKEEL" mode="working" active statusText={activity.byAgent.VAKEEL.text} />
    ) : canDraft ? (
      <Button onClick={() => void ws.startDraft()}>
        <FileText aria-hidden /> Start drafting
      </Button>
    ) : undefined,
  });
  if (state || !brief) return state ?? <></>;

  const grounds = brief.grounds;
  const staleCount = grounds.filter((g) => g.state === "STALE").length;
  const reviewCount = grounds.filter((g) => g.check === "NEEDS_REVIEW").length;
  const pos = brief.statutory_position;
  const exportReason = ws.canExport
    ? ""
    : !ws.gates.approvals.gate1
      ? "Export is locked until counsel approves Gate 1 and Gate 2."
      : "Export is locked until counsel approves Gate 2.";

  const doExport = async (format: ExportFormat) => {
    setExporting(format);
    setExportMsg(null);
    try {
      const files = await ws.exportCase(format);
      setExportMsg({ tone: "ok", text: `Exported ${files.length} file${files.length === 1 ? "" : "s"}.` });
    } catch (e) {
      setExportMsg({ tone: "error", text: errorMessage(e) });
    } finally {
      setExporting(null);
    }
  };

  return (
    <TabShell label="Bail brief" className={className}>
      <TabHeader
        agent="VAKEEL"
        title="Draft brief"
        description="One ground per factor. Every sentence cites a fact from the dossier or an authority that was retrieved, and every claim was checked against its source."
        signature={<AgentSignature agent="VAKEEL" mode="working" active={drafting} statusText={drafting ? activity.byAgent.VAKEEL.text : undefined} />}
      />

      <p role="note" className="rounded-md border border-maroon/50 bg-maroon/[0.06] px-3 py-2 text-sm font-semibold text-maroon">
        {brief.label || DRAFT_LABEL}
      </p>

      <p className="text-sm text-ink-soft" aria-live="polite">
        {grounds.length} ground{grounds.length === 1 ? "" : "s"}
        {reviewCount > 0 ? `, ${reviewCount} needing review` : ""}
        {staleCount > 0 ? `, ${staleCount} stale and being redrafted` : ", all current"}.
      </p>

      <section aria-labelledby="brief-position" className="rounded-lg border border-line bg-parchment p-4">
        <SectionTitle id="brief-position">Statutory position</SectionTitle>
        <dl className="mt-2 grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[9rem_1fr]">
          <dt className="eyebrow pt-0.5">Sections</dt>
          <dd className="cite text-ink">{pos.sections.join("; ") || "None recorded"}</dd>
          {pos.bailable != null ? (
            <>
              <dt className="eyebrow pt-0.5">Bailable</dt>
              <dd className="text-ink">{pos.bailable ? "Bailable" : "Non-bailable"}</dd>
            </>
          ) : null}
          {pos.max_punishment ? (
            <>
              <dt className="eyebrow pt-0.5">Maximum</dt>
              <dd className="text-ink">{pos.max_punishment}</dd>
            </>
          ) : null}
          {pos.rights ? (
            <>
              <dt className="eyebrow pt-0.5">Rights to check</dt>
              <dd className="text-ink">{pos.rights}</dd>
            </>
          ) : null}
        </dl>
      </section>

      <section aria-labelledby="brief-grounds" className="space-y-3">
        <SectionTitle id="brief-grounds">Grounds</SectionTitle>
        {grounds.map((g) => (
          <GroundCard key={g.id} ground={g} revision={latestRevision(data.revisions, g.id)} focusedId={focusedId} />
        ))}
      </section>

      <section aria-labelledby="brief-issues" className="space-y-3">
        <SectionTitle id="brief-issues">Open issues</SectionTitle>
        {brief.open_issues.length === 0 ? (
          <p className="text-sm text-ink-soft">No open issues.</p>
        ) : (
          <ul className="space-y-2">
            {brief.open_issues.map((issue, i) => (
              <IssueRow key={`${i}-${issue.item}`} issue={issue} index={i} focusedId={focusedId} />
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="brief-gate" className="rounded-lg border border-maroon/40 bg-parchment p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h3 id="brief-gate" className="flex items-center gap-2 font-display text-lg font-semibold text-maroon">
              <ShieldCheck aria-hidden className="size-5" /> Gate 2: approve for export
            </h3>
            <p className="mt-1 text-sm text-ink-soft">{gate2.summary} Only counsel can approve; the system never does.</p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={gate2.uiStatus} kind="gate" />
            <Button onClick={() => setGateOpen(true)}>{gate2.approved ? "View approval" : "Review and approve"}</Button>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3">
          {(["DOCX", "PDF"] as const).map((format) => (
            <Button
              key={format}
              variant="secondary"
              size="sm"
              disabled={!ws.canExport || exporting !== null}
              aria-describedby="brief-export-reason"
              onClick={() => void doExport(format)}
            >
              <Download aria-hidden /> {exporting === format ? "Exporting" : `Export ${format}`}
            </Button>
          ))}
          <p id="brief-export-reason" className="text-xs text-ink-soft">
            {ws.canExport ? "Both gates are approved. The file carries the draft label and your court's rules still apply." : exportReason}
          </p>
        </div>
        {exportMsg ? <InlineNote tone={exportMsg.tone === "ok" ? "info" : "error"}>{exportMsg.text}</InlineNote> : null}
        {ws.exports.length > 0 ? (
          <ul aria-label="Exported files" className="mt-2 space-y-0.5 text-xs text-ink-soft">
            {ws.exports.map((f) => (
              <li key={f} className="cite">{f}</li>
            ))}
          </ul>
        ) : null}
      </section>
      <GateModal gate="GATE_2_EXPORT" caseId={caseId} open={gateOpen} onClose={() => setGateOpen(false)} />
    </TabShell>
  );
}

export default BriefTab;
