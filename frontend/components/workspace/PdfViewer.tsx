"use client";
// Case-file viewer (plan §13.1, §13.5): react-pdf and the page renderers load through next/dynamic (ssr: false). Selecting a
// source anywhere (a dossier field, a citation chip, a checklist link) scrolls to its page and box and highlights it.
import dynamic from "next/dynamic";
import type { ReactElement } from "react";
import type { SourceRef } from "@/lib/types";
import { toSelectedSource } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { useBundlePreview } from "./pdfShared";

export interface PdfViewerProps {
  caseId: string;
  /** Document to show; defaults to the workspace's active document. */
  docId?: string;
  /** Source to highlight; defaults to the workspace's selected source. */
  highlight?: SourceRef;
  className?: string;
}

const PdfPages = dynamic(() => import("./PdfPages"), {
  ssr: false,
  loading: () => (
    <div className="grid min-h-40 flex-1 place-items-center bg-parchment-deep text-sm text-ink-soft" role="status">
      Loading the page…
    </div>
  ),
});

export function PdfViewer({ caseId, docId, highlight, className }: PdfViewerProps): ReactElement {
  const ws = useWorkspace();
  const preview = useBundlePreview(caseId);
  const documents = ws.data.ingestion?.documents ?? [];

  const explicit = highlight ? toSelectedSource(highlight, "citation") : null;
  const selection = explicit ?? ws.selectedSource;
  const wantedId = docId ?? (explicit ? explicit.doc_id : ws.activeDocId) ?? documents[0]?.doc_id ?? null;
  const doc = documents.find((d) => d.doc_id === wantedId) ?? null;

  if (!doc && !preview) {
    return (
      <section aria-label="Page viewer" data-testid="pdf-viewer" className={cn("flex min-h-40 flex-1 flex-col items-center justify-center gap-2 bg-parchment-deep p-6 text-center", className)}>
        <p className="font-medium text-ink">This page is not in the case file</p>
        <p className="max-w-[18rem] text-sm text-ink-soft">Add the documents first, then choose a fact to see the page it came from.</p>
      </section>
    );
  }

  return (
    <section aria-label="Page viewer" data-testid="pdf-viewer" className={cn("flex min-h-0 flex-1 flex-col", className)}>
      <PdfPages
        caseId={caseId}
        doc={doc}
        selection={selection}
        nonce={ws.sourceNonce}
        pdfUrl={preview?.url ?? null}
      />
    </section>
  );
}

export default PdfViewer;
