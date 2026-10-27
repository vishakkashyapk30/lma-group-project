# Privacy hardening: consent for client text, quasi-identifiers and date shift (2026-10-27)

Owner of `privacy/` is not settled in `split.md` (design review item 24); please have Shravani review the policy choices marked **decide** below.
No paid API call, no model download, nothing in `data/` written (the T1 orders were only read).

## Done

### 1. Per-case consent for pseudonymised client text (design review item 5 and contradiction row 9)
- `models/sarvam/policy.py` `authorize`: `DataClass.CLIENT_TEXT` now needs counsel's consent event for the case and provider (`sarvam_consent` / `openai_consent`, USER_ACTION by COUNSEL, latest wins, revocable), as `CLIENT_RAW` already did. No case id means refusal. `PUBLIC` stays consent-free. The boundary still runs first, and every client-data call still writes a sizes-only audit event (`capability`, `data_class`, `purpose`, `chars`/`bytes`).
- `case_text_scope(case_id, event_log, mapping)`: entered by `agents/base.py` `ask` around the model call, so a hosted agent call is this case's client text. A scope that the caller already declared wins (Munshi's own, the driver's). Offline clients never read the scope, so offline runs are unchanged.
- `public_source_scope(purpose, mapping=)`: the honest declaration for the evaluation driver and the baselines (cases built from published court orders). Agent clients keep `CLIENT_TEXT` inside it, so the wire step and the boundary run as in production, but no consent is asked for and none is written. A plain `public_scope` does NOT waive consent for an agent client. A test checks that only `eval/` uses `public_source_scope` and that only `policy.py` calls `record_consent`.
- `eval/runners/driver.py`: `_case_scope(case, system, ctx)` uses `public_source_scope` with the case's alias map (a lazy loader). Cases marked `data_class: client` get no declaration. The run manifest gains a `privacy` block (`case_scope`, `agent_data_class`, `consent`, `cases_by_data_class`).
- Docs: plan §16 Privacy row, product-readiness AC-P, `pilot-hosted-model.md` (header note and a new last section), docstrings of `policy.py`, `agents/base.py`, the driver and both adapters. AGENTS.md was left as is: its bullet already says "plus per-case consent".

### 2. Quasi-identifiers and the date shift (`privacy/quasi.py`, new)
- **Design: the wire step, not the intake.** The intake (`pseudonymise_text`) still replaces only names, plus the old email/phone/ID tokens. It now also learns the quasi-identifiers into the case's `PseudonymMap` and draws the case's date shift, but the local text keeps them. The OpenAI and Sarvam clients (`chat`; Sarvam `translate` too) encode every `CLIENT_TEXT` message with `WireCodec` before `authorize` checks it, and decode the reply. So the case shelf, the dossier, the Rights Radar, the custody-day, s.479 BNSS and default-bail arithmetic, the gold scoring (G3 dates) and Peshkar's quote checks all see real values, and the offline stand-ins never touch the codec. Shifting dates in the local copy was rejected: the Rights Radar compares dates with fixed legal dates (BNSS commencement 1 July 2024), and a shift would move cases across that line.
- **Categories:** FIR numbers; case, crime and bail-application numbers (**decide**: the number is replaced and the year is kept, since the year shows IPC versus BNS and identifies nobody on its own); police-station names (after or before the label, Hindi `थाना`); villages, mohallas, colonies, post offices and roads (also Kerala-style `X VILLAGE`, `X HOUSE`, `X POST`); `R/o` addresses; house, plot, door and ward numbers; PIN codes; vehicle registrations (state-code list, BH series); driving licences; IFSC; UPI handles; bank account numbers; Aadhaar (including masked `XXXX XXXX 1234`); PAN; passport; voter ID; emails; mobile and landline numbers; dates of birth; ages (`[AGE-1 18-25]`: the band survives so juvenile or elderly cues stay). Kept: sections, acts, court names, districts, states, tahsils. Each distinct value gets one alias per case (`[FIR-1]`, `[PS-2]`). The key is the exact spelling, so the reply restores byte for byte; two spellings of one station get two aliases.
- **Dates:** one shift per case (`PseudonymMap.date_shift_days`, a negative whole number of weeks between -182 and -28, so intervals and weekdays are kept), drawn at random at intake and stored in `pseudonyms.json`. Evaluation ids (`t<digit>...-`) get a shift computed from the id, so reruns send the same text and hit the OpenAI cache. Every form is shifted and rewritten in its own format: `dd.mm.yyyy`, `/`, `-`, two-digit years, ISO, `16th February, 2024`, `16-Feb-2024`, `February 16, 2024`, `2nd day of March 2023`, ranges, and dates glued to words by OCR. The reply is unshifted through an exact table of what was sent, else by arithmetic, so a date the model computed comes back right. A map without a shift (a case filed before this change) gets a random shift kept per case for the process.
- **Names:** a relatives rule (`his father Ram Lal`, `wife Smt. X`, `-in-law`); `S/o.` with a dot; `PSI|API|PI` ranks; the second sweep now also replaces title-case variants and tokens glued by OCR (`ShuklaCounsel`, `accusedVeeranki`, `PRASADKUSHWAHA`).
- **Boundary:** `assert_pseudonymised(..., wire=True)` is used by `authorize` for `CLIENT_TEXT`. It refuses any quasi-identifier left (`find_quasi`) and any token of five or more letters of a learned name still in the text, whole or glued (`name_token_leaks`; the earlier leak proxy, now a refusal rule). The default check (the agents' own `guard_outbound`) is unchanged, so local case data with a real FIR number is not refused there.
- No switch was added: no baseline needs the old behaviour (baselines run on the same wire step, and their replies come back unshifted).

## Numbers (`scripts/measure_pseudonymiser.py --baseline-ref 87905b6`, 250 T1 orders, dev 50 + cases 200)
Text compared: what a hosted model receives. Before = the intake output at 87905b6 (there was no wire step); after = the new intake output plus `WireCodec`. The checks are separate regexes over the raw order (the FIR and police-station regexes of `pipelines/leakage.py`, label regexes, the name proxy of `pilot-hosted-model.md`) plus the orders' own gold G3 event dates. A value counts as surviving when the same string is still in the sent text; a string that the shift itself produced does not count.

| category (raw occurrences) | surviving before | surviving after |
|---|---|---|
| FIR numbers (62) | 62 | 0 |
| case / crime / bail-application numbers (311) | 311 | 0 |
| police stations, leakage regex (112) | 110 | 9: all on inspection districts or caption words (`PS, Dist Bhilwara`, `P.S. CaseNo`, `P.S. Act`), no station name |
| villages and localities (118) | 118 | 1 (`PANATHADYVILLAGE, VELLARIKUNDU`, glued) |
| `R/o` addresses (46) | 46 | 2 (`R/o Plot`, no name) |
| house numbers (32) | 32 | 0 |
| PIN codes (31) | 31 | 0 |
| vehicle numbers (6) | 6 | 0 |
| ages (99) | 99 | 1 (OCR `Age.3TYrs`) |
| numeric dates (457) | 457 | 0 |
| gold G3 dates in the excerpt (365) | 365 | 0 |
| party-name tokens, proxy (296) | 5 | 1 (`Kumar`, a common particle kept on purpose) |
| account / IFSC / UPI, ID numbers, email or phone, DOB | 0 in T1 | 0 (covered by the unit tests) |

False masking of legal content (raw strings no longer verbatim in the sent text): section references 0 of 593, act names 0 of 537, court phrases 0 of 278, before and after.

Boundary on the same 250: the old check on the old output refused 1; the new wire check refuses 246 of the old outputs; on the new wire text it refuses 5 (t1dev-045 `URMILA JOSHI-PHALKE` judge name part, t1-062 `Karamjeetson`/`Amarjeetin`, t1-085 `SharmaalongwithRajeshKumar`, t1-196 `DhanalakshmiW/oDasari...`, t1-197 a counsel name glued to `Mr.`). All 5 are real residual leaks from OCR glue. In a hosted evaluation these cases' calls fall back to the local model. Round trip: `decode(encode(text)) == text` on all 250; 422 dates shifted, each by exactly the case's shift.

## Tests
New: `tests/unit/privacy/test_consent_policy.py` (no consent refused, consent allowed, revoked refused, per provider and per case, public data free, adapter sends nothing without consent, sizes-only audit event, public-source path works and writes nothing, plain public scope does not waive, only `eval/` uses the declaration); `tests/unit/privacy/test_quasi.py` (every category, legal content kept, FIR year, age band, consistency, exact round trip, every date form, intervals and weekdays, computed dates, non-dates untouched, shift range, intake keeps local text, map persistence, relatives, wire versus default boundary, glued name parts, adapter end to end); `tests/unit/eval/test_driver_privacy_scope.py` (driver declaration, client case needs consent, reproducible shift, manifest block).
Reconciled (`# RECONCILED:`, consent added to the log, nothing weakened): 4 tests in `tests/unit/models/test_openai.py` and 6 in `tests/unit/models/test_sarvam.py` that sent `CLIENT_TEXT` without consent.
Results on the final code (2026-10-27): `tests/unit/privacy tests/unit/models` 463 passed (before: 423); `tests/unit/agents` 579 passed (unchanged); `tests/unit/eval` 514 passed, 1 skipped (`-k 'driver or baseline'`: 60 passed, before 55); `tests/integration -k privacy` selects no test (133 deselected, also before); `tests/system tests/integration` 417 passed; `tests/unit/ingestion tests/unit/api tests/unit/tools` plus integration 707 passed. Rerun the measurement: `.venv/bin/python scripts/measure_pseudonymiser.py --baseline-ref 87905b6 --out <file>` (about a minute, reads `data/testsets/t1` only).

## Not done / next steps
1. **A counsel control to grant and revoke consent** (API route plus UI toggle calling `record_consent` with the counsel actor). Until it exists, the product's hosted mode refuses every client case and runs locally. This is by design, but it should show as a visible message. P0 before any hosted demo on a client file.
2. Judge names: the owner's brief says judge names of public orders stay, but the existing tests (`test_pseudonymise_judge.py`) require that they are aliased; left as tested. **decide**.
3. The wire step runs only for the hosted providers (OpenAI, Sarvam). The team's Ada vLLM gets the intake text (names aliased, quasi-identifiers and dates real), as before. Extend it if Ada counts as external.
4. Residual leaks are OCR-glued names (5 orders); an NER detector (`register_detector`) is still the real fix. Hindi coverage is thin (only `थाना`, `गांव/ग्राम/मोहल्ला`, `उम्र/आयु`); Devanagari digits and Hindi month names are not shifted.
5. Limitation: a fixed legal date the model brings from its own knowledge (BNSS from 1 July 2024) is not shifted, so the model may misplace a shifted case date relative to it. Regime and Rights Radar decisions are local, but the drafter's prose could mention it; check on the next hosted pilot.
6. Quasi aliases learned at wire time (values not seen at intake) live only in the agent's in-memory map; they are not saved.
7. Report and ethics text (`docs/report/sections/system.tex`): state that the boundary is now a name plus quasi-identifier scrubber with a date shift, and give the 5 of 250 refusal rate and the table above.
8. A hosted rerun (small, under the cap) to confirm the extraction quality is unchanged with aliases and shifted dates.
