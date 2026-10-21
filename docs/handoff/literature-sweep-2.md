# Literature sweep 2: verification and adversarial variants (handoff)

Variant ids follow `docs/evaluation-plan.md` section 3.3. Golden for default-off equivalence:
`tests/unit/agents/vakeel/golden_default_run.json` (digests of the offline case-0007 Vakeel + Abhiyojak run, captured from the HEAD versions of
the Vakeel files before any change; helper `tests/unit/agents/vakeel/_variants_helpers.py`; test `test_variants_golden.py`).

| Variant | Switch | Status |
|---|---|---|
| S8 / A2b self-critique repair | `repair_mode='self_critique'` | DONE |
| S10 / A8c no-isolation sparring | `abhiyojak_isolation=False` | DONE |
| S9 / A8b sampling-only critic | `critic_mode='sampling'` | DONE |
| S15 / A13 reasoning-first output | `output_format='reasoning_first'` | DONE (S15b free_then_parse not built) |
| S11 (a) three-role review | `critic_mode='three_role'` | DONE |
| S11b/c draft debate and vote | `draft_mode='debate'`, `'vote'` | DONE |

## S8 (done)
Files: `agents/vakeel/agent.py` (`_self_review`, `_run_check` branch, `_guard_problems` extracted from `_check_sentence` unchanged, `_offered_sources` extracted from
`_reword`, `repair_signals`, `_emit_repair_signals`, `SELF_CRITIQUE_NOTICE` open issue), `prompts.py` (`TASK_SELF_CRITIQUE`, `TASK_SELF_REVISE`, `SelfReview`),
`offline.py` (`self_critique_offline`), `work.py` (problem word), `orchestration/state.py` (`variant_signals`, empty by default), `switches.py` (`S8` in `IMPLEMENTED_VARIANTS`).
Tests: `tests/unit/agents/vakeel/test_variants_self_critique.py`, `test_variants_golden.py`; reconciled `tests/unit/orchestration/test_switches.py` (`# RECONCILED`).
Signals: `state.variant_signals['repair']`, events `self_critique` (per claim) and `repair_signals` (cumulative; the last one is final; replies made through Sutradhar's `_spar` update it).
Notes: the offline stand-in accepts everything except uncited or repeated sentences, so offline S8 never repairs by itself; use a scripted or hosted model for behaviour.

## S10 (done)
Files: `agents/abhiyojak/isolation.py` (`build_open_context`, `vakeel_view`, `NOTE_TOOLS`), `agent.py` (`isolated`, `system_prompt`, `_instructions`, `_context`, `_view_for`, `guard`,
`_log_llm` token tally, `critic_signals`, `_emit_critic_signals`, `run` adds `variant_signals['critic']`), `prompts.py` (`SYSTEM_PROMPT_OPEN`, `NO_ISOLATION_NOTE`), `switches.py`.
Tests: `tests/unit/agents/abhiyojak/test_variants_no_isolation.py` (11); reconciled `test_switches.py`.
Notes: default `guard` still raises `ContextIsolationError`; `build_open_context` raises unless the switch is off; `list_objections_one_call` stays isolated. Offline S10 yields the
same objections as the default (the rule-based stand-in ignores what it reads); the arm's effect needs a real model. `critic_signals()['tokens']` is the agent's own spend (used by S9 for the equal-token budget).

## S9 (done)
Files: `eval/ablations/a8b_sampling_critic.py` (new: `SamplingCritic(AbhiyojakAgent)` replaces only `raise_objections`; `reference_tokens`; `install`; offline handler), `eval/runners/driver.py`
(`wire_variants` puts the critic in Sutradhar's `_peers`; `collect_variant_signals` adds `variant_signals` to the result only when a variant ran), `switches.py` (S9 implemented; new validator:
`abhiyojak_isolation=False` cannot combine with `critic_mode` sampling / three_role). Signature changes: none to existing functions.
Tests: `tests/unit/agents/vakeel/test_variants_sampling_critic.py` (21); reconciled `test_switches.py` (S9 in the implemented set, dispatch test now uses S7).
Equal tokens: the arm stops before a sample that would pass the budget (estimate: mean of past samples, else prompt plus 300); pass the reference as `case['sparring_tokens']`
(`reference_tokens(events)` of the paired Full run, round 1 only). Open: the runs.yaml job for S9 is not added (configs/eval is outside this sweep).

## S15 (done)
Files: `agents/vakeel/prompts.py` (`DraftedGroundReasoned`, `ReasonedReply`, `REASONING_NOTE`), `agents/vakeel/agent.py` (`_schema_and_limit`, `_ins`, `_keep_reasoning`, `reasoning_of`, `output_signals`,
`_emit_output_signals`, `REASONING_ROOM`; draft, reply and reword calls), `offline.py` (`_with_reasoning`), `switches.py`. Tests: `tests/unit/agents/vakeel/test_variants_reasoning_first.py` (12).
Scope: Vakeel only (the plan also names Peshkar and Sutradhar prompts; those agents were not touched here). The reasoning text lives in `reasoning_first` events (first 1500 characters) and `VakeelAgent.reasoning_of`.
The BailBrief schema is unchanged (no reasoning in exports).

## S11 (a) (done)
Files: `eval/ablations/a8d_three_role.py` (new), `driver.wire_variants`, `switches.py`. Tests: `tests/unit/agents/vakeel/test_variants_three_role.py` (7); reconciled `test_switches.py`.

## S11b / S11c (done)
Files: `agents/vakeel/agent.py` (`_draft_many`, `_medoid`, `_similarity`, `draft_signals`, constants `DRAFT_SAMPLES`, `DRAFT_TEMPERATURE`, `CONVERGED`), `prompts.py` (`TASK_DEBATE`), `offline.py` (`debate_offline`).
Tests: `tests/unit/agents/vakeel/test_variants_draft_modes.py` (11). Ground drafting only; aggregation is a medoid; tokens reported, not equalised.

## Not done
S15b (`free_then_parse`); the `runs.yaml` jobs for S8-S11, S15 (configs/eval is outside this sweep); Peshkar and Sutradhar schemas for S15.
The validator refuses `abhiyojak_isolation=False` with `sampling` and `three_role`.
