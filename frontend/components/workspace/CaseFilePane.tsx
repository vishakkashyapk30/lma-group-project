// Stub: Left pane: documents with type, language and route badges; PDF viewer; drop zone and mic (plan §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface CaseFilePaneProps {
  caseId: string;
  className?: string;
}

export function CaseFilePane(props: CaseFilePaneProps): ReactElement {
  return <section data-stub="CaseFilePane" className={props.className} />;
}

export default CaseFilePane;
