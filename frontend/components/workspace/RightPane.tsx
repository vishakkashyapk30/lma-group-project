// Stub: Right pane: tabs synced with the stage rail (plan §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface RightPaneProps {
  caseId: string;
  className?: string;
}

export function RightPane(props: RightPaneProps): ReactElement {
  return <section data-stub="RightPane" className={props.className} />;
}

export default RightPane;
