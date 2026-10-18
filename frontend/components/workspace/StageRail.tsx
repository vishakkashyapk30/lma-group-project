"use client";
// Stage rail (plan §13.5): I Intake · II Dossier ◆ · III Rights · IV Brief · V Spar · VI Hearing prep · VII File ◆, numbered
// like the Parts of the Constitution. The diamonds are the two approval gates: Gate 1 after the Dossier, Gate 2 before File.
// Counsel can jump to any open stage; later stages unlock after Gate 1 and File after Gate 2. Each state shows an icon and
// a word, never colour alone.
import { Check, Circle, CircleDot, Diamond, Lock } from "lucide-react";
import { Fragment, useEffect, useRef, useState, type KeyboardEvent, type ReactElement } from "react";
import { GATE_STATUS_META, TONE_CLASSES } from "@/lib/status";
import { isStageUnlocked, lockReason, stageState, STAGES, type StageState } from "@/lib/stages";
import type { GateId, Stage } from "@/lib/types";
import type { StageContext } from "@/lib/stages";
import { cn } from "@/lib/utils";
import { useOptionalWorkspace } from "@/lib/workspace";
import { StatusIcon } from "@/components/common/StatusBadge";
import { GateModal } from "./GateModal";

export interface StageRailProps {
  /** Stage to mark as viewed; defaults to the workspace's active stage. */
  current?: Stage;
  /** Called with the stage id when an open stage is chosen (the workspace also switches stage when present). */
  onSelect?: (stage: Stage) => void;
  /** Overrides the workspace's Gate 1 state; without a workspace provider it defaults to false. */
  gate1Approved?: boolean;
  className?: string;
}

const STATE_WORD: Record<StageState, string> = { done: "Done", current: "In progress", open: "Open", locked: "Locked" };

function StateIcon({ state, viewed }: { state: StageState; viewed: boolean }): ReactElement {
  const cls = "size-3.5 shrink-0";
  if (state === "locked") return <Lock aria-hidden className={cls} />;
  if (state === "done") return <Check aria-hidden className={cls} strokeWidth={2.6} />;
  if (state === "current") return <CircleDot aria-hidden className={cls} />;
  return <Circle aria-hidden className={cn(cls, viewed && "fill-current")} />;
}

const NO_GATES: Record<GateId, { uiStatus: "LOCKED"; blocking: never[]; summary: string }> = {
  GATE_1_DOSSIER: { uiStatus: "LOCKED", blocking: [], summary: "" },
  GATE_2_EXPORT: { uiStatus: "LOCKED", blocking: [], summary: "" },
};

export function StageRail({ current, onSelect, gate1Approved, className }: StageRailProps): ReactElement {
  const ws = useOptionalWorkspace();
  const baseContext: StageContext = ws?.stageContext ?? { gate1Approved: false, gate2Approved: false };
  const stageContext: StageContext = gate1Approved === undefined ? baseContext : { ...baseContext, gate1Approved };
  const [gateOpen, setGateOpen] = useState<GateId | null>(null);
  const [notice, setNotice] = useState("");
  const listRef = useRef<HTMLOListElement>(null);
  const viewed: Stage = current ?? ws?.activeStage ?? "INTAKE";
  const progressStage: Stage = ws?.progressStage ?? viewed;

  // Keep the viewed stage in view on narrow screens.
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>('[aria-current="step"]');
    el?.scrollIntoView?.({ block: "nearest", inline: "center" });
  }, [viewed]);

  const go = (stage: Stage) => {
    if (!isStageUnlocked(stage, stageContext)) {
      setNotice(lockReason(stage, stageContext) ?? "That stage is locked.");
      return;
    }
    setNotice("");
    ws?.setStage(stage);
    onSelect?.(stage);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLOListElement>) => {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) return;
    const items = Array.from(listRef.current?.querySelectorAll<HTMLElement>("[data-rail-item]") ?? []);
    const at = items.indexOf(document.activeElement as HTMLElement);
    if (at < 0) return;
    e.preventDefault();
    const next = e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : (at + (e.key === "ArrowRight" ? 1 : -1) + items.length) % items.length;
    items[next]?.focus();
  };

  const gateButton = (gate: GateId): ReactElement => {
    const list = ws?.gates.checklists[gate] ?? NO_GATES[gate];
    const meta = GATE_STATUS_META[list.uiStatus];
    const tone = TONE_CLASSES[meta.tone];
    const short = gate === "GATE_1_DOSSIER" ? "Gate 1" : "Gate 2";
    const count = list.blocking.length;
    return (
      <button
        type="button"
        data-rail-item=""
        data-testid={gate === "GATE_1_DOSSIER" ? "gate-diamond-1" : "gate-diamond-2"}
        data-approved={"approved" in list && list.approved ? "true" : "false"}
        onClick={() => setGateOpen(gate)}
        aria-haspopup="dialog"
        aria-label={`${short} approval, ${meta.label}${count ? `, ${count} item${count === 1 ? "" : "s"} to resolve` : ""}. Open the checklist.`}
        title={list.summary}
        className={cn(
          "relative flex h-9 shrink-0 items-center gap-1.5 rounded-pill border px-2.5 text-xs font-semibold transition-colors duration-fast",
          tone.border, tone.bg, tone.text, "hover:brightness-95",
        )}
      >
        <Diamond aria-hidden className="size-3.5 fill-current" />
        <span>{short}</span>
        <span className="hidden items-center gap-1 font-normal xl:inline-flex">
          <StatusIcon icon={meta.icon} />
          {meta.label}
        </span>
        {count > 0 ? <span className="rounded-pill bg-sindoor px-1.5 py-px font-mono text-[10px] leading-4 text-cream">{count}</span> : null}
      </button>
    );
  };

  return (
    <div className={cn("border-b border-gold/50 bg-parchment", className)}>
      <nav aria-label="Case stages" data-testid="stage-rail" className="mx-auto max-w-[1800px] px-3">
        <ol ref={listRef} onKeyDown={onKeyDown} data-lenis-prevent="" className="flex min-h-[3.5rem] items-center gap-1 overflow-x-auto py-2">
          {STAGES.map((stage, i) => {
            const state = stageState(stage.id, progressStage, stageContext);
            const isViewed = stage.id === viewed;
            const locked = state === "locked";
            const reason = lockReason(stage.id, stageContext);
            return (
              <Fragment key={stage.id}>
                {i > 0 ? <li aria-hidden className="h-px w-3 shrink-0 bg-gold/60 sm:w-5" /> : null}
                {stage.gate && stage.gatePosition === "before" ? (
                  <>
                    <li className="flex shrink-0 items-center">{gateButton(stage.gate)}</li>
                    <li aria-hidden className="h-px w-3 shrink-0 bg-gold/60 sm:w-5" />
                  </>
                ) : null}
                <li className="shrink-0">
                  <button
                    type="button"
                    data-rail-item=""
                    data-testid={`stage-${stage.numeral}`}
                    data-state={state}
                    aria-current={isViewed ? "step" : undefined}
                    aria-disabled={locked || undefined}
                    aria-describedby={locked ? `lock-${stage.id}` : undefined}
                    onClick={() => go(stage.id)}
                    title={locked ? (reason ?? undefined) : stage.description}
                    className={cn(
                      "group flex h-10 items-center gap-2 rounded-md border px-2.5 text-left transition-colors duration-fast",
                      isViewed ? "border-maroon bg-maroon text-cream shadow-sm" : "border-transparent hover:border-line-strong/60 hover:bg-cream",
                      locked && !isViewed && "cursor-not-allowed text-ink-muted hover:bg-transparent",
                      !locked && !isViewed && "text-ink",
                    )}
                  >
                    <span
                      aria-hidden
                      className={cn(
                        "grid min-w-[1.75rem] place-items-center rounded-sm px-1 font-display text-sm font-semibold leading-6",
                        isViewed ? "bg-cream/15 text-cream" : "bg-parchment-deep text-maroon",
                        locked && !isViewed && "text-ink-muted",
                      )}
                    >
                      {stage.numeral}
                    </span>
                    <span className="flex flex-col leading-tight">
                      <span className="whitespace-nowrap font-display text-sm font-semibold">
                        <span className="sr-only">Part {stage.numeral}: </span>
                        {stage.label}
                      </span>
                      <span className={cn("flex items-center gap-1 text-[11px]", isViewed ? "text-cream/85" : state === "done" ? "text-neem" : "text-ink-soft")}>
                        <StateIcon state={state} viewed={isViewed} />
                        {STATE_WORD[state]}
                      </span>
                    </span>
                  </button>
                  {locked ? (
                    <span id={`lock-${stage.id}`} className="sr-only">
                      {reason}
                    </span>
                  ) : null}
                </li>
                {stage.gate && stage.gatePosition === "after" ? (
                  <>
                    <li aria-hidden className="h-px w-3 shrink-0 bg-gold/60 sm:w-5" />
                    <li className="flex shrink-0 items-center">{gateButton(stage.gate)}</li>
                  </>
                ) : null}
              </Fragment>
            );
          })}
          <li className="ml-auto hidden shrink-0 pl-3 text-[11px] text-ink-soft 2xl:block" aria-hidden>
            <Diamond className="mr-1 inline size-3 fill-current text-maroon" /> approval by counsel
          </li>
        </ol>
      </nav>
      <p className="sr-only" role="status" aria-live="polite">
        {notice}
      </p>
      {notice ? (
        <p className="border-t border-haldi/30 bg-haldi/[0.08] px-4 py-1.5 text-xs text-ink" aria-hidden>
          {notice}
        </p>
      ) : null}
      {gateOpen && ws ? <GateModal gate={gateOpen} caseId={ws.caseId} open onClose={() => setGateOpen(null)} /> : null}
    </div>
  );
}

export default StageRail;
