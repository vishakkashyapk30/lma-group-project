// Stub: Clickable source chip that scrolls the PDF to the box (plan §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { SourceRef } from "@/lib/types";

export interface SourceChipProps {
  source: SourceRef;
  className?: string;
}

export function SourceChip(props: SourceChipProps): ReactElement {
  return <section data-stub="SourceChip" className={props.className} />;
}

export default SourceChip;
