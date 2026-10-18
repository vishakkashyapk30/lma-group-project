"use client";
// Dispatcher: renders the right signature animation for an agent (plan §13.4). Static icon + text status under
// reduced motion is handled by each component (shared AgentFrame).
import type { ReactElement } from "react";
import type { StoreName } from "@/lib/types";
import { AbhiyojakScales } from "./AbhiyojakScales";
import { MunshiPaperStorm } from "./MunshiPaperStorm";
import { PairokarCauseListBars } from "./PairokarCauseListBars";
import { PeshkarCalendarBars } from "./PeshkarCalendarBars";
import type { Surface } from "./shared";
import { SutradharWheel } from "./SutradharWheel";
import type { AgentSignatureProps as BaseProps } from "./types";
import { VakeelManuscript } from "./VakeelManuscript";

export interface AgentSignatureProps extends BaseProps {
  /** Background the art sits on (default "light"; the landing's oxblood panels use "dark"). */
  surface?: Surface;
  /** Sutradhar only: stores queried so far. */
  litStores?: readonly StoreName[];
  /** Sutradhar only: the tool being called now. */
  activeTool?: string | null;
  /** Sutradhar only: handler for the "Show the plan" button in full mode. */
  onShowPlan?: () => void;
  /** Abhiyojak only: objections still unanswered. */
  unanswered?: number;
}

export function AgentSignature({
  agent, mode, active, statusText, className, surface, litStores, activeTool, onShowPlan, unanswered,
}: AgentSignatureProps): ReactElement {
  const base = { mode, active, statusText, className, surface };
  switch (agent) {
    case "MUNSHI":
      return <MunshiPaperStorm {...base} />;
    case "PESHKAR":
      return <PeshkarCalendarBars {...base} />;
    case "SUTRADHAR":
      return <SutradharWheel {...base} litStores={litStores} activeTool={activeTool} onShowPlan={onShowPlan} />;
    case "VAKEEL":
      return <VakeelManuscript {...base} />;
    case "ABHIYOJAK":
      return <AbhiyojakScales {...base} unanswered={unanswered} />;
    case "PAIROKAR":
      return <PairokarCauseListBars {...base} />;
  }
}

export default AgentSignature;
