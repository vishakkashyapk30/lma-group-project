"use client";
// The rights timeline: the case's calendar from the arrest, with the default-bail window (BNSS s.187) and the
// undertrial limit (BNSS s.479) drawn where they fall, and a hearing date you can move. Moving it says, for that date,
// how long the accused has been in custody and what each right says, in words. A range that depends on a fact the
// papers do not give is drawn as an outline marked "Check", never as a filled "open". It reports dates, not outcomes.
//
// The hearing date is a slider: drag its handle (it resists past either end and coasts on a flick, then settles on a
// day, or on a threshold date when it lands near one), tap the track, use the buttons, or the keyboard (arrows a day,
// Shift or Page keys 30 days, Home and End).
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactElement } from "react";
import { SPRINGS, SpringValue, clamp, prefersReducedMotion, project, rubberClamp, useDrag } from "@/lib/motion";
import { addDays, courtDate, dateAt, diffDays, fraction, stateAt, type LaneState, type TimelineInput } from "@/lib/rightsTimeline";
import { cn } from "@/lib/utils";

export interface RightsTimelineProps {
  input: TimelineInput;
  /** The hearing date to start on (defaults to the as-of date). */
  initialDate?: string;
  /** Named dates offered as buttons, e.g. the next hearing. */
  jumps?: { label: string; date: string }[];
  /** On dark bands the panel stays cream; this only sets the test id. */
  testId?: string;
  className?: string;
}

const WORD_CLASS: Record<LaneState["word"], string> = {
  Closed: "text-ink-soft",
  "Not yet": "text-indigo",
  Check: "text-saffron-ink",
  Open: "text-neem",
  "Does not apply": "text-ink-soft",
};

/** Pixels within which a release settles on a marked date instead of the nearest day. */
const MAGNET = 10;

export function RightsTimeline({ input, initialDate, jumps = [], testId = "rights-timeline", className }: RightsTimelineProps): ReactElement {
  const start = input.arrest;
  const end = useMemo(() => addDays(input.oneHalf ?? addDays(input.asOf, 365), 120), [input.oneHalf, input.asOf]);
  const [date, setDate] = useState(initialDate ?? input.asOf);
  const [announce, setAnnounce] = useState("");
  const track = useRef<HTMLDivElement>(null);
  const handle = useRef<HTMLButtonElement>(null);
  const lanes = useRef<HTMLUListElement>(null);
  const line = useRef<HTMLSpanElement>(null);
  const px = useRef<SpringValue | null>(null);
  const base = useRef(0);
  const width = () => track.current?.getBoundingClientRect().width ?? 1;

  const marks = useMemo(
    () => [input.limitEnd ? addDays(input.limitEnd, 1) : null, input.chargeSheet, input.oneThird, input.oneHalf, input.asOf, ...jumps.map((j) => j.date)].filter((d): d is string => Boolean(d)),
    [input, jumps],
  );

  // The handle is drawn from the spring's pixel value; the date follows it, rounded to the day.
  useEffect(() => {
    px.current = new SpringValue(0, (x) => {
      const w = width();
      const el = handle.current?.parentElement;
      if (el) el.style.transform = `translateX(${x}px)`;
      setDate(dateAt(clamp(x, 0, w) / w, start, end));
    });
    // The hearing line runs from the top of the lanes down to the handle.
    const sizeLine = () => {
      const l = lanes.current?.getBoundingClientRect();
      const tr = track.current?.getBoundingClientRect();
      if (l && tr && line.current) line.current.style.height = `${tr.top + tr.height / 2 - l.top}px`;
    };
    px.current.set(fraction(initialDate ?? input.asOf, start, end) * width());
    sizeLine();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => {
      px.current?.set(fraction(dateRef.current, start, end) * width());
      sizeLine();
    }) : null;
    if (track.current) ro?.observe(track.current);
    if (lanes.current) ro?.observe(lanes.current);
    return () => {
      px.current?.stop();
      ro?.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [start, end]);
  const dateRef = useRef(date);
  dateRef.current = date;

  const say = useCallback((d: string) => {
    const s = stateAt(input, d);
    setAnnounce(`${courtDate(d)}: ${s.custodyDays} days in custody. Default bail: ${s.defaultBail.word}. Undertrial limit: ${s.undertrial.word}.`);
  }, [input]);

  const goTo = useCallback((d: string, velocity = 0) => {
    const w = width();
    const target = fraction(d, start, end) * w;
    px.current?.to(target, { spring: SPRINGS.timeline, velocity, reduced: prefersReducedMotion(), onRest: () => say(dateAt(target / w, start, end)) });
    if (prefersReducedMotion()) say(d);
  }, [start, end, say]);

  useDrag(handle, {
    axis: "x",
    rate: 0.99,
    onStart: () => {
      px.current?.stop();
      base.current = px.current?.value ?? 0;
    },
    onMove: (d) => {
      const w = width();
      const raw = base.current + d;
      px.current?.set(prefersReducedMotion() ? clamp(raw, 0, w) : rubberClamp(raw, 0, w, 32));
    },
    onEnd: ({ velocity, projected }) => {
      const w = width();
      const reduced = prefersReducedMotion();
      let x = clamp((px.current?.value ?? 0) + (reduced ? 0 : projected), 0, w);
      const near = marks.map((m) => fraction(m, start, end) * w).find((mx) => Math.abs(mx - x) <= MAGNET);
      if (near !== undefined) x = near;
      const d = dateAt(x / w, start, end);
      px.current?.to(fraction(d, start, end) * w, { spring: SPRINGS.timeline, velocity, reduced, onRest: () => say(d) });
      if (reduced) say(d);
    },
  });

  const onKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    const step = e.shiftKey || e.key === "PageUp" || e.key === "PageDown" ? 30 : 1;
    let next: string | null = null;
    if (e.key === "ArrowRight" || e.key === "ArrowUp" || e.key === "PageUp") next = addDays(date, step);
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown" || e.key === "PageDown") next = addDays(date, -step);
    else if (e.key === "Home") next = start;
    else if (e.key === "End") next = end;
    if (!next) return;
    e.preventDefault();
    next = next < start ? start : next > end ? end : next;
    px.current?.set(fraction(next, start, end) * width());
    say(next);
  };

  const s = stateAt(input, date);
  const at = (d: string) => `${fraction(d, start, end) * 100}%`;
  const span = (a: string, b: string) => ({ left: at(a), width: `max(4px, ${(fraction(b, start, end) - fraction(a, start, end)) * 100}%)` });
  const years: string[] = [];
  for (let y = Number(start.slice(0, 4)) + 1; `${y}-01-01` < end; y++) if (fraction(`${y}-01-01`, start, end) > 0.12) years.push(`${y}-01-01`);
  const opens = input.limitEnd ? addDays(input.limitEnd, 1) : null;

  return (
    <div data-testid={testId} className={cn("rounded-lg bg-cream p-4 text-ink sm:p-5", className)}>
      {/* Lanes */}
      <div className="relative">
        <div aria-hidden className="relative h-5 text-[11px] text-ink-muted">
          <span className="absolute left-0">Arrest {courtDate(start)}</span>
          {years.map((y) => (
            <span key={y} className="absolute hidden -translate-x-1/2 sm:block" style={{ left: at(y) }}>{y.slice(0, 4)}</span>
          ))}
        </div>
        <ul ref={lanes} aria-label="Rights on the calendar" className="relative mt-1 space-y-3">
          <li className="relative">
            <p className="relative z-[2] bg-cream text-xs font-medium text-ink-soft">In custody</p>
            <div className="relative mt-1 h-3 rounded-xs bg-parchment-deep">
              <div aria-hidden className="absolute inset-y-0 left-0 rounded-xs bg-ink/25" style={{ width: at(date) }} />
            </div>
          </li>
          <li className="relative" data-testid="lane-default-bail" data-word={s.defaultBail.word}>
            <p className="relative z-[2] bg-cream text-xs text-ink-soft">
              <span className="font-medium">Default bail, BNSS s.187 ({input.limitDays ?? "60 or 90"} days)</span>
              {opens && input.chargeSheet && input.chargeSheet > input.limitEnd! ? <span className="text-ink-muted"> · open {courtDate(opens)} to {courtDate(addDays(input.chargeSheet, -1))}</span> : null}
              {opens && !input.chargeSheet ? <span className="text-saffron-ink"> · Check: no charge-sheet date in the papers</span> : null}
            </p>
            <div className="relative mt-1 h-3 rounded-xs bg-parchment-deep">
              {opens && input.chargeSheet && input.chargeSheet > input.limitEnd! ? (
                <div aria-hidden className="absolute inset-y-0 rounded-xs bg-line-strong" style={span(opens, input.chargeSheet)} />
              ) : opens && !input.chargeSheet ? (
                <div aria-hidden className="absolute inset-y-0 rounded-xs border border-saffron" style={span(opens, end)} />
              ) : null}
            </div>
          </li>
          <li className="relative" data-testid="lane-undertrial" data-word={s.undertrial.word}>
            <p className="relative z-[2] bg-cream text-xs text-ink-soft">
              <span className="font-medium">Undertrial limit, BNSS s.479</span>
              {input.oneThird && !input.antecedentsKnown ? <span className="text-saffron-ink"> · Check: one-third applies only to a first-time offender</span> : null}
            </p>
            <div className="relative mt-1 h-3 rounded-xs bg-parchment-deep">
              {input.oneThird && input.oneHalf ? (
                <>
                  <div aria-hidden className="absolute inset-y-0 rounded-xs border-2 border-saffron" style={span(input.oneThird, input.oneHalf)} />
                  <div aria-hidden className="absolute inset-y-0 rounded-xs bg-saffron/60" style={span(input.oneHalf, end)} />
                </>
              ) : null}
            </div>
          </li>
        </ul>

        {/* Hearing date: the line across the lanes and the slider handle under them */}
        <div ref={track} className="relative mt-4 h-11">
          <button
            type="button"
            tabIndex={-1}
            aria-hidden
            onClick={(e) => {
              const r = track.current!.getBoundingClientRect();
              goTo(dateAt(clamp((e.clientX - r.left) / r.width, 0, 1), start, end));
            }}
            className="absolute inset-x-0 top-1/2 h-6 -translate-y-1/2 cursor-pointer"
          >
            <span className="absolute inset-x-0 top-1/2 h-px bg-line-strong" />
          </button>
          <div className="pointer-events-none absolute left-0 top-0 z-[1] h-full will-change-transform">
            <span ref={line} aria-hidden className="absolute bottom-1/2 left-0 w-0.5 -translate-x-1/2 bg-maroon/70" />
            <button
              ref={handle}
              type="button"
              role="slider"
              aria-label="Hearing date"
              aria-valuemin={0}
              aria-valuemax={diffDays(start, end)}
              aria-valuenow={diffDays(start, date)}
              aria-valuetext={`${courtDate(date)}, ${s.custodyDays} days in custody`}
              data-testid="hearing-handle"
              onKeyDown={onKey}
              className="press pointer-events-auto absolute top-1/2 h-11 w-11 -translate-x-1/2 -translate-y-1/2 cursor-grab touch-none rounded-md active:cursor-grabbing"
            >
              <span aria-hidden className="absolute left-1/2 top-1/2 h-6 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-sm border border-maroon bg-cream" />
            </button>
          </div>
        </div>
      </div>

      {/* What the chosen date means, in words */}
      <div className="mt-2 border-t border-line pt-3">
        <p className="text-sm text-ink">
          Hearing on <time dateTime={date} data-testid="hearing-date" className="tabular font-semibold">{courtDate(date)}</time>:{" "}
          <span data-testid="custody-days" className="tabular">{s.custodyDays.toLocaleString("en-IN")}</span> days in custody since the arrest.
        </p>
        <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-[11rem_minmax(0,1fr)]">
          <dt className="text-ink-soft">Default bail</dt>
          <dd className="m-0"><span data-testid="word-default-bail" className={cn("font-semibold", WORD_CLASS[s.defaultBail.word])}>{s.defaultBail.word}.</span> {s.defaultBail.sentence}</dd>
          <dt className="text-ink-soft">Undertrial limit</dt>
          <dd className="m-0"><span data-testid="word-undertrial" className={cn("font-semibold", WORD_CLASS[s.undertrial.word])}>{s.undertrial.word}.</span> {s.undertrial.sentence}</dd>
        </dl>
        {jumps.length > 0 || input.oneThird ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {jumps.map((j) => (
              <button key={j.date} type="button" onClick={() => goTo(j.date)} className="press rounded-md border border-line-strong/60 px-2.5 py-1 text-xs text-ink hover:bg-parchment-deep">
                {j.label}, {courtDate(j.date)}
              </button>
            ))}
            {input.oneThird ? (
              <button type="button" onClick={() => goTo(input.oneThird!)} className="press rounded-md border border-line-strong/60 px-2.5 py-1 text-xs text-ink hover:bg-parchment-deep">
                One-third of the maximum, {courtDate(input.oneThird)}
              </button>
            ) : null}
            {input.oneHalf ? (
              <button type="button" onClick={() => goTo(input.oneHalf!)} className="press rounded-md border border-line-strong/60 px-2.5 py-1 text-xs text-ink hover:bg-parchment-deep">
                One-half, {courtDate(input.oneHalf)}
              </button>
            ) : null}
          </div>
        ) : null}
        <p role="status" aria-live="polite" className="sr-only">{announce}</p>
      </div>
    </div>
  );
}

export default RightsTimeline;
