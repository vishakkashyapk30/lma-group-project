"use client";
// Case workspace (plan §13.5): header, stage rail and three panes (case file | chat | right tabs). Wide screens show all three;
// narrow screens turn the panes into tabs. Everything reads the workspace context, so demo mode works end to end.
import Link from "next/link";
import { AlertTriangle, FolderOpen, LayoutPanelLeft, MessageSquareText, X } from "lucide-react";
import { useEffect, useState, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { BudgetMeter } from "./BudgetMeter";
import { CaseFilePane } from "./CaseFilePane";
import { ChatPane } from "./ChatPane";
import { RightPane } from "./RightPane";
import { StageRail } from "./StageRail";

export interface WorkspaceShellProps {
  caseId: string;
  className?: string;
}

type PaneId = "file" | "chat" | "views";

const PANES: { id: PaneId; label: string; Icon: typeof FolderOpen }[] = [
  { id: "file", label: "Case file", Icon: FolderOpen },
  { id: "chat", label: "Chat", Icon: MessageSquareText },
  { id: "views", label: "Case views", Icon: LayoutPanelLeft },
];

const NARROW = "(max-width: 1023px)";

export function WorkspaceShell({ caseId, className }: WorkspaceShellProps): ReactElement {
  const ws = useWorkspace();
  const [pane, setPane] = useState<PaneId>("chat");

  // On a narrow screen, choosing a source anywhere brings the page viewer forward; choosing a tab or a checklist link brings the views forward.
  useEffect(() => {
    if (ws.sourceNonce > 0 && typeof window !== "undefined" && window.matchMedia(NARROW).matches) setPane("file");
  }, [ws.sourceNonce]);
  useEffect(() => {
    if (ws.focusTarget && typeof window !== "undefined" && window.matchMedia(NARROW).matches) setPane("views");
  }, [ws.focusTarget]);

  const notFound = !ws.loading.summary && !ws.data.summary;
  const summary = ws.data.summary;

  if (notFound) {
    return (
      <div className={cn("mx-auto flex min-h-[60dvh] max-w-md flex-col items-center justify-center gap-3 p-8 text-center", className)}>
        <h1 className="font-display text-2xl text-maroon">This case was not found</h1>
        <p className="text-sm text-ink-soft">
          There is no case <span className="font-mono">{caseId}</span> in this workspace. It may have been removed, or the link may be wrong.
        </p>
        <Button asChild>
          <Link href="/cases">Back to the cause list</Link>
        </Button>
      </div>
    );
  }

  const show = (id: PaneId) => (pane === id ? "flex" : "hidden lg:flex");

  return (
    <div className={cn("flex h-[calc(100dvh-3.5rem)] min-h-[34rem] flex-col bg-parchment", className)}>
      <div className="border-b border-line bg-parchment">
        <div className="mx-auto flex max-w-[1800px] flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2">
          <div className="min-w-0 flex-1">
            <p className="text-2xs font-semibold uppercase tracking-caps text-ink-soft">
              <Link href="/cases" className="rounded-sm hover:text-maroon hover:underline">Cause list</Link> / <span className="font-mono normal-case tracking-normal">{caseId}</span>
            </p>
            <h1 className="truncate font-display text-lg font-semibold text-maroon">
              {summary ? summary.title : <Skeleton className="inline-block h-5 w-48 align-middle" />}
            </h1>
          </div>
          <p className="hidden text-xs text-ink-soft md:block">AI-generated drafts for counsel. Nothing is filed without your approval.</p>
          <BudgetMeter caseId={caseId} />
        </div>
      </div>

      <StageRail />

      {ws.actionError ? (
        <div role="alert" data-testid="error-banner" className="flex items-start gap-2 border-b border-sindoor/40 bg-sindoor/[0.08] px-4 py-2 text-sm text-ink">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0 text-sindoor" />
          <p className="min-w-0 flex-1">{ws.actionError}</p>
          <button type="button" onClick={ws.clearActionError} className="grid size-6 place-items-center rounded-sm text-ink-soft hover:bg-ink/[0.06]" aria-label="Dismiss this message">
            <X aria-hidden className="size-4" />
          </button>
        </div>
      ) : null}

      <div
        role="group"
        aria-label="Choose a pane"
        className="flex shrink-0 gap-1 border-b border-line bg-cream px-2 lg:hidden"
      >
        {PANES.map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            aria-pressed={pane === id}
            onClick={() => setPane(id)}
            className={cn(
              "inline-flex h-10 flex-1 items-center justify-center gap-1.5 border-b-2 text-sm font-semibold",
              pane === id ? "border-maroon text-maroon" : "border-transparent text-ink-soft hover:text-ink",
            )}
          >
            <Icon aria-hidden className="size-4" />
            {label}
          </button>
        ))}
      </div>

      <div className="mx-auto grid min-h-0 w-full max-w-[1800px] flex-1 grid-cols-1 lg:grid-cols-[minmax(17rem,22rem)_minmax(0,1fr)_minmax(20rem,32rem)] xl:grid-cols-[minmax(19rem,25rem)_minmax(0,1fr)_minmax(24rem,36rem)]">
        <div data-testid="pane-case-file" className={cn("min-h-0 flex-col border-r border-line", show("file"))}>
          <CaseFilePane caseId={caseId} className="min-h-0 flex-1" />
        </div>
        <div data-testid="pane-chat" className={cn("min-h-0 flex-col", show("chat"))}>
          <ChatPane caseId={caseId} className="min-h-0 flex-1" />
        </div>
        <div data-testid="pane-right" className={cn("min-h-0 flex-col border-l border-line", show("views"))}>
          <RightPane caseId={caseId} className="min-h-0 flex-1" />
        </div>
      </div>
    </div>
  );
}

export default WorkspaceShell;
