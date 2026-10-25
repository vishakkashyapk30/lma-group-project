// A dossier value, one line per item. Rendered as spans so a whole value can sit inside a button.
import type { ReactElement, ReactNode } from "react";
import { formatFieldValue, sectionDetails } from "@/lib/fields";
import { formatCourtDate } from "@/lib/format";
import type { CoAccusedBail, DossierFieldName, PreviousBail, SectionValue } from "@/lib/types";

export function FieldValue({ name, value }: { name: DossierFieldName; value: unknown }): ReactElement {
  if (value === null || value === undefined) {
    return <span className="block text-ink-soft">Not found</span>;
  }
  const line = (key: string | number, text: ReactNode, sub?: ReactNode) => (
    <span key={key} className="block">
      <span className="block text-ink">{text}</span>
      {sub ? <span className="block text-sm text-ink-soft">{sub}</span> : null}
    </span>
  );
  if (name === "sections") {
    const list = value as SectionValue[];
    const details = sectionDetails(list);
    return (
      <span className="block space-y-1">
        {list.map((s, i) => line(i, <span className="cite font-medium">{s.as_written}{s.equivalent ? ` (≈ ${s.equivalent})` : ""}</span>, details[i]))}
      </span>
    );
  }
  if (name === "previous_bail") {
    const list = value as PreviousBail[];
    if (list.length === 0) return line("none", "None on record");
    return <span className="block space-y-1">{list.map((b, i) => line(i, `${b.court}: ${b.outcome}`, formatCourtDate(b.date)))}</span>;
  }
  if (name === "co_accused_bail") {
    const list = value as CoAccusedBail[];
    if (list.length === 0) return line("none", "None on record");
    return <span className="block space-y-1">{list.map((b, i) => line(i, `${b.id}: ${b.outcome}`, b.date ? formatCourtDate(b.date) : null))}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return line("none", "None");
    return <span className="block space-y-0.5">{value.map((v, i) => line(i, String(v)))}</span>;
  }
  return line("v", formatFieldValue(name, value));
}

export default FieldValue;
