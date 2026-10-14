// Stub: Dispatcher: renders the right signature animation for an agent; static icon + text under reduced motion (plan §13.4). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { AgentName } from "@/lib/types";
import type { AnimationMode } from "./types";

export interface AgentSignatureProps {
  agent: AgentName;
  mode: AnimationMode;
  active: boolean;
  statusText?: string;
  className?: string;
}

export function AgentSignature(props: AgentSignatureProps): ReactElement {
  return <section data-stub="AgentSignature" className={props.className} />;
}

export default AgentSignature;
