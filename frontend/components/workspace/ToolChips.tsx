// Stub: Store and tool chips on every answer (plan §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { ChatMessage } from "@/lib/types";

export interface ToolChipsProps {
  chips: ChatMessage["chips"];
  className?: string;
}

export function ToolChips(props: ToolChipsProps): ReactElement {
  return <section data-stub="ToolChips" className={props.className} />;
}

export default ToolChips;
