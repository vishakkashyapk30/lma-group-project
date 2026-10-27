// Spring maths for direct manipulation (DESIGN.md "Direct manipulation and springs"). Pure functions plus one small
// requestAnimationFrame runner; no React, no library. Units: px and px/s; time in seconds.
//
// Parameters follow the perceptual model of Apple's "Animate with springs" (WWDC23): a duration T and a bounce b map to
// mass 1, stiffness (2π/T)² and damping 4π(1-b)/T. A critically damped spring (b = 0) is within 1.4 % of its target at t = T.

export interface SpringOpts {
  stiffness: number;
  damping: number;
  mass?: number;
  /** Distance to the target below which the spring may rest (px). */
  restDelta?: number;
  /** Speed below which the spring may rest (px/s). */
  restSpeed?: number;
}

/** Mass 1, stiffness and damping from a perceptual duration T (s) and bounce b (0 = critically damped). */
export function fromPerceptual(T: number, b = 0): SpringOpts {
  return { stiffness: (2 * Math.PI / T) ** 2, damping: (4 * Math.PI * (1 - b)) / T, mass: 1 };
}

/** The table in DESIGN.md. */
export const SPRINGS = {
  press: fromPerceptual(0.15, 0),
  panel: fromPerceptual(0.4, 0),
  sheet: fromPerceptual(0.35, 0.1),
  gate: fromPerceptual(0.3, 0),
  timeline: fromPerceptual(0.3, 0),
  demo: fromPerceptual(0.45, 0.15),
} as const satisfies Record<string, SpringOpts>;

/** Rubber-band allowances (px): how far an element may be pulled past its limit at most. */
export const ALLOWANCE = { panel: 48, sheet: 64, gate: 12, timeline: 32, demo: 80 } as const;

/**
 * iOS-style rubber band: `x` is the distance past the limit, `d` the allowance. Diminishing returns, never reaches d:
 * offset = (1 - 1 / (|x| * c / d + 1)) * d, with the sign of x.
 */
export function rubberband(x: number, d: number, c = 0.55): number {
  if (d <= 0 || x === 0) return 0;
  return Math.sign(x) * (1 - 1 / ((Math.abs(x) * c) / d + 1)) * d;
}

/** Keep `x` inside [min, max]; past either end it resists with the rubber band (allowance per side). */
export function rubberClamp(x: number, min: number, max: number, dMin: number, dMax: number = dMin): number {
  if (x < min) return min - rubberband(min - x, dMin);
  if (x > max) return max + rubberband(x - max, dMax);
  return x;
}

/** Hard clamp (reduced motion: the element stops at its limit). */
export function clamp(x: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, x));
}

/**
 * Where a flick would come to rest (WWDC18 "Designing Fluid Interfaces"): v in px/s, deceleration rate per millisecond
 * 0.998 (normal) or 0.99 (fast). Returns the extra distance travelled.
 */
export function project(v: number, rate = 0.998): number {
  return ((v / 1000) * rate) / (1 - rate);
}

const STEP = 1 / 240;

/** One integration step (semi-implicit Euler), exported for tests. */
export function stepSpring(x: number, v: number, to: number, o: SpringOpts, dt = STEP): [number, number] {
  const m = o.mass ?? 1;
  const a = (-o.stiffness * (x - to) - o.damping * v) / m;
  const nv = v + a * dt;
  return [x + nv * dt, nv];
}

export interface SpringSample {
  t: number;
  x: number;
  v: number;
}

/**
 * Simulate a spring without a clock (tests, and to answer "when does it settle"). Stops at rest or after `maxT` seconds.
 * `settleT` is the first time after which the value stays within `settleFrac` of the travelled distance (or restDelta);
 * `overshoot` is how far (px) it passed the target.
 */
export function simulate(from: number, to: number, v0: number, o: SpringOpts, maxT = 3, settleFrac = 0.02): { samples: SpringSample[]; settleT: number; restT: number; overshoot: number } {
  const restDelta = o.restDelta ?? 0.5;
  const restSpeed = o.restSpeed ?? 10;
  const band = Math.max(restDelta, Math.abs(to - from) * settleFrac);
  let x = from;
  let v = v0;
  let t = 0;
  let settleT = 0;
  const samples: SpringSample[] = [{ t, x, v }];
  let restT = maxT;
  while (t < maxT) {
    [x, v] = stepSpring(x, v, to, o);
    t += STEP;
    samples.push({ t, x, v });
    if (Math.abs(x - to) > band) settleT = t;
    if (Math.abs(v) < restSpeed && Math.abs(x - to) < restDelta) {
      restT = t;
      break;
    }
  }
  const overshoot = samples.reduce((m, s) => Math.max(m, (s.x - to) * Math.sign(to - from)), 0);
  return { samples, settleT, restT, overshoot };
}

/**
 * Run a spring from `from` to `to` with initial velocity v0 on requestAnimationFrame. `onUpdate(x, v)` gets every frame;
 * `onRest` fires once at the target. Returns a stop function. To interrupt, stop it and start a new spring (or a drag)
 * from the last x and v, which keeps the motion continuous.
 */
export function runSpring(
  from: number,
  to: number,
  v0: number,
  o: SpringOpts,
  onUpdate: (x: number, v: number) => void,
  onRest?: () => void,
): () => void {
  const restDelta = o.restDelta ?? 0.5;
  const restSpeed = o.restSpeed ?? 10;
  let x = from;
  let v = v0;
  let last = 0;
  let acc = 0;
  let raf = 0;
  let stopped = false;
  const tick = (now: number) => {
    if (stopped) return;
    if (last === 0) last = now;
    acc += Math.min((now - last) / 1000, 0.064);
    last = now;
    while (acc >= STEP) {
      [x, v] = stepSpring(x, v, to, o);
      acc -= STEP;
    }
    if (Math.abs(v) < restSpeed && Math.abs(x - to) < restDelta) {
      onUpdate(to, 0);
      onRest?.();
      return;
    }
    onUpdate(x, v);
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return () => {
    stopped = true;
    cancelAnimationFrame(raf);
  };
}
