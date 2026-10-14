// Stub: Pairokar: cause-list bars slide as cases are scored; the board re-ranks by urgency. Where: /desk (plan §13.4). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { AnimationMode } from "./types";

export interface PairokarCauseListBarsProps {
  mode: AnimationMode;
  active: boolean;
  statusText?: string;
  className?: string;
}

export function PairokarCauseListBars(props: PairokarCauseListBarsProps): ReactElement {
  return <section data-stub="PairokarCauseListBars" className={props.className} />;
}

export default PairokarCauseListBars;
