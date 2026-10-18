"use client";
// Change banner (plan §7.4, §10): when a new document or the passing of time changes the dossier or the Rights Radar, the
// change set waits for counsel's re-approval of Gate 1. It names every changed field and check in words (never colour alone).
import { RefreshCw } from "lucide-react";
import { useState, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { fieldLabel } from "@/lib/fields";
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
    <div
      role="status"
      data-testid="change-banner"
      className={cn("shrink-0 border-b border-haldi bg-haldi/[0.1] px-4 py-2.5", className)}
    >
      <p className="flex items-center gap-2 text-sm font-semibold text-ink">
        <RefreshCw aria-hidden className="size-4 text-haldi" />
        Changed since you last approved: {fields.length + rights.length} item{fields.length + rights.length === 1 ? "" : "s"}
      </p>
      <p className="mt-0.5 text-xs text-ink-soft">
        Peshkar found changes caused by {trigger}. Check them, then approve the dossier again. Only the grounds that depend on them are redrafted.
      </p>
      <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="What changed">
        {fields.map((f) => (
          <li key={`f-${f}`} data-testid="change-item" data-kind="field" data-name={f} className="rounded-pill border border-haldi/60 bg-cream px-2 py-1 text-xs font-medium text-ink">
            <span className="text-ink-soft">Field: </span>
            {fieldLabel(f)}
          </li>
        ))}
        {rights.map((r) => (
          <li key={`r-${r}`} data-testid="change-item" data-kind="right" data-name={r} className="rounded-pill border border-haldi/60 bg-cream px-2 py-1 text-xs font-medium text-ink">
            <span className="text-ink-soft">Right: </span>
            {RIGHTS_CHECK_LABELS[r as RightsCheckName] ?? r}
          </li>
        ))}
      </ul>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button size="sm" onClick={() => setOpen(true)} aria-haspopup="dialog">
          Review and approve again
        </Button>
        {ws.changedFields.length > 0 ? (
          <Button size="sm" variant="ghost" onClick={ws.clearChangedFields}>
            Hide field highlights
          </Button>
        ) : null}
      </div>
      {open ? <GateModal gate="GATE_1_DOSSIER" caseId={ws.caseId} open onClose={() => setOpen(false)} /> : null}
    </div>
  );
}

export default ChangeBanner;
