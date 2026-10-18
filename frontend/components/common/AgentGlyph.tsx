// Small per-agent glyph used on chat messages, chips and the nav (plan §13.4). Static line art in currentColor.
import type { ReactElement, ReactNode } from "react";
import { AGENTS, type AgentGlyphKind } from "@/lib/agents";
import { cn } from "@/lib/utils";
import type { AgentName } from "@/lib/types";

export interface AgentGlyphProps {
  agent: AgentName;
  size?: number;
  /** Accessible label; decorative (aria-hidden) when omitted. */
  title?: string;
  className?: string;
}

const PATHS: Record<AgentGlyphKind, ReactNode> = {
  // Munshi: a stack of papers with a fold
  papers: (
    <>
      <path d="M7 4h9l4 4v12H7z" /><path d="M16 4v4h4" /><path d="M4 8v13h12" /><path d="M10 13h7M10 16.5h5" />
    </>
  ),
  // Peshkar: a calendar page with bars
  calendar: (
    <>
      <rect x="3.5" y="5" width="17" height="15" rx="1.5" /><path d="M3.5 10h17M8 3v4M16 3v4" /><path d="M7 14h4M7 17h7M14 14h3" />
    </>
  ),
  // Sutradhar: a 24-spoke style wheel (8 drawn)
  wheel: (
    <>
      <circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="1.6" />
      <path d="M12 3.5v7M12 13.5v7M3.5 12h7M13.5 12h7M6 6l5 5M13 13l5 5M18 6l-5 5M11 13l-5 5" />
    </>
  ),
  // Vakeel: a manuscript scroll with a nib line
  manuscript: (
    <>
      <path d="M6 4h11a2 2 0 0 1 2 2v12a2 2 0 0 0 2 2H8a2 2 0 0 1-2-2z" /><path d="M6 4a2 2 0 0 0-2 2v2h2" /><path d="M10 9h6M10 12h6M10 15h3" />
    </>
  ),
  // Abhiyojak: scales
  scales: (
    <>
      <path d="M12 4v16M8 20h8M5 7h14" /><path d="M5 7l-3 7a3 3 0 0 0 6 0zM19 7l-3 7a3 3 0 0 0 6 0z" />
    </>
  ),
  // Pairokar: cause-list bars
  bars: (
    <>
      <path d="M4 20V4M4 20h16" /><path d="M7 8h10M7 12h6M7 16h8" />
    </>
  ),
};

export function AgentGlyph({ agent, size = 20, title, className }: AgentGlyphProps): ReactElement {
  const kind = AGENTS[agent].glyph;
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
      data-agent={agent}
      className={cn("shrink-0", className)}
    >
      {title ? <title>{title}</title> : null}
      {PATHS[kind]}
    </svg>
  );
}

export default AgentGlyph;
