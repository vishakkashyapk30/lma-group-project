// prefers-reduced-motion hook (plan §13.4, §13.7): every animation becomes a static icon with a text status.
export function useReducedMotion(): boolean {
  // TODO: matchMedia("(prefers-reduced-motion: reduce)") subscription
  throw new Error("useReducedMotion: not implemented (skeleton)");
}
