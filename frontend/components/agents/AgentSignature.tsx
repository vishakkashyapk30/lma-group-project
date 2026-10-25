"use client";
// An agent's status as one quiet line: its small glyph (which breathes while the agent is working) and a text status.
// The glyph stands still under reduced motion; the text carries the meaning either way.
import type { ReactElement } from "react";
import { AgentGlyph } from "@/components/common/AgentGlyph";
import { AGENTS } from "@/lib/agents";
import type { StoreName } from "@/lib/types";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "@/lib/utils";
import type { AgentSignatureProps as BaseProps } from "./types";

export interface AgentSignatureProps extends BaseProps {
  /** Accepted so existing call sites keep compiling; the indicator no longer draws these. */
  surface?: "light" | "dark";
  litStores?: readonly StoreName[];
  activeTool?: string | null;
  unanswered?: number;
  /** Shows a "Show the plan" button beside the status when mode is "full". */
  onShowPlan?: () => void;
}

export function AgentSignature({ agent, mode, active, statusText, className, onShowPlan }: AgentSignatureProps): ReactElement {
  const reduced = useReducedMotion();
  const meta = AGENTS[agent];
  const status = statusText ?? (active ? meta.workingText : meta.idleText);
  const animate = active && !reduced && mode !== "static";
  return (
    <div
      data-testid="agent-signature"
      data-agent={agent}
      data-mode={mode}
      role="group"
      aria-label={`${meta.name}, ${meta.subtitle}`}
      className={cn("inline-flex max-w-full items-center gap-2 text-sm text-ink-soft", className)}
    >
      <span aria-hidden className={cn("shrink-0 text-maroon", animate && "animate-breathe")}>
        <AgentGlyph agent={agent} size={16} />
      </span>
      <span data-testid="agent-status" role="status" className="min-w-0">{status}</span>
      {mode === "full" && onShowPlan ? (
        <button type="button" onClick={onShowPlan} className="shrink-0 rounded-sm text-sm font-medium text-maroon underline-offset-4 hover:underline">
          Show the plan
        </button>
      ) : null}
    </div>
  );
}

export default AgentSignature;
