// Stub: Centre pane (core): counsel's questions and agent messages with signature icon, store/tool chips, 'Show the plan' (plan §13.5, §6.4). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface ChatPaneProps {
  caseId: string;
  className?: string;
}

export function ChatPane(props: ChatPaneProps): ReactElement {
  return <section data-stub="ChatPane" className={props.className} />;
}

export default ChatPane;
