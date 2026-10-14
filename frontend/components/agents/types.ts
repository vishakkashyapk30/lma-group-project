// Shared props for agent signature animations (plan §13.4).
import type { AgentName } from "@/lib/types";

/** "working": subtle loop (<= 2 s, low amplitude); "full": plays once per session or on click; "static": reduced-motion icon + text status. */
export type AnimationMode = "working" | "full" | "static";

export interface AgentAnimationProps {
  mode: AnimationMode;
  active: boolean;
  statusText?: string;
  className?: string;
}

export interface AgentSignatureProps extends AgentAnimationProps {
  agent: AgentName;
}
