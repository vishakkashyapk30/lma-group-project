import { describe, expect, it, vi } from "vitest";
import { ALLOWANCE, SPRINGS, SpringValue, VelocityTracker, clamp, fromPerceptual, project, rubberClamp, rubberband, shouldCommit, simulate } from "@/lib/motion";

describe("fromPerceptual (mass 1, k = (2π/T)², c = 4π(1-b)/T)", () => {
  it("matches the DESIGN.md table", () => {
    const panel = fromPerceptual(0.4, 0);
    expect(panel.stiffness).toBeCloseTo(246.7, 0);
    expect(panel.damping).toBeCloseTo(31.4, 1);
    const demo = fromPerceptual(0.45, 0.15);
    expect(demo.stiffness).toBeCloseTo(195, 0);
    expect(demo.damping).toBeCloseTo(23.7, 1);
    expect(SPRINGS.press.stiffness).toBeCloseTo(1755, 0);
  });

  it("b = 0 is critical damping (c² = 4mk)", () => {
    const s = fromPerceptual(0.3, 0);
    expect(s.damping ** 2).toBeCloseTo(4 * s.stiffness, 6);
  });
});

describe("springs settle within the 450 ms gesture budget", () => {
  for (const [name, spring] of Object.entries(SPRINGS)) {
    it(`${name}: within 2 % of a 300 px travel by 450 ms, from rest and from a 1500 px/s flick`, () => {
      expect(simulate(0, 300, 0, spring).settleT).toBeLessThanOrEqual(0.45);
      expect(simulate(0, 300, 1500, spring).settleT).toBeLessThanOrEqual(0.45);
    });
  }

  it("critically damped springs never overshoot from rest", () => {
    for (const s of [SPRINGS.panel, SPRINGS.gate, SPRINGS.press, SPRINGS.timeline]) expect(simulate(0, 200, 0, s).overshoot).toBeLessThan(0.01);
  });

  it("a bounce of 0.15 overshoots a little, under 10 % of the travel", () => {
    const { overshoot } = simulate(0, 200, 0, SPRINGS.demo);
    expect(overshoot).toBeGreaterThan(0);
    expect(overshoot).toBeLessThan(20);
  });

  it("carries the release velocity: a flick towards the target arrives sooner than from rest", () => {
    const at = (v: number) => simulate(0, 300, v, SPRINGS.panel).samples.find((s) => s.x >= 150)!.t;
    expect(at(2000)).toBeLessThan(at(0));
  });

  it("comes to rest exactly on the target", () => {
    const { samples, restT } = simulate(10, -40, 0, SPRINGS.sheet);
    expect(restT).toBeLessThan(1);
    expect(Math.abs(samples[samples.length - 1]!.x + 40)).toBeLessThan(0.5);
  });
});

describe("rubberband (offset = (1 - 1/(x*0.55/d + 1)) * d)", () => {
  it("gives the values in the ideation table (corrected: 23 and 17 px at 50 px)", () => {
    expect([20, 50, 100, 200, 400].map((x) => Math.round(rubberband(x, 160)))).toEqual([10, 23, 41, 65, 93]);
    expect([20, 50, 100, 200, 400].map((x) => Math.round(rubberband(x, 48)))).toEqual([9, 17, 26, 33, 39]);
  });

  it("is monotonic, below the allowance, and odd", () => {
    let prev = 0;
    for (let x = 1; x < 5000; x += 7) {
      const r = rubberband(x, ALLOWANCE.panel);
      expect(r).toBeGreaterThan(prev);
      expect(r).toBeLessThan(ALLOWANCE.panel);
      prev = r;
    }
    expect(rubberband(-30, 12)).toBeCloseTo(-rubberband(30, 12), 10);
    expect(rubberband(0, 12)).toBe(0);
    expect(rubberband(10, 0)).toBe(0);
  });

  it("starts with slope 0.55 (resists from the first pixel)", () => {
    expect(rubberband(0.01, 80) / 0.01).toBeCloseTo(0.55, 2);
  });

  it("rubberClamp passes values inside the range and resists past either end", () => {
    expect(rubberClamp(50, 0, 100, 20)).toBe(50);
    expect(rubberClamp(130, 0, 100, 20)).toBeCloseTo(100 + rubberband(30, 20), 10);
    expect(rubberClamp(-30, 0, 100, 10, 20)).toBeCloseTo(-rubberband(30, 10), 10);
    expect(clamp(130, 0, 100)).toBe(100);
  });
});

describe("project (momentum)", () => {
  it("projects a 1000 px/s flick about 499 px at the normal rate and 99 px at the fast rate", () => {
    expect(project(1000)).toBeCloseTo(499, 0);
    expect(project(1000, 0.99)).toBeCloseTo(99, 0);
    expect(project(-500)).toBeCloseTo(-249.5, 1);
    expect(project(0)).toBe(0);
  });
});

describe("shouldCommit", () => {
  it("commits past the fraction, on a fast flick, and not on a flick back", () => {
    expect(shouldCommit(60, 0, 0, 100, 0.5, 500)).toBe(true);
    expect(shouldCommit(20, 0, 0, 100, 0.5, 500)).toBe(false);
    expect(shouldCommit(10, 600, 0, 100, 0.5, 500)).toBe(true);
    expect(shouldCommit(20, 300, 40, 100, 0.5, 500)).toBe(true);
    expect(shouldCommit(70, -900, -400, 100, 0.5, 500)).toBe(false);
  });
});

describe("VelocityTracker", () => {
  it("measures over the last 80 ms", () => {
    const vt = new VelocityTracker();
    vt.reset(0, 0);
    for (let t = 10; t <= 200; t += 10) vt.add(t * 2, t); // 2 px per ms = 2000 px/s
    expect(vt.velocity()).toBeCloseTo(2000, 0);
  });

  it("is zero when the pointer stopped before release", () => {
    const vt = new VelocityTracker();
    vt.reset(0, 0);
    vt.add(100, 50);
    expect(vt.velocity(300)).toBe(0);
  });
});

describe("SpringValue", () => {
  it("jumps at once under reduced motion and calls onRest", () => {
    const seen: number[] = [];
    const v = new SpringValue(0, (x) => seen.push(x));
    const onRest = vi.fn();
    v.to(120, { spring: SPRINGS.panel, reduced: true, onRest });
    expect(seen).toEqual([120]);
    expect(v.value).toBe(120);
    expect(onRest).toHaveBeenCalledOnce();
  });

  it("can be interrupted: stop keeps the value where it was", () => {
    vi.useFakeTimers();
    let frame = 0;
    const raf = vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      frame += 1;
      setTimeout(() => cb(frame * 16), 16);
      return frame;
    });
    const v = new SpringValue(0, () => {});
    v.to(300, { spring: SPRINGS.panel });
    vi.advanceTimersByTime(16 * 6);
    expect(v.running).toBe(true);
    v.stop();
    const at = v.value;
    expect(at).toBeGreaterThan(0);
    expect(at).toBeLessThan(300);
    vi.advanceTimersByTime(500);
    expect(v.value).toBe(at);
    expect(v.running).toBe(false);
    raf.mockRestore();
    vi.useRealTimers();
  });
});
