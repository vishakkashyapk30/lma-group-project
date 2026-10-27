"use client";
// The one step on screen. The stage in the workspace decides which; every step reads the workspace context. A step change
// slides the new step 12 px in from the side it comes from (200 ms; none under reduced motion), so forward and back read
// as moving along the stepper. The stepper itself does not move.
import { useRef, type ReactElement } from "react";
import { STEPPER_STAGES, stepOf } from "@/lib/stages";
import type { Stage } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace";
import { BriefTab } from "./tabs/BriefTab";
import { DossierTab } from "./tabs/DossierTab";
import { ExportTab } from "./tabs/ExportTab";
import { IntakeTab } from "./tabs/IntakeTab";
import { PrepTab } from "./tabs/PrepTab";
import { RightsTab } from "./tabs/RightsTab";

export function StepView({ caseId }: { caseId: string }): ReactElement {
  const ws = useWorkspace();
  const step = stepOf(ws.activeStage);
  const prev = useRef<{ step: Stage; dir: "forward" | "back" | "none" }>({ step, dir: "none" });
  if (prev.current.step !== step) {
    const at = (s: Stage) => STEPPER_STAGES.findIndex((x) => x.id === s);
    prev.current = { step, dir: at(step) > at(prev.current.step) ? "forward" : "back" };
  }
  return (
    <div key={step} data-step-enter={prev.current.dir} className="step-enter">
      <Step caseId={caseId} step={step} />
    </div>
  );
}

function Step({ caseId, step }: { caseId: string; step: Stage }): ReactElement {
  switch (step) {
    case "INTAKE":
      return <IntakeTab caseId={caseId} />;
    case "DOSSIER":
      return <DossierTab caseId={caseId} />;
    case "RIGHTS":
      return <RightsTab />;
    case "BRIEF":
      return <BriefTab caseId={caseId} />;
    case "HEARING_PREP":
      return <PrepTab caseId={caseId} />;
    case "FILE":
      return <ExportTab caseId={caseId} />;
    default:
      return <DossierTab caseId={caseId} />;
  }
}

export default StepView;
