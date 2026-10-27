// The built-in sample case (case-0007, State v. Accused-1). It exists in the browser's sample-data mode and in the mocked
// backend; a strict live build ("NEXT_PUBLIC_API_MODE=live", the product default) shows only the server's cases, so links
// to the sample case fall back to the in-page walkthrough there.
import { API_SETTING } from "./api";

export const SAMPLE_CASE_ID = "case-0007";
export const SAMPLE_CASE_TITLE = "State v. Accused-1";

/** True when /case/case-0007 can open (sample data allowed, or the session may fall back to it). */
export const SAMPLE_CASE_OPENS = API_SETTING !== "live";

/** Where "Try the sample case" goes: the case itself, or the walkthrough on the landing page in a strict live build. */
export function sampleCaseHref(fallback = "#walk"): string {
  return SAMPLE_CASE_OPENS ? `/case/${SAMPLE_CASE_ID}` : fallback;
}
