"use client";
// Left pane (plan §13.5): the filed documents, the page viewer with source highlights, and the drop zone with a mic.
import { FolderOpen } from "lucide-react";
import type { ReactElement } from "react";
import { AgentSignature } from "@/components/agents/AgentSignature";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { DocumentList } from "./DocumentList";
import { DropZone } from "./DropZone";
import { PdfViewer } from "./PdfViewer";

export interface CaseFilePaneProps {
  caseId: string;
  className?: string;
}

export function CaseFilePane({ caseId, className }: CaseFilePaneProps): ReactElement {
  const ws = useWorkspace();
  const munshi = ws.activity.byAgent.MUNSHI;
  const reading = munshi.phase === "working" || ws.uploading;
  const hasDocs = (ws.data.ingestion?.documents.length ?? 0) > 0;

  return (
    <section aria-labelledby="casefile-title" className={cn("flex min-h-0 flex-col bg-cream", className)}>
      <header className="flex items-center gap-2 border-b border-line px-3 py-2.5">
        <FolderOpen aria-hidden className="size-4 text-maroon" />
        <h2 id="casefile-title" className="font-display text-base font-semibold text-maroon">
          Case file
        </h2>
        <span className="ml-auto font-mono text-2xs text-ink-muted">
          {ws.data.ingestion?.documents.length ?? 0} document{(ws.data.ingestion?.documents.length ?? 0) === 1 ? "" : "s"}
        </span>
      </header>

      <div className="border-b border-line bg-parchment/60 px-3 py-2" aria-live="polite">
        <AgentSignature
          agent="MUNSHI"
          mode="working"
          active={reading}
          className="max-w-[10.5rem]"
          statusText={reading ? (munshi.phase === "working" ? munshi.text : "Munshi is reading and filing pages") : undefined}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        <div data-lenis-prevent="" className={cn("min-h-0 overflow-y-auto overscroll-contain border-b border-line", hasDocs ? "max-h-[38%] shrink-0" : "shrink-0")}>
          <DocumentList caseId={caseId} />
        </div>
        <PdfViewer caseId={caseId} />
      </div>

      <div className="border-t border-line bg-parchment/60 p-3">
        <DropZone caseId={caseId} compact={hasDocs} />
      </div>
    </section>
  );
}

export default CaseFilePane;
