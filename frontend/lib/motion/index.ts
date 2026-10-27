// Motion helpers (DESIGN.md "Direct manipulation and springs"). The reduced-motion switch is the app's own
// (lib/useReducedMotion: system setting or the in-app override); read prefersReducedMotion() at release time.
export { ALLOWANCE, SPRINGS, clamp, fromPerceptual, project, rubberClamp, rubberband, runSpring, simulate, stepSpring, type SpringOpts } from "./spring";
export { VelocityTracker } from "./velocity";
export { SpringValue } from "./value";
export { useDrag, type DragOptions, type DragRelease } from "./useDrag";
export { prefersReducedMotion, useReducedMotion } from "../useReducedMotion";

/** Decide a release: past `fraction` of `size` (counting the flick's projection) or faster than `speed` px/s. */
export function shouldCommit(offset: number, velocity: number, projected: number, size: number, fraction: number, speed: number): boolean {
  if (Math.sign(velocity) < 0 && Math.abs(velocity) > speed) return false; // flicked back
  return velocity > speed || offset + projected > size * fraction;
}
