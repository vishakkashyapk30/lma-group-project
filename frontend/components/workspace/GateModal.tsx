// Stub: Approval checklist modal: every UNSUPPORTED field resolved or acknowledged; every NEEDS_REVIEW and UNANSWERED item resolved (plan §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { GateId } from "@/lib/types";

export interface GateModalProps {
  gate: GateId;
  caseId: string;
  open: boolean;
  onClose: () => void;
  className?: string;
}

export function GateModal(props: GateModalProps): ReactElement {
  return <section data-stub="GateModal" className={props.className} />;
}

export default GateModal;
