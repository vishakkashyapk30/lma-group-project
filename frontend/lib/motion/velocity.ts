// Pointer velocity over the last 80 ms (px/s): enough samples to be steady, recent enough to follow a flick.
export class VelocityTracker {
  private samples: { t: number; x: number }[] = [];
  constructor(private readonly windowMs = 80) {}

  reset(x: number, t: number): void {
    this.samples = [{ t, x }];
  }

  add(x: number, t: number): void {
    this.samples.push({ t, x });
    const cutoff = t - this.windowMs;
    while (this.samples.length > 2 && this.samples[0]!.t < cutoff) this.samples.shift();
  }

  /** px/s; 0 with fewer than two samples or when the pointer has been still for longer than the window. */
  velocity(now?: number): number {
    if (this.samples.length < 2) return 0;
    const last = this.samples[this.samples.length - 1]!;
    if (now !== undefined && now - last.t > this.windowMs) return 0;
    const first = this.samples[0]!;
    const dt = last.t - first.t;
    return dt > 0 ? ((last.x - first.x) / dt) * 1000 : 0;
  }
}
