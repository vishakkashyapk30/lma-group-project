// Stub: List of documents with type, language and route badges (plan §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface DocumentListProps {
  caseId: string;
  className?: string;
}

export function DocumentList(props: DocumentListProps): ReactElement {
  return <section data-stub="DocumentList" className={props.className} />;
}

export default DocumentList;
