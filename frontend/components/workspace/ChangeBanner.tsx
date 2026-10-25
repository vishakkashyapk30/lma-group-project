"use client";
// Change banner (plan §7.4, §10): when a new document or the passing of time changes the facts or the rights checks, the change
// waits for the lawyer to confirm the facts again. It names what changed in words (never colour alone).
import { RefreshCw } from "lucide-react";
import { useState, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { fieldLabel } from "@/lib/fields";
import { plural } from "@/lib/format";
import { RIGHTS_CHECK_LABELS } from "@/lib/labels";
import type { RightsCheckName } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { GateModal } from "./GateModal";

export interface ChangeBannerProps {
  className?: string;
}

export function ChangeBanner({ className }: ChangeBannerProps): ReactElement | null {
  const ws = useWorkspace();
  const [open, setOpen] = useState(false);
  const pending = ws.changes.pending;
  if (!pending) return null;
  const fields = ws.changes.changedFields;
  const rights = ws.changes.changedRights;
  const trigger = pending.trigger === "new_document" ? "a new document" : pending.trigger === "clock" ? "the passing of time" : "an edit";

  return (
    <div role="status" data-testid="change-banner" data-print-hide className={cn("shrink-0 border-b border-line bg-cream px-4 py-3 sm:px-6", className)}>
      <div className="mx-auto flex max-w-[48rem] flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-sm font-medium text-ink">
            <RefreshCw aria-hidden className="size-4 shrink-0 text-haldi" />
            {plural(fields.length + rights.length, "item")} changed since you confirmed, because of {trigger}.
          </p>
          <ul aria-label="What changed" className="m-0 mt-1 flex list-none flex-wrap gap-x-3 p-0 pl-6 text-sm text-ink-soft">
            {fields.map((f) => (
              <li key={`f-${f}`} data-testid="change-item" data-kind="field" data-name={f}>
                {fieldLabel(f)}
              </li>
            ))}
            {rights.map((r) => (
              <li key={`r-${r}`} data-testid="change-item" data-kind="right" data-name={r}>
                {RIGHTS_CHECK_LABELS[r as RightsCheckName] ?? r}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex gap-2">
          {ws.changedFields.length > 0 ? (
            <Button size="sm" variant="ghost" onClick={ws.clearChangedFields}>
              Hide highlights
            </Button>
          ) : null}
          <Button size="sm" variant="secondary" onClick={() => setOpen(true)} aria-haspopup="dialog">
            Review and confirm again
          </Button>
        </div>
      </div>
      {open ? <GateModal gate="GATE_1_DOSSIER" caseId={ws.caseId} open onClose={() => setOpen(false)} /> : null}
    </div>
  );
}

export default ChangeBanner;
