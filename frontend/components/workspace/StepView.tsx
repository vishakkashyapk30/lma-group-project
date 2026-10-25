"use client";
// The one step on screen. The stage in the workspace decides which; every step reads the workspace context.
import type { ReactElement } from "react";
import { stepOf } from "@/lib/stages";
import { useWorkspace } from "@/lib/workspace";
import { BriefTab } from "./tabs/BriefTab";
import { DossierTab } from "./tabs/DossierTab";
import { ExportTab } from "./tabs/ExportTab";
import { IntakeTab } from "./tabs/IntakeTab";
import { PrepTab } from "./tabs/PrepTab";
import { RightsTab } from "./tabs/RightsTab";

export function StepView({ caseId }: { caseId: string }): ReactElement {
  const ws = useWorkspace();
  switch (stepOf(ws.activeStage)) {
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
