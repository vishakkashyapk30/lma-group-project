"use client";
// Clickable source chip: "doc · p. N". Click selects the source so the PDF viewer scrolls to the box (plan §13.5).
import { FileText } from "lucide-react";
import type { ReactElement } from "react";
import { cn } from "@/lib/utils";
import type { SourceRef } from "@/lib/types";
import { MOCK_DOC_TITLES } from "@/lib/mock/case0007";
import { useOptionalWorkspace } from "@/lib/workspace";

export interface SourceChipProps {
  source: SourceRef | null | undefined;
  /** Shown instead of the document name. */
  label?: string;
  className?: string;
}

export function sourceLabel(source: SourceRef): string {
  const doc = source.doc ? (MOCK_DOC_TITLES[source.doc] ?? source.doc) : "source";
  return source.page != null ? `${doc} · p. ${source.page}` : doc;
}

export function SourceChip({ source, label, className }: SourceChipProps): ReactElement | null {
  const ws = useOptionalWorkspace();
  if (!source || (!source.doc && source.page == null)) return null;
  const text = label ?? sourceLabel(source);
  return (
    <button
      type="button"
      onClick={() => ws?.selectSource(source, "chip")}
      disabled={!ws}
      title={source.quote ?? `Open ${text}`}
      aria-label={`Open source ${text}`}
      className={cn(
        "inline-flex max-w-full items-center gap-1 rounded-sm border border-line-strong/50 bg-cream px-1.5 py-0.5 font-mono text-[11px] leading-tight text-ink-soft",
        "transition-colors duration-fast hover:border-maroon hover:text-maroon disabled:cursor-default disabled:hover:border-line-strong/50 disabled:hover:text-ink-soft",
        className,
      )}
    >
      <FileText aria-hidden className="size-3 shrink-0" />
      <span className="truncate">{text}</span>
    </button>
  );
}

export default SourceChip;
