"use client";
// Add documents (plan §4, §13.5): drop the case papers, see that each was read, and go on. Anything that could not be read
// or that is missing is listed first.
import Link from "next/link";
import type { ReactElement } from "react";
import { useNeedsYou, useWorkspace } from "@/lib/workspace";
import { DocumentList } from "../DocumentList";
import { DropZone } from "../DropZone";
import { NeedsYou } from "../NeedsYou";
import { StepFooter, StepFrame } from "../StepFrame";

export function IntakeTab({ caseId }: { caseId: string }): ReactElement {
  const ws = useWorkspace();
  const needs = useNeedsYou("INTAKE");
  const count = ws.data.ingestion?.documents.length ?? 0;
  const loading = ws.loading.ingestion && !ws.data.ingestion;

  return (
    <StepFrame
      title="Add documents"
      intro="Add the FIR, the remand order and any other papers. Each page is read and filed."
      footer={count > 0 ? <StepFooter label="Continue to Review facts" onClick={() => ws.setStage("DOSSIER")} /> : undefined}
    >
      {count > 0 ? (
        <>
          <NeedsYou items={needs} empty="Every page was read. Nothing needs your attention." />
          <DocumentList caseId={caseId} />
          <DropZone caseId={caseId} compact />
        </>
      ) : loading ? (
        <DocumentList caseId={caseId} />
      ) : (
        <>
          <DropZone caseId={caseId} />
          <p className="text-sm text-ink-soft">
            Your files stay on your machine unless you turn on an external model service, which is off by default and asks for consent.{" "}
            <Link href="/help#privacy">Read about privacy</Link>.
          </p>
        </>
      )}
    </StepFrame>
  );
}

export default IntakeTab;
