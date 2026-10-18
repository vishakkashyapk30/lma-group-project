"use client";
// Scene 1, We, the People (plan §13.3). The Preamble writes itself (SplitText reveal with calligraphic DrawSVG strokes);
// JUSTICE, LIBERTY, EQUALITY and FRATERNITY stay lit in gold; a 24-spoke wheel turns slowly behind and lights up spoke by
// spoke. Pinned and scrubbed. Reduced motion renders the finished page. Text is real; art is aria-hidden.
import { useRef, type ReactElement } from "react";
import { cn } from "@/lib/utils";
import { registerMotion, SplitText, useGSAP } from "@/lib/motion/register";
import { CalligraphyFlourish } from "../art/Flourish";
import { Wheel24 } from "../art/Wheel24";
import { useSceneReduced } from "../art/useSceneMotion";

export interface Scene1WeThePeopleProps {
  className?: string;
  reducedMotion?: boolean;
}

const IDEALS = [
  { en: "Justice", hi: "न्याय" },
  { en: "Liberty", hi: "स्वतंत्रता" },
  { en: "Equality", hi: "समता" },
  { en: "Fraternity", hi: "बंधुत्व" },
] as const;

function Key({ children }: { children: string }): ReactElement {
  return (
    <span data-key className="font-semibold uppercase tracking-wide text-gold-pale">
      {children}
    </span>
  );
}

export function Scene1WeThePeople({ className, reducedMotion }: Scene1WeThePeopleProps): ReactElement {
  const reduced = useSceneReduced(reducedMotion);
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      if (reduced) return;
      const gsap = registerMotion();
      const el = root.current;
      if (!el) return;
      const heading = el.querySelector<HTMLElement>("[data-heading]");
      const body = el.querySelector<HTMLElement>("[data-preamble]");
      const wheel = el.querySelector<HTMLElement>("[data-wheel]");
      if (!heading || !body || !wheel) return;

      const headSplit = SplitText.create(heading, { type: "chars,words" });
      const bodySplit = SplitText.create(body, { type: "words", aria: "none" });
      const keyWords = bodySplit.words.filter((w) => (w as HTMLElement).closest("[data-key]")) as HTMLElement[];
      const spokes = Array.from(wheel.querySelectorAll<SVGGElement>("[data-spoke]"));
      const strokes = (sel: string) => Array.from(el.querySelectorAll<SVGPathElement>(`${sel} path`));
      const chips = Array.from(el.querySelectorAll<HTMLElement>("[data-ideal]"));
      const small = Array.from(el.querySelectorAll<HTMLElement>("[data-small]"));

      gsap.set(headSplit.chars, { opacity: 0, y: 18 });
      gsap.set(bodySplit.words, { opacity: 0.1 });
      gsap.set(keyWords, { color: "#FBF7EE" });
      gsap.set(chips, { opacity: 0.25, y: 12 });
      gsap.set(small, { opacity: 0, y: 10 });
      gsap.set(spokes, { color: "#B08D57" });

      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: { trigger: el, start: "top top+=56", end: "+=280%", pin: true, scrub: 0.7, anticipatePin: 1 },
      });
      tl.to(wheel, { rotation: 100, duration: 7 }, 0)
        .to(spokes, { color: "#D4B57E", duration: 0.2, stagger: 4.2 / 24 }, 0.6)
        .from(strokes("[data-flourish-top]"), { drawSVG: "0%", duration: 0.9, ease: "power2.inOut", stagger: 0.2 }, 0)
        .to(small, { opacity: 1, y: 0, duration: 0.4, stagger: 0.15 }, 0.2)
        .to(headSplit.chars, { opacity: 1, y: 0, duration: 0.3, stagger: 0.04, ease: "power2.out" }, 0.7)
        .to(bodySplit.words, { opacity: 1, duration: 0.25, stagger: 0.05 }, 1.7)
        .to(keyWords, { color: "#D4B57E", duration: 0.4, stagger: 0.25 }, 4.6)
        .to(keyWords, { scale: 1.07, duration: 0.2, yoyo: true, repeat: 1, stagger: 0.25 }, 4.6)
        .to(chips, { opacity: 1, y: 0, duration: 0.4, stagger: 0.25, ease: "power2.out" }, 4.8)
        .from(strokes("[data-flourish-bottom]"), { drawSVG: "0%", duration: 0.9, ease: "power2.inOut", stagger: 0.2 }, 5.6)
        .to({}, { duration: 0.6 }, 6.4);

      return () => {
        headSplit.revert();
        bodySplit.revert();
      };
    },
    { scope: root, dependencies: [reduced], revertOnUpdate: true },
  );

  return (
    <section
      ref={root}
      id="scene-1"
      data-scene="1"
      data-testid="scene-1"
      data-motion={reduced ? "static" : "animated"}
      aria-labelledby="scene1-heading"
      className={cn("relative flex min-h-[100svh] items-center justify-center overflow-hidden bg-oxblood text-cream", className)}
    >
      <div aria-hidden className="bg-jaali-dark pointer-events-none absolute inset-0 opacity-60" />
      <div aria-hidden className="pointer-events-none absolute left-1/2 top-1/2 w-[min(120vw,125svh)] -translate-x-1/2 -translate-y-1/2 opacity-40">
        <div data-wheel>
          <Wheel24 className="h-auto w-full" lit={reduced ? 24 : 0} strokeWidth={0.9} />
        </div>
      </div>
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgb(var(--rgb-oxblood)/0.88)_30%,transparent_72%)]" />

      <div className="relative z-10 mx-auto flex w-full max-w-4xl flex-col items-center gap-5 px-6 py-16 text-center sm:px-10">
        <p data-small className="font-mono text-xs uppercase tracking-[0.2em] text-gold-pale">
          The Preamble · Constitution of India
        </p>
        <div data-flourish-top aria-hidden className="w-56 sm:w-72">
          <CalligraphyFlourish variant="swash" tone="gold-pale" className="h-auto w-full" />
        </div>
        <p data-small lang="hi" className="font-devanagari text-2xl leading-devanagari text-gold-pale">हम, भारत के लोग</p>
        <h2 id="scene1-heading" data-heading className="font-display text-4xl font-semibold uppercase tracking-[0.04em] text-cream sm:text-5xl lg:text-6xl">
          We, the People of India
        </h2>
        <p data-preamble className="max-w-3xl font-display text-lg leading-[1.7] text-cream/95 sm:text-xl lg:text-[1.4rem]">
          having solemnly resolved to constitute India into a sovereign socialist secular democratic republic and to secure to all its
          citizens: <Key>Justice</Key>, social, economic and political; <Key>Liberty</Key> of thought, expression, belief, faith and
          worship; <Key>Equality</Key> of status and of opportunity; and to promote among them all <Key>Fraternity</Key> assuring the
          dignity of the individual and the unity and integrity of the Nation; in our Constituent Assembly this twenty-sixth day of
          November, 1949, do hereby adopt, enact and give to ourselves this Constitution.
        </p>
        <ul className="mt-2 grid w-full max-w-3xl grid-cols-2 gap-3 sm:grid-cols-4" aria-label="The four ideals">
          {IDEALS.map((i) => (
            <li key={i.en} data-ideal className="flex flex-col items-center gap-0.5 rounded-lg border border-gold-leaf/60 bg-oxblood/70 px-3 py-3">
              <span lang="hi" className="font-devanagari text-xl leading-devanagari text-gold-pale">{i.hi}</span>
              <span className="font-mono text-xs uppercase tracking-[0.16em] text-gold-pale">{i.en}</span>
            </li>
          ))}
        </ul>
        <div data-flourish-bottom aria-hidden className="w-64 sm:w-80">
          <CalligraphyFlourish variant="divider" tone="gold" className="h-auto w-full" />
        </div>
      </div>
    </section>
  );
}

export default Scene1WeThePeople;
