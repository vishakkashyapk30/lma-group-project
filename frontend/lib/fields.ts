// Dossier field helpers (plan §7.1): display order, value formatting, edit parsing and status queries.
import { formatCourtDate } from "./format";
import { DOSSIER_FIELD_LABELS } from "./labels";
import type {
  CaseDossier, ChargeSheetValue, CoAccusedBail, DossierFieldName, DossierFields, FieldStatus, FirValue, PreviousBail,
  SectionValue, TrackedField,
} from "./types";
import { DOSSIER_FIELD_NAMES } from "./types";

/** Display order of the dossier tab (the plan's §7.1 order). */
export const DOSSIER_FIELD_ORDER: readonly DossierFieldName[] = DOSSIER_FIELD_NAMES;

/** Fields whose value is a date string. */
export const DATE_FIELDS: ReadonlySet<DossierFieldName> = new Set(["offence_date", "arrest_date", "first_remand"]);

/** Fields whose value is a list of strings (edited as one item per line). */
export const STRING_LIST_FIELDS: ReadonlySet<DossierFieldName> = new Set(["antecedents", "personal", "parties"]);

const DATE = /^\d{4}-\d{2}-\d{2}$/;

function requireDate(value: string, label: string): string {
  if (!DATE.test(value)) throw new Error(`${label} must use YYYY-MM-DD, for example 2024-08-20.`);
  return value;
}

function lines(text: string): string[] {
  return text.split(/\n+/).map((line) => line.trim()).filter(Boolean);
}

function labelledLines(text: string): Record<string, string> {
  return Object.fromEntries(lines(text).map((line) => {
    const [key, ...rest] = line.split(/:\s*/);
    return [key.toLowerCase(), rest.join(":").trim()];
  }));
}

export function fieldLabel(name: string): string {
  return (DOSSIER_FIELD_LABELS as Record<string, string>)[name] ?? name.replace(/_/g, " ");
}

/** Iterate the dossier's fields in display order. A field the dossier does not carry yet (a fresh case) is skipped. */
export function dossierEntries(dossier: CaseDossier): Array<[DossierFieldName, TrackedField<unknown>]> {
  return DOSSIER_FIELD_ORDER.filter((name) => dossier.fields?.[name] != null).map((name) => [name, dossier.fields[name] as TrackedField<unknown>]);
}

/** Names of fields with a given status. */
export function fieldsWithStatus(dossier: CaseDossier | null | undefined, status: FieldStatus): DossierFieldName[] {
  if (!dossier) return [];
  return DOSSIER_FIELD_ORDER.filter((name) => dossier.fields[name]?.status === status);
}

/** One-line display string for a field value (no status, no source). */
export function formatFieldValue(name: DossierFieldName | string, value: unknown): string {
  if (value === null || value === undefined) return "Not found in the file";
  switch (name) {
    case "fir": {
      const v = value as FirValue;
      const parts = [v.number ? `No. ${v.number}` : null, v.police_station, v.date ? formatCourtDate(v.date) : null];
      return parts.filter(Boolean).join(" · ");
    }
    case "sections": {
      const list = value as SectionValue[];
      return list
        .map((s) => `${s.as_written}${s.equivalent ? ` (≈ ${s.equivalent})` : ""}`)
        .join("; ");
    }
    case "custody_days":
      return `${value} days`;
    case "charge_sheet": {
      const v = value as ChargeSheetValue;
      return v.filed ? `Filed${v.date ? ` on ${formatCourtDate(v.date)}` : ""}` : "Not filed";
    }
    case "previous_bail": {
      const list = value as PreviousBail[];
      if (list.length === 0) return "None";
      return list.map((b) => `${b.court}, ${formatCourtDate(b.date)}: ${b.outcome}`).join("; ");
    }
    case "co_accused_bail": {
      const list = value as CoAccusedBail[];
      if (list.length === 0) return "None";
      return list.map((b) => `${b.id}: ${b.outcome}${b.date ? ` on ${formatCourtDate(b.date)}` : ""}`).join("; ");
    }
    default:
      if (DATE_FIELDS.has(name as DossierFieldName) && typeof value === "string") return formatCourtDate(value);
      if (Array.isArray(value)) return value.length ? value.map(String).join("; ") : "None";
      if (typeof value === "object") return JSON.stringify(value);
      return String(value);
  }
}

/** Secondary details for a sections value: bailable and maximum punishment per section. */
export function sectionDetails(sections: SectionValue[] | null | undefined): string[] {
  return (sections ?? []).map((s) => {
    const bits = [s.max_punishment ? `max ${s.max_punishment}` : null, s.bailable == null ? null : s.bailable ? "bailable" : "non-bailable"];
    return `${s.code} ${s.section}: ${bits.filter(Boolean).join(", ")}`;
  });
}

/** Text shown in an edit box for a field value. */
export function valueToEditText(name: DossierFieldName, value: unknown): string {
  if (value === null || value === undefined) return "";
  if (STRING_LIST_FIELDS.has(name) && Array.isArray(value)) return value.join("\n");
  if (DATE_FIELDS.has(name) && typeof value === "string") return value;
  if (name === "custody_days") return String(value);
  if (name === "fir") {
    const v = value as FirValue;
    return [`Number: ${v.number ?? ""}`, `Police station: ${v.police_station ?? ""}`, `Date: ${v.date ?? ""}`].join("\n");
  }
  if (name === "sections") {
    return (value as SectionValue[]).map((s) => s.as_written).join("\n");
  }
  if (name === "charge_sheet") {
    const v = value as ChargeSheetValue;
    return [`Status: ${v.filed ? "filed" : "not filed"}`, `Date: ${v.date ?? ""}`].join("\n");
  }
  if (name === "previous_bail") {
    return (value as PreviousBail[]).map((b) => `${b.court} | ${b.date} | ${b.outcome}`).join("\n");
  }
  if (name === "co_accused_bail") {
    return (value as CoAccusedBail[]).map((b) => `${b.id} | ${b.outcome} | ${b.date ?? ""}`).join("\n");
  }
  if (typeof value === "string") return value;
  return String(value);
}

/** Parse a counsel-facing edit box back to a typed value; no field asks counsel for JSON. */
export function parseEditText<K extends DossierFieldName>(name: K, text: string): DossierFields[K]["value"] {
  const t = text.trim();
  if (STRING_LIST_FIELDS.has(name)) {
    return t.split(/\n+/).map((s) => s.trim()).filter(Boolean) as DossierFields[K]["value"];
  }
  if (DATE_FIELDS.has(name)) {
    requireDate(t, "Date");
    return t as DossierFields[K]["value"];
  }
  if (name === "custody_days") {
    const n = Number(t);
    if (!Number.isInteger(n) || n < 0) throw new Error("Use a whole number of days.");
    return n as DossierFields[K]["value"];
  }
  if (name === "trial_stage") return t as DossierFields[K]["value"];
  if (name === "fir") {
    const values = labelledLines(t);
    return {
      number: values.number || null,
      police_station: values["police station"] || null,
      date: values.date ? requireDate(values.date, "FIR date") : null,
    } as DossierFields[K]["value"];
  }
  if (name === "sections") {
    const sections = lines(t).map((as_written) => {
      const match = as_written.match(/^(.+?)\s+([\d]+(?:\([^)]*\))?[A-Za-z]?)$/);
      if (!match) throw new Error(`Write each section as a code and section number, for example "NDPS 21(C)": ${as_written}`);
      return { as_written, code: match[1].trim(), section: match[2] };
    });
    if (!sections.length) throw new Error("Add at least one charged section.");
    return sections as DossierFields[K]["value"];
  }
  if (name === "charge_sheet") {
    const values = labelledLines(t);
    const status = values.status?.toLowerCase();
    if (status !== "filed" && status !== "not filed") throw new Error('Status must be "filed" or "not filed".');
    return { filed: status === "filed", date: values.date ? requireDate(values.date, "Charge-sheet date") : null } as DossierFields[K]["value"];
  }
  if (name === "previous_bail") {
    return lines(t).map((line) => {
      const [court, date, outcome, ...extra] = line.split("|").map((part) => part.trim());
      if (!court || !date || !outcome || extra.length) throw new Error("Use one bail order per line: Court | YYYY-MM-DD | granted or rejected.");
      return { court, date: requireDate(date, "Bail-order date"), outcome };
    }) as DossierFields[K]["value"];
  }
  if (name === "co_accused_bail") {
    return lines(t).map((line) => {
      const [id, outcome, rawDate, ...extra] = line.split("|").map((part) => part.trim());
      if (!id || !outcome || extra.length) throw new Error("Use one co-accused per line: Name or alias | granted or rejected | YYYY-MM-DD (optional).");
      return { id, outcome, date: rawDate ? requireDate(rawDate, "Co-accused bail date") : null };
    }) as DossierFields[K]["value"];
  }
  throw new Error("This field cannot be edited here.");
}

/** A plain-language format note shown under a counsel-facing editor. */
export function fieldEditHint(name: DossierFieldName): string {
  if (STRING_LIST_FIELDS.has(name)) return "One item per line.";
  if (DATE_FIELDS.has(name)) return "Use the date picker.";
  if (name === "custody_days") return "A whole number of days.";
  if (name === "trial_stage") return "A short phrase, for example: charges not framed.";
  if (name === "fir") return "Use Number, Police station and Date on separate lines.";
  if (name === "sections") return "One charged section per line, for example: NDPS 21(C).";
  if (name === "charge_sheet") return "Use Status: filed or not filed, then an optional Date: YYYY-MM-DD.";
  if (name === "previous_bail") return "One order per line: Court | YYYY-MM-DD | granted or rejected.";
  if (name === "co_accused_bail") return "One person per line: Name or alias | granted or rejected | YYYY-MM-DD.";
  return "Enter the value in plain language.";
}

/**
 * Mark a field as edited by counsel (plan §7.1: status USER_EDITED). Like the backend (record/views.py), the edited
 * field carries no source: the court record no longer backs the new value.
 */
export function withUserEdit<T>(_field: TrackedField<T>, value: T): TrackedField<T> {
  return { value, source: null, status: "USER_EDITED" };
}
