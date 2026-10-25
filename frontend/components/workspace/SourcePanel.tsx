"use client";
// The source panel: what lies behind a fact, a date or a citation, with the document page beside it. Everything the main
// column leaves out (the quote, the page, how it was read, the language, conflicting values) is here, one click away.
import type { ReactElement, ReactNode } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { sourceLabel as chipLabel } from "@/components/common/SourceChip";
import { Button } from "@/components/ui/button";
import { fieldLabel } from "@/lib/fields";
import { formatCourtDate } from "@/lib/format";
import { langLabel } from "@/lib/labels";
import { FIELD_STATUS_META, getStatusMeta } from "@/lib/status";
import type { SelectedSource, SourceRef } from "@/lib/types";
import { conflictAlternatives, useWorkspace, type DetailTarget } from "@/lib/workspace";
import { PdfViewer } from "./PdfViewer";
import { SidePanel } from "./SidePanel";
import { FieldValue } from "./tabs/FieldValue";
import { SourceQuote } from "./tabs/shared";

function Facts({ rows }: { rows: [string, ReactNode][] }): ReactElement | null {
  const shown = rows.filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (shown.length === 0) return null;
  return (
    <dl className="mt-4 grid grid-cols-[6.5rem_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-sm">
      {shown.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-ink-muted">{k}</dt>
          <dd className="m-0 text-ink-soft">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function asSource(src: SelectedSource | null): SourceRef | null {
  return src ? { doc: src.doc_id, page: src.page, quote: src.quote, quote_en: src.quote_en, lang: src.lang, route: src.route } : null;
}

function FieldDetail({ name }: { name: Extract<DetailTarget, { kind: "field" }>["name"] }): ReactElement | null {
  const ws = useWorkspace();
  const field = ws.data.dossier?.fields[name];
  if (!field) return null;
  const meta = FIELD_STATUS_META[field.status];
  const alternatives = field.status === "AMBIGUOUS" ? conflictAlternatives(field.value, ws.data.dates) : [];
  const source = field.source;
  return (
    <>
      <h3 className="font-display text-xl font-semibold text-ink">{fieldLabel(name)}</h3>
      <div className="mt-2">
        <FieldValue name={name} value={field.value} />
      </div>
      <p className="mt-3 text-sm">
        <StatusBadge status={field.status} kind="field" /> <span className="text-ink-soft">{meta.description}</span>
      </p>
      {alternatives.length > 0 ? (
        <div className="mt-4 border-l-2 border-haldi pl-3" role="group" aria-label="What the other documents say">
          <p className="text-sm font-medium text-ink">Another document says</p>
          <ul className="mt-1 space-y-1.5">
            {alternatives.map((alt) => (
              <li key={alt.event_id} className="text-sm text-ink-soft">
                <span className="tabular text-ink">{formatCourtDate(alt.date)}</span>, {alt.label}
                {alt.source ? (
                  <Button variant="link" size="sm" className="ml-2 h-auto p-0" onClick={() => ws.selectSource(alt.source as SourceRef, alt.label)}>
                    Show page
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {source?.quote ? <SourceQuote source={source} className="mt-4" /> : null}
      <Facts
        rows={[
          ["Page", source?.doc ? chipLabel(source) : null],
          ["Read by", source?.route ?? null],
          ["Language", source?.lang ? langLabel(source.lang) : null],
          ["Calculated by", source?.tool ?? null],
          ["Entered", source?.chat ? `In the chat, ${source.chat}` : null],
        ]}
      />
      {!source || (!source.doc && !source.tool && !source.chat) ? (
        <p className="mt-4 text-sm text-ink-soft">
          {field.status === "USER_EDITED" || field.status === "USER_STATED" ? "You entered this value. No court record backs it." : "There is no page behind this value."}
        </p>
      ) : null}
    </>
  );
}

function DateDetail({ target, src }: { target: Extract<DetailTarget, { kind: "date" }>; src: SelectedSource | null }): ReactElement {
  return (
    <>
      <h3 className="font-display text-xl font-semibold text-ink">{target.label}</h3>
      <p className="mt-1 text-ink">
        <time dateTime={target.date} className="tabular">{formatCourtDate(target.date)}</time>
      </p>
      <p className="mt-2 text-sm">
        <StatusBadge status={target.status} kind="field" />
      </p>
      {src?.quote ? <SourceQuote source={asSource(src)} className="mt-4" /> : null}
      <Facts rows={[["Page", src ? chipLabel({ doc: src.doc_id, page: src.page }) : null], ["Read by", src?.route ?? null], ["Language", src?.lang ? langLabel(src.lang) : null]]} />
    </>
  );
}

function AuthorityDetail({ authority, onPage }: { authority: Extract<DetailTarget, { kind: "authority" }>["authority"]; onPage: boolean }): ReactElement {
  const transfer = authority.transfer ? getStatusMeta(authority.transfer, "transfer") : null;
  const goodLaw = getStatusMeta(authority.good_law, "goodLaw");
  return (
    <>
      <h3 className="font-display text-xl font-semibold text-ink">{authority.citation ?? authority.doc_id}</h3>
      <p className="mt-1 text-ink-soft">
        Paragraph <span className="tabular">{authority.para}</span>
        {authority.sc_root ? `, rooted in ${authority.sc_root}` : ""}
      </p>
      <ul className="mt-3 space-y-2 text-sm">
        <li>
          <StatusBadge status={authority.good_law} kind="goodLaw" /> <span className="text-ink-soft">{goodLaw.description}</span>
        </li>
        {transfer && authority.transfer ? (
          <li>
            <StatusBadge status={authority.transfer} kind="transfer" /> <span className="text-ink-soft">{transfer.description}</span>
          </li>
        ) : null}
      </ul>
      {!onPage ? <p className="mt-4 text-sm text-ink-soft">This is a judgment from the authorities library, not a page in the case file.</p> : null}
    </>
  );
}

export interface SourcePanelProps {
  caseId: string;
}

export function SourcePanel({ caseId }: SourcePanelProps): ReactElement {
  const ws = useWorkspace();
  const { detail, selectedSource: src } = ws;
  return (
    <SidePanel title="Source" onClose={ws.closePanel} testId="source-panel">
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {detail ? (
          <div className="shrink-0 px-5 py-5">
            {detail.kind === "field" ? <FieldDetail name={detail.name} /> : null}
            {detail.kind === "date" ? <DateDetail target={detail} src={src} /> : null}
            {detail.kind === "authority" ? <AuthorityDetail authority={detail.authority} onPage={Boolean(src)} /> : null}
          </div>
        ) : null}
        {src ? (
          <div className="flex min-h-[28rem] flex-1 flex-col border-t border-line">
            <PdfViewer caseId={caseId} />
          </div>
        ) : null}
      </div>
    </SidePanel>
  );
}

export default SourcePanel;
