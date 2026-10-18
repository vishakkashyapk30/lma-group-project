"use client";
// Scene 6, Liberty (Art. 21, 39A) (plan §13.3). The bars lift and become the ruled lines of a manuscript page inside an
// illuminated border; Article 21 inks itself word by word, then Article 39A (real text); then the page expands into the
// case workspace (a FLIP: the workspace starts at the page's rectangle and animates to full size) as the call to action,
// linking to /case/case-0007 and /cases. Pinned and scrubbed. Reduced motion shows the final frame: the page, inked,
// with the call to action beneath it.
import Link from "next/link";
import { useRef, type ReactElement } from "react";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui";
import { cn } from "@/lib/utils";
import { registerMotion, SplitText, useGSAP } from "@/lib/motion/register";
import { IlluminatedBorder } from "../art/IlluminatedBorder";
import { useSceneReduced } from "../art/useSceneMotion";

export interface Scene6LibertyProps {
  className?: string;
  reducedMotion?: boolean;
}

const BARS = 14;
const BAR_PX = 100;
const RULE_OFFSET = 0.74; // baseline position inside a line box, as a fraction of the step
const STAGES = ["I", "II", "III", "IV", "V", "VI", "VII"] as const;

const ART21 = "No person shall be deprived of his life or personal liberty except according to procedure established by law.";
const ART21_HI = "किसी व्यक्ति को उसके प्राण या दैहिक स्वतंत्रता से विधि द्वारा स्थापित प्रक्रिया के अनुसार ही वंचित किया जाएगा, अन्यथा नहीं।";
const ART39A =
  "The State shall secure that the operation of the legal system promotes justice, on a basis of equal opportunity, and shall, in particular, provide free legal aid, by suitable legislation or schemes or in any other way, to ensure that opportunities for securing justice are not denied to any citizen by reason of economic or other disabilities.";

function WorkspaceBackdrop(): ReactElement {
  return (
    <div aria-hidden className="absolute inset-0 flex flex-col overflow-hidden bg-parchment">
      <div data-ws-content className="flex h-11 shrink-0 items-center justify-between bg-maroon px-4 text-cream">
        <span className="font-display text-sm font-semibold">Vakeel-Sahayak</span>
        <span className="hidden gap-4 font-sans text-xs sm:flex"><span>Cause list</span><span>Desk</span><span>Library</span></span>
      </div>
      <div data-ws-content className="flex shrink-0 items-center gap-2 border-b border-gold-leaf/50 bg-cream px-4 py-2">
        {STAGES.map((s, i) => (
          <span key={s} className={cn("flex items-center gap-1 rounded-sm px-2 py-0.5 font-display text-xs", i === 3 ? "bg-maroon text-cream" : "text-ink-muted")}>
            {s}
            {i === 1 || i === 6 ? <span className="text-[8px]">◆</span> : null}
          </span>
        ))}
      </div>
      <div data-ws-content className="grid flex-1 grid-cols-12 gap-3 p-3">
        {[
          { c: "col-span-3", t: "Case file", rows: [88, 72, 80, 60, 76] },
          { c: "col-span-5", t: "Chat", rows: [90, 64, 84, 70, 52, 78] },
          { c: "col-span-4", t: "Dossier · Brief", rows: [82, 66, 74, 58, 80] },
        ].map((p) => (
          <div key={p.t} className={cn(p.c, "flex flex-col gap-3 rounded-md border border-gold-leaf/50 bg-cream p-3")}>
            <span className="font-mono text-[10px] uppercase tracking-wider text-maroon">{p.t}</span>
            {p.rows.map((w, k) => (
              <span key={k} className="block h-[3px] rounded-full bg-ink/20" style={{ width: `${w}%` }} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function CallToAction({ className }: { className?: string }): ReactElement {
  return (
    <div className={cn("mx-auto flex max-w-xl flex-col items-center gap-4 rounded-xl border border-gold-leaf/70 bg-cream/95 px-6 py-7 text-center shadow-[0_24px_60px_-24px_rgba(74,14,23,0.55)]", className)}>
      <h2 className="font-display text-3xl font-semibold leading-tight tracking-tight text-ink sm:text-4xl">
        Equal justice starts with <em className="italic text-maroon">the file in order.</em>
      </h2>
      <p className="max-w-md text-base text-ink-soft">
        Open the sample case and watch the clerk, the conductor and the drafters work, with every claim tied to a source.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button asChild size="lg">
          <Link href="/case/case-0007">Open the sample case <ArrowRight aria-hidden /></Link>
        </Button>
        <Button asChild size="lg" variant="secondary">
          <Link href="/cases">Go to the cause list</Link>
        </Button>
      </div>
      <p className="font-mono text-xs text-ink-muted">AI-generated drafts for counsel. Not legal advice.</p>
    </div>
  );
}

export function Scene6Liberty({ className, reducedMotion }: Scene6LibertyProps): ReactElement {
  const reduced = useSceneReduced(reducedMotion);
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      if (reduced) return;
      const gsap = registerMotion();
      const el = root.current;
      if (!el) return;
      const q = <T extends Element>(s: string) => Array.from(el.querySelectorAll<T>(s));
      const page = el.querySelector<HTMLElement>("[data-page]");
      const ruled = el.querySelector<HTMLElement>("[data-ruled]");
      const frame = el.querySelector<HTMLElement>("[data-frame]");
      const ws = el.querySelector<HTMLElement>("[data-workspace]");
      const cta = el.querySelector<HTMLElement>("[data-cta]");
      const bars = q<HTMLElement>("[data-bar]");
      const draws = q<SVGPathElement>("[data-frame] [data-draw]");
      const wsContent = q<HTMLElement>("[data-ws-content]");
      const intro = q<HTMLElement>("[data-intro]");
      const a21 = q<HTMLElement>("[data-ink='21']");
      const a39 = q<HTMLElement>("[data-ink='39a']");
      const fades = q<HTMLElement>("[data-ink-fade]");
      if (!page || !ruled || !frame || !ws || !cta) return;

      const s21 = a21.map((n) => SplitText.create(n, { type: "words", aria: "none" }));
      const s39 = a39.map((n) => SplitText.create(n, { type: "words", aria: "none" }));
      const splits = [...s21, ...s39];
      const w21 = s21.flatMap((s) => s.words as HTMLElement[]);
      const w39 = s39.flatMap((s) => s.words as HTMLElement[]);

      const centre = (n: Element) => {
        const r = n.getBoundingClientRect();
        return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height, top: r.top };
      };
      const step = () => parseFloat(getComputedStyle(ruled).lineHeight) || 30;
      const lineY = (i: number) => centre(ruled).top + i * step() + step() * RULE_OFFSET - centre(el).y;
      const rowGap = () => Math.min(centre(el).w * 0.7, 900) / BARS;
      const rowY = () => centre(el).h * 0.3;
      const barH = () => centre(el).h * 0.34;

      gsap.set(bars, {
        opacity: 1,
        x: (i: number) => (i - (BARS - 1) / 2) * rowGap(),
        y: () => rowY(),
        scaleY: () => barH() / BAR_PX,
        scaleX: 1,
        rotation: 0,
      });
      gsap.set(frame, { opacity: 0, scale: 0.97 });
      gsap.set(draws, { drawSVG: "0%" });
      gsap.set([...w21, ...w39], { opacity: 0, y: 5 });
      gsap.set(fades, { opacity: 0 });
      gsap.set(intro, { opacity: 0, y: 14 });
      gsap.set(ws, { opacity: 0, transformOrigin: "50% 50%" });
      gsap.set(wsContent, { opacity: 0 });
      gsap.set(cta, { autoAlpha: 0, y: 24 });

      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: { trigger: el, start: "top top+=56", end: "+=520%", pin: true, scrub: 0.7, anticipatePin: 1, invalidateOnRefresh: true },
      });
      tl.to(intro, { opacity: 1, y: 0, duration: 0.5, stagger: 0.12, ease: "power2.out" }, 0)
        // the bars lift and lie down as ruled lines
        .to(bars, {
          x: 0,
          y: (i: number) => lineY(i),
          rotation: 90,
          scaleY: () => ruled.getBoundingClientRect().width / BAR_PX,
          scaleX: 0.4,
          opacity: 0.5,
          duration: 1.0,
          ease: "power3.inOut",
          stagger: 0.05,
        }, 0.7)
        .to(frame, { opacity: 1, scale: 1, duration: 0.7, ease: "power2.out" }, 1.6)
        .to(draws, { drawSVG: "100%", duration: 0.9, ease: "power2.inOut", stagger: 0.04 }, 1.7)
        .to(fades, { opacity: 1, duration: 0.4, stagger: 0.2 }, 2.4)
        // Article 21 inks itself, then 39A
        .to(w21, { opacity: 1, y: 0, duration: 0.2, stagger: 0.06, ease: "power2.out" }, 2.8)
        .to(w39, { opacity: 1, y: 0, duration: 0.2, stagger: 0.035, ease: "power2.out" }, 5.2)
        // FLIP: the workspace starts as the page's rectangle and grows to fill the stage
        .fromTo(
          ws,
          {
            x: () => centre(page).x - centre(el).x,
            y: () => centre(page).y - centre(el).y,
            scaleX: () => centre(page).w / centre(el).w,
            scaleY: () => centre(page).h / centre(el).h,
            opacity: 0,
          },
          { x: 0, y: 0, scaleX: 1, scaleY: 1, opacity: 1, duration: 1.3, ease: "power3.inOut", immediateRender: false },
          8.2,
        )
        .to([page, ...bars], { opacity: 0, duration: 0.6 }, 8.6)
        .to(wsContent, { opacity: 1, duration: 0.5, stagger: 0.1 }, 9.3)
        .to(cta, { autoAlpha: 1, y: 0, duration: 0.6, ease: "power2.out" }, 9.7)
        .to({}, { duration: 1.2 });

      return () => {
        splits.forEach((s) => s.revert());
      };
    },
    { scope: root, dependencies: [reduced], revertOnUpdate: true },
  );

  return (
    <section
      ref={root}
      data-scene="6"
      data-testid="scene-6"
      data-motion={reduced ? "static" : "animated"}
      aria-labelledby={reduced ? "scene6-heading" : undefined}
      aria-label={reduced ? undefined : "Liberty: Articles 21 and 39A"}
      className={cn(
        "relative overflow-hidden bg-parchment text-ink",
        reduced ? "py-16" : "flex min-h-[calc(100svh-3.5rem)] items-center justify-center",
        className,
      )}
    >
      <div aria-hidden className="bg-jaali jaali-fade-b pointer-events-none absolute inset-0 opacity-40" />

      {/* Ruled lines: the bars (animated path only; reduced motion draws them with CSS) */}
      {!reduced ? (
        <div aria-hidden className="pointer-events-none absolute inset-0 z-[15]">
          {Array.from({ length: BARS }, (_, i) => (
            <span
              key={i}
              data-bar
              className="absolute left-1/2 top-1/2 -ml-[1.5px] -mt-[50px] block w-[3px] rounded-sm bg-maroon"
              style={{ height: BAR_PX, opacity: 1 }}
            />
          ))}
        </div>
      ) : null}

      <div className="relative z-10 mx-auto flex w-full max-w-[860px] flex-col items-center gap-3 px-5 py-6">
        <p data-intro className="font-mono text-xs uppercase tracking-[0.2em] text-maroon">Scene 6 · Liberty</p>
        <div data-page className="w-full">
          <div data-frame>
            <IlluminatedBorder
              ornamentSize={56}
              panelClassName="bg-cream"
              header={<span className="font-mono text-2xs uppercase tracking-[0.2em] text-maroon">The Constitution of India</span>}
              footer={<span className="font-mono text-2xs uppercase tracking-[0.2em] text-ink-muted">Part III · Part IV</span>}
            >
              <div
                data-ruled
                className={cn(
                  "[--step:clamp(24px,4.2svh,32px)] text-[clamp(15px,2.3svh,20px)] leading-[var(--step)]",
                  reduced && "[background-image:repeating-linear-gradient(to_bottom,transparent_0,transparent_calc(var(--step)*0.74),rgba(122,22,38,0.28)_calc(var(--step)*0.74),rgba(122,22,38,0.28)_calc(var(--step)*0.74+1px),transparent_calc(var(--step)*0.74+1px),transparent_var(--step))]",
                )}
              >
                <h3 data-ink-fade className="font-display font-semibold leading-[var(--step)] text-maroon">
                  Article 21 <span className="font-sans text-[0.75em] font-normal text-ink-muted">Protection of life and personal liberty</span>
                </h3>
                <p data-ink="21" className="font-display leading-[var(--step)] text-ink">{ART21}</p>
                <p lang="hi" data-ink-fade className="font-devanagari-body leading-[var(--step)] text-ink-soft">{ART21_HI}</p>
                <h3 id={reduced ? "scene6-heading" : undefined} data-ink-fade className="mt-[var(--step)] font-display font-semibold leading-[var(--step)] text-maroon">
                  Article 39A <span className="font-sans text-[0.75em] font-normal text-ink-muted">Equal justice and free legal aid</span>
                </h3>
                <p data-ink="39a" className="font-display leading-[var(--step)] text-ink">{ART39A}</p>
              </div>
            </IlluminatedBorder>
          </div>
        </div>
        {reduced ? <CallToAction className="mt-10" /> : null}
      </div>

      {!reduced ? (
        <>
          <div data-workspace className="absolute inset-0 z-20 border-y border-gold-leaf/60">
            <WorkspaceBackdrop />
          </div>
          <div data-cta className="absolute inset-0 z-30 flex items-center justify-center px-5">
            <CallToAction />
          </div>
        </>
      ) : null}
    </section>
  );
}

export default Scene6Liberty;
