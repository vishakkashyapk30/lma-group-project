"use client";
// Shared plumbing for the six agent signature animations (plan §13.4): palette, status text, session-once playback and
// the accessible frame. Static mode and prefers-reduced-motion render the agent glyph plus a text status instead of art.
import { useCallback, useState, type ReactElement, type ReactNode, type Ref } from "react";
import type { gsap } from "gsap";
import { AgentGlyph } from "@/components/common/AgentGlyph";
import { AGENTS } from "@/lib/agents";
import type { AgentName } from "@/lib/types";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "@/lib/utils";
import type { AgentAnimationProps } from "./types";

/** A GSAP timeline. */
export type TL = gsap.core.Timeline;

/** Which background the art sits on: the workspace (light) or the oxblood landing panels (dark). */
export type Surface = "light" | "dark";

/** Props every signature accepts: the fixed ones plus an optional surface. */
export interface AgentArtProps extends AgentAnimationProps {
  surface?: Surface;
}

export interface Palette {
  /** Strokes drawn straight on the background. */
  line: string;
  /** Faint structure on the background. */
  faint: string;
  /** Gold-leaf ornaments. */
  gold: string;
  /** Cards and paper are always cream, with ink on them. */
  card: string;
  cardLine: string;
  ink: string;
  inkFaint: string;
  maroon: string;
  oxblood: string;
  sindoor: string;
  haldi: string;
  neem: string;
  indigo: string;
  /** Tailwind text class for the visible status line. */
  text: string;
}

const COMMON = {
  card: "var(--color-cream)",
  ink: "var(--color-ink)",
  maroon: "var(--color-maroon)",
  oxblood: "var(--color-oxblood)",
  sindoor: "var(--color-sindoor)",
  haldi: "var(--color-haldi)",
  neem: "var(--color-neem)",
  indigo: "var(--color-indigo)",
};

export const PALETTE: Record<Surface, Palette> = {
  light: {
    ...COMMON,
    line: "var(--color-ink-muted)",
    faint: "var(--color-line)",
    gold: "var(--color-gold-leaf)",
    cardLine: "var(--color-line-strong)",
    inkFaint: "rgba(35,26,22,0.22)",
    text: "text-ink-soft",
  },
  dark: {
    ...COMMON,
    line: "var(--color-gold-pale)",
    faint: "rgba(251,247,238,0.22)",
    gold: "var(--color-gold-pale)",
    cardLine: "var(--color-gold-leaf)",
    inkFaint: "rgba(35,26,22,0.22)",
    text: "text-cream",
  },
};

export function agentStatus(agent: AgentName, active: boolean, statusText?: string): string {
  if (statusText) return statusText;
  const meta = AGENTS[agent];
  return active ? meta.workingText : meta.idleText;
}

/** "Munshi · Intake agent: Munshi is reading and filing pages". */
export function agentLabel(agent: AgentName, status: string): string {
  const meta = AGENTS[agent];
  return `${meta.name} · ${meta.subtitle}: ${status}`;
}

/** Static art (glyph + text) is used for mode "static" and under reduced motion. */
export function useIsStatic(mode: AgentAnimationProps["mode"]): boolean {
  const reduced = useReducedMotion();
  return reduced || mode === "static";
}

const KEY_PREFIX = "vs:agent-full:";

/** True when the full version of this agent's animation has already played this session. */
export function hasPlayed(agent: AgentName): boolean {
  try {
    return window.sessionStorage.getItem(KEY_PREFIX + agent) === "1";
  } catch {
    return false;
  }
}

export function markPlayed(agent: AgentName): void {
  try {
    window.sessionStorage.setItem(KEY_PREFIX + agent, "1");
  } catch {
    /* storage unavailable: the animation simply plays again next mount */
  }
}

/** Replay counter for the click-to-replay control. 0 means "not clicked". */
export function useReplay(): [number, () => void] {
  const [n, setN] = useState(0);
  const bump = useCallback(() => setN((v) => v + 1), []);
  return [n, bump];
}

export interface AgentFrameProps {
  agent: AgentName;
  mode: AgentAnimationProps["mode"];
  active: boolean;
  statusText?: string;
  className?: string;
  surface: Surface;
  isStatic: boolean;
  viewBox: string;
  /** Ref for the GSAP scope (the element with role="img"). */
  rootRef: Ref<HTMLDivElement>;
  /** The SVG contents; rendered only when animated. */
  children: ReactNode;
  /** Replay control for full mode. */
  onReplay?: () => void;
  /** Extra controls under the art (e.g. "Show the plan"). */
  controls?: ReactNode;
}

export function AgentFrame({
  agent, mode, active, statusText, className, surface, isStatic, viewBox, rootRef, children, onReplay, controls,
}: AgentFrameProps): ReactElement {
  const status = agentStatus(agent, active, statusText);
  const label = agentLabel(agent, status);
  const pal = PALETTE[surface];
  const meta = AGENTS[agent];

  if (isStatic) {
    return (
      <div
        ref={rootRef}
        role="img"
        aria-label={label}
        data-agent-signature={agent}
        data-testid="agent-signature"
        data-agent={agent}
        data-mode="static"
        data-motion="static"
        className={cn("inline-flex items-center gap-3", className)}
      >
        <span
          aria-hidden
          className="grid h-12 w-12 shrink-0 place-items-center rounded-full border"
          style={{ borderColor: pal.gold, color: surface === "dark" ? "var(--color-cream)" : "var(--color-maroon)" }}
        >
          <AgentGlyph agent={agent} size={26} />
        </span>
        <span aria-hidden className={cn("text-sm leading-snug", pal.text)}>
          <span className="block font-display text-base">{meta.name}</span>
          <span data-testid="agent-status">{status}</span>
        </span>
      </div>
    );
  }

  return (
    <div data-agent-signature={agent} data-testid="agent-signature" data-agent={agent} data-mode={mode} data-motion="animated" className={cn("inline-flex w-full max-w-[24rem] flex-col gap-2", className)}>
      <div ref={rootRef} role="img" aria-label={label}>
        <svg viewBox={viewBox} className="block h-auto w-full overflow-visible" fill="none" focusable="false" aria-hidden>
          {children}
        </svg>
      </div>
      <div className="flex items-center justify-between gap-3">
        <span aria-hidden data-testid="agent-status" className={cn("text-xs leading-snug", pal.text)}>{status}</span>
        <span className="flex shrink-0 items-center gap-2">
          {controls}
          {mode === "full" && onReplay ? (
            <button
              type="button"
              onClick={onReplay}
              className={cn(
                "rounded-pill border px-2.5 py-0.5 text-xs transition-colors duration-fast",
                surface === "dark"
                  ? "border-gold-leaf text-cream hover:bg-cream/10"
                  : "border-line-strong text-maroon hover:bg-parchment-deep",
              )}
            >
              Replay<span className="sr-only"> {meta.name} animation</span>
            </button>
          ) : null}
        </span>
      </div>
    </div>
  );
}
