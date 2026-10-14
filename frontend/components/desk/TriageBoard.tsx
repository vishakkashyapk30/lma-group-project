// Stub: Cause-list board sorted by urgency with each case's next step (plan §11). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { TriageCard } from "@/lib/types";

export interface TriageBoardProps {
  cards: TriageCard[];
  className?: string;
}

export function TriageBoard(props: TriageBoardProps): ReactElement {
  return <section data-stub="TriageBoard" className={props.className} />;
}

export default TriageBoard;
