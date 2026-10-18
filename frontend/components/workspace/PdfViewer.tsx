"use client";
// Case-file viewer (plan §13.1, §13.5): react-pdf and the page renderers load through next/dynamic (ssr: false). Selecting a
// source anywhere (a dossier field, a citation chip, a checklist link) scrolls to its page and box and highlights it.
import dynamic from "next/dynamic";
import type { ReactElement } from "react";
import { FileSearch } from "lucide-react";
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
    <div className="grid min-h-40 flex-1 place-items-center bg-parchment-deep/60 text-sm text-ink-soft" role="status">
      Loading the page viewer…
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
      <section aria-label="Page viewer" data-testid="pdf-viewer" className={cn("flex min-h-40 flex-1 flex-col items-center justify-center gap-2 bg-parchment-deep/50 p-6 text-center", className)}>
        <FileSearch aria-hidden className="size-8 text-gold-leaf" strokeWidth={1.5} />
        <p className="font-display text-base text-maroon">No page to show yet</p>
        <p className="max-w-[18rem] text-sm text-ink-soft">
          Drop the bundle below. Once Munshi has filed it, pick a document, or select a field in the dossier, to see its source highlighted here.
        </p>
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
        onClear={ws.clearSource}
      />
    </section>
  );
}

export default PdfViewer;
