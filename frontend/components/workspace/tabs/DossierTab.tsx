// Stub: Dossier tab: fields with status chips and source quotes; click scrolls PDF; edit sets USER_EDITED; Approve (Gate 1) (plan §7.1, §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface DossierTabProps {
  caseId: string;
  className?: string;
}

export function DossierTab(props: DossierTabProps): ReactElement {
  return <section data-stub="DossierTab" className={props.className} />;
}

export default DossierTab;
