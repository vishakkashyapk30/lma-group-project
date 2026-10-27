"use client";
// Check: the sample case's rights on a timeline (components/rights/RightsTimeline), starting on its next hearing.
import type { ReactElement } from "react";
import { RightsTimeline } from "@/components/rights/RightsTimeline";
import { MOCK_RIGHTS } from "@/lib/mock/case0007";
import { timelineFromReport } from "@/lib/rightsTimeline";
import { RIGHTS_DATES } from "../sample";

// The sample's antecedents are not in the papers (dossier field "antecedents" is Not found).
const INPUT = timelineFromReport(MOCK_RIGHTS, false)!;

export function CheckDemo(): ReactElement {
  return <RightsTimeline input={INPUT} initialDate={RIGHTS_DATES.nextHearing} jumps={[{ label: "Next hearing", date: RIGHTS_DATES.nextHearing }]} testId="check-demo" />;
}
