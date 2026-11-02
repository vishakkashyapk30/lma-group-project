// A number that is either dragged or sprung, written straight to the element (no React state per frame). Grabbing it
// while it moves stops it where it is and keeps its velocity, so gestures can be interrupted.
import { runSpring, type SpringOpts } from "./spring";

export class SpringValue {
  value: number;
  velocity = 0;
  private stopFn: (() => void) | null = null;

  constructor(initial: number, private readonly apply: (x: number) => void) {
    this.value = initial;
  }

  get running(): boolean {
    return this.stopFn !== null;
  }

  /** Stop any spring where it is (the value and velocity stay as they were on the last frame). */
  stop(): void {
    this.stopFn?.();
    this.stopFn = null;
  }

  /** Set the value directly (during a drag, or as the reduced-motion jump). */
  set(x: number, velocity = 0): void {
    this.stop();
    this.value = x;
    this.velocity = velocity;
    this.apply(x);
  }

  /**
   * Spring to `target`, starting from the current value with `velocity` (defaults to the value's own). With `reduced`
   * the value jumps there at once.
   */
  to(target: number, opts: { spring: SpringOpts; velocity?: number; reduced?: boolean; onRest?: () => void }): void {
    this.stop();
    if (opts.reduced) {
      this.set(target);
      opts.onRest?.();
      return;
    }
    const v0 = opts.velocity ?? this.velocity;
    this.stopFn = runSpring(this.value, target, v0, opts.spring, (x, v) => {
      this.value = x;
      this.velocity = v;
      this.apply(x);
    }, () => {
      this.stopFn = null;
      this.velocity = 0;
      opts.onRest?.();
    });
  }
}
