"use client";
// Scene 4, The paper storm (plan §13.3). Scanned, skewed, stamped and Hindi pages blow in; a Munshi glyph catches each one,
// stamps its type ("FIR · Hindi · scanned → OCR") and files it onto one of four shelves (Law, Case law, Advocacy, Case).
// Scrubbed on a pin. Self-contained for now: <PaperStormStage> below is the inner motif and is the part
// components/agents/MunshiPaperStorm will replace once the shared agent animation exists. The stage contract is data
// attributes: [data-catch] the catch point, [data-glyph] the clerk, [data-doc] / [data-stamp] / [data-chip] per page,
// [data-slot="<shelf>"] the shelf targets. Reduced motion shows the final frame: every page filed.
import { useRef, type ReactElement } from "react";
import { cn } from "@/lib/utils";
import { registerMotion, useGSAP } from "@/lib/motion/register";
import { AgentGlyph } from "@/components/common/AgentGlyph";
import { useSceneReduced } from "../art/useSceneMotion";

export interface Scene4PaperStormProps {
  className?: string;
  reducedMotion?: boolean;
}

type ShelfKey = "law" | "caselaw" | "advocacy" | "case";
type Look = "scan" | "text" | "skew";

interface Doc {
  title: string;
  short: string;
  stamp: string;
  shelf: ShelfKey;
  look: Look;
  hindi?: string;
  tilt: number;
}

const SHELF_LIST: readonly { key: ShelfKey; label: string; note: string }[] = [
  { key: "law", label: "Law", note: "Acts and sections" },
  { key: "caselaw", label: "Case law", note: "Judgments" },
  { key: "advocacy", label: "Advocacy", note: "Formats and practice" },
  { key: "case", label: "Case", note: "This client's papers" },
];

const DOCS: readonly Doc[] = [
  { title: "FIR", short: "FIR", stamp: "FIR · Hindi · scanned → OCR", shelf: "case", look: "scan", hindi: "प्रथम सूचना रिपोर्ट", tilt: -7 },
  { title: "Remand order", short: "Remand order", stamp: "Remand order · English · text layer", shelf: "case", look: "text", tilt: 4 },
  { title: "BNS, Act text", short: "BNS", stamp: "Statute · bilingual · text layer", shelf: "law", look: "text", hindi: "भारतीय न्याय संहिता", tilt: -3 },
  { title: "Arnesh Kumar v. State of Bihar (2014)", short: "Arnesh Kumar", stamp: "Judgment · English · text layer", shelf: "caselaw", look: "text", tilt: 6 },
  { title: "Charge-sheet", short: "Charge-sheet", stamp: "Charge-sheet · Hindi · skewed → OCR", shelf: "case", look: "skew", hindi: "आरोप पत्र", tilt: -9 },
  { title: "Satender Kumar Antil v. CBI (2022)", short: "Antil", stamp: "Judgment · English · text layer", shelf: "caselaw", look: "text", tilt: 3 },
  { title: "Bail application format", short: "Bail format", stamp: "Template · English · text layer", shelf: "advocacy", look: "text", tilt: -5 },
  { title: "Sessions Court bail rejection", short: "Bail rejection", stamp: "Order · English · scanned → OCR", shelf: "case", look: "scan", tilt: 8 },
];

const LINE_WIDTHS = [92, 78, 86, 64, 80, 52] as const;

/** Inner motif: the catch zone (page cards plus the Munshi clerk) and the four shelves. Replaceable by MunshiPaperStorm. */
function PaperStormStage({ reduced }: { reduced: boolean }): ReactElement {
  return (
    <div className="grid items-center gap-8 lg:grid-cols-12 lg:gap-10">
      {/* Catch zone */}
      {!reduced ? (
      <div className="relative flex h-[40svh] min-h-[250px] items-center justify-center lg:col-span-6">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 top-1/2 h-px bg-gradient-to-r from-transparent via-gold-leaf/60 to-transparent" />
        <div data-catch className="relative size-px">
          {DOCS.map((d, i) => (
            <div
              key={d.title}
              data-doc={i}
              aria-hidden
              className={cn(
                "absolute -ml-[115px] -mt-[75px] flex h-[150px] w-[230px] flex-col gap-2 overflow-hidden rounded-[6px] border p-3 shadow-[0_16px_28px_-14px_rgba(35,26,22,0.55)]",
                d.look === "scan" ? "border-ink/30 bg-[#E6DCC6]" : d.look === "skew" ? "border-ink/25 bg-[#EDE3CE]" : "border-gold-leaf/60 bg-cream",
              )}
              style={{ opacity: 0, zIndex: i + 1, transform: `rotate(${d.tilt}deg)` }}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate font-display text-[13px] font-semibold leading-tight text-ink">{d.title}</span>
                <span className="shrink-0 font-mono text-[9px] tracking-wider text-ink-muted">p.{i + 1}</span>
              </div>
              {d.hindi ? (
                <span lang="hi" className="font-devanagari text-[13px] leading-[1.5] text-maroon">{d.hindi}</span>
              ) : null}
              <div className="flex flex-1 flex-col gap-[7px] pt-1">
                {LINE_WIDTHS.slice(0, d.hindi ? 4 : 5).map((w, k) => (
                  <span key={k} className={cn("block h-[3px] rounded-full", d.look === "text" ? "bg-ink/25" : "bg-ink/35")} style={{ width: `${w - (k + i) % 3 * 6}%` }} />
                ))}
              </div>
              {d.look !== "text" ? (
                <span aria-hidden className="pointer-events-none absolute inset-0 opacity-30 [background-image:repeating-linear-gradient(0deg,rgba(35,26,22,0.18)_0_1px,transparent_1px_5px)]" />
              ) : null}
              <span
                data-stamp
                className="absolute bottom-2 right-2 rounded-[3px] border-[1.5px] border-maroon bg-cream/90 px-1.5 py-[3px] font-mono text-[9px] font-medium uppercase tracking-[0.06em] text-maroon"
                style={{ opacity: 0 }}
              >
                {d.stamp}
              </span>
            </div>
          ))}
          <div data-glyph aria-hidden className="absolute left-0 top-0 z-50 flex size-16 -translate-x-1/2 translate-y-[88px] items-center justify-center rounded-full border border-gold-leaf bg-maroon text-cream shadow-lg">
            <AgentGlyph agent="MUNSHI" size={32} />
          </div>
          <p aria-hidden className="absolute left-0 top-0 z-50 w-40 -translate-x-1/2 translate-y-[160px] text-center font-mono text-2xs uppercase tracking-[0.18em] text-ink-muted">Munshi · the clerk</p>
        </div>
      </div>
      ) : (
      <div className="lg:col-span-6">
        <div className="flex items-center gap-4 rounded-lg border border-gold-leaf/60 bg-cream p-4">
          <span className="flex size-14 shrink-0 items-center justify-center rounded-full bg-maroon text-cream">
            <AgentGlyph agent="MUNSHI" size={30} />
          </span>
          <p className="text-base text-ink">
            Munshi reads every page, stamps its type, such as <span className="font-mono text-sm text-maroon">FIR · Hindi · scanned → OCR</span>, and files it on a shelf.
          </p>
        </div>
      </div>
      )}

      {/* Shelves */}
      <ul className="grid grid-cols-2 gap-3 lg:col-span-6" aria-label="The four shelves">
        {SHELF_LIST.map((s) => {
          const filed = DOCS.filter((d) => d.shelf === s.key);
          return (
            <li key={s.key} className="relative flex min-h-[132px] flex-col rounded-lg border border-gold-leaf/70 bg-cream p-3 shadow-[inset_0_-6px_0_-2px_rgba(176,141,87,0.35)]">
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="font-display text-lg font-semibold text-maroon">{s.label}</h3>
                <span className="font-mono text-2xs uppercase tracking-wider text-ink-muted">{filed.length} filed</span>
              </div>
              <p className="text-xs text-ink-muted">{s.note}</p>
              <div data-slot={s.key} className="mt-2 flex flex-1 flex-wrap content-start gap-1.5">
                {filed.map((d) => (
                  <span key={d.title} data-chip={s.key} className="inline-flex items-center gap-1 rounded-sm border border-maroon/40 bg-parchment px-1.5 py-0.5 font-mono text-[10px] text-ink">
                    <span aria-hidden className="size-1.5 rounded-full bg-maroon" />
                    {d.short}
                  </span>
                ))}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function Scene4PaperStorm({ className, reducedMotion }: Scene4PaperStormProps): ReactElement {
  const reduced = useSceneReduced(reducedMotion);
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      if (reduced) return;
      const gsap = registerMotion();
      const el = root.current;
      if (!el) return;
      const q = <T extends Element>(s: string) => Array.from(el.querySelectorAll<T>(s));
      const catchPt = el.querySelector<HTMLElement>("[data-catch]");
      const glyph = el.querySelector<HTMLElement>("[data-glyph]");
      const cards = q<HTMLElement>("[data-doc]");
      const stamps = q<HTMLElement>("[data-stamp]");
      const chips = q<HTMLElement>("[data-chip]");
      const intro = q<HTMLElement>("[data-intro]");
      if (!catchPt || !glyph || cards.length === 0) return;

      const centre = (n: Element) => {
        const r = n.getBoundingClientRect();
        return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
      };
      const delta = (i: number) => {
        const slot = el.querySelector(`[data-slot="${DOCS[i]!.shelf}"]`);
        if (!slot) return { x: 0, y: 0 };
        const a = centre(catchPt);
        const b = centre(slot);
        return { x: b.x - a.x, y: b.y - a.y };
      };

      gsap.set(intro, { opacity: 0, y: 16 });
      gsap.set(chips, { opacity: 0, scale: 0.4 });
      gsap.set(stamps, { opacity: 0 });
      gsap.set(cards, {
        opacity: 0,
        x: (i: number) => 520 + (i % 3) * 70,
        y: (i: number) => -150 + (i % 4) * 70,
        rotation: (i: number) => DOCS[i]!.tilt + (i % 2 ? 38 : -42),
        scale: 1.08,
      });

      const SLOT = 1.5;
      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: { trigger: el, start: "top top+=56", end: "+=360%", pin: true, scrub: 0.7, anticipatePin: 1, invalidateOnRefresh: true },
      });
      tl.to(intro, { opacity: 1, y: 0, duration: 0.5, stagger: 0.12, ease: "power2.out" }, 0);
      cards.forEach((card, i) => {
        const t = 0.5 + i * SLOT;
        tl.to(card, { opacity: 1, x: 0, y: 0, rotation: DOCS[i]!.tilt, scale: 1, duration: 0.5, ease: "power3.out" }, t)
          .to(glyph, { scale: 1.16, duration: 0.1, ease: "power2.out" }, t + 0.5)
          .fromTo(stamps[i]!, { opacity: 0, scale: 1.7, rotation: -14 }, { opacity: 1, scale: 1, rotation: -3, duration: 0.14, ease: "power4.in" }, t + 0.52)
          .to(glyph, { scale: 1, duration: 0.14, ease: "power2.inOut" }, t + 0.62)
          .to(card, { x: () => delta(i).x, y: () => delta(i).y, scale: 0.26, rotation: 0, duration: 0.5, ease: "power2.inOut" }, t + 0.8)
          .to(card, { opacity: 0, duration: 0.12 }, t + 1.2)
          .to(chips.filter((c) => c.dataset.chip === DOCS[i]!.shelf)[DOCS.slice(0, i).filter((d) => d.shelf === DOCS[i]!.shelf).length] ?? [], { opacity: 1, scale: 1, duration: 0.2, ease: "back.out(2)" }, t + 1.15);
      });
      tl.to({}, { duration: 0.8 });
    },
    { scope: root, dependencies: [reduced], revertOnUpdate: true },
  );

  return (
    <section
      ref={root}
      data-scene="4"
      data-testid="scene-4"
      data-motion={reduced ? "static" : "animated"}
      aria-labelledby="scene4-heading"
      className={cn("relative flex min-h-[100svh] items-center overflow-hidden bg-parchment text-ink", className)}
    >
      <div aria-hidden className="bg-jaali jaali-fade-b pointer-events-none absolute inset-0 opacity-50" />
      <div className="relative z-10 mx-auto flex w-full max-w-[1280px] flex-col gap-7 px-6 py-12 sm:px-10">
        <div className="flex flex-col gap-2">
          <p data-intro className="font-mono text-xs uppercase tracking-[0.2em] text-maroon">Scene 4 · The paper storm</p>
          <h2 data-intro id="scene4-heading" className="max-w-3xl font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl">
            Then comes the paper: <em className="italic text-maroon">scanned, skewed, in Hindi.</em>
          </h2>
          <p data-intro className="max-w-2xl text-base text-ink-soft">
            A clerk reads each page, stamps what it is and files it where it belongs, so nothing downstream reasons over a page nobody has read.
          </p>
        </div>
        <PaperStormStage reduced={reduced} />
      </div>
    </section>
  );
}

export default Scene4PaperStorm;
