// Stub: Sutradhar: 24-spoke wheel, each spoke lights as its store or tool is queried; 'Show the plan' opens the trace graph. Where: chat header, trace drawer (plan §13.4). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { AnimationMode } from "./types";

export interface SutradharWheelProps {
  mode: AnimationMode;
  active: boolean;
  statusText?: string;
  className?: string;
}

export function SutradharWheel(props: SutradharWheelProps): ReactElement {
  return <section data-stub="SutradharWheel" className={props.className} />;
}

export default SutradharWheel;
