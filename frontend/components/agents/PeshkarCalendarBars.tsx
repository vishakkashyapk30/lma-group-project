// Stub: Peshkar: calendar pages tick, custody bars grow; full version sweeps the Rights Radar over the timeline with flag chips. Where: Dates and Rights tabs (plan §13.4). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { AnimationMode } from "./types";

export interface PeshkarCalendarBarsProps {
  mode: AnimationMode;
  active: boolean;
  statusText?: string;
  className?: string;
}

export function PeshkarCalendarBars(props: PeshkarCalendarBarsProps): ReactElement {
  return <section data-stub="PeshkarCalendarBars" className={props.className} />;
}

export default PeshkarCalendarBars;
