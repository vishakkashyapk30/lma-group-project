// Stub: Status chip: icon + label + colour from lib/status.ts, never colour alone (plan §13.2). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge(props: StatusBadgeProps): ReactElement {
  return <section data-stub="StatusBadge" className={props.className} />;
}

export default StatusBadge;
