// Stub: Drop zone and mic button for files and dictation (plan §13.5, §4.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface DropZoneProps {
  caseId: string;
  className?: string;
}

export function DropZone(props: DropZoneProps): ReactElement {
  return <section data-stub="DropZone" className={props.className} />;
}

export default DropZone;
