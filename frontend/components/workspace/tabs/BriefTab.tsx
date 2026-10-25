"use client";
// Draft grounds (plan §8.1, §9, §10): the draft reads like a document. Each ground is a headed paragraph with small numbered
// sources; a number opens the source in the side panel. Something that needs the lawyer shows as one small "Needs check" mark and
// in the list at the top; the full detail of a ground is under "Details". The likely objections follow the grounds.
import { CheckCircle2, Pencil, Undo2 } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { diffWords } from "@/lib/diff";
import { fieldLabel } from "@/lib/fields";
import { formatCourtDate } from "@/lib/format";
import { FACTOR_LABELS } from "@/lib/labels";
import { DRAFT_LABEL, type DossierFieldName, type Ground, type GroundRevision, type OpenIssue } from "@/lib/types";
import { cn } from "@/lib/utils";
import { checklistKey, useCaseData, useEdits, useGates, useNeedsYou, useStageNav, useWorkspace } from "@/lib/workspace";
import { NeedsYou } from "../NeedsYou";
import { StepFooter, StepFrame } from "../StepFrame";
import { Cited } from "./citations";
import { ChangedTag, focusClass, focusDomId, InlineNote, SectionTitle, stepState, useFocusItem } from "./shared";
import { ObjectionsSection } from "./SparTab";

const STANCE: Record<Ground["stance"], string> = { favourable: "Favourable", adverse: "Adverse", not_applicable: "Not applicable" };

function latestRevision(revisions: GroundRevision[], groundId: string): GroundRevision | null {
  return revisions.filter((r) => r.ground_id === groundId).sort((a, b) => (a.at < b.at ? 1 : -1))[0] ?? null;
}

function WhatChanged({ before, after }: { before: string; after: string }): ReactElement {
  const segments = diffWords(before, after);
  return (
    <p className="doc-text border-l-2 border-line-strong pl-3 text-base text-ink">
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
  /** Present for grounds: the lawyer can reword the argument. */
  ground?: Ground;
}

/** Reword, accept with a note, or undo: how a "Needs check" item is cleared (Gate 2 needs every one resolved). */
function ReviewControls({ itemKey, label, ground }: ReviewControlsProps): ReactElement {
  const toast = useToast();
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
        <span className="inline-flex items-center gap-1 text-sm font-medium text-neem">
          <CheckCircle2 aria-hidden className="size-4" /> {reworded ? "Reworded by you" : "Reviewed by you"}
          {resolution.note && resolution.note !== "Reworded by counsel" && resolution.note !== "Accepted by counsel" ? <span className="font-normal text-ink-soft">: {resolution.note}</span> : null}
        </span>
        <Button size="sm" variant="ghost" aria-label={`Undo review of ${label}`} onClick={() => (ground && reworded ? resetGround(ground.id) : unresolveItem(itemKey))}>
          <Undo2 aria-hidden /> Undo
        </Button>
      </div>
    );
  }

  const base = `${itemKey.replace(/[^A-Za-z0-9]/g, "-")}`;
  if (mode === "reword" && ground) {
    return (
      <div className="space-y-2" data-print-hide>
        <label htmlFor={`${base}-text`} className="block text-sm font-medium text-ink-soft">New wording for this ground</label>
        <Textarea id={`${base}-text`} ref={areaRef} rows={7} value={text} onChange={(e) => setText(e.target.value)} aria-describedby={`${base}-hint`} />
        <InlineNote tone="info" id={`${base}-hint`}>
          Keep the [F:field] and [A:doc#para] markers so each statement stays tied to a fact or an authority.
        </InlineNote>
        {error ? <InlineNote>{error}</InlineNote> : null}
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => {
              if (!text.trim()) {
                setError("The wording cannot be empty.");
                return;
              }
              editGround(ground.id, text.trim(), "Reworded by counsel");
              setMode("idle");
              toast({ title: "Wording saved", action: { label: "Undo", onClick: () => resetGround(ground.id) } });
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
        <label htmlFor={`${base}-note`} className="block text-sm font-medium text-ink-soft">Your note (optional)</label>
        <Input id={`${base}-note`} ref={noteRef} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why this stands, or what you checked" />
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => {
              resolveItem(itemKey, note.trim() || "Accepted by counsel");
              setMode("idle");
              toast({ title: "Marked as reviewed", action: { label: "Undo", onClick: () => unresolveItem(itemKey) } });
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

/** Why a ground carries the "Needs check" mark: a failed claim, a ground being redrafted, or an authority to qualify. */
function problemsOf(ground: Ground, needsReview: boolean, stale: boolean): string[] {
  const out: string[] = [];
  if (needsReview) out.push("A claim failed its check after two rewrites.");
  if (stale) out.push("Something it depends on changed and it is being redrafted.");
  for (const a of ground.authorities) {
    const name = a.citation ?? a.doc_id;
    if (a.good_law === "OVERRULED") out.push(`${name} has been overruled.`);
    else if (a.good_law === "UNKNOWN") out.push(`How later cases treat ${name} is not known.`);
    if (a.transfer === "CHANGED") out.push(`${name}: the provision changed, so it needs a qualification.`);
  }
  return out;
}

function GroundDetails({ ground }: { ground: Ground }): ReactElement {
  const facts = Object.keys(ground.depends_on.facts);
  return (
    <details className="group mt-4 text-sm">
      <summary className="inline-flex cursor-pointer select-none rounded-sm font-medium text-ink-soft underline-offset-4 hover:text-ink hover:underline">Details</summary>
      <dl className="mt-3 grid gap-x-4 gap-y-2 border-l-2 border-line pl-4 sm:grid-cols-[8rem_minmax(0,1fr)]">
        <dt className="text-ink-muted">Check</dt>
        <dd className="m-0"><StatusBadge status={ground.check} kind="claim" size="sm" testId="aux-badge" /></dd>
        <dt className="text-ink-muted">State</dt>
        <dd className="m-0"><StatusBadge status={ground.state} kind="state" size="sm" testId="state-badge" /></dd>
        <dt className="text-ink-muted">Position</dt>
        <dd className="m-0 text-ink-soft">{STANCE[ground.stance]}</dd>
        {ground.authorities.length > 0 ? (
          <>
            <dt className="text-ink-muted">Authorities</dt>
            <dd className="m-0">
              <ul className="m-0 list-none space-y-1.5 p-0">
                {ground.authorities.map((a) => (
                  <li key={`${a.doc_id}#${a.para}`} className="text-ink">
                    {a.citation ?? a.doc_id} <span className="cite text-ink-soft">¶{a.para}</span>
                    <span className="mt-0.5 flex flex-wrap gap-x-3">
                      <StatusBadge status={a.good_law} kind="goodLaw" size="sm" testId="authority-badge" />
                      {a.transfer ? <StatusBadge status={a.transfer} kind="transfer" size="sm" testId="authority-badge" /> : null}
                    </span>
                  </li>
                ))}
              </ul>
            </dd>
          </>
        ) : null}
        {facts.length > 0 || ground.depends_on.events.length > 0 || ground.depends_on.rights.length > 0 ? (
          <>
            <dt className="text-ink-muted">Depends on</dt>
            <dd className="m-0 text-ink-soft">
              {facts.length ? <>Facts: {facts.map(fieldLabel).join(", ")}. </> : null}
              {ground.depends_on.events.length ? <>Events: {ground.depends_on.events.join(", ")}. </> : null}
              {ground.depends_on.rights.length ? <>Rights checks: {ground.depends_on.rights.join(", ")}.</> : null}
            </dd>
          </>
        ) : null}
      </dl>
    </details>
  );
}

function GroundBlock({ ground, revision, focusedId }: { ground: Ground; revision: GroundRevision | null; focusedId: string | null }): ReactElement {
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
  const problems = problemsOf(ground, needsReview, stale);
  const facts = Object.keys(ground.depends_on.facts);
  // Facts the lawyer stated (dictated or typed) have no court record behind them: the brief says so (plan §4.5, flow 5).
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
      className={cn("scroll-mt-4 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-maroon", focusClass(focusedId, ground.id))}
    >
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h4 id={`${domId}-title`} className="font-display text-xl font-semibold leading-snug text-ink">
          <span className="sr-only">{ground.id}: </span>
          {FACTOR_LABELS[ground.factor] ?? ground.factor}
        </h4>
        {problems.length > 0 ? (
          <span data-testid="needs-review-marker" title={problems.join(" ")}>
            <StatusBadge status="NEEDS_REVIEW" kind="claim" label="Needs check" size="sm" testId="aux-badge" />
          </span>
        ) : null}
      </header>

      {revision || redrafted || stale ? (
        <div className="mt-2 space-y-1.5 text-sm" role="group" aria-label={`Changes to ${ground.id}`}>
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {revision || redrafted ? <ChangedTag>Redrafted after a change</ChangedTag> : <StatusBadge status="STALE" kind="state" size="sm" testId="state-badge" />}
            {revision ? <time dateTime={revision.at} className="tabular text-ink-muted">{formatCourtDate(revision.at)}</time> : null}
          </p>
          <p data-testid={redrafted || revision ? "change-reason" : undefined} className="text-ink-soft">
            {changeReason ?? "Something this ground depends on changed. It is being redrafted; unchanged grounds stay word for word."}
          </p>
          {revision && revision.changed.length > 0 ? (
            <p className="text-ink-soft">
              Changed:{" "}
              {revision.changed.map((c, i) => (
                <span key={c}>
                  {i > 0 ? ", " : ""}
                  <button type="button" onClick={() => focusItem("dossier", c)} className="rounded-sm text-maroon underline-offset-4 hover:underline" aria-label={`Go to ${fieldLabel(c)} in the facts`}>
                    {fieldLabel(c)}
                  </button>
                </span>
              ))}
            </p>
          ) : null}
          {revision?.previous_argument ? (
            <details>
              <summary className="inline-flex cursor-pointer select-none rounded-sm font-medium text-maroon underline-offset-4 hover:underline">Show what changed</summary>
              <div className="mt-2">
                <WhatChanged before={revision.previous_argument} after={ground.argument} />
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

      {stated.length > 0 ? (
        <p data-testid="per-counsel-label" className="mt-2 text-sm text-ink-soft">
          Includes facts you entered, not on the court record: {stated.map((f) => fieldLabel(f)).join(", ")}. The brief says so.
        </p>
      ) : null}

      <Cited text={ground.argument} authorities={ground.authorities} className="mt-3" />

      {ground.check === "NEEDS_REVIEW" ? (
        <div className="mt-4">
          <ReviewControls itemKey={key} label={`ground ${ground.id}`} ground={ground} />
        </div>
      ) : null}
      <GroundDetails ground={ground} />
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
      className={cn("scroll-mt-4 space-y-2 py-3 outline-none focus-visible:ring-2 focus-visible:ring-maroon", focusClass(focusedId, id))}
    >
      <p className="text-ink">{issue.item}</p>
      {issue.type === "NEEDS_REVIEW" ? <ReviewControls itemKey={key} label={`open issue ${index + 1}`} /> : <StatusBadge status={issue.type} kind="openIssue" size="sm" />}
    </li>
  );
}

export function BriefTab({ caseId }: { caseId: string }): ReactElement {
  void caseId;
  const ws = useWorkspace();
  const data = useCaseData();
  const needs = useNeedsYou("BRIEF");
  const brief = data.brief;
  const focused = useFocusItem("brief", Boolean(brief));

  const canDraft = ws.gates.approvals.gate1;
  const drafting = ws.drafting || ws.activity.byAgent.VAKEEL.phase === "working";

  const state = stepState({
    resource: "brief", noun: "draft", loading: data.loading.brief, error: data.errors.brief, hasData: Boolean(brief),
    onRetry: () => void data.refresh(["brief", "revisions"]),
    emptyTitle: drafting ? "Drafting the grounds" : "No draft yet",
    emptyBody: canDraft
      ? "The grounds are drafted from the facts you confirmed, then each claim is checked against its source."
      : "Confirm the facts first. The grounds are drafted from them.",
  });
  if (state || !brief) {
    return (
      <StepFrame
        title="Draft grounds"
        intro="The draft grounds, each tied to the facts and authorities it relies on."
        footer={
          <StepFooter
            label={drafting ? "Drafting" : "Draft the grounds"}
            onClick={() => void ws.startDraft()}
            disabled={!canDraft || drafting}
            hint={canDraft ? undefined : "Confirm the facts first."}
            next={false}
            testId="draft-brief-button"
          />
        }
      >
        {state}
      </StepFrame>
    );
  }

  const pos = brief.statutory_position;
  const revisions = data.revisions;

  return (
    <StepFrame
      title="Draft grounds"
      intro="Each ground is tied to the facts and authorities it relies on. Open a number to see the source."
      footer={<StepFooter label="Continue to Prepare for the hearing" onClick={() => ws.setStage("HEARING_PREP")} />}
    >
      <p role="note" className="text-sm font-medium text-maroon">
        {brief.label || DRAFT_LABEL}
      </p>

      <NeedsYou items={needs} empty="Nothing needs your attention. Read the grounds, then continue." />

      <section aria-labelledby="brief-position">
        <SectionTitle id="brief-position">Statutory position</SectionTitle>
        <dl className="mt-3 grid gap-x-4 gap-y-1.5 sm:grid-cols-[9rem_minmax(0,1fr)]">
          <dt className="text-ink-muted">Sections</dt>
          <dd className="cite m-0 text-ink">{pos.sections.join("; ") || "None recorded"}</dd>
          {pos.bailable != null ? (
            <>
              <dt className="text-ink-muted">Bailable</dt>
              <dd className="m-0 text-ink">{pos.bailable ? "Bailable" : "Non-bailable"}</dd>
            </>
          ) : null}
          {pos.max_punishment ? (
            <>
              <dt className="text-ink-muted">Maximum</dt>
              <dd className="m-0 text-ink">{pos.max_punishment}</dd>
            </>
          ) : null}
          {pos.rights ? (
            <>
              <dt className="text-ink-muted">Rights to check</dt>
              <dd className="m-0 text-ink">{pos.rights}</dd>
            </>
          ) : null}
        </dl>
      </section>

      <section aria-labelledby="brief-grounds" className="flex flex-col gap-10">
        <SectionTitle id="brief-grounds">Grounds</SectionTitle>
        {brief.grounds.map((g) => (
          <GroundBlock key={g.id} ground={g} revision={latestRevision(revisions, g.id)} focusedId={focused?.id ?? null} />
        ))}
      </section>

      {brief.open_issues.length > 0 ? (
        <section aria-labelledby="brief-issues">
          <SectionTitle id="brief-issues">Open issues</SectionTitle>
          <ul className="mt-2 divide-y divide-line border-y border-line">
            {brief.open_issues.map((issue, i) => (
              <IssueRow key={`${i}-${issue.item}`} issue={issue} index={i} focusedId={focused?.id ?? null} />
            ))}
          </ul>
        </section>
      ) : null}

      <ObjectionsSection />
    </StepFrame>
  );
}

export default BriefTab;
