// Stub: Abhiyojak: objection cards drop on one pan, replies on the other; scales stay tipped while anything is unanswered. Where: spar stage (plan §13.4). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";
import type { AnimationMode } from "./types";

export interface AbhiyojakScalesProps {
  mode: AnimationMode;
  active: boolean;
  statusText?: string;
  className?: string;
}

export function AbhiyojakScales(props: AbhiyojakScalesProps): ReactElement {
  return <section data-stub="AbhiyojakScales" className={props.className} />;
}

export default AbhiyojakScales;
