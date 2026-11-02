// The rights timeline (landing "Check" demo and the workspace's Check rights step): where the default-bail window
// (BNSS s.187) and the undertrial limit (BNSS s.479) fall on the calendar of a case, and what each says on a chosen
// hearing date. Pure functions over the Rights Radar's own dates; nothing here is a forecast. A range that depends on a
// fact the papers do not give is a "Check", never "Open".
import type { RightsReport } from "./types";

export interface TimelineInput {
  arrest: string;
  asOf: string;
  firstRemand: string | null;
  /** Day 60 or day 90 from the first remand (the last day of the limit), as the Rights Radar computed it. */
  limitEnd: string | null;
  limitDays: 60 | 90 | null;
  chargeSheet: string | null;
  defaultStatus: string;
  oneThird: string | null;
  oneHalf: string | null;
  undertrialStatus: string;
  /** False when the papers do not say whether the accused has other cases (the one-third rule needs it). */
  antecedentsKnown: boolean;
}

const DAY = 86_400_000;
const t = (iso: string) => Date.parse(`${iso}T00:00:00Z`);

export function addDays(iso: string, n: number): string {
  return new Date(t(iso) + n * DAY).toISOString().slice(0, 10);
}

export function diffDays(a: string, b: string): number {
  return Math.round((t(b) - t(a)) / DAY);
}

export function courtDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

const n = (x: number) => x.toLocaleString("en-IN");

/** Dates the dossier gives, used when a report carries no `dates` of its own. */
export interface DossierDates {
  arrest?: string | null;
  firstRemand?: string | null;
  chargeSheet?: string | null;
}

const num = (s: string) => Number(s.replace(/,/g, ""));

/**
 * Read the timeline's dates from a Rights Radar report; null when the arrest date is missing. A report without `dates`
 * (the API may omit them) falls back to the dossier's dates and to the day counts the Radar states in its own detail
 * ("60-day limit", "852 days ... and 1,278 days"); nothing is worked out from the law here.
 */
export function timelineFromReport(report: RightsReport, antecedentsKnown: boolean, dossier: DossierDates = {}): TimelineInput | null {
  const def = report.checks.find((c) => c.check === "default_bail");
  const ut = report.checks.find((c) => c.check === "undertrial_limit");
  const arrest = ut?.dates?.arrest_date ?? def?.dates?.arrest_date ?? dossier.arrest ?? null;
  if (!arrest) return null;
  const firstRemand = def?.dates?.first_remand ?? dossier.firstRemand ?? null;
  let limitEnd = def?.dates?.day_60 ?? def?.dates?.day_90 ?? null;
  let limitDays: 60 | 90 | null = def?.dates?.day_60 ? 60 : def?.dates?.day_90 ? 90 : null;
  const stated = /\b(60|90)-day limit/.exec(def?.detail ?? "");
  if (!limitEnd && stated && firstRemand) {
    limitDays = Number(stated[1]) as 60 | 90;
    limitEnd = addDays(firstRemand, limitDays - 1); // day 1 is the first remand
  }
  let oneThird = ut?.dates?.one_third ?? null;
  let oneHalf = ut?.dates?.one_half ?? null;
  const thresholds = /([\d,]+) days for a first-time offender.*?([\d,]+) days otherwise/.exec(ut?.detail ?? "");
  if ((!oneThird || !oneHalf) && thresholds) {
    oneThird = addDays(arrest, num(thresholds[1]!));
    oneHalf = addDays(arrest, num(thresholds[2]!));
  }
  return {
    arrest,
    asOf: report.as_of,
    firstRemand,
    limitEnd,
    limitDays,
    chargeSheet: def?.dates?.charge_sheet ?? dossier.chargeSheet ?? null,
    defaultStatus: def?.status ?? "UNKNOWN",
    oneThird,
    oneHalf,
    undertrialStatus: ut?.status ?? "UNKNOWN",
    antecedentsKnown,
  };
}

export interface LaneState {
  /** One plain word: Closed, Check, Not yet, Open, Does not apply. */
  word: "Closed" | "Check" | "Not yet" | "Open" | "Does not apply";
  sentence: string;
}

export interface StateAt {
  date: string;
  custodyDays: number;
  defaultBail: LaneState;
  undertrial: LaneState;
}

/** What each right says on `date`. */
export function stateAt(x: TimelineInput, date: string): StateAt {
  const custodyDays = diffDays(x.arrest, date);
  return { date, custodyDays, defaultBail: defaultBailAt(x, date), undertrial: undertrialAt(x, date, custodyDays) };
}

function defaultBailAt(x: TimelineInput, date: string): LaneState {
  if (!x.limitEnd || !x.firstRemand) return { word: "Check", sentence: "The first remand date is not in the papers, so the default-bail limit cannot be counted." };
  const opens = addDays(x.limitEnd, 1);
  if (x.chargeSheet) {
    const csDay = diffDays(x.firstRemand, x.chargeSheet) + 1;
    if (x.chargeSheet <= x.limitEnd) {
      return { word: "Does not apply", sentence: `The charge sheet was filed on ${courtDate(x.chargeSheet)}, day ${csDay}, within the ${x.limitDays}-day limit.` };
    }
    if (date < opens) return { word: "Not yet", sentence: `The ${x.limitDays}-day limit ends on ${courtDate(x.limitEnd)}; the window opens the next day unless a charge sheet is filed first.` };
    if (date < x.chargeSheet) return { word: x.defaultStatus === "ELIGIBLE" ? "Open" : "Check", sentence: `Open from ${courtDate(opens)} until a charge sheet is filed. It was filed on ${courtDate(x.chargeSheet)}.` };
    return {
      word: "Closed",
      sentence: `Closed on ${courtDate(x.chargeSheet)}, when the charge sheet was filed on day ${csDay}. It was open on days ${x.limitDays! + 1} to ${csDay - 1}: check whether an application was made then.`,
    };
  }
  if (date < opens) return { word: "Not yet", sentence: `The ${x.limitDays}-day limit ends on ${courtDate(x.limitEnd)}.` };
  return {
    word: x.defaultStatus === "ELIGIBLE" ? "Open" : "Check",
    sentence: `From ${courtDate(opens)} the window is open unless a charge sheet was filed. The papers do not give a charge-sheet date.`,
  };
}

function undertrialAt(x: TimelineInput, date: string, days: number): LaneState {
  if (x.undertrialStatus === "NOT_APPLICABLE") return { word: "Does not apply", sentence: "Not available for offences punishable with death or life imprisonment." };
  if (!x.oneThird || !x.oneHalf) return { word: "Check", sentence: "The maximum sentence is not clear from the sections, so the thresholds cannot be dated." };
  const third = diffDays(x.arrest, x.oneThird);
  const half = diffDays(x.arrest, x.oneHalf);
  if (date < x.oneThird) {
    return { word: "Not yet", sentence: `Day ${n(days)} of custody. One-third of the maximum is day ${n(third)} (${courtDate(x.oneThird)}); one-half is day ${n(half)} (${courtDate(x.oneHalf)}).` };
  }
  if (date < x.oneHalf) {
    return x.antecedentsKnown
      ? { word: "Check", sentence: `Past one-third of the maximum (${courtDate(x.oneThird)}), which is enough for a first-time offender. Confirm from the record.` }
      : { word: "Check", sentence: `Past one-third of the maximum (${courtDate(x.oneThird)}). That is enough only for a first-time offender, and the papers do not say whether the accused has other cases. One-half is ${courtDate(x.oneHalf)}.` };
  }
  return { word: "Check", sentence: `Past one-half of the maximum (${courtDate(x.oneHalf)}), the limit for every undertrial under this section. Confirm the custody period from the record.` };
}

/** Position of a date on [start, end] as a fraction (clamped). */
export function fraction(date: string, start: string, end: string): number {
  return Math.min(1, Math.max(0, (t(date) - t(start)) / (t(end) - t(start))));
}

/** The date at a fraction of [start, end], rounded to the day. */
export function dateAt(f: number, start: string, end: string): string {
  return addDays(start, Math.round(f * diffDays(start, end)));
}
