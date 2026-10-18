// Reduced-motion path (plan §13.7): the citizen's journey as seven static frames, each with a caption. No animation, no
// pinning; the frames are real headings and text so a screen reader gets the whole story.
import Link from "next/link";
import type { ReactElement, ReactNode } from "react";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui";
import { cn } from "@/lib/utils";
import { CitizenFigure } from "./art/CitizenFigure";
import { IlluminatedBorder } from "./art/IlluminatedBorder";
import { LadyJustice } from "./art/LadyJustice";
import { Wheel24 } from "./art/Wheel24";

export interface StaticStoryboardProps {
  className?: string;
  /**
   * The pre-hydration copy that rides along in the server markup next to the animated scenes: it carries no test ids so
   * that, until it is dropped, the animated scenes remain the only elements answering to `scene-N`.
   */
  bare?: boolean;
}

interface Frame {
  n: number;
  title: string;
  caption: ReactNode;
  tone: "dark" | "light";
  art: ReactNode;
}

const SHELVES = ["Law", "Case law", "Advocacy", "Case"] as const;

const FRAMES: readonly Frame[] = [
  {
    n: 0,
    title: "Bail is the rule, jail the exception",
    caption: (
      <>
        Krishna Iyer J., <cite className="font-display not-italic">State of Rajasthan v. Balchand</cite> (1977). Vakeel-Sahayak helps bail counsel draft
        applications with every claim tied to a source.
      </>
    ),
    tone: "dark",
    art: <LadyJustice className="h-52 w-auto" tone="gold" held="book" />,
  },
  {
    n: 1,
    title: "We, the People",
    caption: "The Preamble promises Justice, Liberty, Equality and Fraternity. A 24-spoke wheel turns behind them.",
    tone: "dark",
    art: (
      <div className="flex flex-col items-center gap-3">
        <Wheel24 className="h-40 w-40" lit={24} />
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-gold-pale">Justice · Liberty · Equality · Fraternity</p>
      </div>
    ),
  },
  {
    n: 2,
    title: "Arrest (Art. 22)",
    caption: "An arrested person must be produced before a magistrate within 24 hours, excluding the journey, under Article 22(2).",
    tone: "light",
    art: (
      <div className="flex items-end gap-5">
        <CitizenFigure className="h-40 w-auto" />
        <div aria-hidden className="flex h-40 items-stretch gap-2">
          {Array.from({ length: 6 }, (_, i) => (
            <span key={i} className="block w-[3px] bg-maroon" />
          ))}
        </div>
        <p className="pb-2 font-display text-5xl font-semibold text-maroon">24 hrs</p>
      </div>
    ),
  },
  {
    n: 3,
    title: "The wait",
    caption: "Tareekh pe tareekh: date after date. Of people in Indian prisons, 75.8% are undertrials (NCRB, Prison Statistics India 2022).",
    tone: "dark",
    art: (
      <div className="flex flex-col items-center gap-3">
        <p className="font-display text-7xl font-semibold text-gold-pale">75.8%</p>
        <div aria-hidden className="h-3 w-56 overflow-hidden rounded-full bg-cream/15">
          <div className="h-full w-[75.8%] rounded-full bg-gold-pale" />
        </div>
      </div>
    ),
  },
  {
    n: 4,
    title: "The paper storm",
    caption: "Scanned, skewed, stamped and Hindi pages arrive. A clerk stamps each type, such as FIR · Hindi · scanned → OCR, and files it on one of four shelves.",
    tone: "light",
    art: (
      <ul className="grid grid-cols-2 gap-2" aria-label="The four shelves">
        {SHELVES.map((s) => (
          <li key={s} className="rounded-md border border-gold-leaf/70 bg-cream px-4 py-3 font-display text-lg font-semibold text-maroon">{s}</li>
        ))}
      </ul>
    ),
  },
  {
    n: 5,
    title: "The argument",
    caption: "Facts are tied to precedents. IPC 420 and BNS 318(4) are bridged. Objections and replies are weighed until the scales settle.",
    tone: "dark",
    art: (
      <div className="flex flex-col items-center gap-3">
        <Wheel24 className="h-28 w-28" lit={24} />
        <p className="font-mono text-sm text-gold-pale">IPC 420 ══ BNS 318(4)</p>
      </div>
    ),
  },
  {
    n: 6,
    title: "Liberty (Art. 21, 39A)",
    caption: "Article 21 protects life and personal liberty; Article 39A promises equal justice and free legal aid.",
    tone: "light",
    art: (
      <IlluminatedBorder ornamentSize={44} panelClassName="bg-cream" className="w-full max-w-sm" contentClassName="text-center">
        <p className="font-display text-base text-ink">
          No person shall be deprived of his life or personal liberty except according to procedure established by law.
        </p>
        <p className="mt-2 font-mono text-2xs uppercase tracking-wider text-maroon">Article 21</p>
      </IlluminatedBorder>
    ),
  },
];

function Intro({ bare }: { bare: boolean }): ReactElement {
  return (
    <div className="flex flex-col">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-maroon">The journey, in seven frames</p>
      <h1 id="storyboard-heading" className="mt-2 max-w-3xl font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl">
        Bail is the rule, <em className="italic text-maroon">jail the exception.</em>
      </h1>
      <p lang="hi" className="mt-2 font-devanagari-body text-lg leading-devanagari text-ink-soft">ज़मानत नियम है, जेल अपवाद।</p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Button asChild size="lg">
          <Link href="/cases" data-testid={bare ? undefined : "open-case-button"}>Open a case <ArrowRight aria-hidden /></Link>
        </Button>
        <Button asChild size="lg" variant="secondary">
          <Link href="/case/case-0007">Open the sample case</Link>
        </Button>
      </div>
    </div>
  );
}

export function StaticStoryboard({ className, bare = false }: StaticStoryboardProps): ReactElement {
  return (
    <section data-storyboard data-testid={bare ? undefined : "static-storyboard"} aria-labelledby="storyboard-heading" className={cn("bg-parchment text-ink", className)}>
      <div className="mx-auto max-w-[1100px] px-6 py-14 sm:px-10">
        <ol className="grid gap-8 md:grid-cols-2">
          {FRAMES.map((f) => (
            <li key={f.n} data-testid={bare ? undefined : `scene-${f.n}`} data-motion={bare ? undefined : "static"} className={cn(f.n === 0 && "md:col-span-2")}>
              {f.n === 0 ? <div className="mb-8"><Intro bare={bare} /></div> : null}
              <figure className="flex h-full flex-col overflow-hidden rounded-xl border border-gold-leaf/60 bg-cream">
                <div
                  data-storyboard-frame={f.n}
                  className={cn(
                    "flex min-h-[260px] items-center justify-center p-6",
                    f.tone === "dark" ? "bg-oxblood text-cream" : "bg-parchment-deep text-ink",
                  )}
                >
                  {f.art}
                </div>
                <figcaption className="flex flex-1 flex-col gap-1 p-5">
                  <span className="font-mono text-2xs uppercase tracking-[0.18em] text-ink-muted">Frame {f.n + 1} of {FRAMES.length}</span>
                  {f.n === 0 ? null : <h2 className="font-display text-2xl font-semibold text-maroon">{f.title}</h2>}
                  <p data-testid={bare ? undefined : "scene-caption"} className="text-base text-ink-soft">{f.caption}</p>
                </figcaption>
              </figure>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export default StaticStoryboard;
