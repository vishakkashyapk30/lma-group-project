// Stub: Stage rail I-VII with approval gates (diamonds); later stages unlock after Gate 1 (plan §13.5). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { Stage } from "@/lib/types";

export interface StageRailProps {
  current?: Stage;
  className?: string;
}

export function StageRail(props: StageRailProps): ReactElement {
  return <section data-stub="StageRail" className={props.className} />;
}

export default StageRail;
