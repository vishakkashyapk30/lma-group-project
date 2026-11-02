"use client";
// A gate button that holds (DESIGN.md "Gate that holds"). While items are open it is not disabled but held: pressing it,
// or trying to drag it on, moves it at most 12 px against the rubber band, it springs back, and `onHold` shows what is
// still open, so the reason the gate is closed appears at the moment of trying. With nothing open it is an ordinary
// primary button that opens the confirm dialog. Keyboard: Enter or Space does the same as a press. Under reduced motion
// it does not move; the list still opens. Screen readers hear it as unavailable (aria-disabled) with the reason.
import { ArrowRight, Lock } from "lucide-react";
import { useEffect, useRef, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { ALLOWANCE, SPRINGS, SpringValue, clamp, prefersReducedMotion, rubberClamp, useDrag } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface HoldButtonProps {
  label: string;
  /** True while something is open: the button holds instead of acting. */
  held: boolean;
  /** How many items are open (shown on the button while held). */
  openCount: number;
  onPress: () => void;
  onHold: () => void;
  testId?: string;
  describedBy?: string;
  next?: boolean;
  busy?: boolean;
  className?: string;
}

/** Speed of the nudge a press gives the held button (px/s); with the gate spring it travels about 5 px and returns. */
const NUDGE = 320;

export function HoldButton({ label, held, openCount, onPress, onHold, testId, describedBy, next = true, busy, className }: HoldButtonProps): ReactElement {
  const ref = useRef<HTMLButtonElement>(null);
  const value = useRef<SpringValue | null>(null);

  useEffect(() => {
    value.current = new SpringValue(0, (x) => {
      const el = ref.current;
      if (!el) return;
      el.style.translate = x === 0 ? "" : `${x}px 0`;
      el.dataset.holdOffset = String(Math.round(x));
    });
    return () => value.current?.stop();
  }, []);

  useDrag(ref, {
    axis: "x",
    enabled: held,
    onStart: () => value.current?.stop(),
    onMove: (d) => value.current?.set(prefersReducedMotion() ? clamp(0, 0, 0) : rubberClamp(d, 0, 0, ALLOWANCE.gate)),
    onEnd: ({ velocity }) => {
      value.current?.to(0, { spring: SPRINGS.gate, velocity, reduced: prefersReducedMotion() });
      onHold();
    },
  });

  const click = () => {
    if (!held) return onPress();
    if (!prefersReducedMotion()) value.current?.to(0, { spring: SPRINGS.gate, velocity: NUDGE });
    onHold();
  };

  return (
    <Button
      ref={ref}
      data-testid={testId}
      data-held={held || undefined}
      size="lg"
      onClick={click}
      disabled={busy}
      aria-disabled={held || undefined}
      aria-describedby={describedBy}
      className={cn(held && "cursor-default touch-pan-y aria-disabled:pointer-events-auto aria-disabled:opacity-70", className)}
    >
      {held ? <Lock aria-hidden key="lock" className="animate-fade-in" /> : null}
      {label}
      {held ? <span className="tabular font-normal">({openCount} open)</span> : next ? <ArrowRight aria-hidden key="arrow" className="animate-fade-in" /> : null}
    </Button>
  );
}
