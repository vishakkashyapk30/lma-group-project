// Store and tool chips on every answer (plan §13.5): "date_calc · timeline", "search_reasoning · reasoning".
import { Database, Wrench } from "lucide-react";
import type { ReactElement } from "react";
import { STORES, toolLabel } from "@/lib/stores";
import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface ToolChipsProps {
  chips: ChatMessage["chips"];
  className?: string;
}

export function ToolChips({ chips, className }: ToolChipsProps): ReactElement | null {
  if (!chips || chips.length === 0) return null;
  return (
    <ul aria-label="Tools and stores used for this answer" className={cn("flex flex-wrap gap-1.5", className)}>
      {chips.map((chip, i) => {
        const store = chip.store ? STORES[chip.store] : null;
        const description = store
          ? `${toolLabel(chip.tool)} on the ${store.label} store (${store.shelf} shelf, ${store.indexLabel}): ${store.contents}`
          : toolLabel(chip.tool);
        return (
          <li
            key={`${chip.tool}-${chip.store ?? "none"}-${i}`}
            data-testid="tool-chip"
            title={description}
            className="inline-flex items-center gap-1 rounded-sm border border-gold/50 bg-parchment px-1.5 py-0.5 font-mono text-[11px] leading-tight text-ink-soft"
          >
            <Wrench aria-hidden className="size-3 shrink-0 text-gold-leaf" />
            <span className="font-medium text-ink">{chip.tool}</span>
            {store ? (
              <>
                <span aria-hidden>·</span>
                <Database aria-hidden className="size-3 shrink-0 text-gold-leaf" />
                <span>{store.id.split(".")[1]}</span>
                <span className="sr-only">store, {store.shelf} shelf</span>
              </>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export default ToolChips;
