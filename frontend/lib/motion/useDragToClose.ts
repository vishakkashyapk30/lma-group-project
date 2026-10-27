"use client";
// Drag a panel or a sheet away to close it (DESIGN.md "Direct manipulation and springs"). The handle follows the pointer
// 1:1 towards closing; pulled the other way it resists with the rubber band and springs back. Released past `fraction`
// of its size (counting the flick's projection) or faster than `speed`, it carries its velocity off screen and closes;
// otherwise it springs home. Grabbing it mid-flight stops it where it is. Under reduced motion it follows the pointer
// without the rubber band and closes or returns at once. The panel's Close button and Escape stay the primary way.
import { useEffect, useRef, type RefObject } from "react";
import { prefersReducedMotion } from "../useReducedMotion";
import { clamp, rubberClamp, shouldCommit, type SpringOpts } from "./spring";
import { useDrag } from "./useDrag";
import { SpringValue } from "./value";

export interface DragToCloseOptions {
  /** "x": closes to the right; "y": closes downwards. */
  axis: "x" | "y";
  onClose: () => void;
  spring: SpringOpts;
  /** Rubber-band allowance against the closing direction (px). */
  allowance: number;
  /** Fraction of the size past which a release closes. */
  fraction: number;
  /** Release speed (px/s) above which a release closes. */
  speed: number;
  enabled?: boolean;
  /** Stop CSS exit animations from fighting the drag (Radix drawers animate their own close). */
  killExitAnimation?: boolean;
}

export function useDragToClose(panel: RefObject<HTMLElement | null>, handle: RefObject<HTMLElement | null>, o: DragToCloseOptions): void {
  const opts = useRef(o);
  opts.current = o;
  const value = useRef<SpringValue | null>(null);
  const base = useRef(0);
  const size = useRef(0);

  useEffect(() => {
    // Writes to whatever element the ref holds now, so a re-mounted panel keeps working.
    value.current = new SpringValue(0, (x) => {
      const el = panel.current;
      if (!el) return;
      el.style.transform = x === 0 ? "" : opts.current.axis === "x" ? `translateX(${x}px)` : `translateY(${x}px)`;
      el.dataset.dragOffset = String(Math.round(x));
    });
    return () => value.current?.stop();
  }, [panel]);

  useDrag(handle, {
    axis: o.axis,
    enabled: o.enabled,
    rate: 0.99,
    onStart: () => {
      const el = panel.current;
      const v = value.current;
      if (!el || !v) return;
      v.stop();
      base.current = v.value;
      const r = el.getBoundingClientRect();
      size.current = opts.current.axis === "x" ? r.width : r.height;
      el.dataset.dragging = "true";
    },
    onMove: (delta) => {
      const v = value.current;
      if (!v) return;
      const raw = base.current + delta;
      const reduced = prefersReducedMotion();
      v.set(reduced ? clamp(raw, 0, size.current) : rubberClamp(raw, 0, size.current, opts.current.allowance, 0));
    },
    onEnd: ({ velocity, projected }) => {
      const el = panel.current;
      const v = value.current;
      if (!el || !v) return;
      delete el.dataset.dragging;
      const reduced = prefersReducedMotion();
      const { fraction, speed, spring, onClose, killExitAnimation } = opts.current;
      if (shouldCommit(v.value, velocity, projected, size.current, fraction, speed)) {
        const close = () => {
          if (killExitAnimation) el.style.animation = "none";
          onClose();
        };
        // Leaving: never slower than the flick, and it does not bounce back into view.
        v.to(size.current, { spring, velocity: Math.max(velocity, 0), reduced, onRest: close });
      } else {
        v.to(0, { spring, velocity, reduced });
      }
    },
  });
}
