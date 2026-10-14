// Stub: Row of dots with one lit (scene indicator) (plan §13.2, §13.3). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface SceneIndicatorProps {
  total: number;
  active: number;
  className?: string;
}

export function SceneIndicator(props: SceneIndicatorProps): ReactElement {
  return <section data-stub="SceneIndicator" className={props.className} />;
}

export default SceneIndicator;
