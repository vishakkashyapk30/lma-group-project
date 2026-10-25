"use client";
// The stepper at the top of the case: Add documents, Review facts, Check rights, Draft grounds, Prepare for the hearing, Export.
// Each step is done, in progress, open, or locked (muted, with the reason on hover and read out by screen readers). The two
// gates are not separate buttons: confirming the facts and approving the draft happen inside their steps.
import { Fragment, useEffect, useRef, useState, type ReactElement } from "react";
import { Stepper, Step } from "@/components/ui/stepper";
import { isStageUnlocked, lockReason, stageState, stepOf, STEPPER_STAGES } from "@/lib/stages";
import type { StageContext } from "@/lib/stages";
import type { Stage } from "@/lib/types";
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
  const ws = useOptionalWorkspace();
  const baseContext: StageContext = ws?.stageContext ?? { gate1Approved: false, gate2Approved: false };
  const stageContext: StageContext = gate1Approved === undefined ? baseContext : { ...baseContext, gate1Approved };
  const [notice, setNotice] = useState("");
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
      setNotice(lockReason(stage, stageContext) ?? "That step is locked.");
      return;
    }
    setNotice("");
    ws?.setStage(stage);
    onSelect?.(stage);
  };

  return (
    <div ref={railRef} className={className}>
      <nav aria-label="Case steps" data-testid="stage-rail">
        <Stepper label="Steps" className="min-h-[var(--rail-h)] py-2">
          {STEPPER_STAGES.map((stage) => {
            const state = stageState(stage.id, progressStage, stageContext);
            const locked = state === "locked";
            const reason = lockReason(stage.id, stageContext);
            return (
              <Fragment key={stage.id}>
                <Step
                  label={stage.label}
                  state={state}
                  viewed={stage.id === viewed}
                  testId={`stage-${stage.key}`}
                  describedBy={locked ? `lock-${stage.id}` : undefined}
                  onClick={() => go(stage.id)}
                  title={locked ? (reason ?? undefined) : stage.description}
                  srPrefix="Step"
                />
                {locked ? <li className="sr-only" id={`lock-${stage.id}`}>{reason}</li> : null}
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
