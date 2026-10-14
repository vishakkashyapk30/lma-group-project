// Stub: One case card (plan §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { CaseSummary } from "@/lib/types";

export interface CaseCardProps {
  summary: CaseSummary;
  className?: string;
}

export function CaseCard(props: CaseCardProps): ReactElement {
  return <section data-stub="CaseCard" className={props.className} />;
}

export default CaseCard;
