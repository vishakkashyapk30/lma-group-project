"use client";
// The stepper at the top of the case: Add documents, Review facts, Check rights, Draft grounds, Prepare for the hearing, Export.
// Each step is done, in progress, open, or locked (muted, with the reason on hover and read out by screen readers). The two
// gates are not separate buttons: confirming the facts and approving the draft happen inside their steps.
import { ChevronDown } from "lucide-react";
import { Fragment, useEffect, useRef, useState, type ReactElement } from "react";
import { Stepper, Step } from "@/components/ui/stepper";
import { useT } from "@/lib/i18n";
import { isStageUnlocked, lockReason, stageState, stepOf, STEPPER_STAGES } from "@/lib/stages";
import type { StageContext } from "@/lib/stages";
import type { Stage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useOptionalWorkspace } from "@/lib/workspace";

export interface StageRailProps {
  /** Stage to mark as viewed; defaults to the workspace's active stage. */
  current?: Stage;
  /** Called with the stage id when an open stage is chosen (the workspace also switches stage when present). */
  onSelect?: (stage: Stage) => void;
  /** Overrides the workspace's Gate 1 state; without a workspace provider it defaults to false. */
  gate1Approved?: boolean;
  className?: string;
}

export function StageRail({ current, onSelect, gate1Approved, className }: StageRailProps): ReactElement {
  const t = useT();
  const ws = useOptionalWorkspace();
  const baseContext: StageContext = ws?.stageContext ?? { gate1Approved: false, gate2Approved: false };
  const stageContext: StageContext = gate1Approved === undefined ? baseContext : { ...baseContext, gate1Approved };
  const [notice, setNotice] = useState("");
  // On a phone the six steps do not fit one row: one control says "Step 4 of 6: Draft grounds" and opens the whole list.
  const [listOpen, setListOpen] = useState(false);
  const railRef = useRef<HTMLDivElement>(null);
  const viewed: Stage = stepOf(current ?? ws?.activeStage ?? "INTAKE");
  const progressStage: Stage = ws?.progressStage ?? viewed;

  // Keep the viewed step in view on narrow screens.
  useEffect(() => {
    const el = railRef.current?.querySelector<HTMLElement>('[aria-current="step"]');
    el?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [viewed]);

  const go = (stage: Stage) => {
    if (!isStageUnlocked(stage, stageContext)) {
      setNotice(t(lockReason(stage, stageContext) ?? "That step is locked."));
      return;
    }
    setNotice("");
    setListOpen(false);
    ws?.setStage(stage);
    onSelect?.(stage);
  };

  const viewedAt = Math.max(0, STEPPER_STAGES.findIndex((s) => s.id === viewed));
  const viewedLabel = t(STEPPER_STAGES[viewedAt]?.label ?? "");
  const position = t("Step {k} of {n}").replace("{k}", String(viewedAt + 1)).replace("{n}", String(STEPPER_STAGES.length));

  return (
    <div
      ref={railRef}
      className={className}
      onKeyDown={(e) => {
        if (e.key === "Escape" && listOpen) {
          setListOpen(false);
          railRef.current?.querySelector<HTMLElement>("[data-testid=stage-rail-toggle]")?.focus();
        }
      }}
    >
      <nav aria-label={t("Case steps")} data-testid="stage-rail">
        <button
          type="button"
          data-testid="stage-rail-toggle"
          aria-expanded={listOpen}
          aria-controls="stage-rail-list"
          onClick={() => setListOpen((v) => !v)}
          className="flex min-h-11 w-full items-center justify-between gap-3 rounded-md px-1 text-left text-sm lg:hidden"
        >
          <span className="min-w-0 truncate">
            <span className="tabular text-ink-soft">{position}</span>
            <span className="text-ink-soft">: </span>
            <span className="font-semibold text-maroon">{viewedLabel}</span>
          </span>
          <ChevronDown aria-hidden className={cn("size-4 shrink-0 text-ink-soft transition-transform duration-fast", listOpen && "rotate-180")} />
        </button>
        <Stepper label={t("Steps")} id="stage-rail-list" className={cn("min-h-[var(--rail-h)] py-2", !listOpen && "max-lg:hidden")}>
          {STEPPER_STAGES.map((stage) => {
            const state = stageState(stage.id, progressStage, stageContext);
            const locked = state === "locked";
            const reason = lockReason(stage.id, stageContext);
            return (
              <Fragment key={stage.id}>
                <Step
                  label={t(stage.label)}
                  state={state}
                  viewed={stage.id === viewed}
                  testId={`stage-${stage.key}`}
                  describedBy={locked ? `lock-${stage.id}` : undefined}
                  onClick={() => go(stage.id)}
                  title={locked ? (reason ? t(reason) : undefined) : t(stage.description)}
                  srPrefix={t("Step")}
                />
                {locked ? <li className="sr-only" id={`lock-${stage.id}`}>{reason ? t(reason) : null}</li> : null}
              </Fragment>
            );
          })}
        </Stepper>
      </nav>
      <p className="sr-only" role="status" aria-live="polite">
        {notice}
      </p>
      {notice ? (
        <p className="pb-2 text-sm text-ink-soft" aria-hidden>
          {notice}
        </p>
      ) : null}
    </div>
  );
}

export default StageRail;
