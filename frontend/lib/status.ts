// Status presentation map (plan §13.2): each status ALWAYS shows an icon and a label, never colour alone.
import type { ClaimCheck, FieldStatus, RightsStatus, SparringVerdict } from "./types";

export type AnyStatus = FieldStatus | RightsStatus | ClaimCheck | SparringVerdict;
export interface StatusMeta { colorVar: string; icon: string; label: string }

export const STATUS_META: Record<string, StatusMeta> = {
  VERIFIED: { colorVar: "--color-neem", icon: "✔", label: "Verified" },
  SUPPORTED: { colorVar: "--color-neem", icon: "✔", label: "Supported" },
  OK: { colorVar: "--color-neem", icon: "✔", label: "OK" },
  COMPUTED: { colorVar: "--color-indigo", icon: "ƒ", label: "Computed" },
  UNSUPPORTED: { colorVar: "--color-sindoor", icon: "✖", label: "Unsupported" },
  UNANSWERED: { colorVar: "--color-sindoor", icon: "✖", label: "Unanswered" },
  FLAG: { colorVar: "--color-sindoor", icon: "✖", label: "Flag" },
  AMBIGUOUS: { colorVar: "--color-haldi", icon: "?", label: "Ambiguous" },
  CHECK: { colorVar: "--color-haldi", icon: "?", label: "Check" },
  NEEDS_REVIEW: { colorVar: "--color-haldi", icon: "?", label: "Needs review" },
  UNKNOWN: { colorVar: "--color-haldi", icon: "?", label: "Unknown" },
  USER_STATED: { colorVar: "--color-clay", icon: "✎", label: "Stated by counsel" },
  USER_EDITED: { colorVar: "--color-clay", icon: "✎", label: "Edited by counsel" },
  // TODO: remaining Rights Radar statuses (ELIGIBLE, NOT_YET, WINDOW_CLOSED, NOT_APPLICABLE, BAR_APPLIES, A-D), ANSWERED, PARTLY, REPAIRED
};
