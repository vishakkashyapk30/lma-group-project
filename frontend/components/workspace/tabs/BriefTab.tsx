// Stub: Brief tab: grounds with claim states, checks, authorities (transfer and good-law badges), open issues, change highlights (Vakeel manuscript animation) (plan §8.1, §10). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface BriefTabProps {
  caseId: string;
  className?: string;
}

export function BriefTab(props: BriefTabProps): ReactElement {
  return <section data-stub="BriefTab" className={props.className} />;
}

export default BriefTab;
