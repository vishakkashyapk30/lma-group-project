"use client";
// Hero product loop: one run of about 8.5 s that shows the product working, then rests on its final frame.
// Case file arrives, facts appear and one source quote is highlighted, a "Needs your check" item is resolved, a draft
// with numbered sources appears, then "Approved for export". Built from the real status component. Pure CSS keyframes
// (styles/landing.css): every element rests in its final state, so reduced motion shows that frame with no animation.
// Replay remounts the panel. The run is paused while the tab is hidden.
import { useEffect, useRef, useState, type CSSProperties, type ReactElement } from "react";
import { FileText } from "lucide-react";
import { Logo } from "@/components/common/Logo";
import { StatusBadge } from "@/components/common/StatusBadge";

const t = (d: number, o?: number): CSSProperties => ({ "--d": `${d}s`, ...(o !== undefined ? { "--o": `${o}s` } : {}) }) as CSSProperties;

function Check({ className, style }: { className?: string; style?: CSSProperties }): ReactElement {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden className={className} style={style}>
      <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Sup({ n }: { n: number }): ReactElement {
  return <sup className="ml-0.5 font-mono text-[10px] font-medium text-indigo">[{n}]</sup>;
}

export function HeroLoop({ className }: { className?: string }): ReactElement {
  const [run, setRun] = useState(0);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onVis = () => {
      if (root.current) root.current.dataset.paused = String(document.hidden);
    };
    document.addEventListener("visibilitychange", onVis);
    onVis();
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  return (
    <div className={className}>
      <div ref={root} className="hl-root relative">
        <div aria-hidden className="absolute inset-0 translate-x-3 translate-y-3 rounded-lg bg-saffron sm:translate-x-4 sm:translate-y-4" />
        <div
          key={run}
          role="img"
          aria-label="Product preview: a case file arrives, each fact is checked against its source, one item is resolved by counsel, a draft with numbered sources appears, and the application is approved for export."
          className="relative overflow-hidden rounded-lg border border-line-strong/40 bg-cream"
        >
          <div aria-hidden>
            <div className="flex items-center gap-3 border-b border-line bg-parchment px-4 py-2.5">
              <Logo markOnly />
              <p className="truncate text-sm text-ink-soft">Cases <span className="px-1 text-ink-muted">/</span> <span className="font-semibold text-ink">State v. Accused-1, FIR 112/2024</span></p>
            </div>

            <div className="grid md:grid-cols-[2fr_3fr]">
              {/* Case file */}
              <div className="min-w-0 border-b border-line bg-parchment p-4 md:border-b-0 md:border-r">
                <p className="mb-2 text-sm font-semibold text-ink">Case file</p>
                <div className="hl-slide rounded-md border border-line bg-cream p-3" style={t(0.4)}>
                  <p className="flex items-center gap-1.5 text-[13px] font-medium text-ink"><FileText className="size-3.5 text-indigo" /> FIR 112/2024 <span className="font-normal text-ink-muted">3 pages</span></p>
                  <p className="doc-text mt-2 text-[13px] leading-[1.55]">
                    …the accused was arrested on <span className="hl-mark" style={t(3.4)}>14.08.2024 at 6.40 pm</span> near the bus stand and taken to the police station…
                  </p>
                  <p className="mt-1.5 font-mono text-[11px] text-ink-muted">FIR p.1</p>
                </div>
                <div className="hl-slide mt-2 rounded-md border border-line bg-cream p-3" style={t(0.75)}>
                  <p className="flex items-center gap-1.5 text-[13px] font-medium text-ink"><FileText className="size-3.5 text-indigo" /> Remand order <span className="font-normal text-ink-muted">2 pages</span></p>
                </div>
              </div>

              {/* Dossier and draft */}
              <div className="min-w-0 p-4">
                <p className="hl-fade mb-1 text-sm font-semibold text-ink" style={t(1.9)}>Dossier</p>
                <ul className="text-[13px]">
                  <li className="hl-rise grid grid-cols-[1fr_auto] items-center gap-3 border-b border-line/70 py-2" style={t(2.1)}>
                    <div><span className="text-ink-soft">FIR number</span> <span className="ml-1 font-medium text-ink">112/2024, PS-1</span></div>
                    <StatusBadge status="VERIFIED" kind="field" label="Confirmed" size="sm" testId="loop-status" />
                  </li>
                  <li className="hl-rise grid grid-cols-[1fr_auto] items-center gap-3 border-b border-line/70 py-2" style={t(2.4)}>
                    <div><span className="text-ink-soft">Date of arrest</span> <span className="ml-1 font-medium text-ink">14.08.2024</span> <span className="ml-1 rounded-sm bg-indigo-tint px-1 py-0.5 font-mono text-[11px] text-indigo">FIR p.1</span></div>
                    <StatusBadge status="VERIFIED" kind="field" label="Confirmed" size="sm" testId="loop-status" />
                  </li>
                  <li className="hl-rise grid grid-cols-[1fr_auto] items-center gap-3 border-b border-line/70 py-2" style={t(2.7)}>
                    <div><span className="text-ink-soft">Days in custody</span> <span className="ml-1 font-medium text-ink">63</span></div>
                    <StatusBadge status="COMPUTED" kind="field" label="Calculated" size="sm" testId="loop-status" />
                  </li>
                  <li className="hl-rise relative grid grid-cols-[1fr_auto] items-center gap-3 border-b border-line/70 py-2" style={t(3.0)}>
                    <span aria-hidden className="hl-leave absolute inset-x-[-0.5rem] inset-y-0 bg-saffron-wash" style={t(0, 5.3)} />
                    <div className="relative"><span className="text-ink-soft">Antecedents</span> <span className="ml-1 font-medium text-ink">Two cases, documents differ</span></div>
                    <div className="relative grid justify-items-end">
                      <span className="hl-leave [grid-area:1/1]" style={t(0, 5.3)}><StatusBadge status="AMBIGUOUS" kind="field" label="Needs your check" size="sm" className="!text-saffron-ink" testId="loop-status" /></span>
                      <span className="hl-fade [grid-area:1/1]" style={t(5.45)}><StatusBadge status="VERIFIED" kind="field" label="Confirmed by you" size="sm" testId="loop-status" /></span>
                    </div>
                  </li>
                </ul>

                <div className="hl-rise mt-3" style={t(6.1)}>
                  <p className="mb-1 text-sm font-semibold text-ink">Draft application</p>
                  <p className="doc-text text-[13.5px] leading-[1.55]">
                    <span className="hl-fade" style={t(6.2)}>The applicant was arrested on 14.08.2024 and has been in custody for 63 days<Sup n={1} />.</span>{" "}
                    <span className="hl-fade" style={t(6.7)}>The remand order records no charge sheet date<Sup n={2} />.</span>
                  </p>
                  <p className="hl-fade mt-1.5 font-mono text-[11px] text-ink-muted" style={t(7.2)}>[1] FIR p.1 &nbsp; [2] Remand order p.1</p>
                </div>
              </div>
            </div>

            {/* Status strip: one phase at a time, ending on the approval */}
            <div className="relative grid border-t border-line text-[13px]">
              <span aria-hidden className="hl-fade bg-neem-tint [grid-area:1/1]" style={t(8.3)} />
              <p className="hl-phase px-4 py-2.5 text-ink-soft [grid-area:1/1]" style={t(0.4, 1.9)}>Reading the papers</p>
              <p className="hl-phase px-4 py-2.5 text-ink-soft [grid-area:1/1]" style={t(1.9, 5.4)}>Checking each fact against its source</p>
              <p className="hl-phase px-4 py-2.5 text-ink-soft [grid-area:1/1]" style={t(5.4, 8.3)}>Drafting the application</p>
              <p className="hl-fade hl-final flex items-center gap-1.5 px-4 py-2.5 font-medium text-neem-deep [grid-area:1/1]" style={t(8.3)}>
                <Check className="hl-check" style={t(8.45)} /> Approved for export
              </p>
            </div>
          </div>
        </div>
      </div>
      <div className="mt-6 flex justify-end pr-1">
        <button type="button" onClick={() => setRun((n) => n + 1)} className="hl-replay link-draw rounded-sm text-sm text-ink-soft hover:text-maroon">
          Replay
        </button>
      </div>
    </div>
  );
}
