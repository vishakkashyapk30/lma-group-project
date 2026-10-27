"use client";
// Pointer drag on one axis for mouse, touch and pen: pointer capture, a 4 px slop so taps stay clicks, velocity over the
// last 80 ms, and a click swallowed after a real drag. The caller turns the raw movement into an offset (usually with
// rubberClamp) and decides what the release does; keyboard and button paths live in the component (DESIGN.md parity).
import { useEffect, useRef, type RefObject } from "react";
import { project } from "./spring";
import { VelocityTracker } from "./velocity";

export interface DragRelease {
  /** Raw pointer movement since the grab, on the axis (px). */
  delta: number;
  /** Velocity at release on the axis (px/s). */
  velocity: number;
  /** Extra distance a flick at this velocity would travel (px). */
  projected: number;
}

export interface DragOptions {
  axis: "x" | "y";
  /** Called on the grab (after the slop); stop running springs here. */
  onStart?: () => void;
  /** Raw pointer movement since the grab (px), every move. */
  onMove: (delta: number) => void;
  onEnd: (release: DragRelease) => void;
  /** Called when a grab ends without a drag (a tap or click); the click itself still fires. */
  onTap?: () => void;
  enabled?: boolean;
  /** Pixels before a press becomes a drag. */
  slop?: number;
  /** Deceleration rate for the projection (0.998 normal, 0.99 fast). */
  rate?: number;
}

export function useDrag(ref: RefObject<HTMLElement | null>, options: DragOptions): void {
  const opts = useRef(options);
  opts.current = options;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let id: number | null = null;
    let origin = 0;
    let cross = 0;
    let dragging = false;
    const vt = new VelocityTracker();
    const pos = (e: PointerEvent) => (opts.current.axis === "x" ? e.clientX : e.clientY);
    const other = (e: PointerEvent) => (opts.current.axis === "x" ? e.clientY : e.clientX);

    const swallowClick = (ev: MouseEvent) => {
      ev.stopPropagation();
      ev.preventDefault();
    };

    const onDown = (e: PointerEvent) => {
      if (opts.current.enabled === false || id !== null) return;
      if (e.pointerType === "mouse" && e.button !== 0) return;
      id = e.pointerId;
      origin = pos(e);
      cross = other(e);
      dragging = false;
      vt.reset(origin, e.timeStamp);
    };

    const onMove = (e: PointerEvent) => {
      if (e.pointerId !== id) return;
      const d = pos(e) - origin;
      if (!dragging) {
        const slop = opts.current.slop ?? 4;
        // A mostly cross-axis move is a scroll or another gesture: let it go.
        if (Math.abs(other(e) - cross) > slop && Math.abs(other(e) - cross) > Math.abs(d)) {
          id = null;
          return;
        }
        if (Math.abs(d) < slop) return;
        dragging = true;
        try {
          el.setPointerCapture(e.pointerId);
        } catch {
          /* synthetic events in tests */
        }
        opts.current.onStart?.();
      }
      e.preventDefault();
      vt.add(pos(e), e.timeStamp);
      opts.current.onMove(d);
    };

    const finish = (e: PointerEvent, cancelled: boolean) => {
      if (e.pointerId !== id) return;
      id = null;
      if (!dragging) {
        if (!cancelled) opts.current.onTap?.();
        return;
      }
      dragging = false;
      const velocity = vt.velocity(e.timeStamp);
      const delta = pos(e) - origin;
      // A drag is not a click: swallow the click the browser fires after pointerup.
      el.addEventListener("click", swallowClick, { capture: true, once: true });
      window.setTimeout(() => el.removeEventListener("click", swallowClick, { capture: true }), 0);
      opts.current.onEnd({ delta, velocity: cancelled ? 0 : velocity, projected: cancelled ? 0 : project(velocity, opts.current.rate) });
    };
    const onUp = (e: PointerEvent) => finish(e, false);
    const onCancel = (e: PointerEvent) => finish(e, true);

    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onCancel);
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onCancel);
    };
  }, [ref]);
}
