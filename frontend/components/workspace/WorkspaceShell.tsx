// Stub: Case workspace: header, stage rail and three panes (plan §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface WorkspaceShellProps {
  caseId: string;
  className?: string;
}

export function WorkspaceShell(props: WorkspaceShellProps): ReactElement {
  return <section data-stub="WorkspaceShell" className={props.className} />;
}

export default WorkspaceShell;
