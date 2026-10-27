// Motion helpers (DESIGN.md "Direct manipulation and springs"). The reduced-motion switch is the app's own
// (lib/useReducedMotion: system setting or the in-app override); read prefersReducedMotion() at release time.
export { ALLOWANCE, SPRINGS, clamp, shouldCommit, fromPerceptual, project, rubberClamp, rubberband, runSpring, simulate, stepSpring, type SpringOpts } from "./spring";
export { VelocityTracker } from "./velocity";
export { SpringValue } from "./value";
export { useDrag, type DragOptions, type DragRelease } from "./useDrag";
export { useDragToClose, type DragToCloseOptions } from "./useDragToClose";
export { prefersReducedMotion, useReducedMotion } from "../useReducedMotion";

