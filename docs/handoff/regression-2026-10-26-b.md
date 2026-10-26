# Regression, second pass (26-27 October 2026)

Run per test file in the background with a 10-minute timeout (`faulthandler_timeout` set). No full-tree run: it hangs. `tests/unit/finetune` is not touched (another agent). Nothing committed. Edits sit on top of Satvik's `b147163`/`c317615` and the lead's later commits; the api/record edits were re-read against HEAD and none duplicates his fixes.

## Result table (passed / failed)

| Area | Before (first note) | After |
|---|---|---|
| tests/unit (minus finetune) | about 4,288 passed (whole tree), 6 eval failures (3 Wilcoxon, 3 ingestion helpers) | 4,227 passed, 0 failed, 7 skipped (`parler_tts` missing: needs torch) |
| tests/integration | 74 passed, 43 failed | 130 passed, 2 failed (see below) |
| tests/system | 157 passed, 109 failed, flow6 and an SSE test hung | 295 passed, 1 failed (flow4) |

Hangs: not hangs. `load_config()` re-parsed the YAML files on every model-role lookup, so 120-case batch tests took minutes (now cached by file mtime, `config.py`); the SSE test hung because its finite log view still offered `EventLog.follow` (never ends), fixed in the test view.

## Done, by cause

Wilcoxon and ingestion helpers (Harshita's area, done minimally by the lead's request, no change to her tests): `scipy` was not installed (it is in the `eval` extra, not in `dev`: `pip install "scipy>=1.11"` is enough, 35 MB). `by_kind`, `escalation_rate`, `questions_asked` added to `eval/metrics/ingestion.py`. `eval/metrics/unsupported_fact.py` implemented (MiniCheck when installed, else the NLI facade, offline lexical NLI by default; `checker_backend()` names it). No test requires it; the plan does.

Harness (tests, not production):
- Laptop and Ada scripted clients fall back to the offline model for what is not scripted (`OfflineBackedLLM` in `tests/system/_helpers.py`; `Dispatch` in `tests/integration/_helpers.py`); schema titles mapped to the real ones (`DraftedGround`, `RaisedObjections`, `JudgedReply`).
- Scenario: `as_of` set, Gate 1 opened and stage advanced after Peshkar (what the graph does), Gate 2 opened after the draft, `file_item` logs STORE_WRITE like the real tool, drafts keyed by factor and the scenario keeps only the scripted factors, name detector registered for the planted names, upload kept in `inbox/`.
- Case bundle now states the co-accused bail and the sole-earner plea; batch cases carry the bail order and custody certificate; fake store search uses the English text and skips duplicate chunk ids; fake store `put` validates into the field type; fake `span_check` uses the real tool.

Production fixes (small, each with its reason):
- Peshkar offline reader: FIR number split by "सं." or "No."; FIR date only right after the FIR number (it read the arrest date); one FIR from complementary readings (`merge_subsumed`); FIR cue for "Information Report" and Hindi; blank answer from counsel leaves the question open; rights fallback `state.rights` in `detect_changes`.
- Filing: chunks carry route, language and confidence; `previous_bail` merge read models and dicts (crash).
- Events and text: a closing date belongs to the sentence before it; Hindi "सं." is not a sentence end; "घटना dated"; Hindi FIR cue; Devanagari statute abbreviations (बी.एन.एस. etc.) and "धारा" read as BNS / section; offline NLI aliases case-insensitive; names already aliases ("Accused-1") are no longer learned as names (this leaked the privacy boundary).
- Privacy: chat and dictation routes pseudonymise before logging (the Hindi name leaked into the log).
- Safety: more prediction and lay-advice phrasings refused (English and Hindi); export/approve pressure answered with the Gate 2 pointer; instruction guard catches Hindi "निर्देश:" and gate-approval commands; sensitive-matter decline carries `excluded_from_evaluation`, a Hindi BNS 64 FIR is declined, and a declined file in a batch gets no card or queue entry (`MatterDeclined`).
- Gates: Gate 2 cannot be approved before Gate 1 or before Vakeel opened it; an acknowledged UNSUPPORTED field no longer shows as unresolved after approval.
- Orchestration: LangGraph checkpoint file is shared under the cases folder (the waiting gate survives a new process); TriageQueue default is the durable `batch/queue.sqlite` (`":memory:"` for tests).
- Sutradhar: discarded objections reach the sparring record; a lower per-factor store cap on the tracker wins over the contract's; Abhiyojak ids are positional.
- Munshi `emit` dropped `parent_id`, and file_item calls carry their source (audit trail).
- Batch: default-bail card text "opens in 3 days" (plan §11), triage cards written to each case record so `/api/desk/board` shows them, a zip with no PDF is 422.
- `models/labeler.py`: Qwen refused before the offline check (a test failed after the lead's commit).

RECONCILED tests (marked in the files): chat answers are composed from tool results (flow2), the uploaded bundle sits in `inbox/` (flow1, export checks), `SutradharAgent.run` stops at evidence packs so the tests call `delegate` too, discarded and kept objections are found by wording not id, export node records a blocked export instead of raising, page reads and the pseudonymiser are unlogged by design (privacy), Munshi probes one page past the end, translation shows as a route entry, "authority" scores are not probabilities, a few helper bugs. Goldens re-captured with reasons: `tests/unit/agents/{munshi,peshkar,pairokar}/golden_default_run.json`.

## Still red (3 tests) and why

| Test | Owner | Cause |
|---|---|---|
| `tests/system/test_flow4...::test_the_redrafted_ground_depends_on_the_new_value` | Vishak/Shravani | The dossier is read from the papers now; the scripted "charge sheet not filed" first draft and the later order never change the dossier value, so the dependency hash cannot differ. Needs the test to ingest the new order for real (Munshi, then Peshkar) with a first bundle whose charge sheet reads differently. |
| `tests/integration/test_change_set_flow.py::test_charge_sheet_filed_reopens_its_factor...` | Vishak | Contradicts the sibling test: a changed `default_bail` check (asserted there) reopens `custody_period` by design (`FACTOR_RIGHTS`, `_CHANGED_RIGHTS_FACTORS`). Decide which rule is right. |
| `tests/integration/test_sutradhar_with_fakes.py::test_weak_slot_is_relaxed...` | Vishak | The relaxation loop stops once the authority slot fills after the family widens, so "court" is never dropped as the test expects. |

Flow6 now passes (the last text fix, "N days", was checked on the batch and Pairokar unit tests and the card regex only).

## The three red tests, resolved (27 October)

Only tests changed; the production code was right in all three.

- `test_sutradhar_with_fakes::test_weak_slot_is_relaxed...`: the regression note was wrong. The loop does not stop when the slot fills (it stays WEAK, 1 of 2). It stops on the hard budget of plan §6.2 (8 store calls per factor): the six slots of the parity contract cost 6 calls in round 1, then one call each for the factor relaxation and the section-family widening makes 8, so the court is never reached. The code keeps the plan's hard stop. RECONCILED: the ordered ladder (factor, family, court, `before` kept) is now asserted at the 16-call point of the budget sweep (limit raised after planning with `set_factor_limits`), and a new test asserts the default-budget behaviour (3 rounds, factor then family, court kept, exactly 8 calls).
- `test_change_set_flow::test_charge_sheet_filed_reopens...`: the custody_period assertion contradicted plan §10 (RightsReport entries are dependencies) and the sibling test: custody_period's ground reads `default_bail` (`FACTOR_RIGHTS`), and the filing changes that check, so it is reopened by design. RECONCILED: the test now asserts custody_period IS reopened; the strict check that parity stays closed is kept.
- `test_flow4_case_moves_on::test_the_redrafted_ground_depends_on_the_new_value`: the first bundle's order sheet already said "charge sheet filed on 02.11.2024", and the later order never reaches the state's dossier before counsel re-approves. The first bundle now reads 28.10.2024 (a "not filed" sheet would make the factor not applicable and leave no G2), and the test applies counsel's re-approval of the value read from the new order (02.11.2024) before redrafting, so the dossier value and the dependency hash really change.
