// The guided demo of the demo build (NEXT_PUBLIC_API_MODE=demo): one tour over the sample case-0007, in the shape of
// GET /api/demo/tours/{slug}, so the tour works with no server and the specs run offline. The live server serves its own
// tours, recorded on real runs; this one describes the sample data and claims no recording.
import { MOCK_CASE_ID } from "./case0007";

export const MOCK_TOUR_SLUG = "00-sample-cheating-parity";

export const MOCK_TOUR = {
  slug: MOCK_TOUR_SLUG,
  case_id: MOCK_CASE_ID,
  title: "Demo · Cheating with a co-accused on bail (sample case)",
  story:
    "Accused-1 is charged with cheating and criminal breach of trust over one transaction and has been in custody since August 2024. The co-accused was granted bail in December and the charge sheet is filed. The file does not say whether there are other pending cases.",
  variant: {
    offence: "Cheating and criminal breach of trust, BNS 318(4) and 316(2)",
    custody: "In custody since 20 Aug 2024, 167 days on the as-of date",
    record: "Clean papers; antecedents not in the file",
    parity: "Co-accused-1 granted bail on 5 Dec 2024",
  },
  recorded: { date: "2025-02-03", backend: "sample data", model: "none (built-in sample case)", cost_inr: 0 },
  steps: [
    {
      stage: "INTAKE", tab: "dossier", agent: "MUNSHI",
      title: "The papers are read and filed",
      caption:
        "Munshi read the FIR (in Hindi), the two remand orders, the Sessions Court bail order, the order sheet and the co-accused's bail order, page by page. Page 3 of the FIR could not be read, so Munshi asked for a clearer copy instead of guessing.",
      filled: [
        { label: "Documents", value: "FIR 112/2024 (Hindi), remand orders of 21 Aug and 4 Sep 2024, Sessions Court bail rejection, order sheet, Co-accused-1 bail order" },
        { label: "Questions for counsel", value: "A clearer copy of FIR page 3; the charge-sheet cover; the jail custody certificate" },
      ],
      action: null,
    },
    {
      stage: "DOSSIER", tab: "dossier", agent: "PESHKAR",
      title: "Every fact points to its page",
      caption:
        "Peshkar built the dossier: each fact carries the page and the quote it came from, or says that it was calculated or stated by counsel. Antecedents are not in the papers, so the fact stays Not found until counsel answers. Open a fact to see its source.",
      filled: [
        { label: "Counsel's answer: other pending cases", value: "Not known from the file; marked unknown" },
        { label: "Personal circumstances (stated by counsel)", value: "Sole earning member of the family" },
      ],
      action: null,
    },
    {
      stage: "GATE_1", tab: "dossier", agent: "SUTRADHAR",
      title: "Gate 1: counsel confirms the facts",
      caption:
        "Drafting cannot start until counsel confirms the facts. Sutradhar holds the gate while any fact is unresolved. Counsel marked the antecedents as unknown and confirmed.",
      filled: [
        { label: "Acknowledged", value: "Antecedents: not found, marked unknown" },
        { label: "Approved by", value: "Counsel" },
      ],
      action: null,
    },
    {
      stage: "RIGHTS", tab: "rights", agent: "PESHKAR",
      title: "Rights worked out from the dates",
      caption:
        "The Rights Radar works through the dates in the file: arrest on 20 Aug 2024, charge sheet on 2 Nov 2024, custody of 167 days. The charge sheet came on day 74, so the default bail window closed unless an application was made on days 61 to 73. The other checks are listed with the rule each one applies.",
      filled: [
        { label: "Arrest", value: "20 Aug 2024" },
        { label: "Charge sheet", value: "Filed 2 Nov 2024 (day 74)" },
        { label: "Custody", value: "167 days" },
      ],
      action: null,
    },
    {
      stage: "BRIEF", tab: "brief", agent: "VAKEEL",
      title: "Grounds drafted from the confirmed facts",
      caption:
        "Vakeel drafted the grounds, each tied to the facts and authorities it relies on. Every sentence is checked against its sources; two grounds are marked for counsel's check rather than dropped.",
      filled: [
        { label: "Parity", value: "Co-accused-1, granted bail on 5 Dec 2024" },
        { label: "Grounds marked for a check", value: "2" },
      ],
      action: null,
    },
    {
      stage: "SPAR", tab: "spar", agent: "ABHIYOJAK",
      title: "What the prosecution is likely to say",
      caption:
        "Abhiyojak argued the other side: each likely objection is tied to the record, a statute or a fact, with the reply the draft gives. One objection has no reply in the draft yet.",
      filled: [{ label: "Objections", value: "Answered, partly answered and unanswered, grouped by ground" }],
      action: null,
    },
    {
      stage: "HEARING_PREP", tab: "prep", agent: "VAKEEL",
      title: "One page for the hearing",
      caption:
        "The hearing card puts the points to make, the questions the bench may ask and the conditions courts have imposed in similar orders on one page.",
      filled: [],
      action: null,
    },
    {
      stage: "GATE_2", tab: "prep", agent: "SUTRADHAR",
      title: "Gate 2: counsel approves the draft",
      caption:
        "Nothing is exported until counsel approves the draft. Pressing Next approves it on counsel's behalf for this demo, with the open items accepted as reviewed.",
      filled: [{ label: "Approval", value: "Recorded as counsel's decision" }],
      action: "approve_gate_2",
    },
    {
      stage: "FILE", tab: "prep", agent: null,
      title: "Export the application",
      caption:
        "The draft is approved, so the export buttons are open. Export as Word file to download the bail application; it carries the label that it is an AI-generated draft and not legal advice.",
      filled: [],
      action: null,
    },
  ],
} as const;

/** GET /api/demo/tours in the demo build. */
export function mockTourList() {
  const { slug, case_id, title, story, variant } = MOCK_TOUR;
  return [{ slug, case_id, title, story, variant }];
}
