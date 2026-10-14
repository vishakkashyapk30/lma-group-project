// Stub: IPC<->BNS bridge with text diff (plan §5.4, §13.1). TODO: implement; no animation or business logic yet.
import type { ReactElement } from "react";

export interface BridgeViewProps {
  className?: string;
}

export function BridgeView(props: BridgeViewProps): ReactElement {
  return <section data-stub="BridgeView" className={props.className} />;
}

export default BridgeView;
