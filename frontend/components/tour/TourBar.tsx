"use client";
// The guided demo's bar, docked under the case workspace (opened with ?tour=<slug>). It shows step k of n, the step's title
// and caption (read out when they change), the agent that did the work and what was filled in at that step, as read-only
// fields. Next moves the workspace to the step's stage with the workspace's own navigation; on the Gate 2 step it first
// approves the draft through the real approve route, once. Keyboard: Right or Enter for Next, Left for Back, Escape to leave
// the demo (only while focus is on the page or in the bar, never while typing or with a dialog open).
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, ChevronDown, ChevronUp } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { AGENTS } from "@/lib/agents";
import * as api from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDateLong } from "@/lib/format";
import { useLang, useT } from "@/lib/i18n";
import { GATE_LABELS } from "@/lib/stages";
import {
  createTourMachine, gateOfStep, localizedStep, workspaceStageFor, workspaceTabFor, type Tour, type TourMachine, type TourState, type TourStep,
} from "@/lib/tour";
import { TOUR_READ_ONLY_NOTE } from "@/lib/tourMode";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { tourHref } from "./GuidedDemos";

export interface TourBarProps {
  slug: string;
  caseId: string;
}

/** Fills {name} placeholders in a translated string. */
function fill(text: string, values: Record<string, string | number>): string {
  return text.replace(/\{(\w+)\}/g, (m, k: string) => (k in values ? String(values[k]) : m));
}

const NO_STATE: TourState = { index: 0, total: 0, busy: false, error: null };
const noSubscribe = () => () => {};

/** Brings the step's part of the workspace into view: the objections inside Draft grounds, or the top of the step. */
function revealSection(step: TourStep): () => void {
  const timers: ReturnType<typeof setTimeout>[] = [];
  const pane = () => document.querySelector<HTMLElement>('[data-testid="pane-main"]');
  if (workspaceTabFor(step) === "spar") {
    // The objections load with the draft; look for them for up to about a second.
    const tryScroll = (left: number) => {
      const el = document.getElementById("spar-list");
      if (el) el.scrollIntoView({ block: "start" });
      else if (left > 0) timers.push(setTimeout(() => tryScroll(left - 1), 100));
    };
    timers.push(setTimeout(() => tryScroll(10), 50));
  } else {
    timers.push(setTimeout(() => pane()?.scrollTo({ top: 0 }), 0));
  }
  return () => timers.forEach(clearTimeout);
}

export function TourBar({ slug, caseId }: TourBarProps): ReactElement {
  const t = useT();
  const { lang } = useLang();
  const ws = useWorkspace();
  const router = useRouter();
  const pathname = usePathname();
  const barRef = useRef<HTMLElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const wsRef = useRef(ws);
  wsRef.current = ws;

  // undefined while loading, null for an unknown slug.
  const [tour, setTour] = useState<Tour | null | undefined>(undefined);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [blocked, setBlocked] = useState(false);
  // Below lg the bar can be folded to its title and buttons, so a phone keeps more of the workspace in view.
  const [folded, setFolded] = useState(false);

  useEffect(() => {
    let live = true;
    setTour(undefined);
    setLoadError(null);
    api
      .getTour(slug)
      .then((found) => live && setTour(found))
      .catch((e) => {
        if (!live) return;
        setLoadError(errorMessage(e));
        setTour(null);
      });
    return () => {
      live = false;
    };
  }, [slug]);

  const usable = tour && tour.case_id === caseId ? tour : null;

  const machine: TourMachine | null = useMemo(
    () =>
      usable
        ? createTourMachine(usable, {
            isGate2Approved: () => wsRef.current.gates.approvals.gate2,
            approveGate2: async () => {
              // Counsel's approval, given here by the evaluator's Next: every open item on the checklist is sent as reviewed,
              // the way the confirm dialog sends counsel's resolutions.
              const items = wsRef.current.gates.checklists.GATE_2_EXPORT.items;
              await api.approveGate(caseId, "GATE_2_EXPORT", items.map((i) => (i.kind === "UNSUPPORTED" ? i.ref : i.key)));
              await wsRef.current.refresh(["summary", "gates"]);
            },
            recheckGate2: async () => {
              const status = await api.getGate(caseId, "GATE_2_EXPORT");
              if (!status.open) await wsRef.current.refresh(["summary", "gates"]);
              return !status.open;
            },
          })
        : null,
    [usable, caseId],
  );
  const state = useSyncExternalStore(machine?.subscribe ?? noSubscribe, machine?.getState ?? (() => NO_STATE), () => NO_STATE);
  const step = usable?.steps[state.index] ?? null;
  const last = state.index === state.total - 1;

  // Move the workspace to the step, with its own navigation, once the case is known.
  const summaryLoading = ws.loading.summary;
  useEffect(() => {
    if (!step || summaryLoading) return;
    setBlocked(!wsRef.current.setStage(workspaceStageFor(step.stage)));
    return revealSection(step);
  }, [step, summaryLoading]);

  // The last step exports by itself once Gate 2 is approved, so the evaluator only presses Next and finds the download links.
  const gate2Approved = ws.gates.approvals.gate2;
  const exported = (ws.exports?.length ?? 0) > 0;
  const autoExported = useRef(false);
  useEffect(() => {
    if (step?.stage !== "FILE" || !gate2Approved || exported || autoExported.current) return;
    autoExported.current = true;
    wsRef.current.exportCase("DOCX").catch(() => {
      autoExported.current = false; // the workspace shows the error; Next or the export button can try again
    });
  }, [step, gate2Approved, exported]);

  // Toasts sit above the bar, not over its buttons (components/ui/toast.tsx reads --tour-bar-h).
  useEffect(() => {
    const el = barRef.current;
    const root = document.documentElement;
    if (!el) return;
    // Beside the workspace (wide screens) the bar does not cover the bottom edge, so toasts need no extra room.
    const set = () => root.style.setProperty("--tour-bar-h", `${el.offsetWidth < window.innerWidth * 0.6 ? 0 : el.offsetHeight}px`);
    set();
    root.dataset.tour = "1";
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(set) : null;
    ro?.observe(el);
    return () => {
      ro?.disconnect();
      root.style.removeProperty("--tour-bar-h");
      delete root.dataset.tour;
    };
  }, [tour]);

  // Start with focus on Next, so Enter moves on.
  useEffect(() => {
    if (machine) nextRef.current?.focus({ preventScroll: true });
  }, [machine]);

  const exit = useCallback(() => {
    router.replace(pathname ?? `/case/${encodeURIComponent(caseId)}`);
    requestAnimationFrame(() => document.getElementById("step-title")?.focus());
  }, [router, pathname, caseId]);

  const next = useCallback(() => {
    if (!machine) return;
    if (machine.getState().index === machine.getState().total - 1) exit();
    else void machine.next();
  }, [machine, exit]);
  const back = useCallback(() => {
    machine?.back();
  }, [machine]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.isComposing) return;
      const target = e.target instanceof HTMLElement ? e.target : null;
      const onPage = !target || target === document.body || target === document.documentElement;
      const inBar = Boolean(target && barRef.current?.contains(target));
      if (!onPage && !inBar) return;
      if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
      if (document.querySelector("[role='dialog'], [role='alertdialog']")) return;
      // Enter on a button in the bar presses that button; Enter elsewhere (the page, the bar itself) means Next.
      const onControl = Boolean(target?.closest("button, a"));
      if (e.key === "ArrowRight" || (e.key === "Enter" && !onControl)) {
        e.preventDefault();
        next();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        back();
      } else if (e.key === "Escape") {
        e.preventDefault();
        exit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, back, exit]);

  const frame = (body: ReactElement) => (
    <section
      ref={barRef}
      tabIndex={-1}
      aria-label={t("Guided demo")}
      data-testid="tour-bar"
      data-print-hide
      className="shrink-0 border-t border-line-strong/60 bg-cream outline-none lg:flex lg:w-[24rem] lg:flex-col lg:border-l lg:border-t-0 xl:w-[28rem] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-maroon"
    >
      {body}
    </section>
  );

  if (tour === undefined) {
    return frame(
      <p role="status" className="min-h-[5.5rem] px-4 py-3 text-sm text-ink-soft sm:px-6">
        {t("Opening the guided demo")}
      </p>,
    );
  }

  if (!usable || !step) {
    const elsewhere = tour && tour.case_id !== caseId ? tour : null;
    return frame(
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6" data-testid="tour-missing">
        <p role="alert" className="min-w-0 flex-1 text-ink">
          {elsewhere
            ? t("This guided demo belongs to another case.")
            : loadError
              ? `${t("The guided demo could not be loaded.")} ${loadError}`
              : t("This guided demo was not found.")}
        </p>
        {elsewhere ? (
          <Button asChild variant="secondary" size="sm">
            <Link href={tourHref(elsewhere)}>{t("Open its case")}</Link>
          </Button>
        ) : null}
        <Button variant="ghost" size="sm" onClick={exit} data-testid="tour-exit">
          {t("Exit the demo")}
        </Button>
      </div>,
    );
  }

  const agent = step.agent ? AGENTS[step.agent] : null;
  const gate = gateOfStep(step.stage);
  const gateApproved = gate === "GATE_1_DOSSIER" ? ws.gates.approvals.gate1 : gate === "GATE_2_EXPORT" ? ws.gates.approvals.gate2 : false;
  const approving = step.action === "approve_gate_2" && !gateApproved;
  const nextLabel = state.busy ? t("Approving") : last ? t("Finish") : approving ? t("Approve and continue") : t("Next");
  const rec = usable.recorded;
  const text = localizedStep(step, lang);

  return frame(
    <div className="flex max-h-[42dvh] flex-col gap-3 px-4 py-3 sm:px-6 lg:h-full lg:max-h-none lg:min-h-0 lg:px-5 lg:py-5">
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain" data-testid="tour-step" data-stage={step.stage} data-index={state.index}>
        <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-ink-soft">
          <span className="font-medium text-ink">{t("Guided demo")}</span>
          {" · "}
          <span data-testid="tour-progress" className="tabular">{fill(t("Step {k} of {n}"), { k: state.index + 1, n: state.total })}</span>
          {agent ? (
            <>
              {" · "}
              <span data-testid="tour-agent">{fill(t("Done by {agent}"), { agent: `${agent.name}, ${t(agent.subtitle)}` })}</span>
            </>
          ) : null}
        </p>
        <button
          type="button"
          onClick={() => setFolded((v) => !v)}
          aria-expanded={!folded}
          aria-controls="tour-details"
          data-testid="tour-fold"
          className="-mr-2 -mt-2 inline-flex min-h-11 shrink-0 items-center gap-1 rounded-md px-2 text-sm font-medium text-maroon hover:bg-ink/[0.06] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 lg:hidden"
        >
          {folded ? <ChevronUp aria-hidden className="size-4" /> : <ChevronDown aria-hidden className="size-4" />}
          {folded ? t("Read") : t("Hide")}
        </button>
        </div>
        <p data-testid="tour-readonly" className={cn("text-sm text-ink-soft", folded && "max-lg:hidden")}>{t(TOUR_READ_ONLY_NOTE)}</p>
        <div aria-live="polite" aria-atomic="true">
          <h2 id="tour-step-title" className="mt-1 font-display text-xl font-semibold leading-snug text-ink">
            {text.title}
          </h2>
          <p id="tour-details" data-testid="tour-caption" className={cn("mt-1 max-w-prose text-ink", folded && "max-lg:hidden")}>
            {text.caption}
          </p>
        </div>
        {gate ? (
          <p data-testid="tour-gate" data-approved={gateApproved} className={cn("mt-2 flex max-w-prose items-start gap-1.5 text-sm", folded && "max-lg:hidden")}>
            {gateApproved ? <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-neem" /> : null}
            <span className={gateApproved ? "text-neem-deep" : "text-ink-soft"}>
              <span className="font-medium">
                {gate === "GATE_1_DOSSIER"
                  ? gateApproved ? t("Gate 1 is approved.") : t("Gate 1 is open.")
                  : gateApproved ? t("Gate 2 is approved.") : t("Gate 2 is open. Next approves the draft for export.")}
              </span>{" "}
              <span className="text-ink-soft">{t(GATE_LABELS[gate].description)}</span>
            </span>
          </p>
        ) : null}
        {text.filled.length > 0 ? (
          <div className={cn("mt-3", folded && "max-lg:hidden")}>
            <h3 className="font-sans text-sm font-semibold text-ink">{t("Filled in at this step")}</h3>
            <dl data-testid="tour-filled" className="mt-1.5 grid gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-1">
              {text.filled.map((f, i) => (
                <div key={`${f.label}-${i}`} data-testid="tour-field" className="min-w-0">
                  <dt className="text-sm text-ink-soft">{f.label}</dt>
                  <dd className="mt-0.5 rounded-md border border-line bg-parchment px-2.5 py-1.5 text-sm text-ink">
                    {f.value || "-"}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}
        {blocked ? (
          <p role="status" className="mt-2 text-sm text-ink-soft">
            {t("This step is not open in this case yet. It opens once counsel confirms the facts.")}
          </p>
        ) : null}
        {state.error ? (
          <p role="alert" data-testid="tour-error" className="mt-2 text-sm text-sindoor">
            {state.error}
          </p>
        ) : null}
        {rec && state.index === 0 ? (
          <p className={cn("mt-2 text-sm text-ink-soft", folded && "max-lg:hidden")}>
            {fill(t("Recorded on {date} with {backend} ({model})."), { date: formatDateLong(rec.date), backend: rec.backend, model: rec.model })}
          </p>
        ) : null}
      </div>
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 lg:border-t lg:border-line lg:pt-3 [&_button]:max-lg:h-11 [&_button]:max-lg:min-w-11">
        <Button variant="ghost" size="md" onClick={exit} data-testid="tour-exit" aria-keyshortcuts="Escape">
          {t("Exit the demo")}
        </Button>
        <Button variant="secondary" size="md" onClick={back} disabled={state.index === 0 || state.busy} data-testid="tour-back" aria-keyshortcuts="ArrowLeft">
          <ArrowLeft aria-hidden /> {t("Back")}
        </Button>
        <Button
          ref={nextRef}
          size="md"
          onClick={() => (state.busy ? undefined : next())}
          aria-disabled={state.busy || undefined}
          data-testid="tour-next"
          aria-keyshortcuts="ArrowRight Enter"
          className={cn(state.busy && "cursor-progress")}
        >
          {nextLabel} {last ? null : <ArrowRight aria-hidden />}
        </Button>
      </div>
    </div>,
  );
}

export default TourBar;
