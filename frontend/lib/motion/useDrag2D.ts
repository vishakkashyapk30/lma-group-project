"use client";
// Free 2D drag for a card (the landing's "drop the FIR on the file"): pointer capture on the card itself (it has no
// child controls), a 4 px slop so a tap stays a click, and velocity on both axes at release. Page scroll is left alone
// by giving the card `touch-action: none` only.
import { useEffect, useRef, useState, type RefObject } from "react";
import { VelocityTracker } from "./velocity";

export interface Drag2DRelease {
  dx: number;
  dy: number;
  vx: number;
  vy: number;
}

export interface Drag2DOptions {
  onStart?: () => void;
  onMove: (dx: number, dy: number) => void;
  onEnd: (r: Drag2DRelease) => void;
  enabled?: boolean;
}

export function useDrag2D(ref: RefObject<HTMLElement | null>, options: Drag2DOptions): void {
  const opts = useRef(options);
  opts.current = options;
  const [el, setEl] = useState<HTMLElement | null>(null);
  // Rebind when the element behind the ref changes (the card re-mounts after "Put the FIR back").
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (ref.current !== el) setEl(ref.current);
  });
  useEffect(() => {
    if (!el) return;
    let id: number | null = null;
    let ox = 0;
    let oy = 0;
    let dragging = false;
    const tx = new VelocityTracker();
    const ty = new VelocityTracker();
    const swallow = (ev: MouseEvent) => {
      ev.stopPropagation();
      ev.preventDefault();
    };
    const down = (e: PointerEvent) => {
      if (opts.current.enabled === false || id !== null || (e.pointerType === "mouse" && e.button !== 0)) return;
      id = e.pointerId;
      ox = e.clientX;
      oy = e.clientY;
      dragging = false;
      tx.reset(ox, e.timeStamp);
      ty.reset(oy, e.timeStamp);
      try {
        el.setPointerCapture(e.pointerId);
      } catch {
        /* synthetic events */
      }
    };
    const move = (e: PointerEvent) => {
      if (e.pointerId !== id) return;
      const dx = e.clientX - ox;
      const dy = e.clientY - oy;
      if (!dragging) {
        if (Math.hypot(dx, dy) < 4) return;
        dragging = true;
        opts.current.onStart?.();
      }
      tx.add(e.clientX, e.timeStamp);
      ty.add(e.clientY, e.timeStamp);
      opts.current.onMove(dx, dy);
    };
    const up = (e: PointerEvent, cancelled = false) => {
      if (e.pointerId !== id) return;
      id = null;
      if (!dragging) return;
      dragging = false;
      el.addEventListener("click", swallow, { capture: true, once: true });
      window.setTimeout(() => el.removeEventListener("click", swallow, { capture: true }), 0);
      opts.current.onEnd({
        dx: e.clientX - ox,
        dy: e.clientY - oy,
        vx: cancelled ? 0 : tx.velocity(e.timeStamp),
        vy: cancelled ? 0 : ty.velocity(e.timeStamp),
      });
    };
    const onUp = (e: PointerEvent) => up(e);
    const onCancel = (e: PointerEvent) => up(e, true);
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onCancel);
    return () => {
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onCancel);
    };
  }, [el]);
}
