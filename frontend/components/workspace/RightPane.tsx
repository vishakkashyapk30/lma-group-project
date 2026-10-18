"use client";
// Right pane (plan §13.5): Dossier · Dates · Rights · Brief · Spar · Prep, kept in sync with the stage rail. Locked tabs
// stay focusable so keyboard users can hear why (Gate 1 unlocks the brief); items that need counsel show a count.
import { Lock } from "lucide-react";
import { useState, type ReactElement } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { lockReason, stageForTab, STAGE_BY_ID, TAB_LABELS, WORKSPACE_TABS, type WorkspaceTab } from "@/lib/stages";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { ChangeBanner } from "./ChangeBanner";
import { BriefTab } from "./tabs/BriefTab";
import { DatesTab } from "./tabs/DatesTab";
import { DossierTab } from "./tabs/DossierTab";
import { PrepTab } from "./tabs/PrepTab";
import { RightsTab } from "./tabs/RightsTab";
import { SparTab } from "./tabs/SparTab";

export interface RightPaneProps {
  caseId: string;
  className?: string;
}

export function RightPane({ caseId, className }: RightPaneProps): ReactElement {
  const ws = useWorkspace();
  const [notice, setNotice] = useState("");

  // Items counsel still has to deal with, shown on the tab where they are resolved.
  const counts: Partial<Record<WorkspaceTab, number>> = {};
  const g1 = ws.gates.checklists.GATE_1_DOSSIER;
  const g2 = ws.gates.checklists.GATE_2_EXPORT;
  if (!g1.approved) counts.dossier = g1.blocking.length;
  if (g1.approved && !g2.approved) {
    counts.brief = g2.blocking.filter((i) => i.kind === "NEEDS_REVIEW").length;
    counts.spar = g2.blocking.filter((i) => i.kind === "UNANSWERED").length;
    counts.dossier = g2.blocking.filter((i) => i.kind === "UNSUPPORTED").length;
  }

  const onChange = (value: string) => {
    const tab = value as WorkspaceTab;
    if (ws.setTab(tab)) setNotice("");
    else setNotice(lockReason(stageForTab(tab), ws.stageContext) ?? "That tab is locked.");
  };

  const stage = STAGE_BY_ID[ws.activeStage];
  const fill = "min-h-0 flex-1 overflow-y-auto overscroll-contain";

  return (
    <section aria-label="Case views" className={cn("flex min-h-0 flex-col bg-cream", className)}>
      <Tabs value={ws.activeTab} onValueChange={onChange} className="flex min-h-0 flex-1 flex-col">
        <TabsList aria-label="Case views" className="shrink-0 bg-parchment/70 px-2">
          {WORKSPACE_TABS.map((tab) => {
            const locked = !ws.isTabUnlocked(tab);
            const count = counts[tab] ?? 0;
            return (
              <TabsTrigger key={tab} value={tab} data-testid={`right-tab-${tab}`} onClick={() => onChange(tab)} aria-disabled={locked || undefined} className={cn(locked && "text-ink-muted")} title={locked ? (lockReason(stageForTab(tab), ws.stageContext) ?? undefined) : undefined}>
                {locked ? <Lock aria-hidden className="size-3.5" /> : null}
                {TAB_LABELS[tab]}
                {locked ? <span className="sr-only"> (locked)</span> : null}
                {count > 0 ? (
                  <span className="rounded-pill bg-sindoor px-1.5 py-px font-mono text-[10px] leading-4 text-cream">
                    {count}
                    <span className="sr-only"> item{count === 1 ? "" : "s"} need attention</span>
                  </span>
                ) : null}
              </TabsTrigger>
            );
          })}
        </TabsList>
        <ChangeBanner />
        {notice ? (
          <p role="status" className="shrink-0 border-b border-haldi/30 bg-haldi/[0.08] px-4 py-1.5 text-xs text-ink">
            {notice}
          </p>
        ) : null}
        <p className="shrink-0 border-b border-line px-4 py-1.5 text-xs text-ink-soft">
          <span className="font-display font-semibold text-maroon">
            {stage.numeral} · {stage.label}.
          </span>{" "}
          {stage.description}
        </p>
        <TabsContent value="dossier" className={fill}>
          <DossierTab caseId={caseId} />
        </TabsContent>
        <TabsContent value="dates" className={fill}>
          <DatesTab caseId={caseId} />
        </TabsContent>
        <TabsContent value="rights" className={fill}>
          <RightsTab caseId={caseId} />
        </TabsContent>
        <TabsContent value="brief" className={fill}>
          <BriefTab caseId={caseId} />
        </TabsContent>
        <TabsContent value="spar" className={fill}>
          <SparTab caseId={caseId} />
        </TabsContent>
        <TabsContent value="prep" className={fill}>
          <PrepTab caseId={caseId} />
        </TabsContent>
      </Tabs>
    </section>
  );
}

export default RightPane;
