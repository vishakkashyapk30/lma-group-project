// Stub: 'Show the plan' drawer with the live trace graph (React Flow) (plan §13.1, §13.4). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface TraceDrawerProps {
  caseId: string;
  open: boolean;
  onClose: () => void;
  className?: string;
}

export function TraceDrawer(props: TraceDrawerProps): ReactElement {
  return <section data-stub="TraceDrawer" className={props.className} />;
}

export default TraceDrawer;
