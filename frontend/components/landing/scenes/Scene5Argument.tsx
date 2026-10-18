"use client";
// Scene 5, The argument (plan §13.3). One pinned timeline in three acts on oxblood:
//   A. the wheel returns as Sutradhar and its spokes light towards the four shelves;
//   B. gold threads tie fact chips to precedent chips, and the IPC 420 == BNS 318(4) bridge appears;
//   C. objection cards drop on one pan of the scales and replies on the other until the scales settle.
// Only transform, opacity and DrawSVG are animated. Reduced motion shows the final frame of each act, stacked.
import { useRef, type ReactElement } from "react";
import { cn } from "@/lib/utils";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import { Wheel24 } from "../art/Wheel24";
import { useSceneReduced } from "../art/useSceneMotion";

export interface Scene5ArgumentProps {
  className?: string;
  reducedMotion?: boolean;
}

/** Spokes 0-5 (top, clockwise) face the north-east shelf, 6-11 south-east, 12-17 south-west, 18-23 north-west. */
const QUADRANTS = [
  { shelf: "Law", note: "Statutes and the IPC to BNS bridge", side: "right", row: 0 },
  { shelf: "Case law", note: "Precedents and their good-law status", side: "right", row: 1 },
  { shelf: "Advocacy", note: "Formats and practice notes", side: "left", row: 1 },
  { shelf: "Case", note: "This client's own papers", side: "left", row: 0 },
] as const;

const FACTS = [
  "No prior convictions on record",
  "Fixed residence, family in the city",
  "Charge-sheet filed; investigation complete",
  "In custody, trial yet to begin",
] as const;
const PRECEDENTS = [
  { name: "State of Rajasthan v. Balchand", year: "1977", note: "bail, not jail" },
  { name: "Sanjay Chandra v. CBI", year: "2012", note: "detention is not punishment" },
  { name: "Arnesh Kumar v. State of Bihar", year: "2014", note: "arrest is not automatic" },
  { name: "Satender Kumar Antil v. CBI", year: "2022", note: "bail jurisprudence restated" },
] as const;
/** fact i is tied to precedent THREAD_TO[i] (crossing on purpose: the threads are matched, not a lookup table). */
const THREAD_TO = [2, 0, 3, 1] as const;

const OBJECTIONS = ["Flight risk", "Gravity of the offence", "Tampering with witnesses"] as const;
const REPLIES = ["Fixed address; a surety is offered", "Charge-sheet is filed; the evidence is documentary", "Key witnesses already examined"] as const;
const OBJ_TILT = [-5, -9, -12] as const;
const REPLY_TILT = [-8, -3.5, 1.5] as const;

const PILE_TOP = [70, 40, 10] as const;

function Scales({ reduced }: { reduced: boolean }): ReactElement {
  const pan = (side: "left" | "right") => {
    const items = side === "left" ? OBJECTIONS : REPLIES;
    const label = side === "left" ? "Objection" : "Reply";
    return (
      <div className={cn("absolute top-0 w-0", side === "left" ? "left-0" : "right-0")}>
        <div data-pan className="absolute -left-[100px] top-0 h-[148px] w-[200px]">
          <svg aria-hidden viewBox="0 0 200 124" className="absolute inset-x-0 top-0 h-[124px] w-full text-gold-pale" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
            <path d="M100 0L8 118M100 0L192 118M100 0V118" />
          </svg>
          <div className="absolute inset-x-0 top-[116px] h-8 rounded-b-[100px] border-x border-b border-gold-pale bg-oxblood/80" />
          {items.map((t, k) => (
            <div
              key={t}
              data-card={side}
              className={cn(
                "absolute left-1/2 -ml-[82px] flex h-[46px] w-[164px] flex-col justify-center rounded-[4px] border bg-cream px-2 text-ink shadow-md",
                side === "left" ? "border-maroon" : "border-gold-leaf",
              )}
              style={{ top: PILE_TOP[k]!, zIndex: 10 + k, opacity: reduced ? 1 : 0 }}
            >
              <span className={cn("font-mono text-[9px] uppercase tracking-wider", side === "left" ? "text-maroon" : "text-ink-muted")}>{label} {k + 1}</span>
              <span className="text-[11px] font-medium leading-tight">{t}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };
  return (
    <div className="relative mx-auto h-[min(50svh,350px)] min-h-[300px] w-[min(94vw,640px)]">
      <svg aria-hidden viewBox="0 0 40 300" className="absolute left-1/2 top-[44px] h-[calc(100%-44px)] w-10 -translate-x-1/2 text-gold-pale" preserveAspectRatio="xMidYMin meet" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
        <path d="M20 4V270M6 296H34M12 296C12 280 16 272 20 270C24 272 28 280 28 296" />
      </svg>
      <div data-beam className="absolute inset-x-[7%] top-[44px] h-[3px] rounded-full bg-gold-pale">
        <span aria-hidden className="absolute left-1/2 top-1/2 size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-gold-pale bg-oxblood" />
        {pan("left")}
        {pan("right")}
      </div>
    </div>
  );
}

export function Scene5Argument({ className, reducedMotion }: Scene5ArgumentProps): ReactElement {
  const reduced = useSceneReduced(reducedMotion);
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      if (reduced) return;
      const gsap = registerMotion();
      const el = root.current;
      if (!el) return;
      const q = <T extends Element>(s: string) => Array.from(el.querySelectorAll<T>(s));
      const [panA, panB, panC] = [q("[data-act='a']")[0], q("[data-act='b']")[0], q("[data-act='c']")[0]];
      const spokes = q<SVGGElement>("[data-lit-wheel] [data-spoke]");
      const labels = q<HTMLElement>("[data-shelf-label]");
      const rings = q<HTMLElement>("[data-shelf-ring]");
      const facts = q<HTMLElement>("[data-fact]");
      const precs = q<HTMLElement>("[data-prec]");
      const threads = q<SVGPathElement>("[data-thread]");
      const bridge = q<HTMLElement>("[data-bridge]");
      const beam = q<HTMLElement>("[data-beam]");
      const pans = q<HTMLElement>("[data-pan]");
      const objs = q<HTMLElement>("[data-card='left']");
      const reps = q<HTMLElement>("[data-card='right']");
      const settle = q<HTMLElement>("[data-settled]");
      const intro = q<HTMLElement>("[data-intro]");
      if (!panA || !panB || !panC || !beam[0]) return;

      gsap.set(intro, { opacity: 0, y: 16 });
      gsap.set([panB, panC], { opacity: 0 });
      gsap.set(spokes, { opacity: 0 });
      gsap.set(rings, { opacity: 0 });
      gsap.set(labels, { opacity: 0.55 });
      gsap.set([...facts, ...precs, ...bridge], { opacity: 0, y: 14 });
      gsap.set(settle, { opacity: 0, y: 10 });
      gsap.set([...objs, ...reps], { opacity: 0, y: -260 });
      gsap.set(beam, { transformOrigin: "50% 50%" });
      gsap.set(pans, { transformOrigin: "50% 0%" });

      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: { trigger: el, start: "top top+=56", end: "+=620%", pin: true, scrub: 0.7, anticipatePin: 1, invalidateOnRefresh: true },
      });
      tl.to(intro, { opacity: 1, y: 0, duration: 0.5, stagger: 0.12, ease: "power2.out" }, 0);

      // Act A: the spokes light towards the shelves, quadrant by quadrant
      QUADRANTS.forEach((_, qi) => {
        const t = 0.7 + qi * 0.85;
        tl.to(spokes.slice(qi * 6, qi * 6 + 6), { opacity: 1, duration: 0.2, stagger: 0.07, ease: "power2.out" }, t)
          .to(rings[qi]!, { opacity: 1, duration: 0.25 }, t + 0.35)
          .to(labels[qi]!, { opacity: 1, duration: 0.25 }, t + 0.35);
      });

      // Act A to B
      const tB = 4.6;
      tl.to(panA, { opacity: 0, duration: 0.5 }, tB).to(panB, { opacity: 1, duration: 0.5 }, tB + 0.3);
      tl.to(facts, { opacity: 1, y: 0, duration: 0.3, stagger: 0.15, ease: "power2.out" }, tB + 0.6)
        .to(precs, { opacity: 1, y: 0, duration: 0.3, stagger: 0.15, ease: "power2.out" }, tB + 0.9);
      threads.forEach((th, i) => {
        tl.fromTo(th, { drawSVG: "0%" }, { drawSVG: "100%", duration: 0.6, ease: "power1.inOut" }, tB + 1.7 + i * 0.35);
      });
      tl.to(bridge, { opacity: 1, y: 0, duration: 0.4, stagger: 0.2, ease: "power2.out" }, tB + 3.4);

      // Act B to C
      const tC = tB + 5.0;
      tl.to(panB, { opacity: 0, duration: 0.5 }, tC).to(panC, { opacity: 1, duration: 0.5 }, tC + 0.3);
      const tilt = (deg: number, at: number, dur = 0.45, ease = "power2.out") => {
        tl.to(beam, { rotation: deg, duration: dur, ease }, at).to(pans, { rotation: -deg, duration: dur, ease }, at);
      };
      objs.forEach((c, k) => {
        const at = tC + 0.9 + k * 0.9;
        tl.to(c, { opacity: 1, y: 0, duration: 0.45, ease: "bounce.out" }, at);
        tilt(OBJ_TILT[k]!, at + 0.3);
      });
      reps.forEach((c, k) => {
        const at = tC + 4.0 + k * 0.9;
        tl.to(c, { opacity: 1, y: 0, duration: 0.45, ease: "bounce.out" }, at);
        tilt(REPLY_TILT[k]!, at + 0.3);
      });
      tilt(0, tC + 6.9, 0.9, "elastic.out(1, 0.45)");
      tl.to(settle, { opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }, tC + 7.4).to({}, { duration: 1.0 });
    },
    { scope: root, dependencies: [reduced], revertOnUpdate: true },
  );

  const actClass = (extra?: string) => cn(reduced ? "relative" : "absolute inset-0", "flex flex-col items-center justify-center gap-5", extra);
  const hidden = reduced ? undefined : { opacity: 0 };

  return (
    <section
      ref={root}
      data-scene="5"
      data-testid="scene-5"
      data-motion={reduced ? "static" : "animated"}
      aria-labelledby="scene5-heading"
      className={cn("relative flex min-h-[100svh] items-center overflow-hidden bg-oxblood text-cream", className)}
    >
      <div aria-hidden className="bg-jaali-dark pointer-events-none absolute inset-0 opacity-50" />
      <div className="relative z-10 mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-6 py-10 sm:px-10">
        <div className="flex flex-col gap-2">
          <p data-intro className="font-mono text-xs uppercase tracking-[0.2em] text-gold-pale">Scene 5 · The argument</p>
          <h2 data-intro id="scene5-heading" className="max-w-4xl font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl">
            Facts meet precedent, <em className="italic text-gold-pale">and every objection gets a reply.</em>
          </h2>
        </div>

        <div className={cn("relative", reduced ? "flex flex-col gap-16" : "h-[min(66svh,600px)] min-h-[440px]")}>
          {/* Act A: Sutradhar */}
          <div data-act="a" className={actClass()}>
            <p className="font-mono text-2xs uppercase tracking-[0.18em] text-gold-pale">Sutradhar, the conductor, asks each shelf</p>
            <div className="grid w-full max-w-[860px] grid-cols-[1fr_auto_1fr] items-center gap-3 sm:gap-6">
              {(["left", "right"] as const).map((side) => (
                <div key={side} className={cn("flex flex-col justify-between gap-[min(16svh,120px)]", side === "left" ? "items-end" : "items-start")}>
                  {[0, 1].map((row) => {
                    const qi = QUADRANTS.findIndex((x) => x.side === side && x.row === row);
                    const Q = QUADRANTS[qi]!;
                    return (
                      <div key={Q.shelf} data-shelf-label style={{ opacity: reduced ? 1 : 0.55 }} className="relative w-full max-w-[210px] rounded-md border border-gold-leaf/50 bg-oxblood/60 px-3 py-2">
                        <span data-shelf-ring aria-hidden className="pointer-events-none absolute -inset-px rounded-md border-2 border-gold-pale" style={{ opacity: reduced ? 1 : 0 }} />
                        <p className="font-display text-lg font-semibold text-cream">{Q.shelf}</p>
                        <p className="text-xs text-cream/85">{Q.note}</p>
                      </div>
                    );
                  })}
                </div>
              ))}
              <div className="relative aspect-square w-[min(44vw,40svh,360px)]">
                <Wheel24 className="absolute inset-0 h-full w-full" strokeWidth={1.1} lit={reduced ? 24 : undefined} />
                {!reduced ? (
                  <div data-lit-wheel aria-hidden className="pointer-events-none absolute inset-0">
                    <Wheel24 className="h-full w-full [&_[data-part]]:opacity-0" strokeWidth={1.1} lit={24} />
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          {/* Act B: threads and the bridge */}
          <div data-act="b" className={actClass()} style={hidden}>
            <p className="font-mono text-2xs uppercase tracking-[0.18em] text-gold-pale">Gold threads tie each fact to the precedent it rests on</p>
            <div
              className="grid w-full max-w-[900px] grid-cols-[minmax(0,1fr)_14%_minmax(0,1fr)] grid-rows-4"
              style={{ ["--row" as string]: "clamp(50px, 7.4svh, 72px)", gridTemplateRows: "repeat(4, var(--row))" }}
            >
              {FACTS.map((f, i) => (
                <div key={f} data-fact className="col-start-1 flex items-center justify-end py-1" style={{ gridRowStart: i + 1 }}>
                  <p className="flex w-full items-center justify-between gap-2 rounded-md bg-cream px-3 py-1.5 text-sm font-medium leading-tight text-ink">
                    <span>{f}</span>
                    <span aria-hidden className="size-2 shrink-0 rounded-full bg-maroon" />
                  </p>
                </div>
              ))}
              <svg aria-hidden viewBox="0 0 100 4" preserveAspectRatio="none" className="col-start-2 row-span-4 row-start-1 h-full w-full text-gold-pale" fill="none" stroke="currentColor" strokeLinecap="round">
                {FACTS.map((f, i) => {
                  const j = THREAD_TO[i]!;
                  return <path key={f} data-thread d={`M0 ${i + 0.5}C55 ${i + 0.5} 45 ${j + 0.5} 100 ${j + 0.5}`} strokeWidth="2" vectorEffect="non-scaling-stroke" />;
                })}
              </svg>
              {PRECEDENTS.map((p, j) => (
                <div key={p.name} data-prec className="col-start-3 flex items-center py-1" style={{ gridRowStart: j + 1 }}>
                  <p className="flex w-full items-center gap-2 rounded-md bg-cream px-3 py-1.5 leading-tight text-ink">
                    <span aria-hidden className="size-2 shrink-0 rounded-full bg-maroon" />
                    <span className="min-w-0">
                      <span className="block font-display text-[13px] font-semibold">{p.name} <span className="font-mono text-[11px] font-normal text-ink-muted">({p.year})</span></span>
                      <span className="block text-[11px] text-ink-muted">{p.note}</span>
                    </span>
                  </p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
              <span data-bridge className="rounded-md border border-gold-pale px-3 py-1.5 font-mono text-sm text-gold-pale">IPC 420</span>
              <span data-bridge aria-hidden className="flex w-14 flex-col gap-[5px]"><i className="block h-[2px] bg-gold-pale" /><i className="block h-[2px] bg-gold-pale" /></span>
              <span data-bridge className="rounded-md border border-gold-pale bg-gold-pale/10 px-3 py-1.5 font-mono text-sm text-cream">BNS 318(4)</span>
              <span data-bridge className="w-full text-center text-sm text-cream/90 sm:ml-3 sm:w-auto">Cheating, renumbered: older judgments cite one, new FIRs charge the other.</span>
            </div>
          </div>

          {/* Act C: the scales */}
          <div data-act="c" className={actClass()} style={hidden}>
            <p className="font-mono text-2xs uppercase tracking-[0.18em] text-gold-pale">Abhiyojak objects, Vakeel replies</p>
            <Scales reduced={reduced} />
            <p data-settled className="font-display text-xl italic text-gold-pale">The scales settle only when nothing is left unanswered.</p>
          </div>
        </div>
      </div>
    </section>
  );
}

export default Scene5Argument;
