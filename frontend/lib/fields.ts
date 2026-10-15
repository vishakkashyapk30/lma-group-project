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

export function fieldLabel(name: string): string {
  return (DOSSIER_FIELD_LABELS as Record<string, string>)[name] ?? name.replace(/_/g, " ");
}

/** Iterate the dossier's fields in display order. */
export function dossierEntries(dossier: CaseDossier): Array<[DossierFieldName, TrackedField<unknown>]> {
  return DOSSIER_FIELD_ORDER.map((name) => [name, dossier.fields[name] as TrackedField<unknown>]);
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
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

/** Parse an edit box back to a value; throws Error with a readable message when the text does not fit the field. */
export function parseEditText<K extends DossierFieldName>(name: K, text: string): DossierFields[K]["value"] {
  const t = text.trim();
  if (STRING_LIST_FIELDS.has(name)) {
    return t.split(/\n+/).map((s) => s.trim()).filter(Boolean) as DossierFields[K]["value"];
  }
  if (DATE_FIELDS.has(name)) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) throw new Error("Use a date as YYYY-MM-DD, for example 2024-08-20.");
    return t as DossierFields[K]["value"];
  }
  if (name === "custody_days") {
    const n = Number(t);
    if (!Number.isInteger(n) || n < 0) throw new Error("Use a whole number of days.");
    return n as DossierFields[K]["value"];
  }
  if (name === "trial_stage") return t as DossierFields[K]["value"];
  try {
    return JSON.parse(t) as DossierFields[K]["value"];
  } catch {
    throw new Error("This field takes structured data (JSON).");
  }
}

/**
 * Mark a field as edited by counsel (plan §7.1: status USER_EDITED). Like the backend (record/views.py), the edited
 * field carries no source: the court record no longer backs the new value.
 */
export function withUserEdit<T>(_field: TrackedField<T>, value: T): TrackedField<T> {
  return { value, source: null, status: "USER_EDITED" };
}
