"use client";
// The confirm dialog for the two gates (plan §13.5, §16): "Confirm these facts" and "Approve this draft for export". It says what
// will be locked and lists anything that still needs the lawyer, each with a jump to it. Confirming is the lawyer's own action:
// the system never approves. Confirm stays disabled until every item is dealt with.
import { useEffect, useState, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/errors";
import { dossierEntries } from "@/lib/fields";
import { plural } from "@/lib/format";
import { GATE_LABELS, nextStep } from "@/lib/stages";
import { DRAFT_LABEL, type GateId } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useGateChecklist, useWorkspace, type ChecklistItem } from "@/lib/workspace";

export interface GateModalProps {
  gate: GateId;
  caseId: string;
  open: boolean;
  onClose: () => void;
  className?: string;
}

export function GateModal({ gate, open, onClose, className }: GateModalProps): ReactElement {
  const ws = useWorkspace();
  const toast = useToast();
  const checklist = useGateChecklist(gate);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { refresh } = ws;
  // The checklist is re-read from the backend every time the dialog opens, so it never shows a stale list.
  useEffect(() => {
    if (open) {
      setError(null);
      void refresh(["gates", "dossier", "brief", "spar"]);
    }
  }, [open, refresh]);

  const label = GATE_LABELS[gate];
  const isGate2 = gate === "GATE_2_EXPORT";
  const pending = checklist.items.filter((i) => !i.resolved);
  const done = checklist.items.filter((i) => i.resolved);
  const facts = ws.data.dossier ? dossierEntries(ws.data.dossier).length : 0;
  const events = ws.data.dates?.length ?? 0;
  const grounds = ws.data.brief?.grounds.length ?? 0;
  const objections = ws.data.spar?.objections.length ?? 0;

  const locks = isGate2
    ? [
        `${plural(grounds, "ground")} as worded now.`,
        objections > 0 ? `Your replies to ${plural(objections, "likely objection")}.` : "Your notes on the draft.",
        "Export opens once you approve.",
      ]
    : [
        `${plural(facts, "fact")} as shown. Changing one later asks you to confirm again.`,
        events > 0 ? `The List of Dates, ${plural(events, "event")}.` : "The List of Dates.",
        "Drafting starts from these facts.",
      ];

  const approve = async () => {
    setBusy(true);
    setError(null);
    try {
      await ws.approveGate(gate);
      onClose();
      toast(isGate2 ? "Draft approved for export" : "Facts confirmed");
      const next = isGate2 ? null : nextStep("DOSSIER");
      if (next) ws.goToWhenOpen(next);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const go = (item: ChecklistItem) => {
    onClose();
    ws.focusItem(item.target.tab, item.target.id, item.kind === "UNSUPPORTED" ? "edit" : undefined);
  };

  const why = checklist.approved
    ? "Already confirmed."
    : !checklist.reachable
      ? "Confirm the facts first."
      : checklist.blocking.length > 0
        ? `${plural(checklist.blocking.length, "item")} still ${checklist.blocking.length === 1 ? "needs" : "need"} you.`
        : !checklist.canApprove
          ? checklist.summary
          : "";

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="lg" data-testid="gate-modal" className={className} aria-describedby="gate-desc">
        <DialogHeader>
          <DialogTitle>{label.label}</DialogTitle>
          <DialogDescription id="gate-desc">{label.description}</DialogDescription>
        </DialogHeader>

        <DialogBody className="flex flex-col gap-6">
          {pending.length > 0 ? (
            <section aria-labelledby="gate-open">
              <h3 id="gate-open" className="font-sans text-sm font-semibold text-ink">Still needs you</h3>
              <ul className="mt-2 divide-y divide-line border-y border-line">
                {pending.map((item) => (
                  <li key={item.key} data-testid="gate-checklist-item" data-kind={item.kind.toLowerCase()} data-item={item.ref} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-ink">{item.label}</p>
                      {item.detail ? <p className="mt-0.5 text-sm text-ink-soft">{item.detail}</p> : null}
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-2">
                      {item.canAcknowledge ? (
                        <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-sm px-1.5 py-1 text-sm text-ink hover:bg-parchment-deep">
                          <input
                            type="checkbox"
                            className="size-4 accent-maroon"
                            checked={item.resolution === "acknowledged"}
                            onChange={(e) => (e.target.checked ? ws.acknowledge(item.key) : ws.unacknowledge(item.key))}
                          />
                          Mark as unknown
                        </label>
                      ) : null}
                      <Button variant="secondary" size="sm" onClick={() => go(item)}>
                        Go to it
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {done.length > 0 ? (
            <section aria-labelledby="gate-done">
              <h3 id="gate-done" className="font-sans text-sm font-semibold text-ink">Dealt with</h3>
              <ul className="mt-2 divide-y divide-line border-y border-line">
                {done.map((item) => (
                  <li key={item.key} data-testid="gate-checklist-item" data-kind={item.kind.toLowerCase()} data-item={item.ref} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5">
                    <p className="min-w-0 flex-1 text-ink-soft">{item.label}</p>
                    <span className="text-sm text-ink-muted">{item.resolution === "acknowledged" ? "Marked as unknown" : "Reviewed"}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section aria-labelledby="gate-locks">
            <h3 id="gate-locks" className="font-sans text-sm font-semibold text-ink">What this locks</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-soft">
              {locks.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </section>

          {isGate2 ? <p className="text-sm font-medium text-maroon">{ws.data.brief?.label || DRAFT_LABEL}</p> : null}
          {error ? (
            <p role="alert" className={cn("text-sm font-medium text-sindoor")}>
              {error}
            </p>
          ) : null}
        </DialogBody>

        <DialogFooter>
          {!checklist.canApprove && why ? <p className="mr-auto text-sm text-ink-soft" aria-hidden>{why}</p> : null}
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button data-testid="gate-approve-button" onClick={approve} disabled={!checklist.canApprove || busy} aria-describedby="approve-reason">
            {checklist.approved ? "Confirmed" : busy ? "Saving" : isGate2 ? "Approve for export" : "Confirm facts"}
          </Button>
          <span id="approve-reason" className="sr-only">
            {why}
          </span>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default GateModal;
