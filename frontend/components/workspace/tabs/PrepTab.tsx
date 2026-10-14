// Stub: Prep tab: hearing-prep card, application preview, export (Gate 2) (plan §8.2, §8.3). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface PrepTabProps {
  caseId: string;
  className?: string;
}

export function PrepTab(props: PrepTabProps): ReactElement {
  return <section data-stub="PrepTab" className={props.className} />;
}

export default PrepTab;
