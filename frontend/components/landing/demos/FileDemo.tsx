"use client";
// Hero demo: put the FIR of the sample case on the file and see what Munshi and Peshkar make of it. Drag the FIR card
// onto the dossier (mouse, touch or pen) or press "Add this FIR" (keyboard). The card follows the pointer, resists past
// the edge of the demo, and on release either snaps into the dossier or springs home with its velocity. Then the page
// strip and the facts appear: what the FIR gives with its page, and what it does not give, said plainly.
import { FileText, GripVertical } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { AnimatePresence, m, MotionProvider, usePresenceTransition } from "@/components/motion/MotionProvider";
import { Button } from "@/components/ui/button";
import { ALLOWANCE, SPRINGS, SpringValue, prefersReducedMotion, project, rubberClamp, useDrag2D } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { FIR_DOC, FIR_FACTS } from "../sample";

function within(r: DOMRect, x: number, y: number, pad = 24): boolean {
  return x >= r.left - pad && x <= r.right + pad && y >= r.top - pad && y <= r.bottom + pad;
}

export function FileDemo({ className }: { className?: string }): ReactElement {
  const tr = usePresenceTransition();
  const [added, setAdded] = useState(false);
  const [over, setOver] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const card = useRef<HTMLDivElement>(null);
  const target = useRef<HTMLDivElement>(null);
  const pos = useRef<{ x: SpringValue; y: SpringValue } | null>(null);
  const base = useRef({ x: 0, y: 0 });
  const bounds = useRef({ minX: 0, maxX: 0, minY: 0, maxY: 0 });
  const xy = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const write = () => {
      const el = card.current;
      if (!el) return;
      const { x, y } = xy.current;
      el.style.transform = x === 0 && y === 0 ? "" : `translate(${x}px, ${y}px)`;
    };
    pos.current = {
      x: new SpringValue(0, (v) => { xy.current.x = v; write(); }),
      y: new SpringValue(0, (v) => { xy.current.y = v; write(); }),
    };
    return () => {
      pos.current?.x.stop();
      pos.current?.y.stop();
    };
  }, [added]);

  const file = useCallback(() => {
    setAdded(true);
    setOver(false);
  }, []);

  useDrag2D(card, {
    enabled: !added,
    onStart: () => {
      const p = pos.current;
      const el = card.current;
      const r = root.current?.getBoundingClientRect();
      if (!p || !el || !r) return;
      p.x.stop();
      p.y.stop();
      base.current = { x: p.x.value, y: p.y.value };
      const c = el.getBoundingClientRect();
      // How far the card may travel and stay inside the demo (from its resting place).
      const restLeft = c.left - p.x.value;
      const restTop = c.top - p.y.value;
      bounds.current = { minX: r.left - restLeft, maxX: r.right - c.width - restLeft, minY: r.top - restTop, maxY: r.bottom - c.height - restTop };
      el.dataset.lifted = "true";
    },
    onMove: (dx, dy) => {
      const p = pos.current;
      if (!p) return;
      const b = bounds.current;
      const reduced = prefersReducedMotion();
      const rx = base.current.x + dx;
      const ry = base.current.y + dy;
      p.x.set(reduced ? Math.min(b.maxX, Math.max(b.minX, rx)) : rubberClamp(rx, b.minX, b.maxX, ALLOWANCE.demo));
      p.y.set(reduced ? Math.min(b.maxY, Math.max(b.minY, ry)) : rubberClamp(ry, b.minY, b.maxY, ALLOWANCE.demo));
      const c = card.current!.getBoundingClientRect();
      const t = target.current?.getBoundingClientRect();
      setOver(Boolean(t && within(t, c.left + c.width / 2, c.top + c.height / 2)));
    },
    onEnd: ({ vx, vy }) => {
      const p = pos.current;
      const el = card.current;
      const t = target.current?.getBoundingClientRect();
      if (!p || !el || !t) return;
      delete el.dataset.lifted;
      const reduced = prefersReducedMotion();
      const c = el.getBoundingClientRect();
      const cx = c.left + c.width / 2;
      const cy = c.top + c.height / 2;
      // Dropped on the dossier, or thrown at it: either way it goes in.
      const hit = within(t, cx, cy) || within(t, cx + project(vx, 0.99), cy + project(vy, 0.99), 0);
      if (hit) {
        const tx = p.x.value + (t.left + t.width / 2 - cx);
        const ty = p.y.value + (t.top + Math.min(t.height / 2, 60) - cy);
        let done = 0;
        const rest = () => (done += 1) === 2 && file();
        p.x.to(tx, { spring: SPRINGS.demo, velocity: vx, reduced, onRest: rest });
        p.y.to(ty, { spring: SPRINGS.demo, velocity: vy, reduced, onRest: rest });
      } else {
        setOver(false);
        p.x.to(0, { spring: SPRINGS.demo, velocity: vx, reduced });
        p.y.to(0, { spring: SPRINGS.demo, velocity: vy, reduced });
      }
    },
  });

  const found = FIR_FACTS.filter((r) => r.status === "VERIFIED").length;
  const missing = FIR_FACTS.length - found;

  return (
    <MotionProvider>
      <div ref={root} data-testid="file-demo" data-added={added || undefined} className={cn("relative rounded-lg border border-line-strong/40 bg-cream", className)}>
        <div className="grid sm:grid-cols-[minmax(0,12.5rem)_minmax(0,1fr)]">
          <div className="border-b border-line bg-parchment p-4 sm:border-b-0 sm:border-r">
            <p className="text-sm font-semibold text-ink">Papers</p>
            {added ? (
              <p className="mt-3 text-sm text-ink-soft">The FIR is on the file.</p>
            ) : (
              <>
                <div
                  ref={card}
                  data-testid="fir-card"
                  className="relative z-raised mt-3 cursor-grab touch-none select-none rounded-md border border-line bg-cream p-3 data-[lifted=true]:cursor-grabbing data-[lifted=true]:shadow-lg"
                >
                  <p className="flex items-center gap-1.5 text-[13px] font-medium text-ink">
                    <FileText aria-hidden className="size-3.5 shrink-0 text-indigo" />
                    <span className="min-w-0 flex-1">{FIR_DOC.title}</span>
                    <GripVertical aria-hidden className="size-4 shrink-0 text-ink-muted" />
                  </p>
                  <p lang="hi" className="mt-1.5 text-[13px] leading-snug text-ink-soft">{FIR_FACTS[0]!.source?.quote}</p>
                  <p className="mt-1 text-xs text-ink-muted">{FIR_DOC.lang}, {FIR_DOC.pages.length} pages</p>
                </div>
                <Button variant="secondary" size="sm" className="mt-3" data-testid="add-fir-button" onClick={file}>
                  Add this FIR
                </Button>
              </>
            )}
          </div>

          <div
            ref={target}
            data-testid="dossier-drop"
            data-over={over || undefined}
            className={cn("min-w-0 p-4 transition-[box-shadow] duration-fast", over && "shadow-[inset_0_0_0_1px_var(--color-maroon)]")}
          >
            <p className="text-sm font-semibold text-ink">Dossier</p>
            {added ? (
              <>
                <ol aria-label="Pages of the FIR" className="mt-3 flex flex-wrap gap-2">
                  {FIR_DOC.pages.map((p, i) => (
                    <m.li
                      key={p.page}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={tr(i * 0.06)}
                      data-testid="demo-page"
                      data-status={p.status}
                      className={cn("rounded-sm border px-2 py-1 text-xs", p.status === "OK" ? "border-line text-ink-soft" : "border-saffron bg-saffron-wash text-saffron-ink")}
                    >
                      p. {p.page} {p.status === "OK" ? (p.kind.includes("handwriting") ? "read, handwriting" : "read") : "unreadable"}
                    </m.li>
                  ))}
                </ol>
                <ul aria-label="Facts from the FIR" className="mt-3 text-[13px]">
                  <AnimatePresence>
                    {FIR_FACTS.map((r, i) => (
                      <m.li
                        key={r.key}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={tr(0.18 + i * 0.05)}
                        data-testid="demo-row"
                        data-status={r.status}
                        className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 gap-y-0.5 border-b border-line/70 py-2 last:border-b-0"
                      >
                        <div className="min-w-0">
                          <span className="text-ink-soft">{r.label}</span>{" "}
                          {r.value ? <span className="font-medium text-ink">{r.value}</span> : <span className="text-ink-soft">{r.note}</span>}
                          {r.source ? <span className="ml-1.5 rounded-sm bg-indigo-tint px-1 py-0.5 font-mono text-[11px] text-indigo">FIR p.{r.source.page}</span> : null}
                        </div>
                        <StatusBadge status={r.status} kind="field" size="sm" label={r.status === "VERIFIED" ? "Confirmed" : "Not found"} testId="demo-status" />
                      </m.li>
                    ))}
                  </AnimatePresence>
                </ul>
                <p className="mt-3 text-[13px] text-saffron-ink">{FIR_DOC.question}</p>
                <button type="button" onClick={() => setAdded(false)} className="mt-2 rounded-sm text-sm text-ink-soft underline-offset-4 hover:text-maroon hover:underline">
                  Put the FIR back
                </button>
              </>
            ) : (
              <div className="mt-3 grid min-h-[9rem] place-items-center rounded-md border border-dashed border-line-strong/60 px-4 text-center text-sm text-ink-soft">
                Drop the FIR here
              </div>
            )}
          </div>
        </div>
        <p role="status" className="sr-only">{added ? `FIR read. ${found} facts found with their page, ${missing} not found in the FIR, page 3 unreadable.` : ""}</p>
      </div>
    </MotionProvider>
  );
}
