"use client";
// "Needs your attention": the short list each step opens with. Each item has one button that jumps to it. When nothing needs
// the lawyer it says so in one calm line.
import type { ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { useWorkspace, type NeedItem } from "@/lib/workspace";

export interface NeedsYouProps {
  items: NeedItem[];
  /** Shown when the list is empty. */
  empty: string;
  className?: string;
}

/** Runs the jump an item asks for: open an item in its step, open the chat, or go back to adding documents. */
export function useRunNeed(): (item: NeedItem) => void {
  const ws = useWorkspace();
  return (item) => {
    const t = item.target;
    if (!t) return;
    if (t.kind === "chat") ws.openChat();
    else if (t.kind === "files") ws.setStage("INTAKE");
    else ws.focusItem(t.tab, t.id, t.intent);
  };
}

export function NeedsYou({ items, empty, className }: NeedsYouProps): ReactElement {
  const run = useRunNeed();
  if (items.length === 0) {
    return (
      <p data-testid="needs-you" data-count="0" className={className ? `text-ink-soft ${className}` : "text-ink-soft"}>
        {empty}
      </p>
    );
  }
  return (
    <section data-testid="needs-you" data-count={items.length} aria-labelledby="needs-you-title" className={className}>
      <h3 id="needs-you-title" className="font-sans text-sm font-semibold text-ink">
        Needs your attention
      </h3>
      <ul className="mt-2 divide-y divide-line border-y border-line">
        {items.map((item) => (
          <li key={item.key} data-testid="needs-you-item" className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
            <div className="min-w-0 flex-1">
              <p className="text-ink">{item.text}</p>
              {item.detail ? <p className="mt-0.5 line-clamp-2 text-sm text-ink-soft">{item.detail}</p> : null}
            </div>
            {item.target ? (
              <Button variant="secondary" size="sm" onClick={() => run(item)} aria-label={`${item.label}: ${item.text}`}>
                {item.label}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default NeedsYou;
