"use client";
// Scene 0, the hero (plan §13.3). LawStatu layout: a cream half with the headline and one accented phrase, an oxblood panel
// with gold line-art Lady Justice breaking out of its left edge, and a dark stats band. Motif: Nyay ki Devi.
// Motion: the lines draw in (DrawSVG), the blindfold dissolves and the eyes open; then, scrubbed on a short pin, the
// sword morphs into the bound Constitution (MorphSVG). Reduced motion renders the final frame: eyes open, book held.
import Link from "next/link";
import { useRef, type ReactElement } from "react";
import { ArrowRight, Play } from "lucide-react";
import { Button } from "@/components/ui";
import { cn } from "@/lib/utils";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import { CalligraphyFlourish } from "../art/Flourish";
import { LadyJustice } from "../art/LadyJustice";
import { Wheel24 } from "../art/Wheel24";
import { useSceneReduced } from "../art/useSceneMotion";
import { jumpToScene } from "../SceneIndicator";

export interface Scene0HeroProps {
  className?: string;
  reducedMotion?: boolean;
}

const STATS = [
  { value: "75.8%", label: "of people in Indian prisons are undertrials", source: "NCRB, Prison Statistics India 2022" },
  { value: "½", label: "of the maximum sentence served: release on bond (⅓ for a first offender)", source: "BNSS s.479 (CrPC s.436A)" },
  { value: "24 hrs", label: "to produce an arrested person before a magistrate", source: "Constitution of India, Art. 22(2)" },
  { value: "15100", label: "free legal aid helpline, for anyone who cannot afford a lawyer", source: "NALSA" },
] as const;

function watchJourney(): void {
  jumpToScene(1);
}

export function Scene0Hero({ className, reducedMotion }: Scene0HeroProps): ReactElement {
  const reduced = useSceneReduced(reducedMotion);
  const root = useRef<HTMLElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useGSAP(
    () => {
      if (reduced) return;
      const gsap = registerMotion();
      const section = root.current;
      const svg = svgRef.current;
      if (!section || !svg) return;
      const layer = (n: string) => svg.querySelector<SVGGElement>(`[data-layer="${n}"]`);
      const strokes = (n: string) =>
        Array.from(layer(n)?.querySelectorAll<SVGGeometryElement>('path:not([data-part="wash"]), circle:not([fill="currentColor"])') ?? []);
      const part = (n: string, p: string) => layer(n)?.querySelector<SVGElement>(`[data-part="${p}"]`) ?? null;

      const sword = layer("sword");
      const book = layer("book");
      const blindfold = layer("blindfold");
      const eyes = layer("eyes");
      const wash = part("figure", "wash");
      const blade = part("sword", "blade") as SVGPathElement | null;
      const cover = part("book", "cover") as SVGPathElement | null;
      const details = part("book", "details");
      if (!sword || !book || !blindfold || !eyes || !blade || !cover || !details) return;

      // Start frame: blindfolded, sword in hand, nothing drawn.
      gsap.set(sword, { opacity: 1 });
      gsap.set(book, { opacity: 0 });
      gsap.set(details, { opacity: 0 });
      gsap.set(blindfold, { opacity: 1 });
      gsap.set(eyes, { opacity: 0 });
      if (wash) gsap.set(wash, { opacity: 0 });

      const flourish = section.querySelectorAll<SVGPathElement>("[data-hero-flourish] path");
      const reveal = section.querySelectorAll<HTMLElement>("[data-hero-reveal]");
      // A wipe rather than a fade: the text keeps its full colour (and contrast) while it rises into view.
      gsap.set(reveal, { clipPath: "inset(0 0 100% 0)", y: 22 });

      const intro = gsap.timeline({ defaults: { ease: "power2.inOut" } });
      intro
        .to(reveal, { clipPath: "inset(0 0 -12% 0)", y: 0, duration: 0.9, stagger: 0.09, ease: "power3.out", clearProps: "clipPath" }, 0.1)
        .from(strokes("figure"), { drawSVG: "0%", duration: 2.4, stagger: 0.025 }, 0.1)
        .from([...strokes("beam"), ...strokes("scale-left"), ...strokes("scale-right")], { drawSVG: "0%", duration: 1.4, stagger: 0.05 }, 0.7)
        .from(strokes("sword"), { drawSVG: "0%", duration: 1.2, stagger: 0.06 }, 1.1)
        .from(strokes("blindfold"), { drawSVG: "0%", duration: 0.8 }, 1.5)
        .from(flourish, { drawSVG: "0%", duration: 1.1 }, 1.6);
      if (wash) intro.to(wash, { opacity: 1, duration: 1.2, ease: "power1.out" }, 1.8);
      // The blindfold dissolves and the eyes open.
      intro
        .to(blindfold, { opacity: 0, scaleX: 1.12, svgOrigin: "200 106", duration: 1.1, ease: "power2.out" }, 3.0)
        .fromTo(eyes, { opacity: 0, scaleY: 0.1, svgOrigin: "200 107" }, { opacity: 1, scaleY: 1, duration: 0.8, ease: "back.out(2)" }, 3.3);

      // Scrubbed on a short pin: the sword becomes the bound Constitution.
      const hiltParts = [part("sword", "hilt"), part("sword", "fuller")].filter(Boolean) as SVGElement[];
      const scrub = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: { trigger: section, start: "top top+=56", end: "+=90%", pin: true, scrub: 0.6, anticipatePin: 1 },
      });
      scrub
        .to(hiltParts, { opacity: 0, duration: 0.3 }, 0)
        .to(blade, { morphSVG: { shape: cover, shapeIndex: "auto" }, duration: 0.7, ease: "power2.inOut" }, 0.15)
        .set(book, { opacity: 1 }, 0.85)
        .set(sword, { opacity: 0 }, 0.85)
        .to(details, { opacity: 1, duration: 0.25 }, 0.85)
        .from(part("book", "details")?.querySelectorAll("path, circle") ?? [], { drawSVG: "0%", duration: 0.25, stagger: 0.02 }, 0.85);
    },
    { scope: root, dependencies: [reduced], revertOnUpdate: true },
  );

  return (
    <section
      ref={root}
      data-scene="0"
      data-testid="scene-0"
      data-motion={reduced ? "static" : "animated"}
      aria-label="Bail is the rule, jail the exception"
      className={cn("relative flex min-h-[calc(100svh-3.5rem)] flex-col bg-cream text-ink", className)}
    >
      <div className="relative grid flex-1 lg:grid-cols-2">
        {/* Left: cream half */}
        <div className="relative z-10 flex flex-col justify-center gap-7 px-6 pb-12 pt-14 sm:px-10 lg:py-12 lg:pl-[max(2.5rem,calc((100vw-1280px)/2))] lg:pr-16">
          <p data-hero-reveal className="font-mono text-xs uppercase tracking-[0.18em] text-maroon">
            <span lang="hi" className="font-devanagari normal-case tracking-normal">वकील सहायक</span>
            <span aria-hidden className="mx-2 text-gold-leaf">·</span>
            Drafting assistant for bail counsel
          </p>
          <h1 data-hero-reveal className="font-display text-5xl font-semibold leading-[1.02] tracking-tight text-ink sm:text-6xl lg:text-[4.6rem]">
            Bail is the rule,{" "}
            <span className="relative inline-block">
              <em className="italic text-maroon">jail the exception.</em>
              <span data-hero-flourish aria-hidden className="absolute -bottom-3 left-0 block h-3 w-full">
                <CalligraphyFlourish variant="underline" tone="gold" strokeWidth={2} className="h-full w-full" />
              </span>
            </span>
          </h1>
          <figure data-hero-reveal className="flex flex-col gap-1">
            <p lang="hi" className="font-devanagari-body text-lg leading-devanagari text-ink-soft">ज़मानत नियम है, जेल अपवाद।</p>
            <figcaption className="text-sm text-ink-muted">
              Krishna Iyer J., <cite className="font-display not-italic">State of Rajasthan v. Balchand</cite> (1977)
            </figcaption>
          </figure>
          <p data-hero-reveal className="max-w-xl text-lg leading-relaxed text-ink-soft">
            Upload the FIR and the case papers. Vakeel-Sahayak reads them, checks your client&rsquo;s bail rights against the dates, and
            drafts the application for you to review, every line traced to its source.
          </p>
          <div data-hero-reveal className="flex flex-wrap items-center gap-x-6 gap-y-4">
            <Button asChild size="lg" className="rounded-pill px-8">
              <Link href="/cases" data-testid="open-case-button">
                Open a case
                <ArrowRight aria-hidden />
              </Link>
            </Button>
            <div className="flex items-center gap-3">
              <Button asChild variant="play" size="round">
                {/* A real link to scene 1: it works even before the page has hydrated, and smooth-scrolls once it has. */}
                <a
                  href="#scene-1"
                  aria-label="Watch the journey"
                  title="Watch the journey"
                  data-testid="watch-journey-button"
                  onClick={(e) => {
                    e.preventDefault();
                    watchJourney();
                  }}
                >
                  <Play aria-hidden="true" className="translate-x-[1px] fill-current" />
                </a>
              </Button>
              <button
                type="button"
                tabIndex={-1}
                aria-hidden
                onClick={watchJourney}
                className="rounded-pill px-1 text-base font-semibold text-maroon underline-offset-4 hover:underline"
              >
                Watch the journey
              </button>
            </div>
          </div>
          <p data-hero-reveal className="max-w-md border-l-2 border-gold-leaf pl-4 text-sm leading-relaxed text-ink-muted">
            Not a lawyer? If you or someone you know is held and cannot afford one, free legal aid is a right. Call{" "}
            <a href="tel:15100" className="font-semibold text-maroon underline underline-offset-4">NALSA 15100</a>.
          </p>
        </div>

        {/* Right: oxblood panel, Lady Justice breaking out of its left edge */}
        <div className="relative z-20 min-h-[540px] bg-oxblood lg:min-h-0">
          <div aria-hidden className="absolute inset-0 overflow-hidden">
            <div className="bg-jaali-dark absolute inset-0 opacity-70" />
            <div className="absolute -right-24 -top-24 w-[34rem] opacity-30">
              <Wheel24 className="h-auto w-full" tone="gold" />
            </div>
            <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-oxblood to-transparent" />
          </div>
          <div className="pointer-events-none absolute bottom-[-2.25rem] left-1/2 z-30 h-[104%] -translate-x-1/2 lg:left-0 lg:-translate-x-[14%]">
            <LadyJustice svgRef={svgRef} tone="gold" strokeWidth={1.9} className="h-full w-auto" />
          </div>
          <div className="relative z-10 flex h-full flex-col justify-between gap-10 p-8 pt-12 lg:ml-[46%] lg:p-10 lg:pt-16">
            <div data-hero-reveal className="max-w-[16rem]">
              <p lang="hi" className="font-devanagari text-4xl leading-devanagari text-gold-pale">न्याय की देवी</p>
              <p className="mt-1 font-display text-xl italic text-cream">Nyay ki Devi</p>
              <p className="mt-4 text-sm leading-relaxed text-cream/80">
                Eyes open. The Constitution where the sword was. The scales, kept.
              </p>
            </div>
            <p data-hero-reveal lang="hi" className="font-devanagari text-lg leading-devanagari text-gold-pale lg:text-right">
              यतो धर्मस्ततो जयः
            </p>
          </div>
        </div>
      </div>

      {/* Stats band */}
      <div data-testid="stats-band" className="relative z-10 border-t border-gold-leaf/50 bg-oxblood text-cream">
        <dl className="mx-auto grid max-w-[1400px] grid-cols-2 gap-x-8 gap-y-6 px-6 py-7 sm:px-10 lg:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.value} className="flex flex-col gap-1 border-gold-leaf/30 lg:border-l lg:pl-6 lg:first:border-l-0 lg:first:pl-0">
              <dt className="font-display text-4xl font-semibold leading-none text-gold-pale">{s.value}</dt>
              <dd className="text-sm leading-snug text-cream/90">{s.label}</dd>
              <dd className="font-mono text-2xs uppercase tracking-wider text-gold-pale/80">{s.source}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

export default Scene0Hero;
