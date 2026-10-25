"use client";
// One line for long-running agent work, with a small glyph that breathes while it runs. Never a dashboard of agents.
import type { ReactElement } from "react";
import { AgentSignature } from "@/components/agents/AgentSignature";
import { progressLine, useWorkspace } from "@/lib/workspace";

export function ProgressLine({ className }: { className?: string }): ReactElement | null {
  const ws = useWorkspace();
  const line = progressLine(ws.activity, ws.events, { uploading: ws.uploading, drafting: ws.drafting });
  if (!line) return null;
  return <AgentSignature agent={line.agent} mode="working" active statusText={line.text} className={className} />;
}

export default ProgressLine;
