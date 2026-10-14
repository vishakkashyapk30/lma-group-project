"""Plan example payloads, written out as the plan prints them (plan §4.6, §6.3, §8.1, §9, §11)."""

from __future__ import annotations

# plan §4.6 (the "..." placeholder row of d2 is dropped)
INGESTION_REPORT = {
    "case_id": "case-0007",
    "file": "bundle_1.pdf",
    "documents": [
        {
            "doc_id": "d1", "type": "FIR", "pages": [1, 3], "lang": "hi", "type_confidence": 0.94,
            "page_routes": [
                {"page": 1, "kind": "scanned", "route": ["text_layer: rejected (legacy font)", "ocr: surya-hi"],
                 "ocr_conf": 0.81, "status": "OK"},
                {"page": 2, "kind": "scanned, handwriting", "route": ["ocr: surya-hi", "vision: qwen3-vl"],
                 "ocr_conf": 0.42, "status": "OK"},
                {"page": 3, "kind": "photo", "route": ["dewarp", "ocr: surya-hi", "vision: qwen3-vl"],
                 "status": "UNREADABLE"},
            ],
        },
        {
            "doc_id": "d2", "type": "REMAND_ORDER", "pages": [4, 5], "lang": "en",
            "page_routes": [{"page": 4, "kind": "born-digital", "route": ["text_layer"], "status": "OK"}],
        },
    ],
    "filed": {"timeline_events": 6, "parties": 4, "sections": 2, "chunks": 31},
    "gaps": [{"item": "charge-sheet status", "action": "searched pages 6-14; not found; asked counsel"}],
    "questions": [
        "Page 3 of the FIR is unreadable. Can you upload a clearer copy?",
        "Has the charge sheet been filed? If so, please upload the order.",
    ],
}

# plan §6.3
RETRIEVAL_PLAN = {
    "factor": "parity_with_co_accused", "round": 1, "budget_left": {"store_calls": 6, "tokens": 9000},
    "steps": [
        {"slot": "co_accused_order", "tool": "search_case_docs",
         "args": {"query": "co-accused granted bail", "doc_types": ["BAIL_ORDER"]}},
        {"slot": "authority", "tool": "search_reasoning",
         "args": {"factor": "parity_with_co_accused", "section_family": ["BNS 318(4)", "IPC 420"],
                  "before": "2025-02-03", "outcome": "granted", "k": 10}},
        {"slot": "good_law", "tool": "citations",
         "args": {"doc_ids": "$authority.top3", "want": ["overruled_by", "sc_root"]}},
        {"slot": "likely_objection", "tool": "search_objections",
         "args": {"factor": "parity_with_co_accused", "section_family": ["BNS 318(4)", "IPC 420"]}},
    ],
    "assessment": {"co_accused_order": "FILLED", "authority": "WEAK (1 of 2)", "good_law": "FILLED",
                   "likely_objection": "FILLED"},
    "next": "relax section_family to the offence group 'cheating'; retry authority",
}

# plan §8.1 (two grounds; G2 depends on G1 so the claim-to-claim edge is covered)
BAIL_BRIEF = {
    "case_id": "case-0007",
    "statutory_position": {
        "sections": ["BNS 318(4) (≈ IPC 420)"], "bailable": False, "max_punishment": "7 years",
        "rights": "default-bail window closed; s.479 not yet reached (see RightsReport)",
    },
    "grounds": [
        {
            "id": "G1", "factor": "parity_with_co_accused", "stance": "favourable",
            "argument": "Co-accused-1, with an identical role, was granted bail on 05.12.2024 [F:co_accused_bail] ...",
            "authorities": [{"doc_id": "DLHC-2022-1187", "para": 14, "citation": "<rendered from metadata>",
                             "transfer": "SAME_TEXT", "good_law": "OK", "sc_root": "SC-2014-0463"}],
            "depends_on": {"facts": {"co_accused_bail": "h:3f2a", "sections": "h:91c0"}, "events": ["e12"],
                           "authorities": ["DLHC-2022-1187#14"]},
            "check": "SUPPORTED", "state": "CURRENT",
        },
        {
            "id": "G2", "factor": "charge_sheet_filed", "stance": "favourable", "argument": "...",
            "authorities": [],
            "depends_on": {"facts": {"charge_sheet": "h:77aa"}, "claims": ["G1"]},
            "check": "REPAIRED", "state": "STALE",
        },
    ],
    "open_issues": [
        {"type": "NEEDS_REVIEW", "item": "Antecedents unknown: confirm no other pending cases."},
        {"type": "CHANGED_PROVISION",
         "item": "DLHC-2021-0420 interprets IPC 420; BNS 318(4) wording differs: qualify."},
        {"type": "MISSING_EVIDENCE",
         "item": "No trial-delay authority in the same section family; widened to all cheating offences."},
    ],
    "label": "AI-generated draft. Not legal advice.",
}

# plan §9
SPARRING_RECORD = {
    "case_id": "case-0007", "rounds": 2,
    "objections": [
        {"id": "O1", "against": "G1", "factor": "parity_with_co_accused",
         "objection": "The applicant, unlike Co-accused-1, received the money into his own account.",
         "grounds": [{"store": "advocacy.objections", "doc_id": "DLHC-2023-0911", "para": 6}, {"fact": "fir"}],
         "reply": {"text": "...", "authorities": [], "check": "SUPPORTED"}, "verdict": "ANSWERED"},
        {"id": "O2", "against": "general", "factor": "witness_tampering",
         "objection": "Charges are not framed and the complainant is yet to be examined.",
         "grounds": [{"fact": "trial_stage"}], "reply": None, "verdict": "UNANSWERED"},
    ],
    "discarded": ["Applicant is a flight risk (no grounding found)"],
}

# plan §11
TRIAGE_CARD = {
    "case_id": "case-0142", "urgency_rank": 4,
    "reasons": ["Default-bail window opens in 3 days (BNSS s.187(3))"],
    "flags": ["CHECK: antecedents unknown"],
    "missing_docs": ["custody certificate"],
    "next_step": "full brief queued; flag default-bail window to counsel",
}
