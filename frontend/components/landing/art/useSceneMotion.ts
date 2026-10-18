"use client";
// Resolves whether a scene should render its final static frame: an explicit `reducedMotion` prop wins, otherwise the
// user's preference (useReducedMotion). Shared by the landing scenes and transitions.
import { useReducedMotion } from "@/lib/useReducedMotion";

export function useSceneReduced(prop?: boolean): boolean {
  const pref = useReducedMotion();
  return prop ?? pref;
}
