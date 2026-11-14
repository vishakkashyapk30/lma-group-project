# Why the sparring step leaves objections unanswered (2026-11-15)

Question: in all six recorded demo runs every objection ended UNANSWERED, and on the frozen blind slice 86% of the winner's 599 objections did (10% answered). Bug or inherent?

## Verdict
Not a bug in the judge, and not mainly a weakness of the replies. It is **token-budget starvation** that the product records as "unanswered". Most objections are never judged: the reply and judge calls are refused with `BudgetExhausted` (`agents/base.py`, `ask`) because the factor's drafting pool (16,000 tokens, `configs/budgets.yaml`) or the case cap (150,000) was already spent by Vakeel's drafting and repair. `_judge_one` (`agents/abhiyojak/agent.py`) then returns UNANSWERED with the reason "The reply could not be judged; counsel to read it." That fail-safe is by design, but the budget was calibrated on a smaller measured spend (`pilot-hosted-model.md`: 12.0K to 12.8K per factor plus 25% headroom) and Sarvam-105B spends 16.4K to 20.3K per factor on drafting alone. No code was changed: the cure is a budget policy decision that changes default behaviour and the golden event digest (see the proposal).

## Counts, six demo cases (`demo/cases/*/events.jsonl`: `model_failed`, `reply`, `verdict`, `BUDGET_HIT` events)
| Case | Objections | Reply never drafted (call refused) | Reply drafted (all NEEDS_REVIEW) | Judge call refused | Judged for real |
|---|---|---|---|---|---|
| 01 cheating | 7 | 7 | 0 | 7 | 0 |
| 02 theft | 3 | 1 | 2 | 3 | 0 |
| 03 NDPS small | 6 | 2 | 4 | 6 | 0 |
| 04 NDPS commercial | 6 | 6 (5 budget, 1 privacy boundary) | 0 | 6 (5 budget, 1 privacy) | 0 |
| 05 attempt to murder | 9 | 9 | 0 | 9 | 0 |
| 06 breach of trust | 10 | 4 | 6 | 9 | 1 ("only restates the custody duration") |
| Total | 41 | 29 | 12 | 40 | 1 |

40 of 41 (98%) were refused before judging; 1 was a real judgement. The objection-raising call was also refused in 5 of 6 cases (01: 3 factors, 02: 2, 03: 1, 04: 5, 05: 3), so fewer objections were raised than the plan allows. The case cap was hit in 01, 03, 04, 05 (150.3K to 154.6K); the per-factor drafting pool was hit 3 to 7 times per case in all six (16.4K to 20.3K spent). In 02 and 06 the case cap was not reached, so the drafting pool alone starved the sparring step. The 12 drafted replies are all NEEDS_REVIEW because the repair call (`vakeel.reword_claim`) was refused too (3, 22 and 11 refusals in 02, 03, 06).

Mean tokens per call in the demo runs: reply 3.1K, judge 0.8K (one call only), raise-objections 5.4K, repair (reword_claim) 3.4K, draft_ground 3.7K. The 127 repair calls took 427K of the 1,198K tokens charged (36%).

## Counts, frozen blind slice (80 orders, winner s13+..., event logs under `data/eval/dev_runs/sarvam_blind/outputs/s13*/_events` in the frozen run worktree, read only)
599 objections: 406 (68%) never judged (394 refused for budget, 11 by the privacy boundary, 1 `ModelUnavailable`); 109 (18%) judged UNANSWERED; 26 (4%) PARTLY; 58 (10%) ANSWERED. Replies: 208 never drafted (177 budget, 31 privacy boundary), 216 NEEDS_REVIEW, 101 REPAIRED, 74 SUPPORTED.

Of the 109 judged unanswered: 79 say the reply restates or gives no facts or authority, 28 other, 2 "counsel to"; 26 carry the NO_REPLY text (no supported reply could be drafted); 36 name the NDPS s.37 bar.

## Classification of the four causes asked about
- (a) every reply sentence withheld by the checker (strict abstention): small. 26 of 599 blind objections were judged with the NO_REPLY text; in the demo runs none (their empty replies are refused calls, not withheld sentences).
- (b) reply cites law but no case facts: 79 of the 109 judged unanswered (13% of all 599).
- (c) objection not applicable: 72 objections are on the statutory-bar factor, 59 of them in orders whose text does not mention NDPS or narcotics (keyword check, approximate), 53 of those unanswered (9% of all). The judge has only ANSWERED, PARTLY, UNANSWERED, so it can never say "does not apply". Inherent in the three labels; not changed.
- (d) code bug: none found in ids, parsing or what the judge sees (it receives the reply text, its check, authorities and the objection facts). The dominant cause (406 of 599 blind, 40 of 41 demo) is the budget refusal, a calibration defect that fails safe to counsel.
- The offline stand-ins cannot reproduce this: the offline Abhiyojak raises no objections (`driver smoke` prints "no objections raised by the offline stand-in"), and the scripted-model unit tests of the judge pass the reply through correctly.

## What changed
Documentation only: this note, and two sentences in the report (`docs/report/sections/blind.tex` failure example 2; `limitations.tex` "Absolute quality") saying 68% of objections were never judged and only 18% were judged unanswered. The frozen numbers (599, 86%, 10%) are unchanged; they describe the frozen code and were not re-measured.

## Proposal (one, not applied)
Give the sparring step its own token reserve so replies and judging cannot be starved by drafting: an opt-in switch (for example `sparring_reserve_tokens`, default 0, byte-identical) that, when positive, charges Abhiyojak's calls and Vakeel's reply and reply-repair calls to a separate pool of that size and lifts the case cap by it for those calls. Sizing from the demo numbers: about 3.9K per objection (reply plus judge) plus repair, so 60K covers 7 to 10 objections. Expected effect: the judge runs on every objection, so UNANSWERED falls toward the judged share (18% on the blind slice) and the Gate 2 lists of the demos show real verdicts; causes (b) and (c) remain. Cost: about 30K to 40K more tokens per case (about 20%). Golden digests (BUDGET_HIT counts) stay unchanged only while the switch is off. Needs a paper-style docstring citation and a row in `docs/literature-to-code-map.md` (budget allocation is an engineering choice; cite the repo's own pilot note).
Cost to test (not run; no hosted calls): re-record the six demo cases, about 75 Sarvam calls each (the demo runs cost INR 2.9 to 3.6 each, about INR 20 in total); on the 30 development orders about 30 x 75 = 2,250 calls. Zero-cost interim step: add a sentence to the SPAR tour captions that objections left open are for counsel to answer (the Gate 2 list already carries them).

## How to check
Read `demo/cases/<slug>/events.jsonl` and count `AGENT_MESSAGE` events whose `tool` is `model_failed` (outputs.task, outputs.error), `reply` (outputs.drafted, outputs.check) and `verdict` (outputs.reason), plus `kind == BUDGET_HIT` (outputs.spent, outputs.cap). The same on the blind event logs named above.
