"use client";
// The case workspace: a slim stepper on top, one step in a single reading column, and at most one panel beside it (the source
// page, or the chat). The documents list is a popover; the agent trace and budget are behind "Details". On a narrow screen the
// panel is a full-screen sheet.
import Link from "next/link";
import { AlertTriangle, MessageSquareText, X } from "lucide-react";
import type { ReactElement } from "react";
import { usePublishCaseMeta } from "@/components/shell/meta";
import { Button } from "@/components/ui/button";
import { STAGE_BY_ID, stepOf } from "@/lib/stages";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { ChangeBanner } from "./ChangeBanner";
import { ChatPane } from "./ChatPane";
import { DocumentsMenu } from "./DocumentsMenu";
import { SavedNote } from "./SavedNote";
import { SidePanel } from "./SidePanel";
import { SourcePanel } from "./SourcePanel";
import { StageRail } from "./StageRail";
import { StepView } from "./StepView";
import { TraceDrawer } from "./TraceDrawer";

export interface WorkspaceShellProps {
  caseId: string;
  className?: string;
}

export function WorkspaceShell({ caseId, className }: WorkspaceShellProps): ReactElement {
  const ws = useWorkspace();
  usePublishCaseMeta(caseId, ws.data.summary?.title ?? null, STAGE_BY_ID[stepOf(ws.activeStage)]?.label ?? null);

  const notFound = !ws.loading.summary && !ws.data.summary;
  const summary = ws.data.summary;

  if (notFound) {
    return (
      <div className={cn("mx-auto flex min-h-[60dvh] max-w-md flex-col items-center justify-center gap-3 p-8 text-center", className)}>
        <h1 className="font-display text-2xl">This case was not found</h1>
        <p className="text-sm text-ink-soft">
          There is no case <span className="font-mono">{caseId}</span> in this workspace. It may have been removed, or the link may be wrong.
        </p>
        <Button asChild>
          <Link href="/cases">Back to Cases</Link>
        </Button>
      </div>
    );
  }

  const panelOpen = ws.chatOpen || ws.selectedSource !== null || ws.detail !== null;

  return (
    <div className={cn("flex h-[calc(100dvh-var(--nav-h))] min-h-[34rem] flex-col bg-parchment", className)}>
      <h1 className="sr-only">{summary ? summary.title : "Case"}</h1>
      {/* Below xl the stepper takes its own row (it scrolls sideways on a phone); from xl it shares the row with the case controls. */}
      <div data-print-hide className="flex flex-wrap items-center gap-x-3 border-b border-line bg-parchment px-3 sm:px-4">
        <StageRail className="min-w-0 basis-full xl:basis-0 xl:flex-1" />
        <div className="ml-auto flex min-w-0 max-w-full flex-wrap items-center justify-end gap-1 pb-2 xl:pb-0">
          <SavedNote />
          <DocumentsMenu caseId={caseId} />
          <Button variant="ghost" size="sm" data-testid="details-button" aria-pressed={ws.detailsOpen} onClick={() => ws.setDetailsOpen(!ws.detailsOpen)}>
            Details
          </Button>
          <Button variant="secondary" size="sm" data-testid="chat-button" aria-label="Ask about this case" aria-pressed={ws.chatOpen} onClick={() => (ws.chatOpen ? ws.closeChat() : ws.openChat())}>
            <MessageSquareText aria-hidden /> <span className="2xl:hidden">Ask</span><span className="hidden 2xl:inline">Ask about this case</span>
          </Button>
        </div>
      </div>

      {ws.actionError ? (
        <div role="alert" data-testid="error-banner" className="flex items-start gap-2 border-b border-sindoor/40 bg-cream px-4 py-2 text-sm text-ink">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0 text-sindoor" />
          <p className="min-w-0 flex-1">{ws.actionError}</p>
          <button type="button" onClick={ws.clearActionError} className="grid size-6 place-items-center rounded-sm text-ink-soft hover:bg-ink/[0.06]" aria-label="Dismiss this message">
            <X aria-hidden className="size-4" />
          </button>
        </div>
      ) : null}
      <ChangeBanner />

      <div className="flex min-h-0 flex-1">
        <div data-testid="pane-main" className="min-w-0 flex-1 overflow-y-auto overscroll-contain">
          <StepView caseId={caseId} />
        </div>
        {ws.chatOpen ? (
          <SidePanel title="Ask about this case" onClose={ws.closeChat} testId="pane-chat">
            <ChatPane caseId={caseId} />
          </SidePanel>
        ) : panelOpen ? (
          <SourcePanel caseId={caseId} />
        ) : null}
      </div>

      <TraceDrawer caseId={caseId} open={ws.detailsOpen} onClose={() => ws.setDetailsOpen(false)} />
    </div>
  );
}

export default WorkspaceShell;
