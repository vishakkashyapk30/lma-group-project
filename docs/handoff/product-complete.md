# Product-side completion and variant-effect audit

Date 2026-10-27. Nothing committed. Offline only (no hosted model call, no spend). Owner of the code areas touched: `pipelines/`, `tools/`, `agents/`, `models/` (no change), `schemas/rights_report.py`, `rights/base.py` (comment only).

## Done
1. **Order splitter rescue** (`pipelines/order_splitter.py`): `rescue_with_non_qwen(dropped_path, out_path=None, labeler=None) -> int` no longer raises. It asks the evaluation labeler facade (`models/labeler.EvalLabeler`: OpenAI gpt-6-luna on PUBLIC court text inside `public_scope`; never Qwen, refused by the facade) for a part per paragraph block, as JSON constrained to the five part names. The model writes no text: every rescued part is a join of whole blocks of the order, each checked to occur verbatim in it (span grounding), stage order must not go backwards and the length floors of `analyse_split` must hold, else the order stays dropped. Offline (`VS_MODELS=offline`) the labeler is unavailable and the stand-in keeps the rule decision: count 0, nothing rescued. Opt-in: nothing calls it, `split_all` is unchanged. Rescued rows go to `<dropped>.rescued.jsonl` with `parts`, `spans` (the verbatim blocks) and `rescued_by`. `rescue_dropped` returns the full report. Tests: `tests/unit/pipelines/test_order_splitter_rescue.py` (fake client).
2. **`assemble_application` tool** (`tools/drafting/application.py`): was already calling `export.application.assemble_application_docx`; the docstring and `PHASE5_MESSAGE` still said "stub". Updated. Gate rule kept in code: the tool writes the draft DOCX to `<cases_dir>/<case_id>/draft/application.docx`, never to `export/`, which only `export_case` fills after Gate 2 (before this change the tool wrote into `export/`). `BaseAgent.call_tool` returns the real path (test drives it through `VakeelAgent.call_tool` with the real registry); the `not_implemented` branch stays only for genuinely stubbed tools. `make smoke` prints SMOKE OK with export blocked. Tests: `tests/unit/tools_drafting/test_assemble_application_real.py`.
3. **Rights `last_verified`** (person task, not invented): `RightsCheckResult.verification` (a property, not a field, so serialised reports are unchanged) reads `unverified` until `last_verified` is set; `RightsReport.unverified_checks` lists them (all seven today). **Who must act: Harshita** re-checks the seven rule texts in `configs/rights_rules.yaml` / `rights/rules/*` against the bare acts (BNSS, CrPC, Constitution) and the cited judgments, then sets `last_verified` per rule (PR-46 in `docs/product-readiness.md`). The UI/API (not mine to edit) should render `verification` next to each rule text. Test: `tests/unit/rights/test_unverified_surface.py`.
4. **Variant-effect audit** (below). Test: `tests/unit/eval/test_variant_effects.py` (42 tests, about 30 s: every id of `IMPLEMENTED_VARIANTS` runs through the driver's own path on the case-0007 fixture with the offline models and is compared with Full on its mechanism marker; Munshi, scheduler, batch-cache and injection variants are checked on the structure that carries them; a coverage test fails when a new implemented id has no effect test).
5. **Leftovers in agents** (see the end).

## Variant-effect audit
Method: `driver smoke-all` offline (`VS_MODELS=offline`, the real built stores read-only, case `t1dev-000`, 61 ids, 61 pass), then per id the event log and `variant_signals` against Full (439 events, 105,396 tokens, 97 store calls). The stand-in LLM is a template, so "fired" means the mechanism ran and left its marker; the size of the effect says nothing about a real model. Fixture column: the same marker is asserted in `test_variant_effects.py`.

| Variant | Mechanism marker | Fired on dev case | Note / fix |
|---|---|---|---|
| A1 | Sutradhar searches raw facts (`search_case_docs` +) | yes (+1,966 tok, brief differs) | |
| A2 | no `check` decisions, no `check_claim` | yes (-10 `check_claim`) | |
| A3 | `rights_check` etc. refused `disabled_by_switch` | yes | |
| A4 | Sutradhar `search_reasoning`/`search_objections` args lack `factor`/`section_family` | yes (+2,631 tok) | by design only Sutradhar's retrieval is plain; Abhiyojak's refusal search keeps its factor filter |
| A5 base_4b / prompted_32b | `peshkar.extract_field` role `munshi_4b` / `teacher` | yes (23 calls change role) | offline stand-in answers identically, so tokens and brief are equal; the effect needs a real model |
| A6 | `fixed_router` decisions, no `plan_factor` call | yes (-5,927 tok) | |
| A7 | no plan/assess/replan; Abhiyojak calls instead | yes (-16,695 tok) | |
| A8 / A9 | no Abhiyojak `retrieve`/`objection`; A9 also no `check` | yes (-58,674 / -50,304 tok) | |
| A10 x7 stores | knocked-out store never queried; no drafting | yes for law.statutes, caselaw.reasoning, caselaw.citations, advocacy.objections; **no for law.concordance, caselaw.similar, advocacy.arguments on this case** | not a bug: no contract slot of the three factors this case opens queries them (they serve parity, flight risk with co-accused, and BNS/IPC mapping). The effect shows on cases that open those slots |
| B5 | `store_prior` decisions, `similar_orders` calls, no slots | yes (-5,360 tok) | runs on the neutral prior (see S6) |
| S1 | `critique` decisions, `critique_slot` LLM calls | yes (+14,554 tok) | |
| S2 | `depth` decision per factor | yes | all three factors classify `multi` here, so the run equals Full in tokens; `none`/`single` need non-adverse factors (unit tests in `test_variants_depth.py`) |
| S3 | `sufficiency` check after the rules pass | yes (1 rater call, +2,622 tok) | |
| S3b | rater on every round | yes (3 calls, +6,356 tok) | |
| S4 | `with_scores` on reasoning searches, `skew` signals | yes (3 scored calls) | no weak flag raised (Gini 0.03-0.08 with the hashed offline embedder), so brief equals Full |
| S5 | `expand_graph` on authority searches, `graph` signals | yes (1 expand call, 2 hits, +1,762 tok) | |
| S6 | `store_prior` signals, `store_prior_untrained` decision | wired, **effect none: no trained artefact** (`<data dir>/eval/store_prior.json` absent), so the order equals the contract's | **fix:** a loud `store_prior_untrained` event, so S6 cannot be read as a null result silently. **Open prerequisite:** train the artefact (`python -m vakeel_sahayak.agents.sutradhar.store_prior train --orders <train-split orders with G1-G3 gold>`); the gold labelling of train orders is not done (needs the hosted labeler, eval side). `runs.yaml` already lists `s6_b5_router` as deferred |
| S7 | `gap_signals` differ from sequential | no on dev case (bundle only: the T1 case is text) | bundle test `test_s7_...`: hierarchy goes to the page that shows the item |
| S8 | `self_critique` decisions, `repair` signals | yes (11 critic calls, 2 claims repaired) | |
| S9 | `sample_objections` x5, `critic` signals | yes (-33,368 tok, 5 objections) | |
| S10 | `isolation_off` events; Abhiyojak reads Vakeel's notes | yes, **but it killed sparring: 0 objections** | **fix (agents/base.py `untrusted`)**: the spotlight tag is a hash prefix; a tag with ten digits in a row (`cc9937724702`) matched the phone pattern of the privacy boundary and every Abhiyojak call with Vakeel's view was refused `privacy_boundary`. `BaseAgent.untrusted` now re-derives such a tag (only those; other texts are wrapped byte for byte as before). After the fix S10 gives 11 objections, 126,623 tok. **Owner of the root cause: privacy** (`privacy/injection_guard.wrap_untrusted` should avoid tags the boundary reads as phone/ID numbers; the same false positive can hit any hosted run) |
| S11 | `critic_mode=three_role`, role tasks | yes (-34,754 tok) | |
| S11b / S11c | `draft_debate` / `draft_vote` | yes (+657 / +1,994 tok) | |
| S12 / S12b | `topology` decision per factor | yes (S12b -5,930 tok: no separate plan prompt) | |
| S13 | grid point switch applied (`stopping=llm`) | yes | evaluator for the search itself is not wired (eval side) |
| S14 | `plan_cache` decisions | one case: 3 misses, 0 hits (a hit needs a second case through the same cache) | fixture test runs two cases: second case 3 hits, fewer `plan_factor` calls |
| S14b / S14c | scheduling order of Pairokar | no per-case effect by design | test: FIFO order differs from urgency on the six-file batch |
| S14d | `prefix` signals | yes (31% shared prefix tokens) | |
| S15 | `reasoning_first` decisions | yes (+578 tok) | |
| S16 / S16b | chunking strategy of the stores | no per-case effect by design (`systems.VARIANT_SCOPE: retrieval_only`) | test: proposition units differ from structure chunks on the same order; late keeps the boundaries |
| S17 / S17b / S17d | `injection` signals: `spliced`/`unmarked` x23 | yes | |
| S17c | `missed` counter, no `injection_flag` event | no on the dev case (no instruction-like text in it) | unit test with an instruction-like payload: guard on flags the path, S17c only counts it |
| S18 | `authority_stance` decisions; adverse authority offered with warning | yes (+2,066 tok, brief differs) | |
| P5 / P6 / P7 / P8 | page-search / split / vision / keep-weak calls | no on dev case (bundle only: the facts are filed as text) | bundle tests: P5 no `search_pages`, P6 no `split_bundle`, P7 all 14 pages to vision, P8 `keep_weak` reaches the ladder (the pdf level test is `tests/unit/ingestion/test_keep_weak_text.py`) |
| b0 b0l b0s b1 b2 b3 b4 b6 | baseline runners | pass | not variants |

Dead counter noted (privacy owner): `privacy/defences.Tally.calls` ("model calls seen") is never incremented, so `injection.*.calls` is always 0.

## Not done / next steps
- Train the store-prior artefact (S6 is a no-op without it). Needs gold-labelled TRAIN orders.
- S7/P5-P8 need T2 bundle cases (`testsets/t2/driver_cases.jsonl`, eval side) to show on a driver run.
- Harshita: verify the Rights rule texts and set `last_verified` (above). Frontend/API: show `verification`.
- Privacy owner: fix the nonce/phone-number false positive at its source (the agent-side re-derivation is a safety net).
- Rescue of unclean order splits with a real labeler has only been tested with a fake client (no hosted call was made).

## Leftovers in agents
`agents/base.py` abstract `run` and `stores/base.py` abstract methods raise NotImplementedError by design. `except NotImplementedError` in `sutradhar/agent.py` (truth-maintenance helpers), `vakeel/facts.py` (hash helper fallback) and `munshi/decisions.py` are defensive fallbacks, not reachable stubs. The `TODO: tune on dev` notes (authority weights, ingestion thresholds, hierarchy) are tuning, not missing code. No dead branch found that a default run reaches.

## Test results (2026-10-27)
- `tests/unit/{agents,tools,tools_drafting,pipelines,stores,models,ingestion,batch,rights,schemas}` and `tests/unit/eval/test_variant_effects.py`: 2,389 passed (run before the last agent-side change); `tests/unit/agents` and `tests/unit/tools_drafting` re-run after it: 638 passed.
- `tests/integration` and `tests/system` (900 s cap, background): 413 passed, 3 failed, 6 deselected. The 3 failures are the ones already listed as test-versus-design conflicts in `docs/handoff/regression-2026-10-26-b.md` (flow4 redrafted ground, change-set reopen, weak-slot relaxation); none touches code changed here.
- `make smoke`: SMOKE OK, export blocked before Gate 2. `driver smoke-all` offline: 61 of 61 ids pass.
- New tests: `tests/unit/eval/test_variant_effects.py` (42), `tests/unit/pipelines/test_order_splitter_rescue.py` (8), `tests/unit/tools_drafting/test_assemble_application_real.py` (2), `tests/unit/rights/test_unverified_surface.py` (1), `tests/unit/agents/test_untrusted_tag.py` (2). Ruff clean on every file touched.

## Privacy false positive on the spotlight tag, and the trained S6 / B5 store prior

**Root cause.** `wrap_untrusted` tags its delimiter with 12 hex characters (a SHA-256 prefix). The phone pattern `(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)` matched any ten-digit run inside such a tag (`cc9937724702`), so the boundary refused the call (`privacy_boundary`) under S10 and under any hosted call whose wrapped text carried such a tag. Fixed in `privacy/`, not in the wrapper:

- `pseudonymise._PII` phone: now `(?<![\da-f]{2})(?<!\d)(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?![\da-f])`. It no longer matches inside a lowercase hex token, and it now also catches the spaced form `98765 43210` (before, only ten contiguous digits). A single letter glued before the number (`phone9876543210`) still counts.
- `pseudonymise._PII` 12-digit ID: `(?<![\da-f]{2})(?<!\d)(?<![A-Z]{4})\d{4}\s?\d{4}\s?\d{4}(?![\da-f])` (before: `(?<!\d)(?<![A-Z]{4})\d{4}\s?\d{4}\s?\d{4}(?!\d)`).
- `boundary._find_problems`: the delimiter `<<<(END_)UNTRUSTED_DOCUMENT_DATA <12 hex>>>>` is blanked before the checks, so a tag of twelve digits (about 0.4 % of tags) is not read as an ID number either. Client text next to a block is still checked (test).
- `BaseAgent.untrusted` no longer re-derives the tag (the workaround is removed); `tests/unit/agents/test_untrusted_tag.py` was reconciled to assert the same text passes unmodified.
- `Tally.calls` was never incremented: `BaseAgent.ask` now counts one per model call (`injection.<agent>.calls`); asserted in `tests/unit/eval/test_variant_effects.py`.
- Tests: `tests/unit/privacy/test_hash_tag_false_positive.py` (tags pass; real numbers with `+91`, separators, glued prefix and 12-digit Aadhaar-like numbers are still refused).

**Store prior (S6 / B5) is now trained.** Build and train in one command (offline, no model call, about 50 s, needs `data/interim`):

```bash
.venv/bin/python scripts/build_store_prior_train.py            # --n 1500 --seed 17; --interim and --out-dir default to <VS_DATA_DIR or data>/interim and /eval
```

It samples at most 1,500 TRAIN-split High Court orders dated before 2024 with a clean split, balanced round-robin over (court, BNS era), after dropping the 464 excluded ids (test plus same-FIR, `pipelines.leakage.excluded_doc_ids`; dev, blind and test ids are never train in `splits.json`). Labels are the rule labelers on the court's own text (G1 rule labels, G2 resolved citations through `oil_metadata`, G3 sections, split parts); no hosted model, no manual label. Outputs under `data/eval/` (gitignored): `store_prior_train_orders.jsonl` (11 MB), `store_prior.json` (the artefact, 0.7 MB, digest `f503cecee94a12fa`) and `store_prior_manifest.json` (copy in `docs/results/store_prior_manifest.json`). Stats: 115,988 orders scanned, 25 courts, 1,500 orders used, 16,196 training rows, 2,636 store/factor pairs skipped as unknown. Limit: every sampled order is IPC era (BNS-era orders are dated 2024-07 or later, so none is in the train window); the era is in the context key, so BNS cases back off to the court and factor levels.

Where the variants look: `store_prior.default_artefact_path()` = `$VS_STORE_PRIOR` if set, else `<VS_DATA_DIR or <repo>/data>/eval/store_prior.json`. From a worktree with `data/` symlinked nothing more is needed; otherwise `export VS_STORE_PRIOR=/abs/path/data/eval/store_prior.json` (a sweep or Sarvam run that sets `VS_DATA_DIR` to another folder must copy `store_prior.json` into its `eval/` or set `VS_STORE_PRIOR`). With the artefact present the `store_prior_untrained` event disappears and `trained` is true in the signals. On the case-0007 fixture the trained prior leaves the one two-store slot in contract order (the court's text gives caselaw reasoning and similar the same label); the test `test_s6_trained_prior_changes_the_store_order_and_drops_the_untrained_event` uses a prior that prefers similar orders to show the reorder.
