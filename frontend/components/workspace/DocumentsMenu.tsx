"use client";
// "Documents (4)": the case file as a popover under the button, so the list is never a permanent pane. Choosing a document
// opens its page in the side panel.
import { FileText } from "lucide-react";
import type { ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/lib/workspace";
import { DocumentList } from "./DocumentList";
import { Popover } from "./Popover";

export function DocumentsMenu({ caseId }: { caseId: string }): ReactElement {
  const ws = useWorkspace();
  const count = ws.data.ingestion?.documents.length ?? 0;
  return (
    <Popover
      testId="documents-button"
      trigger={
        <>
          <FileText aria-hidden className="size-4" />
          <span>
            {/* Below 2xl the label is the count only, so the stepper keeps one row at laptop widths; the name stays for screen readers. */}
            <span className="sr-only 2xl:not-sr-only">Documents </span>
            <span className="tabular">({count})</span>
          </span>
        </>
      }
      panelClassName="max-h-[min(34rem,calc(100dvh-8rem))] overflow-y-auto"
      align="right"
    >
      {(close) => (
        <div data-testid="pane-case-file" className="p-2">
          <DocumentList caseId={caseId} onPick={close} />
          <div className="border-t border-line px-2 pt-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                ws.setStage("INTAKE");
                close();
              }}
            >
              Add more documents
            </Button>
          </div>
        </div>
      )}
    </Popover>
  );
}

export default DocumentsMenu;
