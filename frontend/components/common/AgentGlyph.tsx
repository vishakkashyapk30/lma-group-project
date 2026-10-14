// Stub: Small per-agent glyph used on chat messages and chips (plan §13.4). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { AgentName } from "@/lib/types";

export interface AgentGlyphProps {
  agent: AgentName;
  className?: string;
}

export function AgentGlyph(props: AgentGlyphProps): ReactElement {
  return <section data-stub="AgentGlyph" className={props.className} />;
}

export default AgentGlyph;
