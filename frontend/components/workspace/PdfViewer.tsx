// Stub: react-pdf viewer; highlight overlays drawn from Munshi's boxes; clicking a field or citation scrolls to its source box (plan §13.1, §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { SourceRef } from "@/lib/types";

export interface PdfViewerProps {
  caseId: string;
  docId?: string;
  highlight?: SourceRef;
  className?: string;
}

export function PdfViewer(props: PdfViewerProps): ReactElement {
  return <section data-stub="PdfViewer" className={props.className} />;
}

export default PdfViewer;
