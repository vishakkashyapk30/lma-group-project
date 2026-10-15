// Demo page facsimiles for the PDF viewer (demo mode has no real PDF). Sized in PDF points (A4: 595 x 842), page
// numbers are file pages (as in SourceRef.page), and every box the dossier and timeline cite exists here, so
// "click a field -> scroll to its source box" works in the demo. Hindi lines are real Devanagari text.
import type { Box, MockPage, MockPageLine } from "../types";

const W = 595;
const H = 842;

type LineSpec = [text: string, y: number, opts?: { style?: MockPageLine["style"]; en?: string; x0?: number; x1?: number; h?: number; hand?: boolean }];

function lines(x0: number, x1: number, specs: LineSpec[]): MockPageLine[] {
  return specs.map(([text, y, o]) => ({
    text,
    text_en: o?.en,
    box: [o?.x0 ?? x0, y, o?.x1 ?? x1, y + (o?.h ?? 26)] as Box,
    style: o?.style ?? "body",
    handwritten: o?.hand,
  }));
}

function page(doc_id: string, pageNo: number, lang: string, kind: string, body: MockPageLine[], extra?: Partial<MockPage>): MockPage {
  return { doc_id, page: pageNo, width: W, height: H, lang, kind, lines: body, ...extra };
}

export const MOCK_PAGES: MockPage[] = [
  // d1: FIR (Hindi), pages 1-3
  page("d1", 1, "hi", "scanned", [
    ...lines(64, 531, [
      ["प्रथम सूचना रिपोर्ट", 60, { style: "heading", en: "First Information Report", x0: 200, x1: 400, h: 32 }],
      ["(भारतीय नागरिक सुरक्षा संहिता की धारा 173 के अंतर्गत)", 92, { en: "(Under section 173, Bharatiya Nagarik Suraksha Sanhita)", x0: 150, x1: 450, h: 22 }],
      ["प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024", 120, { en: "FIR No. 112/2024 dated 14.08.2024", x1: 540, h: 32 }],
      ["ज़िला: District-1     थाना: PS-1     वर्ष: 2024", 160, { en: "District: District-1   Police station: PS-1   Year: 2024" }],
      ["अधिनियम एवं धाराएँ: भारतीय न्याय संहिता, 2023 - धारा 318(4), 316(2)", 196, { en: "Act and sections: Bharatiya Nyaya Sanhita, 2023 - sections 318(4), 316(2)" }],
      ["घटना की तिथि: 10.08.2024", 236, { en: "Date of occurrence: 10.08.2024", x1: 420 }],
      ["सूचना प्राप्त होने की तिथि: 14.08.2024, समय 11:40", 266, { en: "Information received: 14.08.2024 at 11:40" }],
      ["शिकायतकर्ता: Complainant-1;  आरोपीगण: Accused-1, Co-accused-1;", 300, { en: "Complainant: Complainant-1; accused: Accused-1, Co-accused-1;" }],
      ["विवेचना अधिकारी: IO-1", 326, { en: "Investigating officer: IO-1" }],
      ["विवरण: शिकायतकर्ता के अनुसार आरोपीगण ने निवेश का झांसा देकर", 380, { en: "Details: according to the complainant, the accused, on the pretext of an investment," }],
      ["₹4,20,000 प्राप्त किए और राशि वापस नहीं की।", 406, { en: "took ₹4,20,000 and did not return the amount." }],
      ["राशि का एक भाग Co-accused-1 के खाते में भी स्थानांतरित किया गया।", 432, { en: "Part of the amount was also transferred to Co-accused-1's account." }],
      ["थाना प्रभारी, PS-1", 760, { style: "signature", en: "Station house officer, PS-1", x0: 360 }],
    ]),
    { text: "PS-1 · प्राप्त", text_en: "PS-1 · received", box: [400, 700, 520, 740], style: "stamp" },
  ], { skew: -1.2 }),
  page("d1", 2, "hi", "scanned, handwriting", [
    ...lines(64, 531, [
      ["प्रथम सूचना रिपोर्ट सं. 112/2024 - पृष्ठ 2", 60, { style: "heading", en: "FIR No. 112/2024 - page 2", h: 28 }],
      ["शिकायतकर्ता का कथन (हस्तलिखित)", 110, { en: "Statement of the complainant (handwritten)", hand: true }],
      ["मैंने दिनांक 02.07.2024 को आरोपी को ₹2,00,000 नकद दिए", 150, { en: "On 02.07.2024 I gave the accused ₹2,00,000 in cash", hand: true }],
      ["और शेष राशि बैंक हस्तांतरण द्वारा दी।", 180, { en: "and the remaining amount by bank transfer.", hand: true }],
      ["आरोपी ने हर महीने लाभ का वादा किया था।", 210, { en: "The accused had promised a return every month.", hand: true }],
      ["पढ़कर सुनाया गया, सही माना।  ह. Complainant-1", 300, { en: "Read over and admitted correct. Sd. Complainant-1", hand: true }],
      ["ह. IO-1", 760, { style: "signature", en: "Sd. IO-1", x0: 420, hand: true }],
    ]),
  ], { skew: 0.8 }),
  page("d1", 3, "hi", "photo", [
    ...lines(64, 531, [["[पृष्ठ अपठनीय - धुंधली फोटो]", 400, { en: "[Page unreadable - blurred photo]", x0: 160, x1: 440 }]]),
  ], { skew: -4, unreadable: true }),

  // d2: first remand order, pages 4-5 (born-digital)
  page("d2", 4, "en", "born-digital", lines(72, 523, [
    ["IN THE COURT OF THE CHIEF JUDICIAL MAGISTRATE, DISTRICT-1", 72, { style: "heading", h: 30 }],
    ["Remand Application No. 2231/2024", 112],
    ["State v. Accused-1, FIR No. 112/2024 dated 15.08.2024, PS-1", 150],
    ["Under sections 318(4), 316(2) of the Bharatiya Nyaya Sanhita, 2023", 180],
    ["Present: APP for the State; IO-1 in person; counsel for the accused.", 222],
    ["The accused Accused-1 was arrested on 20.08.2024 in connection with the above FIR.", 262],
    ["Accused produced today, i.e. 21.08.2024. Heard the APP and the counsel for the accused.", 300],
    ["Remanded to judicial custody for 14 days, to be produced on 04.09.2024.", 342],
    ["Copy of this order be given to the accused free of cost.", 384],
    ["Sd/- CJM, District-1, 21.08.2024", 760, { style: "signature", x0: 330 }],
  ])),
  page("d2", 5, "en", "born-digital", lines(72, 523, [
    ["Remand Application No. 2231/2024 - continued", 72, { style: "heading", h: 28 }],
    ["The remand paper records the arrest; no arrest memo is annexed.", 120],
    ["Medical examination of the accused conducted on 20.08.2024.", 150],
    ["The IO seeks no police custody.", 180],
    ["Sd/- CJM, District-1", 760, { style: "signature", x0: 360 }],
  ])),

  // d3: second remand order, pages 6-7 (scanned, degraded)
  page("d3", 6, "en", "scanned, skewed", lines(72, 523, [
    ["IN THE COURT OF THE CHIEF JUDICIAL MAGISTRATE, DISTRICT-1", 72, { style: "heading", h: 30 }],
    ["State v. Accused-1, FIR No. 112/2024, PS-1", 120],
    ["04.09.2024. Accused produced from judicial custody.", 210],
    ["Judicial custody of the accused extended for 14 days.", 250],
    ["Investigation is stated to be in progress.", 290],
    ["Sd/- CJM, District-1", 760, { style: "signature", x0: 360 }],
  ]), { skew: 2.4 }),
  page("d3", 7, "en", "degraded scan, stamp", [
    ...lines(72, 523, [
      ["18.09.2024. Judicial custody extended till 02.10.2024.", 120],
      ["Next date 02.10.2024.", 160],
    ]),
    { text: "CERTIFIED COPY", box: [300, 600, 520, 660], style: "stamp" },
  ], { skew: -1.6 }),

  // d4: Sessions Court bail rejection, pages 8-10 (scanned)
  page("d4", 8, "en", "scanned", lines(72, 523, [
    ["IN THE COURT OF THE ADDITIONAL SESSIONS JUDGE-02, DISTRICT-1", 72, { style: "heading", h: 30 }],
    ["Accused-1 v. State", 120],
    ["Bail Application No. 1043/2024, filed on 12.09.2024", 196],
    ["Application under section 483 of the BNSS for grant of regular bail.", 236],
  ])),
  page("d4", 9, "en", "scanned", lines(72, 523, [
    ["Counsel for the applicant submits that the applicant is falsely implicated", 120],
    ["and that the dispute is civil in nature.", 146],
    ["The APP opposes the application: the investigation is at a nascent stage", 200],
    ["and the money trail is yet to be traced.", 226],
  ])),
  page("d4", 10, "en", "scanned, signature", lines(72, 523, [
    ["The allegations are serious, and the investigation is at a nascent stage.", 300],
    ["The money trail is yet to be traced.", 330],
    ["...the bail application of the applicant Accused-1 is dismissed. Pronounced on 30.09.2024.", 420],
    ["Sd/- ASJ-02, District-1", 760, { style: "signature", x0: 360 }],
  ])),

  // d5: order sheet, pages 11-12 (born-digital table, some Hindi)
  page("d5", 11, "mixed", "born-digital, table", lines(60, 535, [
    ["ORDER SHEET · SC No. 88/2024 · State v. Accused-1 and another", 72, { style: "heading", h: 30 }],
    ["Date | Proceedings", 120, { style: "table" }],
    ["02.10.2024: Judicial custody extended. Investigation pending.", 200, { style: "table" }],
    ["16.10.2024: Judicial custody extended. Next date 02.11.2024.", 250, { style: "table" }],
    ["02.11.2024: Charge sheet filed by IO-1 under ss. 318(4), 316(2) BNS. Copy supplied.", 300, { style: "table" }],
    ["आरोप पत्र प्रस्तुत; प्रतियाँ अभियुक्तों को दी गईं।", 330, { style: "table", en: "Charge sheet filed; copies given to the accused." }],
  ])),
  page("d5", 12, "mixed", "born-digital, table", lines(60, 535, [
    ["Date | Proceedings (continued)", 72, { style: "table" }],
    ["05.12.2024: Co-accused-1 admitted to bail (separate order).", 130, { style: "table" }],
    ["20.01.2025: Arguments on charge not concluded. Charges not framed. Put up on 18.02.2025.", 180, { style: "table" }],
  ])),

  // d6: co-accused bail order, pages 13-14 (born-digital)
  page("d6", 13, "en", "born-digital", lines(72, 523, [
    ["IN THE COURT OF THE ADDITIONAL SESSIONS JUDGE-02, DISTRICT-1", 72, { style: "heading", h: 30 }],
    ["Bail Application No. 1388/2024 · Co-accused-1 v. State", 120],
    ["The charge sheet has been filed and the applicant is no longer required for investigation.", 300],
    ["...Co-accused-1 is admitted to bail on furnishing a personal bond of ₹50,000 with one surety...", 380],
    ["Pronounced on 05.12.2024.", 420],
  ])),
  page("d6", 14, "en", "born-digital", lines(72, 523, [
    ["Conditions: the applicant shall appear on every date and shall not contact the complainant.", 120],
    ["Sd/- ASJ-02, District-1", 760, { style: "signature", x0: 360 }],
  ])),

  // d7: jail custody certificate (flow 4 upload)
  page("d7", 1, "en", "scanned, table", lines(60, 535, [
    ["CENTRAL JAIL, DISTRICT-1 · CUSTODY CERTIFICATE", 72, { style: "heading", h: 30 }],
    ["Prisoner: Accused-1 · UTP No. 4471/2024", 130, { style: "table" }],
    ["Date of admission: 21.08.2024 (on remand by the CJM, District-1)", 180, { style: "table" }],
    ["Custody as on date: 167 days", 230, { style: "table" }],
    ["Conduct in jail: satisfactory", 280, { style: "table" }],
    ["Involvement in other cases: Nil.", 330, { style: "table" }],
    ["Sd/- Superintendent", 760, { style: "signature", x0: 360 }],
  ])),
];

/** Facsimile of one page, or null when the demo has none. `docId` may be "d1" or "d1 (FIR)". */
export function getMockPage(docId: string, pageNo: number): MockPage | null {
  const id = docId.split(/\s|\(/)[0];
  return MOCK_PAGES.find((p) => p.doc_id === id && p.page === pageNo) ?? null;
}

/** Facsimiles of every page of a document, in order. */
export function getMockDocumentPages(docId: string): MockPage[] {
  const id = docId.split(/\s|\(/)[0];
  return MOCK_PAGES.filter((p) => p.doc_id === id).sort((a, b) => a.page - b.page);
}
