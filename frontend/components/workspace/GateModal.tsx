"use client";
// Approval checklist (plan §13.5, §16). Approve stays disabled until every UNSUPPORTED field is resolved or acknowledged
// and every NEEDS_REVIEW and UNANSWERED item is resolved. Each item links to the place where counsel resolves it. Approval
// is counsel's own action: the system never approves. Export stays disabled, with the reason, until Gate 2 is approved.
import { ArrowUpRight, Diamond, Download, ShieldCheck } from "lucide-react";
import { useEffect, useState, type ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { errorMessage } from "@/lib/errors";
import { TAB_LABELS, GATE_LABELS } from "@/lib/stages";
import { GATE_STATUS_META } from "@/lib/status";
import type { GateId } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useGateChecklist, useWorkspace, type ChecklistItem } from "@/lib/workspace";

export interface GateModalProps {
  gate: GateId;
  caseId: string;
  open: boolean;
  onClose: () => void;
  className?: string;
}

const KIND_COPY: Record<ChecklistItem["kind"], { status: string; heading: string; rule: string }> = {
  UNSUPPORTED: { status: "UNSUPPORTED", heading: "Unsupported fields", rule: "Edit or state the value, or acknowledge that it stays unsupported." },
  NEEDS_REVIEW: { status: "NEEDS_REVIEW", heading: "Needs review", rule: "Must be resolved: reword, accept with a note, or remove from the draft." },
  UNANSWERED: { status: "UNANSWERED", heading: "Unanswered objections", rule: "Must be resolved: write a reply or accept the point." },
};

export function GateModal({ gate, open, onClose, className }: GateModalProps): ReactElement {
  const ws = useWorkspace();
  const checklist = useGateChecklist(gate);
  const [busy, setBusy] = useState<"approve" | "export" | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const { refresh } = ws;
  // The checklist is re-read from the backend every time the modal opens, so it never shows a stale list.
  useEffect(() => {
    if (open) void refresh(["gates", "dossier", "brief", "spar"]);
  }, [open, refresh]);
  const label = GATE_LABELS[gate];
  const ui = GATE_STATUS_META[checklist.uiStatus];
  const isGate2 = gate === "GATE_2_EXPORT";
  const groups = (["UNSUPPORTED", "NEEDS_REVIEW", "UNANSWERED"] as const)
    .map((kind) => ({ kind, items: checklist.items.filter((i) => i.kind === kind) }))
    .filter((g) => g.items.length > 0);
  const resolvedCount = checklist.items.length - checklist.blocking.length;

  const approve = async () => {
    setBusy("approve");
    setMessage(null);
    try {
      await ws.approveGate(gate);
      // The diamond on the rail now shows the approval; the modal has done its job.
      onClose();
    } catch (e) {
      setMessage({ tone: "error", text: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };

  const doExport = async () => {
    setBusy("export");
    setMessage(null);
    try {
      const files = await ws.exportCase("DOCX");
      setMessage({ tone: "ok", text: `Exported ${files.length} file${files.length === 1 ? "" : "s"}.` });
    } catch (e) {
      setMessage({ tone: "error", text: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };

  const go = (item: ChecklistItem) => {
    onClose();
    ws.focusItem(item.target.tab, item.target.id);
  };

  const approveReason = checklist.approved
    ? "Already approved."
    : !checklist.reachable
      ? "Approve Gate 1 first."
      : checklist.blocking.length > 0
        ? `${checklist.blocking.length} item${checklist.blocking.length === 1 ? "" : "s"} still to resolve.`
        : !checklist.canApprove
          ? checklist.summary
          : "";
  const exportReason = ws.canExport
    ? ""
    : isGate2 && checklist.reachable
      ? "Export is locked until counsel approves Gate 2."
      : "Export is locked until counsel approves Gate 1 and Gate 2.";

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="lg" data-testid="gate-modal" className={className} aria-describedby="gate-desc">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Diamond aria-hidden className="size-4 fill-maroon text-maroon" />
            <span className="text-xs font-semibold uppercase tracking-caps text-ink-soft">{label.short}</span>
            <StatusBadge status={checklist.uiStatus} kind="gate" size="sm" />
          </div>
          <DialogTitle>{label.label}</DialogTitle>
          <DialogDescription id="gate-desc">
            {label.description} {checklist.summary}
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
          {groups.length === 0 ? (
            <p className="rounded-md border border-neem/40 bg-neem/[0.06] p-3 text-sm text-ink">
              {checklist.reachable
                ? "Nothing to resolve: no unsupported fields" + (isGate2 ? ", needs-review items or unanswered objections." : ".")
                : "Gate 2 opens once Gate 1 is approved."}
            </p>
          ) : (
            <>
              <p className="mb-3 text-xs text-ink-soft" aria-live="polite">
                {resolvedCount} of {checklist.items.length} resolved. Approval is enabled only when all are resolved or acknowledged.
              </p>
              <div className="flex flex-col gap-5">
                {groups.map(({ kind, items }) => (
                  <section key={kind} aria-labelledby={`gate-${kind}`}>
                    <h3 id={`gate-${kind}`} className="font-display text-sm font-semibold text-maroon">
                      {KIND_COPY[kind].heading} <span className="font-sans text-xs font-normal text-ink-soft">({items.filter((i) => i.resolved).length}/{items.length})</span>
                    </h3>
                    <p className="mb-2 text-xs text-ink-soft">{KIND_COPY[kind].rule}</p>
                    <ul className="flex flex-col gap-2">
                      {items.map((item) => (
                        <li
                          key={item.key}
                          data-testid="gate-checklist-item"
                          data-kind={item.kind.toLowerCase()}
                          data-item={item.ref}
                          className={cn(
                            "flex flex-wrap items-start gap-x-3 gap-y-2 rounded-md border p-3",
                            item.resolved ? "border-neem/40 bg-neem/[0.05]" : "border-line-strong/60 bg-cream",
                          )}
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              {item.resolved ? (
                                <StatusBadge status="OK" kind="rights" label={item.resolution === "acknowledged" ? "Acknowledged" : "Resolved"} size="sm" />
                              ) : (
                                <StatusBadge status={KIND_COPY[item.kind].status} size="sm" />
                              )}
                              <span className="text-sm font-medium text-ink">{item.label}</span>
                            </div>
                            {item.detail ? <p className="mt-1 text-xs text-ink-soft">{item.detail}</p> : null}
                            {item.note ? <p className="mt-1 text-xs italic text-ink-soft">Counsel&apos;s note: {item.note}</p> : null}
                          </div>
                          <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                            <Button variant="secondary" size="sm" onClick={() => go(item)}>
                              Go to {TAB_LABELS[item.target.tab]} <ArrowUpRight aria-hidden />
                            </Button>
                            {item.canAcknowledge && (item.resolution === null || item.resolution === "acknowledged") ? (
                              <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-sm px-1.5 py-1 text-xs font-semibold text-ink hover:bg-parchment-deep">
                                <input
                                  type="checkbox"
                                  className="size-4 accent-maroon"
                                  checked={item.resolution === "acknowledged"}
                                  onChange={(e) => (e.target.checked ? ws.acknowledge(item.key) : ws.unacknowledge(item.key))}
                                />
                                Acknowledge: stays unsupported
                              </label>
                            ) : null}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
            </>
          )}

          <div className="mt-5 rounded-md border border-line bg-parchment/70 p-3 text-xs text-ink-soft">
            <p className="flex items-center gap-1.5 font-semibold text-ink">
              <ShieldCheck aria-hidden className="size-4 text-maroon" /> Counsel approves, not the system
            </p>
            <p className="mt-1">
              The approval below is recorded as your action. Every draft is AI-generated, built from the record, and must be reviewed before anything is filed.
            </p>
          </div>
          {message ? (
            <p role="status" className={cn("mt-3 text-sm font-medium", message.tone === "ok" ? "text-neem" : "text-sindoor")}>
              {message.text}
            </p>
          ) : null}
        </DialogBody>

        <DialogFooter className="flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 text-xs text-ink-soft">
            {isGate2 ? (
              <>
                <Button variant="secondary" size="sm" onClick={doExport} disabled={!ws.canExport || busy !== null} aria-describedby="export-reason">
                  <Download aria-hidden /> Export DOCX and card
                </Button>
                <p id="export-reason" className="mt-1.5">
                  {ws.canExport ? "Gate 2 is approved: export is open." : exportReason}
                </p>
              </>
            ) : (
              <p id="export-reason">{exportReason} Drafting opens after this gate.</p>
            )}
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Badge variant="outline" size="md" className="hidden sm:inline-flex">
              {ui.label}
            </Badge>
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
            <Button data-testid="gate-approve-button" onClick={approve} disabled={!checklist.canApprove || busy !== null} aria-describedby="approve-reason">
              <Diamond aria-hidden className="fill-current" />
              {checklist.approved ? "Approved" : busy === "approve" ? "Approving…" : `Approve ${label.short}`}
            </Button>
            <span id="approve-reason" className="sr-only">
              {approveReason}
            </span>
          </div>
        </DialogFooter>
        {!checklist.canApprove && approveReason ? (
          <p className="border-t border-line bg-parchment/60 px-5 py-2 text-xs text-ink-soft" aria-hidden>
            Approve is disabled: {approveReason}
          </p>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

export default GateModal;
