"use client";
// Export (plan §16): approve the draft (Gate 2), then export. Export stays disabled, with the reason, until the draft is
// approved. Anything still unresolved is listed first, each with a jump to where it is fixed.
import { Download } from "lucide-react";
import { useState, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/errors";
import { DRAFT_LABEL, type ExportFormat } from "@/lib/types";
import { plural } from "@/lib/format";
import { useGateChecklist, useNeedsYou, useWorkspace } from "@/lib/workspace";
import { GateModal } from "../GateModal";
import { NeedsYou } from "../NeedsYou";
import { StepFooter, StepFrame } from "../StepFrame";
import { InlineNote, stepState } from "./shared";

export function ExportTab({ caseId }: { caseId: string }): ReactElement {
  const ws = useWorkspace();
  const toast = useToast();
  const gate2 = useGateChecklist("GATE_2_EXPORT");
  const needs = useNeedsYou("FILE");
  const [gateOpen, setGateOpen] = useState(false);
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const brief = ws.data.brief;

  const state = stepState({
    resource: "brief", noun: "draft", loading: ws.loading.brief, error: ws.errors.brief, hasData: Boolean(brief),
    onRetry: () => void ws.refresh(["brief"]),
    emptyTitle: "There is no draft to export",
    emptyBody: "Draft the grounds first.",
    emptyAction: <Button variant="secondary" onClick={() => ws.setStage("BRIEF")}>Go to Draft grounds</Button>,
  });
  if (state || !brief) {
    return (
      <StepFrame title="Export" intro="Approve the draft, then export it.">
        {state}
      </StepFrame>
    );
  }

  const run = async (format: ExportFormat) => {
    setBusy(format);
    setMessage(null);
    try {
      const files = await ws.exportCase(format);
      toast(`Exported ${plural(files.length, "file")}`);
    } catch (e) {
      setMessage(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const approved = gate2.approved;
  const blocked = gate2.blocking.length > 0;

  return (
    <StepFrame
      title="Export"
      intro={approved ? "The draft is approved. Export it when you are ready." : "Approve the draft, then export it."}
      footer={
        approved ? (
          <StepFooter
            label={busy === "DOCX" ? "Exporting" : "Export as Word file"}
            onClick={() => void run("DOCX")}
            busy={busy !== null}
            next={false}
            testId="export-button"
            secondary={
              <Button variant="secondary" size="lg" onClick={() => void run("PDF")} disabled={busy !== null}>
                <Download aria-hidden /> {busy === "PDF" ? "Exporting" : "Export as PDF"}
              </Button>
            }
          />
        ) : (
          <StepFooter
            label="Approve this draft for export"
            onClick={() => setGateOpen(true)}
            disabled={blocked}
            hint={blocked ? `${plural(gate2.blocking.length, "item")} above ${gate2.blocking.length === 1 ? "needs" : "need"} you before you can approve.` : undefined}
            next={false}
            testId="approve-export-button"
          />
        )
      }
    >
      <p role="note" className="text-sm font-medium text-maroon">
        {brief.label || DRAFT_LABEL}
      </p>
      <NeedsYou items={needs} empty={approved ? "Nothing needs your attention." : "Nothing needs your attention. Approve the draft when you are satisfied with it."} />
      <p className="text-ink-soft">The files carry the label above. Your court&apos;s own rules still apply.</p>
      {message ? <InlineNote>{message}</InlineNote> : null}
      {ws.exports.length > 0 ? (
        <section aria-labelledby="exported-title">
          <h3 id="exported-title" className="font-sans text-sm font-semibold text-ink">Exported files</h3>
          <ul className="mt-2 divide-y divide-line border-y border-line">
            {ws.exports.map((f) => (
              <li key={f} className="py-2.5">
                <a data-testid="export-link" href={f} download className="cite text-maroon underline underline-offset-4">
                  {f.split("/").pop() || f}
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <GateModal gate="GATE_2_EXPORT" caseId={caseId} open={gateOpen} onClose={() => setGateOpen(false)} />
    </StepFrame>
  );
}

export default ExportTab;
