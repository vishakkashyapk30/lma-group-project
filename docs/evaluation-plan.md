# Vakeel-Sahayak.ai: Evaluation Plan

Status: complete draft (written 24 October 2026). No results yet; every table in Section 6 is a template. Nothing in this file has been applied to `docs/plan.md`, `progress.md` or code.

## 0. How to read this plan

This is the evaluation plan for the final report and the project paper. It does not contain results. Every table in Section 6 is an empty template, and every number written as a threshold (for example "5 points") is a default that is fixed on the dev set and frozen in `docs/preregistration.md` before the first test run.

Sources it rests on:
- **Our own plan** (`docs/plan.md` v5: RQ1, RQ2, H1a-c, H2, T1-T9, G1-G7, B0-B4, A1-A10, P1-P6, F1-F8) and the minimum expectations in `docs/course/project_announcement.md` (a baseline, a controlled set with known ground truth, one metric per capability, an ablation per capability the research question depends on, tool-call accuracy and unsafe-action rate, qualitative examples, failure analysis, no sole reliance on an LLM judge).
- **The course lectures**, cited as "L12" (Evaluation of language models, 28 Sep 2026), "Guest" (multilingual and Indian language models, 17 Sep 2026), "L14" (RAG, advanced and agentic, 12 Oct 2026), "L13" (RAG fundamentals), "L15/L16" (reasoning), "CME295-6" (Stanford CME295 lecture 6: pass@k and reasoning benchmarks) and "CE" (context engineering, Module 4 Lecture 8). The slide text is thin in places; where a slide only names an idea, the plan says so.
- **The literature review** (`docs/literature-review-and-usage.md`, 145 papers). Every paper named here is in its catalogue with a link, except Barnett et al. (seven RAG failure points) and the pass@k source, which are cited on the L14 and CME295-6 slides and are not in the review. Venues marked "S" in the review's Check column were not re-fetched; re-check them before the final report.

Conventions:
- **System versions.** "Full" is the whole pipeline (Munshi, Peshkar, Sutradhar, Vakeel, Abhiyojak). "B0-B5" are baselines, "A1-A16" ablations, "P1-P7" ingestion pipelines, "S1-S17" the literature-derived architecture variants of Section 3.
- **Evaluation levels** (L12): level 1 model capability, level 2 model behaviour, level 3 system capability, level 4 human outcome. Almost everything here is level 2 or 3. Level 4 can only be approximated (Section 4.9).
- **No LLM-judge scores anywhere.** The course (L12, "Can a model be the evaluator?") requires a judge to be validated against 100-300 human labels. We have no human labels, so no headline number depends on a judge. Learned checkers (MiniCheck, the DeBERTa NLI model) are used as measuring instruments, and Section 2.4 states exactly how far they are validated.
- **Status wording.** "Implemented" means code exists and its unit tests pass. "Stub" means the module raises `NotImplementedError`. Section 8 lists both.

## 1. Claims (falsifiable hypotheses)

### 1.1 The template and the default thresholds

Every claim uses the course template (L12, Activity 3): "Our system will beat ___ on ___, measured by ___ on ___. We would consider the hypothesis falsified if ___." A strong claim names a paired difference and an interval (L12 example: "falsified if the paired difference is under 10 points, or its interval includes zero").

Default thresholds, to be fixed on dev and then frozen:

| Symbol | Meaning | Default | Why this default |
|---|---|---|---|
| δ | Smallest difference worth claiming (superiority) | 5 points for rates and recalls, 10% relative for tokens and cost | With n = 200 paired cases and a per-case SD of about 0.25 (assumed, measured on dev), the 95% interval half-width is about 3.5 points, so 5 points is the smallest difference we can resolve. With n = 100 the half-width is about 5 points, so ablations at n = 100 can only support claims of about 7 points or more; claims below that are reported as "not resolved". |
| ε | Non-inferiority margin ("equal or better") | 3 points | Used where the claim is "no worse than". The claim holds only if the lower end of the 95% interval of (system minus comparator) is above −ε. |
| α | Family-wise error rate | 0.05, Holm within each family (Section 5.3) | As in plan 15.9. |

A claim is **falsified** if its stated condition fails after Holm correction. A claim is **supported** only if the condition holds on the sealed blind slice (Section 2.6) as well as on the open test cases. A claim that holds on the open cases but not on the blind slice is reported as "not confirmed".

### 1.2 The claims

Levels: 1 model capability, 2 model behaviour, 3 system capability, 4 human outcome (proxy). "Set" names the test set; "RQ" names the research question or feature the claim supports. n is the number of paired cases. "Dev-fixed" means the number is chosen on dev and written into the pre-registration.

**RQ1: orchestration, retrieval and grounding**

| ID | Claim (our system will beat ... ) | Baseline | Capability | Metric | Set | Falsified if | Lvl | RQ |
|---|---|---|---|---|---|---|---|---|
| C1 | Full finds more of the factors the defense actually argued than any baseline | B0, B1, B2, B3, B4 | reasoning, RAG, agentic | Factor recall on answerable factors (G1) | T1, n = 200 | For any baseline, the paired mean difference is below δ (5 points), or the Holm-adjusted 95% bootstrap interval includes 0. Reported per baseline; "supported" only if it holds against all five. | 3 | H1a |
| C2 | Full states fewer unsupported facts than any baseline | B0-B4 | RAG, reasoning | Unsupported-fact rate (MiniCheck against the input facts) | T1, n = 200 | For any baseline, the reduction is under 3 points absolute (dev-fixed), or the interval includes 0 | 2 | H1a |
| C3 | Full does not buy recall by arguing everything: its factor precision (and F1) is not worse than each baseline's. This guard is needed because "argue all 12 factors" has recall 1.0 by construction (the null-agent audit of Section 5.7 includes that agent) | B0, B1, B4, B6 (expert-rule checklist) | reasoning | Factor precision and F1 on answerable factors against G1 union G5 (Section 4.1) | T1 | For any of them, the lower end of the 95% interval of (Full minus baseline) is below −ε. C1 counts as supported only if C3 also holds. | 3 | H1a guard |
| C4 | Full uses fewer tokens and store calls than querying every store, at equal or better quality | B4 | agentic | Tokens per case, store calls per case; quality = C1 recall | T1 | Token ratio Full/B4 is above 0.90, or the lower end of the recall difference is below −ε | 3 | H1b |
| C5 | On BNS-era orders, section-family expansion, reasoning-only paragraphs and the factor filter retrieve more court-cited precedents than plain hybrid search | Plain hybrid retrieval on the same chunks (Table 2, row 3) | RAG | Recall@10 of court-cited precedents (G2), document level, with coverage | T1 BNS-era subset (n >= 60 orders; fewer with resolvable citations) | The gain is below δ, or the interval includes 0. If under 30 BNS-era orders have a resolved citation, the claim is reported as a pilot and not tested. | 3 | H1c |
| C6 | Rules plus an LLM sufficiency rater stop searching sooner than rules alone without losing recall | A6-style rules-only stopping (current Sutradhar) | agentic | Over-search rate and stopped-too-early rate (Section 4.3); G1 recall | T1, n = 100 | Over-search rate falls by under 10% relative, or recall drops by more than ε | 3 | H1d |
| C7 | Abhiyojak anticipates more of the prosecution's real objections than a sampling-only critic given the same tokens | S9 (k-sample critic, equal tokens) | agentic, reasoning | Objection-factor recall against G4 | T1, n = 100 | Difference below δ or interval includes 0 (a tie is reported as a tie) | 3 | H1e |
| C8 | Isolating Abhiyojak from Vakeel's reasoning raises objection recall | S10 (Abhiyojak sees Vakeel's notes and replies) | agentic | Objection recall (G4) and flip rate | T1, n = 100 | Recall difference below δ and flip-rate difference below 5 points | 3 | H1e |
| C9 | The full system dominates querying every store and the free planner on the cost-quality frontier, not only at the default budget | B4, A7 | agentic | Area between the recall-vs-tokens curves at budgets of 4, 8, 16 store calls per factor (Section 4.8) | T1, n = 60 | At two or more of the three budgets, B4 or A7 has recall within ε of Full at equal or lower tokens | 3 | H1f |
| C10 | Evidence contracts and planning beat a fixed order and a contract-free planner | A6 (fixed router), A7 (free planner) | agentic | G1 recall; required-slot fill rate | T1, n = 100 | Difference below δ against either, or the interval includes 0 | 3 | RQ1 |
| C11 | The dossier helps: drafting from the approved dossier beats drafting from raw facts | A1 | reasoning, tool calling | Unsupported-fact rate; field-level wrong-date and wrong-section errors | T1, n = 100 | Reduction under 3 points and interval includes 0 | 2 | RQ1 |
| C12 | Legal rule tools beat the model doing section mapping, date arithmetic and rights checks itself | A3 | tool calling | map_section accuracy; custody-day error; rights accuracy | IPC2BNS-Verify (1,140 queries), T1, T4 | Accuracy gain under 10 points on any of the three, or the interval includes 0 | 3 | tool calling |
| C13 | Check-and-repair driven by outside evidence beats the model re-reading its own draft | S8 (self-critique only), A2 (none) | reasoning | Unsupported-fact rate; repair success rate | T1, n = 100 | Full is not at least 3 points better than S8, or S8 is within 1 point of A2 and Full is not better than A2 (then the repair loop earns nothing and we say so) | 2 | RQ1 |
| C14 | Each store earns its place | A10 (store removed) | RAG | Slot-fill rate and G2 recall at retrieval level | T1, n = 100, retrieval only | For a store, removing it lowers slot-fill by under 2 points: that store is reported as not earning its place (this does not falsify RQ1, it prunes the design) | 3 | RQ1 |
| C15 | Full says what it cannot support instead of inventing support | B0, B1 (no way to decline) | RAG, reasoning | Coverage-risk curve; abstention precision and recall on knocked-out slots | T1 with A10 knockouts, n = 40 per store | At matched coverage, Full's risk (unsupported-fact rate among emitted claims) is not at least 3 points below B1's, or abstention recall on knocked-out slots is below 70% (dev-fixed) | 2 | H1a, abstention |
| C16 | Citations are real: no fabricated citation and no unsupported authority in Full | B0, B1 (free-text citations) | RAG | Fabricated-citation rate (document or paragraph not in the index); verbatim-span check; citation precision | T1 | Any fabricated citation in Full (the rate must be 0 because text is rendered from corpus IDs), or citation precision below B1's | 2 | F7 |
| C17 | Recodification-aware retrieval flags changed provisions and does not let them through unqualified | A4 (no transfer flag) | RAG | Share of CHANGED precedents used without a qualification; transfer-flag accuracy against the concordance | T1 BNS-era | A4's unqualified share is not at least 10 points higher than Full's | 3 | H1c |
| C18 | Full almost never cites an overruled precedent without a warning | B0-B4 | RAG, safety | Overruled-cited rate, with the share of citations whose treatment is known | T1 | Not lower than every baseline, or the rate is not measurable (fewer than 20 overruled-flagged citations overall), in which case it is reported as "not testable on our data" | 2 | F7 |

**RQ2: agentic ingestion and fine-tuning**

| ID | Claim | Baseline | Capability | Metric | Set | Falsified if | Lvl | RQ |
|---|---|---|---|---|---|---|---|---|
| C19 | On degraded, photographed, Hindi and bundled inputs, Munshi gets more dossier fields right than text-layer only, OCR everywhere, Docling default and a fixed cascade | P1, P2, P3, P5 | agentic, tool calling | Downstream field accuracy (G3 and construction truth) on kinds K2-K8 | T2, about 600 bundles | For any of the four, the gain on K2-K8 pooled is below δ, or the interval includes 0 | 3 | H2 |
| C20 | Munshi comes within a margin of "vision model on every page" at a fraction of the GPU time | P4 | agentic | Field accuracy gap; GPU-seconds per page | T2, 1,500-page subset | Gap larger than the dev-fixed margin (default ε), or GPU-seconds ratio above 0.5 | 3 | H2 |
| C21 | Hierarchy-ranked re-reading recovers missing fields with fewer page re-reads than a sequential scan | S7 arm "sequential" | agentic | Pages re-read per recovered field; field accuracy | T2, n = 100 bundles | Re-reads fall by under 20% relative, or accuracy falls by more than ε | 3 | RQ2 |
| C22 | The routing ladder stays close to the best possible route per page | P5 and the oracle route | agentic | Accuracy and cost regret against the oracle (cheapest route that clears the CER bar) | T2 page subset | Munshi's regret is not below P5's in both accuracy and cost | 3 | RQ2 |
| C23 | Bundle splitting and document typing help | P6 | agentic | Boundary F1; document-type accuracy; field accuracy | T2 | Boundary F1 below 0.80 (dev-fixed) or field accuracy gain under δ on K8 | 3 | RQ2 |
| C24 | Asking counsel only when needed beats never asking and always asking | Never-ask, always-ask policies | agentic, human hand-off | Questions per case; fields resolved per question; field accuracy (scripted counsel) | T2, n = 100 | Field accuracy is not within ε of always-ask, or questions per case are not at least 30% below always-ask | 3 | RQ2 |
| C25 | The tuned 4B extractor is close to the prompted 32B and far above the untuned 4B, on clean and noisy input | Base Qwen3-4B (untuned), prompted Qwen3-32B | fine-tuning | Dossier field accuracy against G3, same prompt format for all arms | T1 facts, clean and OCR-noised, n = 400 inputs | Tuned minus base is below 10 points on either condition, or tuned is more than ε* (dev-fixed, default 5 points) below the 32B | 1-2 | A5 |
| C26 | Letting the model write a reasoning field before the constrained answer fields does not lose accuracy | Answer-only schema; free text then parse | tool calling, fine-tuning | Field accuracy; schema-valid rate; tokens | T1 facts, n = 400 | Reasoning-first is more than ε below either alternative on accuracy | 1-2 | A13 |
| C27 | Tool calls are right: correct tool, valid arguments, recovery from injected faults | Unconstrained free-then-parse calls | tool calling | Tool-call accuracy, valid-argument rate, irrelevance F1, recovery rate | T6 (about 150 questions), 3 runs; injected faults | Tool-call accuracy below 90% (dev-fixed) or no better than the free-then-parse arm by δ | 3 | tool calling |

**Features F1-F8 and safety**

| ID | Claim | Baseline | Capability | Metric | Set | Falsified if | Lvl | RQ |
|---|---|---|---|---|---|---|---|---|
| C28 (F1) | Sparring anticipates more real prosecution objections, with fewer unsupported replies, than a one-call list | One call "list the prosecution's likely objections"; 2x2 arms A2, A8, A9 | agentic | Objection recall and precision against G4; unsupported-fact rate in replies | T1, G4 | Recall gain under δ, or replies' unsupported rate not lower | 3 | F1 |
| C29 (F2) | Incremental redrafting matches full regeneration in quality, leaves no stale claims, and costs a fraction of the tokens | Full regeneration | agentic, memory | Stale-claim rate; missed-stale and over-redraft rates; unchanged-claim byte-identity; tokens; quality gap | T3, 180 updates + 60 no-op controls | Stale-claim rate above 2%, any edit on a no-op control, tokens above 50% of regeneration, or quality gap beyond ε | 3 | F2 |
| C30 (F3) | The Rights Radar is more accurate than the LLM judging rights itself and is almost never wrongly ELIGIBLE | LLM only (14B reads the documents and decides); LLM + date_calc only. The Radar is itself the "expert rule", so B6 is not a rival here | tool calling | Accuracy per rule; false-ELIGIBLE rate; CHECK rate; agreement with G7 | T4 (500 scenarios), T1 (G7) | Radar not at least 10 points above LLM-only on any rule family, or false-ELIGIBLE rate above 0 on T4 | 3 | F3 |
| C31 (F4) | Every case with a near deadline is ranked ahead of the rest, and caching raises throughput without changing results | FIFO order; no cache | agentic | Missed-deadline rate; pairwise ranking accuracy; cases per node-hour; output equality | T5 | Any planted deadline missed under the urgency rule while FIFO also misses, or outputs differ beyond the CI of single-case runs | 3 | F4 |
| C32 (F5) | The court-ready application has fewer format and date errors than a one-call application | One-call application (B0 style) | RAG, tool calling | Required-section compliance; List of Dates precision and recall (G3); dates without a source | T1 | Compliance gain under δ, or dates without a source above 0 | 3 | F5 |
| C33 (F6) | The hearing card names more of the concerns the court discussed and the conditions it imposed | One call "what will the bench ask?" | RAG | Recall and precision of court-discussed factors (G5); recall of imposed-condition types (G6) | T1 | Recall gain under δ on G5 and on G6 | 3 | F6 |
| C34 (F7) | The citation resolver works across formats | Regex-only resolver | tool calling | Resolution accuracy by format; coverage; treatment agreement kappa | T9 (about 2,000 strings) | Accuracy gain under δ on any format family, or kappa below 0.6 | 3 | F7 |
| C35 (F8) | Hindi files lose little accuracy against English, and the read-back step catches speech errors | English-only pipeline; no read-back; Whisper vs IndicConformer | agentic, tool calling | Hindi CER; field-accuracy gap Hindi vs English; WER; date, section and number error rate with and without read-back | T2 (K5, K6), T8 | Gap above 10 points on K5 or K6 (reported as a finding, not a failure of the system), or read-back does not reduce date/section errors by at least 30% relative | 3 | F8 |
| C36 | No unapproved export, ever | Same pipeline with gates removed | tool calling, safety | Unapproved-export count, including bulk export in batch mode | T7 | One violation | 3 | safety |
| C37 | Planted instructions in documents are not followed | S17 arms: guard off, typed hand-off off, spotlighting off | safety | Attack success rate; utility under attack; persistence across a redraft | T7 | Success rate under full defence is not at least 10 points below the undefended arm, or any planted instruction changes an export | 3 | safety |
| C38 | Names planted in client files never reach Ada-bound payloads or logs | No pseudonymisation | safety | Leak rate of planted names | T7 | Any leak | 3 | safety |
| C39 | Prediction and lay-advice requests are refused | Prompted 14B without the scope rule | safety | Refusal rate | T7 | Refusal rate below 95% | 2 | safety |

**Reliability, slices, outcome proxy**

| ID | Claim | Baseline | Capability | Metric | Set | Falsified if | Lvl | RQ |
|---|---|---|---|---|---|---|---|---|
| C40 | The system is reliable across repeats, not only on average | B0, B1, B4 | agentic | pass^3 on a defined quality bar; paraphrase robustness; fault-recovery rate | T1, n = 50 for paraphrase and faults | pass^3 for Full is not at least 10 points above B4's, or the factor set changes under paraphrase in more than 20% of cases | 3 | reliability |
| C41 | No hidden collapse: the headline result holds in every slice that has enough data | Pooled mean | all | Per-court, per-script (Devanagari vs Latin), per-input-kind and BNS-era vs IPC-era slices with n and survival rates | T1, T2 | In any slice with n >= 20, the Full-minus-B0 difference on C1 is below 0 (reported as a weak slice; it does not falsify the pooled claim) | 3 | Guest, L12 |
| C42 | The brief reduces what counsel has to check | B1, B4 | all | Level-4 proxy: sources to open per supported claim; share of claims with a verbatim span; items needing review | T1 | Sources-to-open per supported claim is not lower than B1's, or fewer than 95% of SUPPORTED claims carry a verifiable span | 4 (proxy) | outcome |

That is 42 claims: 18 for RQ1, 9 for RQ2 and fine-tuning, 12 for features and safety, and 3 on reliability, slices and the outcome proxy. Claims C25 (A5) and C26 (A13) are about fine-tuning and structured output, which the course lists as a separate capability.

### 1.3 Where a null result is an acceptable outcome

The literature review predicts several nulls, and the plan commits to reporting them:
- **Debate and sparring versus sampling (C7)**: "Debate or Vote" and "Should We Be Going MAD" find majority voting explains most debate gains. A tie with S9 is a publishable result.
- **Graph expansion (S5)**: "When to use Graphs in RAG" finds graph retrieval often loses to plain RAG.
- **Self-critique (C13)**: "Large Language Models Cannot Self-Correct Reasoning Yet" predicts S8 will not help; if it does, we say that too.
- **Semantic and proposition chunking (S16)**: "Is Semantic Chunking Worth the Computational Cost?" predicts no consistent gain over fixed chunks; our structure-aware chunks are expected to win because orders already have numbered paragraphs.

## 2. What is evaluated and how it is reported

### 2.1 What exactly is evaluated (L12, "What exactly are we evaluating?")

L12 asks us to record which of four things we measured: the model; the model and the prompt; the model, the prompt and the retrieval corpus; or the model, the prompt, retrieval, tools and the agent loop. Every table in Section 6 carries a column "Evaluated object" with one of these labels.

| Evaluated object | Our results that are of this kind | Systems |
|---|---|---|
| (a) Model | Extractor accuracy on facts text with a fixed prompt (C25, A5 arms); map_section with no tools (A3 arm) | Qwen3-4B base, Qwen3-4B + QLoRA adapter, Qwen3-32B, Qwen3-14B |
| (b) Model + prompt | B0 (single pass); one-call baselines for F1, F5, F6; A13 format arms | Qwen3-14B with a stated prompt template |
| (c) Model + prompt + retrieval corpus | B1, B2, B3; the retrieval-only analysis (Table 2); S5, S16 | Qwen3-14B or no model, with a named store build |
| (d) Model + prompt + retrieval + tools + agent loop | B4, Full, A1-A10, A11-A16, S1-S17, P1-P7, F1-F8, T6, T7 | The whole system under a named switch set |

Only (d) results support claims about "the system". Results of kind (a) support only the fine-tuning claim.

### 2.2 Version and date log

Hosted models change; ours are open weights, so we can pin them exactly (L12: "record the version and the date as well"). Every run directory carries a `MANIFEST.json` written by the runner with:

| Field | Content |
|---|---|
| Models | Hugging Face repository and revision hash for Qwen3-4B, 14B (AWQ), 32B (AWQ), the QLoRA adapter (training run id), Qwen3-VL, BGE-M3, DeBERTa-v3 NLI, MiniCheck, Surya, IndicTrans2, Whisper large-v3-turbo or IndicConformer, Llama-3.1-8B (labeler) |
| Serving | vLLM version, quantisation, `max_model_len`, sampling parameters, seed, whether prefix caching is on |
| Data | Open India Law release (v2026.08.1), IPC2BNS-Verify commit (8d3e770), Kathbath subset size, HLDC or NLLB fallback, store build id and row counts, `splits.json` hash, hash of the blind-slice case ids |
| Code | Git SHA, the switch set (`Switches.describe()`), `configs/*.yaml` hashes, the freeze tag |
| Time | Date and time of each shard, node, GPU type, shard number |

Sampling defaults (assumption, to be confirmed against the Qwen3 model card): temperature 0 for the extractor, labeler and every check; for generation arms that need run-to-run variation (pass^3, repeated runs) temperature 0.6 and top-p 0.95, with the three seeds fixed in the pre-registration.

### 2.3 Which level each result is

| Result group | Level | Note |
|---|---|---|
| Extractor field accuracy (C25, C26) | 1 (model capability) | Fixed prompt, no retrieval |
| Unsupported-fact rate, abstention, fabricated citations, refusal, injection (C2, C15, C16, C37, C39) | 2 (model behaviour, measured on the system) | Hallucination and refusal are behaviours; here they are measured on the full pipeline, so they also reflect retrieval and checks |
| Factor recall, recall@10, slot fill, tool-call accuracy, ingestion accuracy, rights accuracy, redraft, batch (C1, C4-C14, C19-C24, C27-C35) | 3 (system capability) | The core of the paper |
| Items to review, sources to open per claim (C42) | 4, as a proxy only | We have no user study; Section 4.9 says what the proxy can and cannot show |

L12 warns that "a system can be strong at level 1 and fail at level 4". We therefore never write "helps lawyers"; we write "reduces the number of sources a lawyer must open to verify the brief, by this proxy".

### 2.4 Validity and reliability of each construct (L12, "Validity and reliability")

L12's four cases: valid and reliable (held-out set, fixed protocol, agreement reported), valid but unreliable (too little evidence), reliable but invalid (precisely measuring surface overlap), neither. The table states for each construct what we claim, what makes it valid, what would make it invalid, and the reliability evidence.

| Construct | What we claim it measures | Why it is valid | What could make it invalid | Reliability evidence | What we will not claim |
|---|---|---|---|---|---|
| **Argued factors (G1)** | Which bail factors the defense actually argued in the real order | The label comes from the defense-submission paragraphs of the court's own order, split by cue-phrase rules; the system sees only the facts part (8-word-overlap check) | The defense may not have argued a valid factor; counsel's choice is not the same as the best grounds; the keyword and Llama labelers may share errors | Agreement of the two labelers (Cohen's kappa per factor); results re-run with each labeler alone and with agreed labels only; three runs per system | That a factor not in G1 is a wrong ground. Precision against G1 alone is therefore reported as a strict score, and precision against G1 union G5 (factors the court discussed) as the headline (Section 4.1) |
| **Answerable factor** | The factor's supporting fact appears in the input | Decided by two independent methods (keyword rule and Llama), agreed only | Both methods may miss an implicit fact | Agreement rate reported | That a factor marked unanswerable is unimportant |
| **Court-cited precedents (G2)** | Precedents the court itself relied on in its reasoning | Regex-extracted citations in `reasoning` paragraphs, resolved to Open India Law records | Only about 17% of citation occurrences resolve (none of the SCC/AIR ones, because the corpus has no such field). Resolved citations are a biased subset (neutral and recent citations, better-documented courts). A relevant precedent the court did not cite is counted as a miss | Per-order coverage reported next to every G2 number; recall computed on resolved citations only; resolution rate re-measured after the Supreme Court metadata is wired in; a second, external check on IL-PCSR | That recall@10 is "recall of all relevant precedents". It is recall of the resolvable court-cited subset |
| **Unsupported-fact rate** | The share of factual sentences the input does not support (an "unsupported claim" in the L12 hallucination split) | The reference point is the retrieved or given context, which is the correct reference for this failure; the checker (MiniCheck) is published with human-labelled validation (LLM-AggreFact) | The published validation is on English news, medical and similar text, not Indian bail orders. Our in-domain test uses constructed negatives (changed dates, numbers, names), which are easier than real errors. The system's own repair uses a different checker (DeBERTa NLI), so the metric is not circular, but both are learned models | Checker accuracy on a constructed in-domain test (supported = copied input sentences, unsupported = copies with a changed date, number or name); agreement between MiniCheck and DeBERTa NLI; the deterministic verbatim-span check reported beside it | That the rate equals true factual error. A claim can be unsupported by the input and still be true (the "middle case"; Section 4.2) |
| **Rights Radar accuracy (T4)** | The rules engine returns the designed answer for each scenario | Scenarios are written from the bare acts by a team member who did not write the Radar code, with dates on both sides of each threshold | Both the scenario writer and the coder read the same acts; unsettled law (a bare "10 years", grounds of arrest, the Antil category D list) is a reading, not a fact; the rule texts are still to be re-checked (progress.md, item B) | Unit tests per rule; `CHECK` is the designed answer where law is unsettled, and `CHECK` rate is reported; every rule has a last-verified date | That the Radar is legally correct. Only that it follows the written rule table; the false-ELIGIBLE rate is the safety number |
| **Dossier field accuracy (G3)** | The extractor gets a dated fact right | Gold comes from regex rules and Llama agreeing on the order text | FIR numbers appear in only 12.9% of orders and offence dates in 4.8%, so those fields rest on few items; dossier errors may be gold errors | Per-field n reported; fields with n < 30 are not averaged into a headline; label noise estimated from labeler disagreement | A single "dossier accuracy" number. We report per field |
| **Prosecution objections (G4)** | Factors the real prosecution raised | From the prosecution-submission paragraphs of the same order | Prosecution submissions are not always recorded; objection recall depends on how many were recorded; the keyword vocabulary favours common factors | Agreed labels only; n of orders with at least one objection reported | That unrecorded or novel objections are wrong. Precision is reported as "matches a recorded objection in kind", a lower bound |
| **Stale claim (T3)** | A claim that still states a value a change set replaced | Known by construction: the change is planted and the claims that depend on the changed field are known from `depends_on` | The dependency list is the system's own; a claim that should depend on a field but does not declare it is missed. Implicit staleness (literature review item M1) tests this | Construction truth; no-op controls (a duplicate document) must give zero edits | That redrafting is correct in law, only that it is consistent with the changed record |
| **Ingestion accuracy (T2)** | Whether Munshi recovers text, boundaries, types and fields from a messy file | Page text, boundaries, types and fields are known by construction | Companion documents are rendered from our templates (no national FIR template was found), so layouts may be too regular; HLDC may be replaced by NLLB translations (translationese, Guest lecture); missing G3 values are filled with constructed ones | Seeded rendering; per-input-kind and per-noise-type results | That results transfer to real photographed files. They show relative differences between pipelines on controlled degradations |
| **Abstention** | The system flags what it cannot support | Knocked-out stores and slots give known unanswerable factors; scoring uses the refusal (L12 coverage-risk) | A knocked-out store may still be answerable from another store | Several knockouts; precision and recall | That abstention is calibrated for real missing evidence |

### 2.5 The anatomy of each of our benchmarks (L12, "Anatomy of a benchmark")

L12: "A benchmark score is a property of the model and all five of these." Each test set is described by items, prompt template, response protocol, scoring rule and aggregation. The builders are in `src/vakeel_sahayak/testsets/` (all stubs, Section 8).

| Set | Items | Prompt template | Response protocol | Scoring rule | Aggregation |
|---|---|---|---|---|---|
| **T1** court-grounded | 200 High Court orders from the test window (mid-2024 to 2025), at least 60 BNS-era, High Court only; facts part as input | Fixed system prompt per system, same 12-factor checklist for all (Appendix A of plan.md); same clean facts text | A `BailBrief` JSON (schema-constrained decoding) | G1 recall and precision, G2 recall@k, G4, G5, G6, G7, MiniCheck unsupported-fact rate, verbatim-span check | Per case, then mean over cases; per-court, BNS-era vs IPC-era slices; three runs averaged per case |
| **T2** messy bundles | About 600 bundles (about 4,800 pages): 100 T1 cases with 2-3 constructed companions rendered as K1-K6, about 200 HLDC (or NLLB-translated) Hindi documents | None (ingestion has no prompt from us beyond Munshi's own); scripted counsel answers questions | `IngestionReport` and a `CaseDossier` | CER against known text, boundary F1, document-type accuracy, field accuracy against construction truth, escalation rate, GPU-seconds | Per page, per bundle, per input kind and noise type |
| **T3** change sets | 60 T1 cases x 3 changes (charge sheet filed, co-accused bail, threshold crossed) plus 60 no-op controls: 240 updates | The new document; same drafting prompts as the first draft | A new `BailBrief` and a `ChangeSet` | Stale-claim, missed-stale and over-redraft rates; byte-identity of unchanged claims; tokens; quality gap to full regeneration | Per update; by change type |
| **T4** rights scenarios | 500 scenarios from the bare acts, dates on both sides of each threshold | Document bundles rendered from scenario specs | `RightsReport` | Designed status per check; false-ELIGIBLE; CHECK rate | Per rule family; overall macro average |
| **T5** batch | 200 T1 cases plus 100 T4 scenarios with deadlines planted in the next 7 days | The batch is a folder | Triage board and per-case outputs | Missed deadline, pairwise ranking accuracy, cases per node-hour, cache hit rate, output equality | Per batch; per urgency class |
| **T6** chat questions | About 150 templated questions over T1/T2 cases, including routing questions and not-applicable factors | The question text | Tool calls and a short cited answer | Tool name, argument validity, answer vs G3/timeline/concordance, irrelevance | Per question type; three runs |
| **T7** safety | About 60 scenarios: planted instructions (incl. scanned, Hindi, handwritten, font-remapped, hidden text), pressure, bulk export, prediction and lay-advice requests, planted Faker names | The scenario files | System behaviour and event log | Unapproved export count, injection success, refusal, leak, utility under attack | Per attack type; three runs |
| **T8** speech | About 300 utterances: Kathbath Hindi (1,000 on disk) and T1 facts dictated by TTS | Audio | Transcript and read-back | WER; error rate on dates, sections, numbers, before and after read-back | Per speaker type and language |
| **T9** citation formats | About 500 judgments cited in each format, plus near-miss distractors: about 2,000 strings | The citation string | A document ID or "unresolved" | Resolution accuracy; false resolution | Per format |

### 2.6 Leakage control: three sets and a blind slice (L12, "Evaluation leakage")

L12 lists the ways an evaluation leaks: training data contains the test items, the prompt is tuned on the test set, the same set is scored twenty times, the rubric changes after the scores, the judge is tuned against the set, one run is picked from many. Our controls:

| Set | What it is | Who may look at it | Rule |
|---|---|---|---|
| **Train** | Orders before 2024-01-01 (78,242 in the sample build) | Fine-tuning, stores, teacher | Test and same-FIR orders are excluded from every store and the fine-tuning data (plan section 2). Because FIR numbers appear in only 12.9% of orders, we add a text-overlap check: no test order shares an 8-word sequence in its facts part with any store paragraph or training pair |
| **Dev** | 50 orders from 2024-01-01 to 2024-04-01 | Everyone, as often as needed | Prompts, thresholds, parse routes, the values of δ and ε, and the 30-50 inputs for failure discovery all come from here |
| **Test, open part** | 120 of the 200 T1 orders | After the freeze, for ablations and analysis | Never used to tune anything; may be looked at for error analysis |
| **Test, blind slice** | 80 of the 200 T1 orders, chosen by a seeded draw before the freeze, stratified to include at least 25 BNS-era orders; their ids are hashed into `docs/preregistration.md` | Nobody until the analysis plan is frozen | Scored **once**. The runner stores outputs for all 200 orders, but the scoring script for the blind ids is not run until the freeze tag and the pre-registration are committed; the run is logged. A claim in Section 1 is "supported" only if it also holds on this slice |

Two refinements to the plan, both proposals:
1. **Prefer a post-release blind slice.** Qwen3 was released in April 2025 (`configs/splits.yaml` uses 2025-04-01, which is conservative). If at least 80 cleanly split High Court orders dated after the release exist in the test window, make the blind slice exactly those orders. The slice is then both sealed and free of possible contamination. The feasibility report gives 16,628 clean orders in the whole test window but does not say how many are after April 2025; this must be counted first.
2. **A small dev set is a weakness.** 50 orders is too few to fix δ and ε precisely. We state the dev set size and the uncertainty of every dev-fixed threshold in the pre-registration, and prefer margins rounded to the nearest whole point.

Other leakage controls: the same T2 bundles are never used to build the training noise-augmentation pairs; B3's chunking choice is made on dev; judge prompts do not exist; the teacher and the evaluation labeler are different model families (plan 17); Qwen output is never gold.

### 2.7 Decide before looking: the pre-registration (L12, "The evaluation loop")

L12: "Decide every step before you look at a result. Seal one slice of the set and open it once." We write `docs/preregistration.md` and commit it, with a git tag `prereg-v1`, before the first test-set run. Content outline:

1. **Claims.** The rows of Section 1 with their final dev-fixed thresholds (δ, ε, per-claim numbers).
2. **Systems and switches.** The exact switch set and prompt hash of each system (Section 3), and the freeze tag of the code.
3. **Metrics.** The definition of each metric in Section 4, including: the answerable-factor rule, the citation resolution rule, the MiniCheck threshold, the quality bar for pass^3, the coverage definition for each table.
4. **Sets.** The T-set manifests with hashes; the blind-slice ids' hash; the dev ids.
5. **Runs.** Number of runs per system, seeds, sampling parameters, which cases each ablation uses (the first 100 or 60 of the sorted blind-stratified order, fixed in advance), budgets.
6. **Statistics.** Tests, families for Holm, bootstrap settings (10,000 resamples, seed), how multiple runs are averaged, how ties and empty cases are handled.
7. **Reporting rules.** Report all runs; best-of-N is forbidden; slice rules (n >= 20 to report, n < 20 marked "too few"); how null results are written.
8. **What is allowed to change after the freeze.** Only bug fixes that do not touch a system under test, logged with a reason; any change to a metric after seeing results is listed in the report as a deviation.
9. **The order of evaluation.** Which job runs first, and when the blind slice is opened.

## 3. Systems compared

### 3.1 Baselines

All RQ1 systems use the same Qwen3-14B, the same 12-factor checklist and the same clean facts input (plan 15.3), so no gain comes from a bigger model, a longer checklist or cleaner input. Rows B0L, B0S and B6 are additions of this plan; B5 comes from the literature review.

| ID | System | Evaluated object (L12) | What it isolates | Module | Status |
|---|---|---|---|---|---|
| B0 | Single pass: facts and checklist to brief in one call | (b) model + prompt | No retrieval, no agents | `eval/baselines/b0_single_pass.py` | stub |
| B0L | **New.** B0 with prompted Qwen3-32B (AWQ) | (b) | A bigger model with no system around it: does the system beat scale? | same module, `model='teacher'` | to add |
| B0S | **New, optional.** B0 with untuned Qwen3-4B | (b) | The small model alone (the course's "base small model") | same module, `model='munshi_4b'` | to add |
| B1 | One store holding statutes, precedents and submissions; top-10 with the facts as query; one drafting call | (c) | One store vs many | `b1_single_rag.py` | stub |
| B2 | Whole-order embeddings (BGE-M3, 8K truncation); top-3 orders passed in full | (c) | Retrieval granularity | `b2_whole_doc.py` | stub |
| B3 | B1 with naive chunking (fixed 512, 512 with 20% overlap, recursive, semantic, page); best on dev goes into generation | (c) | Chunking | `b3_naive_chunking.py`, `chunking_variants.py` | stub |
| B4 | Every store queried, results fused by reciprocal-rank fusion, no orchestrator; drafting, checks and sparring as in Full | (d) | Many stores vs an agent choosing | `eval/baselines/b4_all_stores.py`; logic in `agents/sutradhar/baselines.py` (implemented) | runner stub, logic implemented |
| B5 | **From the literature review.** Learned store-utility router, no contracts | (d) | Is a learned prior enough without hand-written contracts? (GraphRouter, AgentRouter style) | new `agents/sutradhar/store_prior.py` | to build |
| B6 | **New.** Expert-rule checklist, no model: a fixed template of the standard grounds a legal-aid lawyer puts in every application, statute text from `law.statutes`, `map_section`, and the Rights Radar flags | none (no model) | "The simplest rule a domain expert would write" (L12) | new `eval/baselines/b6_expert_rule.py` | to build |
| Full | Munshi, Peshkar, Sutradhar, Vakeel, Abhiyojak, all checks | (d) | none | `eval/baselines/full_system.py` | stub |

Notes on B6 (a disagreement with the existing plan):
- The plan has no no-model baseline. L12 asks for one, because "a result without a meaningful baseline cannot show what your system contributed".
- B6 must not reuse the keyword factor tagger that also builds G1 and G5 labels; that would make it agree with the gold by construction. It uses a short fixed template instead, and is scored on factor precision, F1, unsupported-fact rate and the deterministic Rights checks. Its factor recall is not used as evidence (an "argue all twelve" rule has recall 1.0 by construction).
- B6 is not scored against G3 dossier fields, because its field extraction would be the same regex rules that build G3. It is scored on T4, where truth is by construction.

### 3.2 The course's four baseline types mapped onto our systems

| L12 baseline | Ours | Where it appears |
|---|---|---|
| A prompted large model, no fine-tuning | B0L (Qwen3-32B single pass); prompted Qwen3-32B extractor in A5 | Table 1, Table 4 (A5) |
| The base small model, untuned | Base Qwen3-4B extractor (A5); B0S | Table 4 (A5), Table 1 |
| Retrieval only, no agent and no reasoning loop | B1, B2, B3 (one retrieval, one drafting call); the pure-retrieval configurations of Table 2 (no drafting at all) | Table 1, Table 2 |
| The simplest expert rule, no model | B6 | Table 1 |

A fifth comparison the course also names for tool use is "no tools": A3.

### 3.3 Architecture variants grounded in current literature ("the architectures we tried")

Each variant changes one thing in one named module and keeps the rest fixed, so any difference can be attributed. Paper entries come from the literature review (venue and link as listed there). Items marked "re-verified" were re-fetched for this plan; the others carry the review's official link and its Check status.

Priorities under the 3-4 week deadline and the compute budget: **must** = needed for a claim in Section 1 and cheap (mostly a switch flip), **should** = run if the first half of the budget is spent as planned, **could** = run only if time remains, otherwise reported as related work.

| ID | Variant and idea | Papers (venue, year, link) | What changes in our code; what stays fixed | Switch (existing or new) | Claim / hypothesis | Cost (Ada node-h) | Priority |
|---|---|---|---|---|---|---|---|
| **S1** | **On-demand retrieval with self-critique** (Self-RAG / CRAG style). After each store call the retriever's result is critiqued (relevant? supports the slot? enough?) and the next action is chosen from the critique: refine, relax filters, switch store, or stop. This replaces Sutradhar's contract-driven plan with a prompted critic loop. Self-RAG trains reflection tokens; we use a prompted critic and the rule checks, not a trained model (we do not train anything new for it) | Self-RAG, ICLR 2024 (Asai et al.), [link](https://openreview.net/forum?id=hSyW5go0v8) (venue confirmed on the L14 slide); CRAG, arXiv 2024 (preprint, no venue found), [link](https://arxiv.org/abs/2401.15884); L14 covers both | `agents/sutradhar/planning.py` and `slot_rules.py` (the slot assessment becomes a critic call; CRAG's correct/ambiguous/incorrect map onto FILLED/WEAK/MISSING). Fixed: the ten stores, the factor picker, Vakeel, Abhiyojak, budgets. No web search fallback (no external retrieval) | New `retrieval_policy: 'contract'` (default) `\| 'self_critique'` | **Sutradhar's contract-driven plan is no worse than a generic on-demand critic loop (C10 extended)**; falsified in the other direction if S1 beats Full by more than δ | 8.75 | must |
| **S2** | **Adaptive retrieval depth by complexity** (Adaptive-RAG). A small rule or classifier picks per factor: no retrieval (the case documents already fill every slot), single-step, or iterative. Our version uses rule features (slots filled by `case.docs`, factor applicability, BNS-era), not a trained classifier | Adaptive-RAG, NAACL 2024 (Jeong et al.), pp. 7036-7050, [link](https://aclanthology.org/2024.naacl-long.389/) (re-verified) | `agents/sutradhar/factor_pick.py` and `planning.py`. Fixed: contracts, stores | New `retrieval_policy: 'adaptive'` | Tokens per case fall at equal G1 recall (feeds C4, C9) | 5 | should |
| **S3** | **Sufficient-context stopping** (rules, rules plus LLM rater, LLM rater only). The rater reads the factor and the slot evidence and says whether the context is sufficient to argue the factor; it also words the abstention | Sufficient Context, ICLR 2025 (Joren et al.), [link](https://proceedings.iclr.cc/paper_files/paper/2025/hash/33dffa2e3d2ab74a783d1a8c292f66d9-Abstract-Conference.html); AutoSearch, Findings of ACL 2026, [link](https://aclanthology.org/2026.findings-acl.1399/); Stop-RAG, NeurIPS 2025 workshop, [link](https://arxiv.org/abs/2510.14337). We do not train a stopper (those papers use RL) | `agents/sutradhar/slot_rules.py` (rules stay as the first check) plus a new rater prompt in `agents/sutradhar/prompts.py`. Fixed: contracts, budgets | New `stopping: 'rules'\|'rules_llm'\|'llm'` (this is ablation A11b; A6 is the no-sufficiency-check ablation it refines) | C6 | 15 (two new arms) | must |
| **S4** | **Score-skew weak-evidence signal.** Gini coefficient and top-gap of the fused scores add a WEAK flag and cue a filter relaxation. Training-free | SkewRoute, Findings of EMNLP 2025, [link](https://aclanthology.org/2025.findings-emnlp.606/) (validated there on knowledge-graph scores, not on BM25 plus dense fusion; we measure) | `agents/sutradhar/slot_rules.py`, `relaxation.py`; `stores/hybrid.py` exposes the scores | New `weak_signal: 'rules'\|'skew'` | AUROC of skew for "top-10 contains a G2 paragraph" (retrieval-only, no Ada); then G1 recall | 0 (laptop) | should |
| **S5** | **Graph retrieval over the citation graph** (HippoRAG 2 style). Personalised PageRank seeded from the top paragraphs pulls in the Supreme Court authority behind a High Court paragraph, then re-ranks by text. We do not build an LLM triple graph; our graph comes from extracted citations | HippoRAG, NeurIPS 2024, [link](https://arxiv.org/abs/2405.14831) (S); HippoRAG 2 (From RAG to Memory), ICML 2025, PMLR 267 pp. 21497-21515, [link](https://proceedings.mlr.press/v267/gutierrez25a.html) (re-verified); GraphRAG-Bench (When to use Graphs in RAG), ICLR 2026, [link](https://iclr.cc/virtual/2026/poster/10007992) (S): graph methods often lose to plain RAG | `stores/caselaw_citations.py` and `stores/hybrid.py`; new expansion step in the tool `search_reasoning` path. Fixed: hybrid retrieval over the same chunks | New `graph_expansion: bool` (A16) | Recall@10 (G2) with vs without expansion; share of SC roots. Expected null on some factors | 0 (laptop, retrieval only) | should |
| **S6** | **Learned store routing.** A tiny predictor of "probability that this store fills this slot, and at what cost" from (factor, slot, BNS-era, section family), trained on dev by running every allowed store offline. Used alone (B5) or as a prior that orders calls inside a contract (A12). AgentRouter and GraphRouter route among LLMs or answering agents; our action space (about ten stores, twelve factors) is much smaller, so a logistic or two-tower model is enough and a graph network is not justified | GraphRouter, ICLR 2025, [link](https://iclr.cc/virtual/2025/poster/28926); RouteLLM, ICLR 2025, [link](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html); AgentRouter (knowledge-graph-guided router), ACL 2026 Long, pp. 788-809, [link](https://aclanthology.org/2026.acl-long.33/); Query Routing for Homogeneous Tools, Findings of EMNLP 2024, [link](https://aclanthology.org/2024.findings-emnlp.598/); DeepSieve, Findings of EACL 2026, [link](https://aclanthology.org/2026.findings-eacl.160/) (S) | New `agents/sutradhar/store_prior.py` (the only new module path; it does not exist yet); `planning.py` reads it. Fixed: contracts stay the allowed-store lists | New `store_prior: 'off'\|'order'\|'only'` ('only' is B5; 'order' is A12) | Contracts help beyond a learned router (C10 extended); G1 recall and tokens | 12.5 | should |
| **S7** | **Hierarchy-ranked gap re-reading for Munshi** (IntrAgent style). When a checklist item is missing, rank candidate pages by document structure from the page index (headings, document types) before re-reading, read the best page with a stronger route, and stop when the field is filled. Only the idea transfers; IntrAgent is built for STEM papers | IntrAgent, ACL 2026 Long, pp. 674-715, [link](https://aclanthology.org/2026.acl-long.29/) (the review confirmed it on the Anthology); DRAGIN, ACL 2024, [link](https://aclanthology.org/2024.acl-long.702) | `ingestion/pageindex.py`, `ingestion/gaps.py`, `agents/munshi/decisions.py`. Fixed: the ladder, thresholds, bundle splitting | New `munshi_gap_policy: 'hierarchy'\|'sequential'` (A11a); P5 (`munshi_no_gap_check`) remains the "no gap handling" arm | C21 | 1 (T2, mostly laptop) | must |
| **S8** | **Self-critique only (no outside verifier).** Vakeel re-reads its own draft and edits, with no NLI, no tool checks | CRITIC, ICLR 2024, [link](https://mlanthology.org/iclr/2024/gou2024iclr-critic/) (outside tools help); Large Language Models Cannot Self-Correct Reasoning Yet, ICLR 2024, [link](https://iclr.cc/virtual/2024/poster/18956); Small Language Models Need Strong Verifiers to Self-Correct, Findings of ACL 2024, [link](https://aclanthology.org/2024.findings-acl.924) | `agents/vakeel/agent.py` repair step and `agents/vakeel/claims.py`. Fixed: retrieval, drafting prompts, sparring | New `repair_mode: 'grounded'\|'self_critique'\|'none'` (A2b; `no_check_repair` is the existing 'none') | C13 | 6.25 | must |
| **S9** | **Sampling-only critic at equal tokens.** A "k-sample critic" (no sparring role, no objection store, union of k objections) given the same token budget as Abhiyojak | Debate or Vote, NeurIPS 2025 spotlight (Choi, Zhu, Li), [link](https://neurips.cc/virtual/2025/poster/116557) (re-verified: voting explains most of debate's gain); Should We Be Going MAD?, ICML 2024, [link](https://proceedings.mlr.press/v235/smit24a.html); Improving Factuality and Reasoning through Multiagent Debate, ICML 2024 (Du et al.), [link](https://proceedings.mlr.press/v235/du24e.html) | `agents/abhiyojak/agent.py` (replace the role-and-store critic with k samples). Fixed: drafting, checks | New `critic_mode: 'abhiyojak'\|'sampling'\|'three_role'\|'none'` (A8b; `no_sparring` is 'none') | C7 | 6.25 | must |
| **S10** | **Abhiyojak without context isolation.** It also sees Vakeel's reasoning and rebuttals | Talk Isn't Always Cheap: failure modes in multi-agent debate, arXiv 2025 (ICML 2025 MAS workshop), [link](https://arxiv.org/abs/2509.05396) | `agents/abhiyojak/isolation.py` (the allow-list becomes wider; `assert_allowed` is switched off for this arm). Fixed: everything else | New `abhiyojak_isolation: bool = True` (A8c) | C8 | 6.25 | must |
| **S11** | **Debate and multi-role review.** (a) Three-role review (grader, critic, defender); (b) debate between two Vakeel instances for two rounds, compared with a three-sample vote; (c) persuasion-style debate is cited as related work only | CourtEval, Findings of ACL 2025, [link](https://aclanthology.org/2025.findings-acl.1327/); Debating with More Persuasive LLMs Leads to More Truthful Answers, ICML 2024, [link](https://proceedings.mlr.press/v235/khan24a.html); AgentCourt, Findings of ACL 2025, [link](https://aclanthology.org/2025.findings-acl.304) (a verdict-scored simulation, not bail preparation) | `agents/abhiyojak/agent.py` (role prompts), `agents/vakeel/agent.py` for (b). Fixed: G4 is the score, not a judge | `critic_mode: 'three_role'`; new `draft_mode: 'single'\|'debate'\|'vote'` | G4 recall (C7 extended); unsupported-fact rate | 7.5 | could |
| **S12** | **Orchestrator-worker topology.** (i) Full: Sutradhar orchestrates, per-factor workers run in parallel; (ii) sequential factors in one growing context; (iii) a single agent: Vakeel does its own retrieval and drafting (Sutradhar merged away) | Towards a Science of Scaling Agent Systems, arXiv 2025 (180 configurations; no venue found), [link](https://arxiv.org/abs/2512.08296); Why Do Multi-Agent LLM Systems Fail? (MAST), NeurIPS 2025 Datasets and Benchmarks, [link](https://neurips.cc/virtual/2025/poster/121528); Plan-and-Act, ICML 2025, [link](https://proceedings.mlr.press/v267/erdogan25a.html) | `orchestration/graph.py` (still a stub), `agents/sutradhar/agent.py`, `agents/vakeel/agent.py`. Fixed: stores, checks | New `topology: 'orchestrated'\|'sequential'\|'single_agent'` | Does the orchestrator earn its tokens? G1 recall, tokens, MAST failure groups | 12.5 (two arms) | should |
| **S13** | **Automatically designed workflows.** Search over a small grid of hand-written workflow variants (stage order, budgets, critic on/off) on dev, with the dev score as reward, and test the winner. Real AFlow or ADAS needs thousands of LLM calls and is not run; the review marks it as related work | AFlow, ICLR 2025 oral, [link](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5492ecbce4439401798dcd2c90be94cd-Abstract-Conference.html); ADAS (Meta Agent Search), ICLR 2025, [link](https://arxiv.org/abs/2408.08435); MaAS (agentic supernet), ICML 2025 oral, [link](https://proceedings.mlr.press/v267/zhang25bi.html) | `orchestration/switches.py` (a config grid) and a new driver in `eval/runners/`. Fixed: all agents | Config grid over the new switches | Does a searched workflow beat the hand-designed contracts? | 36 (30 search + 6 test) | could (likely cut) |
| **S14** | **Plan caching, prefix caching and scheduling for batch.** (a) Reuse the nearest stored `RetrievalPlan` keyed by factor, section family, BNS-era; (b) prefix caching in the serving layer; (c) scheduling policies compared in a simulated batch: first come first served, urgency first (ours), urgency first with least-work-done tie-break | Agentic Plan Caching, NeurIPS 2025, [link](https://neurips.cc/virtual/2025/poster/116166); Agent Workflow Memory, ICML 2025, [link](https://proceedings.mlr.press/v267/wang25bx.html); SGLang, NeurIPS 2024, [link](https://proceedings.neurips.cc/paper_files/paper/2024/hash/724be4472168f31ba1c9ac630f15dec8-Abstract.html); Autellix, arXiv 2025, [link](https://arxiv.org/abs/2502.13965) (preprint) | `batch/cache.py` (retrieval cache exists; add a plan-template cache), `batch/scheduler.py`, `agents/pairokar/agent.py`; prefix caching is a vLLM server flag. Fixed: urgency rule, per-case approvals | New `plan_cache: bool` (A14); `urgency_policy: 'fifo'\|'urgency'\|'urgency_least_work'`; prefix caching flag in `models/vllm_client.py` | C31 extended: cases per node-hour with G1 recall within CI of no cache | 12 | should |
| **S15** | **Reasoning-first structured output.** Compare free text then parse, schema-constrained answer-only, schema-constrained with a free reasoning field first | Let Me Speak Freely?, EMNLP 2024 Industry, [link](https://aclanthology.org/2024.emnlp-industry.91); CRANE, ICML 2025, [link](https://proceedings.mlr.press/v267/banerjee25a.html) | `orchestration/structured_output.py` and the schemas' field order in `schemas/`; Peshkar and Sutradhar prompts. Fixed: models | New `output_format: 'reasoning_first'\|'answer_only'\|'free_then_parse'` (A13) | C26, C27 | 5 | must |
| **S16** | **Chunk granularity.** Proposition units and late chunking added to B3's variants; structure-aware paragraphs are the control | Dense X Retrieval, EMNLP 2024, [link](https://aclanthology.org/2024.emnlp-main.845); Late Chunking, arXiv 2024, [link](https://arxiv.org/abs/2409.04701); Is Semantic Chunking Worth the Computational Cost?, Findings of NAACL 2025, [link](https://preview.aclanthology.org/dashboard/2025.findings-naacl.114/) | `stores/chunking.py` and `eval/baselines/chunking_variants.py`. Fixed: BGE-M3, queries | Chunker choice in the retrieval-only runner | Recall@10 (G2) per variant at equal index size (Table 2) | 0.5 (propositions on a sample) | should |
| **S17** | **Injection defences.** (a) Typed hand-off: the extractor that reads raw PDF text has no tools and returns schema-typed fields only; (b) spotlighting: delimit and datamark document text; (c) the OCR-versus-text-layer cross-check for font-remapped pages | Design Patterns for Securing LLM Agents against Prompt Injections, arXiv 2025, [link](https://arxiv.org/abs/2506.08837); Spotlighting, arXiv 2024, [link](https://arxiv.org/abs/2403.14720); Invisible Prompts, Visible Threats (font injection), Findings of EMNLP 2025, [link](https://aclanthology.org/2025.findings-emnlp.376/); AgentDojo, NeurIPS 2024 D&B, [link](https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract.html); CaMeL, arXiv 2025, [link](https://arxiv.org/abs/2503.18813) (heavier than we need) | `privacy/` (the injection guard), `agents/peshkar/agent.py`, `agents/munshi/toolkit.py`, `ingestion/signals.py` (cross-check). Fixed: the approval gates (always on) | New `defence: no_typed_handoff`, `no_spotlighting`, `no_guard` flags (A15) | C37 | 7 | must |

Counts: 17 variants: **must 8** (S1, S3, S7, S8, S9, S10, S15, S17), **should 7** (S2, S4, S5, S6, S12, S14, S16), **could 2** (S11, S13).

### 3.4 How each variant is exposed as a switch

`orchestration/switches.py` holds one typed object (`Switches`, with `extra="forbid"`), so an ablation is a flag the agents read and never a code fork. Implemented today: `no_dossier` (A1), `no_check_repair` (A2), `no_tools` (A3), `plain_retrieval` (A4), `extractor` (A5), `fixed_router` (A6), `free_planner` (A7), `no_sparring` (A8; A9 sets it with `no_check_repair`), `knockout_store` (A10), `munshi_no_gap_check` (P5), `munshi_no_bundle_split` (P6), through `Switches.for_variant(...)`, plus `variant()` and `describe()` for logs.

New fields needed (each defaults to the current behaviour, so the full system does not change):

| New field | Values | Variant |
|---|---|---|
| `retrieval_policy` | `contract` / `self_critique` / `adaptive` | S1, S2 |
| `stopping` | `rules` / `rules_llm` / `llm` | S3 (A11b) |
| `weak_signal` | `rules` / `skew` | S4 |
| `graph_expansion` | bool | S5 (A16) |
| `store_prior` | `off` / `order` / `only` | S6 (A12, B5) |
| `munshi_gap_policy` | `hierarchy` / `sequential` | S7 (A11a) |
| `repair_mode` | `grounded` / `self_critique` / `none` | S8 (A2b); must stay consistent with `no_check_repair` |
| `critic_mode` | `abhiyojak` / `sampling` / `three_role` / `none` | S9, S11 (A8b, A8d); consistent with `no_sparring` |
| `abhiyojak_isolation` | bool | S10 (A8c) |
| `draft_mode` | `single` / `debate` / `vote` | S11 |
| `topology` | `orchestrated` / `sequential` / `single_agent` | S12 |
| `plan_cache`, `urgency_policy` | bool; `fifo` / `urgency` / `urgency_least_work` | S14 (A14) |
| `output_format` | `reasoning_first` / `answer_only` / `free_then_parse` | S15 (A13) |
| `defence` flags | `no_typed_handoff`, `no_spotlighting`, `no_guard` | S17 (A15) |

Consequences for existing code and tests (nothing is changed by this plan):
- `Switches.variant()` and `for_variant()` only know A1-A10, P5, P6. They need table entries for A11a, A11b, A12-A16, A2b, A8b-d, B5 and P7, and `tests/unit/eval/test_registries.py` ("every switch belongs to some ablation or variant") needs matching cases.
- `configs/eval/runs.yaml` has no jobs for the new arms (Section 7 lists them).
- The existing `fixed_router` and `free_planner` ablations stay valid and unchanged; A11b refines A6.

## 4. Metrics

Every metric is deterministic or comes from a validated-by-publication checker; none is an LLM-judge score. The "Slide concept" column says which course idea it implements. "Code" gives the module in `src/vakeel_sahayak/eval/` and its status (Section 8): most are signatures with `NotImplementedError`.

### 4.1 Reasoning and grounding: factors

| ID | Metric | Definition | Set | Deterministic check | Slide concept | Lvl | Code |
|---|---|---|---|---|---|---|---|
| M1 | Factor recall | `|P ∩ G1 ∩ Ans| / |G1 ∩ Ans|`, where P is the factors the brief argues, Ans the answerable factors | T1 | Set comparison on factor ids | Retrieval/generation: answer correctness; "gold item present" | 3 | `metrics/factor_scores.py` (stub) |
| M2 | Factor precision, strict and lenient | Strict: `|P ∩ G1 ∩ Ans| / |P ∩ Ans|`. Lenient (headline): the same with G1 replaced by G1 ∪ G5 (factors the defense argued or the court discussed) | T1 | Set comparison | Validity: a valid ground the defense did not argue is not an error (L12) | 3 | same |
| M3 | Factor F1 and "argue-all" reference | Harmonic mean of M1 and lenient M2; the F1 of the argue-all-twelve rule is printed in every table as a floor | T1 | Set comparison | Null-agent audit (Section 5.7) | 3 | same |
| M4 | Court-discussed factor recall (G5), objection recall and precision (G4), condition-type recall (G6) | As M1 against G5, G4, G6 (factors, factors, about ten condition types) | T1 | Set comparison | Same | 3 | `features/f1_sparring.py`, `f6_hearing_card.py` (stubs) |
| M5 | Label-source sensitivity | M1-M4 recomputed with (a) keyword rules only, (b) Llama-3.1-8B only, (c) agreed only; kappa between labelers per factor | T1 | Re-scoring | Reliability; "agreement reported" (L12) | 3 | `label_sensitivity.py` (stub) |

### 4.2 Hallucination, split into its four kinds (L12, "Hallucination: failures and their reference points")

L12 says each kind needs its own reference. Ours:

| ID | Kind | Metric | Reference point | Deterministic check | Code |
|---|---|---|---|---|---|
| M6 | Unsupported claim | Unsupported-fact rate: share of factual sentences that MiniCheck finds unsupported by the input facts (threshold fixed on dev, in the pre-registration) | The given context (facts part, plus retrieved paragraphs for authority claims) | MiniCheck; validated on the constructed in-domain test (Section 2.4) | `metrics/unsupported_fact.py` (stub) |
| M7 | Factual error | Wrong section, wrong date, wrong statute text, wrong custody-day count, wrong IPC-BNS mapping | Sources outside the model: `law.statutes`, `law.concordance`, official tables (IPC2BNS-Verify), `date_calc` | Exact comparison to the tool result; no model | `metrics/tool_calling.py` (stub) |
| M8 | Unfaithful summary | Synopsis, brief facts and List of Dates statements not entailed by the approved dossier or timeline; every List of Dates row must have a source | The dossier and `case.timeline` | Row-by-row comparison to the timeline (exact); MiniCheck for the synopsis sentences | `features/f5_application.py` (stub) |
| M9 | Fabricated citation | Share of citations whose document id or paragraph is not in the index, or whose quoted span is not found verbatim in the cited paragraph (after removing whitespace, because the corpus has glued-word artefacts) | The corpus index | Index lookup and string search; no model | `metrics/retrieval.py` (stub; a function to add) |

**Faithfulness versus correctness (L12: "the middle row is the one a reader cannot catch").** For every factual sentence the system writes, we compute two checks and report the four-cell table:

- *Faithful* (F): supported by the input facts part (MiniCheck).
- *Corroborated* (C): supported by a part of the same order that the system never saw (defense submissions, prosecution submissions, reasoning, operative order), or verifiable with a tool (statute text, concordance).

| | C = yes | C = no |
|---|---|---|
| **F = yes** | Faithful and corroborated: the good case | Faithful but not corroborated (the input says it; the rest of the order does not repeat it): not an error |
| **F = no** | **Unfaithful but corroborated: the middle row.** Likely true, but the input does not support it, so the lawyer cannot verify it from the file given | **Unfaithful and uncorroborated: likely wrong** |

The two bottom cells are reported separately. Absence from the rest of the order does not prove falsity, so the bottom-right cell is an upper bound on factual error, not a count of it. This is a label-free way to separate "unsupported" from "wrong" using only court text.

### 4.3 Retrieval, orchestration and citations

| ID | Metric | Definition | Set | Deterministic check | Slide concept | Lvl | Code |
|---|---|---|---|---|---|---|---|
| M10 | Recall@k of court-cited precedents (G2), with **coverage** | Document-level `|retrieved@k ∩ gold| / |gold|`, k = 5, 10, 20; gold = resolved court-cited precedents in `reasoning` paragraphs. **Coverage columns:** (i) share of citation occurrences that resolved (about 17% at week 0), (ii) number of orders with at least one resolved citation, (iii) mean gold size per order | T1 (BNS-era subset separate) | Set membership | L14: "gold document in the top k"; recall@k | 3 | `metrics/retrieval.py` (`recall_at_k`, stub) |
| M11 | MRR and nDCG@10 | MRR = mean of 1/rank of the first gold document; nDCG@10 with binary gain. L14: "MRR ignores everything after the first relevant hit", so MRR is only reported next to recall@k and nDCG | T1 | Ranking arithmetic | L14: measuring retrieval | 3 | to add |
| M12 | Slot-fill rate | Share of required slots FILLED at the end; MISSING slots must appear as open issues | T1, A10 | Rule checks (`agents/sutradhar/slot_rules.py`) | L14: refusal on unanswerable, coverage | 3 | `metrics/retrieval.py` (`slot_fill_rate`, stub) |
| M13 | Authority quality | Share of authorities that are court reasoning (not counsel's submissions); share of SC roots; share of cited paragraphs dated before the order | T1 | Metadata fields | Leakage rule: only documents before the order | 3 | to add |
| M14 | Transfer-flag accuracy and unqualified CHANGED rate | Transfer flag (SAME_TEXT / CHANGED / NEW) compared with the concordance edge type; share of CHANGED precedents used without the qualification text | T1 BNS-era | Concordance lookup; string check for the qualification | L14: failure point 6 (incorrect specificity) | 3 | to add |
| M15 | Good-law violation rate | Share of cited precedents that carry an overruled flag and are cited without a warning; plus the **known-treatment share** (citations whose treatment label both labelers agreed on), because "unknown" is not "good" | T1, T9 | Graph lookup; string check | Coverage reported next to risk | 2 | `features/f7_citations.py` (stub) |
| M16 | Citation precision and recall (ALCE style) | Precision: share of citations whose paragraph MiniCheck judges to support the sentence. Recall: share of authority claims that carry a supporting citation | T1 | MiniCheck; verbatim span | L14: citation precision | 2 | to add |
| M17 | Citation faithfulness by removal | Share of claims that change when their cited paragraph is deleted from the context and the claim is redrafted. A claim that survives unchanged was probably written from memory and the citation is post-hoc. Lower bound only | T1 subset, n = 50 | Redraft and string comparison | L14: correctness is independent of whether reasoning used the evidence | 2 | to add |
| M18 | Stopping quality | Over-search rate: calls beyond the fewest calls after which the slot first passed its rules. Stopped-too-early rate: cases where running the same case to the 16-call budget would add a G1-correct factor or a G2 hit | T1, n = 100 | Replay of the same plan; offline | L14: "the whole trajectory", cost of the loop | 3 | to add |
| M19 | Weak-evidence AUROC | AUROC of the score-skew signal (S4) for "the top-10 contains a G2 paragraph" | T1 retrieval only | Rank statistics | L14: measuring retrieval | 3 | to add |

### 4.4 Ingestion (RQ2)

| ID | Metric | Definition | Set | Deterministic check | Slide concept | Lvl | Code |
|---|---|---|---|---|---|---|---|
| M20 | CER, per script | Character error rate against the known page text, reported **per character** and split into Devanagari and Latin pages | T2 | Edit distance (`character_error_rate`) | Guest: report quality per character, per script | 3 | `metrics/ingestion.py` (stub) |
| M21 | Boundary F1 and document-type accuracy | F1 of predicted vs true (first page, last page) ranges; accuracy of the document label | T2 | Exact range match | L12 deterministic checks | 3 | same |
| M22 | Downstream field accuracy **and field coverage** | Per field: accuracy against construction truth (T2) or G3 (T1); coverage = share of cases where gold for the field exists. FIR number about 12.9%, offence date about 4.8% of real orders. Averaged only over fields with n >= 30 | T1, T2 | Exact or normalised-date match | Guest: data scarcity as selection bias: report n and survival | 3 | `field_accuracy` (stub) |
| M23 | Escalation rate, questions asked, cost per page | Share of pages that reach the vision route; questions to counsel per bundle; seconds and GPU-seconds per page, by input kind K1-K10 | T2 | Logged route per page | Context engineering: budgets | 3 | same |
| M24 | Ladder regret against the oracle | Accuracy regret and cost regret of the chosen route vs the cheapest route that clears the CER bar, per page | T2 page subset | All routes run and cached | Router evaluation (literature review U2) | 3 | to add |
| M25 | Tokenizer cost by script | Qwen3 tokens per page and per 1,000 characters for Devanagari and Latin pages; effective context left for retrieval | T2 | Count | Guest: fertility confounds cost and context | 3 | to add |

### 4.5 Tool calling, task completion and reliability

| ID | Metric | Definition | Set | Deterministic check | Slide concept | Lvl | Code |
|---|---|---|---|---|---|---|---|
| M26 | Tool-call accuracy | Share of calls with the right tool name and schema-valid, type-correct, value-correct arguments; map_section accuracy on 1,140 IPC2BNS-Verify queries | T6, IPC2BNS-Verify | Compare to expected calls (`tool_call_accuracy`, `map_section_accuracy`) | L12: tool calling = schema valid, types correct, right tool | 3 | `metrics/tool_calling.py` (stub) |
| M27 | Irrelevance F1 and recovery rate | Irrelevance: a store is not called for a factor marked not applicable. Recovery: after an injected fault (OCR crash, store timeout, malformed date) the run finishes with a correct result or an explicit open issue | T6, fault injection | Event log | L12: agent behaviour; announcement: recover from errors | 3 | to add |
| M28 | Task completion | A case completes if the brief is schema-valid, every check ran, every required slot is FILLED or an open issue, and no unsafe action occurred | T1 | Event log and schema | L12: "task completed, no unsafe action, steps in budget" | 3 | `metrics/agentic.py` (stub) |
| M29 | pass^k and pass@k | pass^k: share of cases where **all** k runs meet the quality bar (k = 3). pass@k: share where **any** run does (the CME295-6 definition). The bar: M28 true, unsupported-fact rate at most a dev-fixed τ, factor recall at least a dev-fixed value. For k below the number of runs n, the unbiased estimate C(c,k)/C(n,k) | T1 (50 cases for k = 3 reliability) | Counting | CME295-6: pass@k, "at least 1 of k attempts succeeds"; for agents the opposite question (do all runs succeed) is the one that matters | 3 | `pass_hat_k` (stub) |
| M30 | Steps, tokens and calls per case; progress rate | Tool calls, store calls, tokens; progress = share of required slots filled after step t | T1 | Event log | L12: steps in budget; CE: context budget | 3 | to add |
| M31 | Cost per passed case | Total tokens (or GPU-seconds) divided by the number of cases that meet the bar | T1 | Division | AI Agents That Matter (cost-aware evaluation) | 3 | to add |
| M32 | Reasoning-trace statistics | Per run: plan validity rate, slots filled per call, relaxation steps used, repeated identical calls, budget hits, rounds of repair; failures grouped into MAST's three groups | T1 | Event log and `failure_analysis.py` | Course announcement: analyse intermediate steps; L15/L16: reasoning traces | 3 | `failure_analysis.py` (stub) |

### 4.6 Abstention: the coverage-risk curve (L12, "Abstention and the coverage-risk curve")

| ID | Metric | Definition | Set | Deterministic check | Lvl |
|---|---|---|---|---|---|
| M33 | Coverage-risk curve and area | Sweep a support threshold τ over claims. Coverage(τ) = share of claims emitted without NEEDS_REVIEW, UNANSWERED or refusal. Risk(τ) = unsupported-fact rate (M6) among emitted claims. The curve is plotted for Full, S3 variants and A2/A2b; B0 and B1 have one point because they cannot decline ("a system with no way to decline has one point on this curve"). Area under the risk-coverage curve is the single number | T1 | MiniCheck score and flags | 2 |
| M34 | Abstention precision and recall on knocked-out slots | On cases where a store or slot is removed (A10), the factors that become unanswerable are known; recall = share flagged as open issues; precision = share of flagged items that are truly unanswerable | T1 with A10 | Known knockouts | 2 |
| M35 | Confident-wrong rate | Share of emitted claims that are in the F = no, C = no cell (Section 4.2) | T1 | Section 4.2 | 2 |

### 4.7 Features and safety

| ID | Metric | Definition | Set | Check | Code |
|---|---|---|---|---|---|
| M36 | Objection recall and precision; flip rate | Recall against G4 (M4); precision = share of generated objections that match a recorded objection's factor; flip rate = share of round-1 objections dropped after seeing the reply | T1 | Set comparison | `features/f1_sparring.py` (stub) |
| M37 | Staleness | Stale-claim rate (claims still stating an old value); missed-stale rate (stale claim not redrafted); over-redraft rate (unaffected claim redrafted); byte-identity of unchanged claims (must be 100%); tokens saved = 1 − tokens(incremental)/tokens(full regeneration) | T3 | Construction truth; string equality | `metrics/agentic.py` (`stale_claim_rate`, stub), `features/f2_incremental_redraft.py` (stub) |
| M38 | Rights Radar accuracy | Per-rule accuracy against the designed answer; **false-ELIGIBLE rate** (the safety number); CHECK rate; agreement with G7 on real orders | T4, T1 | Exact match | `metrics/rights.py` (stub) |
| M39 | Batch | Missed-deadline rate; pairwise ranking accuracy (share of urgent-vs-not pairs ranked correctly); cases per node-hour; cache hit rate; equality of cached and single-case outputs | T5 | Planted deadlines | `features/f4_batch_desk.py` (stub) |
| M40 | Application quality | Required-section compliance; List of Dates precision and recall against G3 dates; dates without a source (must be 0); annexure index matches uploaded files | T1 | Checklist; set comparison | `features/f5_application.py` (stub) |
| M41 | Speech | WER; date, section and number error rate before and after the read-back step | T8 | Edit distance; exact match | `features/f8_hindi_voice.py` (stub) |
| M42 | Citation resolution | Accuracy by format; false-resolution rate; coverage | T9 | Document id match | `features/f7_citations.py` (stub) |
| M43 | Safety | Unapproved-export count (including bulk export in batch mode); injection success rate, utility under attack, persistence across a redraft; refusal rate; leak rate of planted names | T7 | Event log; string search | `metrics/safety.py` (stub) |

### 4.8 Cost, latency and the cost-quality frontier

| ID | Metric | Definition | Notes |
|---|---|---|---|
| M44 | Tokens and store calls per case | Mean and distribution (Figure 3) | CE: the context budget is a fixed number of tokens; Hindi text costs more tokens (M25) |
| M45 | GPU-seconds and wall-clock per case and per page | From the shard logs; node type recorded | 2080 Ti nodes and the 4060 laptop are reported separately |
| M46 | Frontier | G1 recall (and unsupported-fact rate) against tokens at budgets of 4, 8, 16 store calls per factor, for Full, A7, B4 | C9; Figure 2 |
| M47 | Context use | Tokens per evidence pack against the window; share of packs truncated | L14 failure point 3 (not in context) |

### 4.9 A proxy for level 4 (human outcome)

L12: "Does it help the person? Time saved, errors avoided, harm avoided." A user study needs counsel and human subjects; we have neither, and the team has no legal collaborator, so **a user study is out of scope**. The proxies, all computed from outputs:

| ID | Proxy | Definition |
|---|---|---|
| M48 | Items counsel must still review | NEEDS_REVIEW, UNANSWERED, UNSUPPORTED and AMBIGUOUS items per brief |
| M49 | Time-to-verify proxy | Number of distinct sources (document, page, paragraph) a lawyer must open to verify all SUPPORTED claims, per claim; with the verbatim-span share (M9) |
| M50 | Errors avoided | Of the errors in B0 and B1 outputs (M6, M7, M9), the share that Full's checks would have caught or avoided |

What the proxy can show: the brief is easier to verify and carries fewer hidden errors. What it cannot show: that a lawyer saves time or that outcomes improve. The report says so in its limitations.

### 4.10 Slices: per court, script, input kind, register (Guest lecture)

The guest lecture: "Mean multilingual accuracy is the wrong sufficient statistic; the risk surface is per language, script, register, and task". Every headline metric is also reported by:

| Slice | Values | Why |
|---|---|---|
| Court | High Courts with n >= 20 test orders; the rest pooled as "other" | Per-court skew: Madhya Pradesh has no BNS-era orders at week 0, Kerala 3; Allahabad and Madras carry most |
| Era | BNS-era vs IPC-era | Recodification (H1c) |
| Script | Devanagari vs Latin pages (T2, T8) | Script as a variable (Guest) |
| Input kind | K1-K10 | RQ2 |
| Origin of Hindi text | Native HLDC vs NLLB-translated | Guest: translationese; report native and translated separately |
| Register | Court order vs constructed companion (FIR, remand, certificate) | Register mismatch |
| Noise type | Character confusion, dropped lines, table damage, stamps | Literature review U4 |

**Script as an intervention (Guest: "compare f(x) with f(τ(x))").** For T2 Hindi pages we add a cheap paired condition, a rule-based transliteration of the same text into Latin script, and report the field-accuracy difference between the Devanagari and the transliterated version. Status: proposed (should).

**Survival rates (Guest: data scarcity as selection bias).** Section 6 includes a table of how many items survive each filter: High Court bail orders (1,483,143), cleanly split (88,121; 5.9%), test window, BNS-era (6,211 clean), with a FIR number (12.9%), with an offence date (4.8%), with at least one resolved citation (about 17% of occurrences), by court. A claim is only as general as its surviving strata.

### 4.11 Places where the existing plan's metric cannot be measured as written, and the fix

| Plan item | Problem | Fix in this plan |
|---|---|---|
| Plan 15.8: "recall@10 of court-cited precedents (G2)" | Only about 17% of citation occurrences resolve; none of the SCC/AIR ones. Recall is on a thin, biased subset | Always report coverage (M10); restrict to orders with at least one resolved citation; re-measure after wiring in the Supreme Court metadata; add the IL-PCSR external check; do not state C5 as tested if fewer than 30 BNS-era orders qualify |
| Plan 15.8: factor precision against G1 | The defense argues a subset of valid factors | Lenient precision against G1 ∪ G5 as headline (M2) |
| Plan 15.8: factor recall as the RQ1 headline | "Argue everything" has recall 1.0 | Pair it with precision/F1 and the argue-all reference (M3, C3) |
| Plan 15.8: "field accuracy against G3" | FIR numbers in 12.9% and offence dates in 4.8% of orders | Per-field n; no pooled headline from fields with n < 30; T2 uses constructed truth (clearly labelled "constructed, not court-derived") for fields G3 does not have |
| Plan 15.8: "objection recall (G4)" | Not every prosecution submission is recorded | Report n of orders with a recorded objection; precision is a lower bound |
| Plan 15.9: "MiniCheck unsupported-fact rate" | MiniCheck's validation is on other domains; constructed in-domain negatives are easy | State this in Section 2.4; add the deterministic verbatim-span check and the F/C table |
| Plan 15.8: "pass^3 on 50 cases" | No definition of "pass" | Fixed in M29 (quality bar written into the pre-registration) |
| Plan 15.6, F4: "missed-deadline rate" | A planted deadline is missed by definition only if the policy ranks it late | Report FIFO and urgency order on the same T5; the metric is the difference |

## 5. Protocol and statistics

### 5.1 Runs, seeds and what is averaged

| Item | Rule |
|---|---|
| Runs per system | Full, B0, B1, B4: 3 runs on all 200 T1 cases (target; floor in Section 7 is 2 runs for Full and B4). B0L, B2, B3, B6: 1 run (B6 is deterministic). Ablations and S-variants: 1 run on 100 cases (60 where Section 7 says so). pass^3 and paraphrase studies: 3 runs on 50 cases |
| Seeds | Three fixed seeds written into the pre-registration; the same seeds for every system, so run r of every system shares a seed |
| Sampling | Extractor, labeler, checks: temperature 0. Generation: temperature 0.6, top-p 0.95 (to be confirmed against the Qwen3 model card) |
| Averaging | First average the runs within each case, then do paired tests across cases. Case-level, not run-level, is the unit of analysis (runs of one case are not independent) |
| Run-to-run spread | Report the SD of the per-case score across runs and the share of cases whose pass/fail flips between runs |
| Same cases | Every comparison is paired: both systems run on the same case ids from the sorted, pre-registered list |
| Saved outputs | Every case output is saved as it finishes (resumable shards, plan 17) and never overwritten |

### 5.2 Which test for which data (L12, "Error bars on benchmark scores")

| Data type | Example | Test and interval |
|---|---|---|
| Binary item-level outcome, paired | Is factor f (of case c) found by system A and by B? Does the case meet the pass^3 bar? | **McNemar** (exact binomial test when the discordant count is under 25) on the discordant pairs; effect = difference in proportions, with a paired bootstrap interval; odds ratio from the discordant counts. L12: "For two systems scored on the same items, test the item-level differences." |
| Continuous per-case score, paired | Per-case recall, F1, unsupported-fact rate, tokens | **Paired bootstrap 95% interval** of the mean difference (10,000 resamples of cases, fixed seed) as the primary result; **Wilcoxon signed-rank** as the confirmatory test (the repository registry names it) |
| Pooled item-level data from several items per case | Factor-level or claim-level outcomes | Resample **cases** (clusters), not items, so items from one case stay together |
| Proportion with no pairing | A safety count over T7 scenarios | Wilson interval; for counts that must be zero, report the upper bound (rule of three: 3/n) |
| Equivalence ("equal or better") | C4, C20, C29 | Non-inferiority: the lower end of the 95% interval of (system − comparator) must be above −ε |
| Rank-based retrieval metrics | Recall@10 per order | Paired bootstrap over orders |

Code status: `eval/stats/bootstrap.py`, `wilcoxon.py` and `holm.py` exist as stubs with tests in `tests/unit/eval/test_stats.py`. **McNemar and the cluster bootstrap are not in the repository** and are to be added (Section 8).

### 5.3 Multiple comparisons: Holm by family

Holm-Bonferroni (`eval/stats/holm.py`) is applied within each family below, with α = 0.05. A family is fixed in the pre-registration before any result is seen.

| Family | Comparisons |
|---|---|
| F-RQ1-recall | C1: Full against B0, B0L, B1, B2, B3, B4 on factor recall (6 tests) |
| F-RQ1-halluc | C2: the same six on unsupported-fact rate |
| F-RQ1-guard | C3: precision and F1 against B0, B1, B4, B6 |
| F-ablate-recall | C10, C11, C12: A1, A3, A4, A6, A7 against Full on recall |
| F-sparring | C7, C8, C13, C28: the 2x2 arms, S8, S9, S10 |
| F-retrieval | C5, C14, C17, S4, S5, S16 on recall@10 |
| F-ingestion | C19-C23: Munshi against P1-P6 |
| F-features | One family per feature (F1-F8) |
| F-safety | C36-C39 (safety counts are not tested, only bounded) |

Separate families are not pooled into one correction, because they answer separate questions; the report says so. Exploratory slice results are labelled exploratory and are not corrected.

### 5.4 Effect sizes and what we can resolve

- **Primary effect size:** the paired mean difference with its 95% interval, in the metric's own units (points of recall, tokens). This is what the falsification criteria use.
- **Secondary:** Cohen's d_z (mean difference over SD of differences) for continuous paired data; rank-biserial correlation for Wilcoxon; odds ratio for McNemar.
- **What n lets us resolve** (assuming a per-case SD of differences of 0.25, to be measured on dev): n = 200 gives a 95% half-width of about 3.5 points, n = 100 about 4.9, n = 80 (the blind slice) about 5.5, n = 60 about 6.3. Differences smaller than the half-width are reported as "not resolved", not as "no difference".
- **A tie is a result.** A non-inferiority claim (C4, C20, C29) needs the interval lower bound above −ε; if the interval is wider than 2ε at the chosen n, the report says the data cannot settle it.

### 5.5 Reporting rules

1. **Report all runs.** Best-of-N is forbidden. Every table states n and the number of runs.
2. **Report every pre-registered comparison**, including those that fail.
3. **Report slices with n and survival rates** (Section 4.10). A slice with n < 20 is printed as "too few" rather than a number.
4. **Report the evaluated object** (Section 2.1) and the version log (Section 2.2).
5. **State label sources.** Every G-based number says whether it is agreed-labels-only and its coverage.
6. **No judge scores.** Qualitative case studies are labelled as examples, never as evidence.
7. **Deviations are listed.** Anything that differs from `docs/preregistration.md` is listed in the report with a reason.

### 5.6 Contamination handling (L12, Guest "source leakage")

- **Training-data leakage into our own pipeline:** test orders and same-FIR orders are removed from every store and from fine-tuning (plan section 2). Because FIR numbers are present in only 12.9% of orders, this is backed by the 8-word-overlap check and by date-restricted queries (a query only sees documents before the case's order).
- **Pre-training contamination of Qwen3:** Open India Law is public and Qwen3 may have seen some test orders. We report every headline result separately for orders dated **after the Qwen3 release** (April 2025; `configs/splits.yaml` uses 2025-04-01) and for earlier orders, using `eval/contamination.py` (stub). A claim whose effect disappears on the post-release subset is flagged. The blind slice is preferably the post-release subset (Section 2.6).
- **Memorisation probe (cheap, no model training):** for a sample of test orders, give the model the first half of the facts text and measure verbatim continuation overlap; report the rate for pre- and post-release orders. Status: proposed (could).
- **Labeler contamination:** Llama-3.1-8B (the labeler) is a different family from Qwen. Its release predates most test orders, so it may have seen some; labels are agreed with rule outputs, and results are re-run with rule-only labels (Section 5.9).

### 5.7 Auditing the metrics themselves: the null-agent test

AI Agents That Matter and tau-bench show that a metric can reward doing nothing (an empty reply counted as success). Before any run, every metric is run against five degenerate agents; each must score near the floor, and the audit is a unit test.

| Null agent | Output | Expected |
|---|---|---|
| Empty brief | No grounds | Recall 0; unsupported-fact rate undefined (reported as "no claims"), not 0 |
| Copy-the-facts | The input facts text as the brief | High faithfulness, factor recall near 0 on the structured fields, no authorities |
| Copy-the-checklist | The 12 factor names | Recall 1.0 on answerable factors; precision and F1 low; zero supported grounds |
| Argue-all-twelve | A template ground for every factor | Same as above; shows why C3 exists |
| Random citations | Real doc ids chosen at random | Recall@10 near chance; citation precision near 0 |

Also run: a case with every store removed (abstention must be 100%), and a run that exports with no approval (violation count must be at least 1, proving the safety metric can fire).

### 5.8 How the blind slice is opened once

1. Before the freeze: draw the blind ids with a seeded draw; write their hash in `docs/preregistration.md`; commit and tag `prereg-v1`.
2. After the freeze: run all systems on all 200 cases and save outputs. The scoring command takes a `--slice open|blind` flag; the blind scoring entry point refuses to run unless the tag exists and a lock file `data/eval/BLIND_OPENED` is absent.
3. First analyse the open 120 cases (errors, slices, failure types).
4. Open the blind slice once: run the blind scoring, create the lock file, record the date and git SHA in the report.
5. Report both. If results differ, the blind numbers are the headline and the difference is discussed.

### 5.9 Label-source sensitivity

For each G-based metric we report three numbers: (a) rule-only labels, (b) Llama-3.1-8B-only labels, (c) agreed labels (headline). We report the agreement kappa and the coverage of each (how many factors or fields have a label at all). A conclusion is "robust" only if its sign and significance survive in (a) and (b). Optionally, the Sarvam model (documented in `progress.md` as an independent labeler for public data) is a fourth label source for the same re-scoring; it is used only on public text.

### 5.10 Failure-mode-first discovery (L12, "Start from failure modes")

L12: "run your prototype on 30 to 50 real inputs from your domain; write down every failure, in the words of someone who would be harmed by it; group the failures; each group becomes a slice; the metric for each slice follows from what went wrong." "A metric chosen before the failures are known measures what was convenient to measure."

**Procedure (done on dev, before the freeze, by the team):**
1. Run Full and B0 on the 50 dev orders and on 10 T2 bundles (Section 7: about 7.5 node-hours).
2. Each team member reads outputs and writes failures in plain words ("the brief says custody is 167 days but the order says 189", "cites a case about a different offence").
3. Group into four or five groups; each group becomes a named slice with a membership rule that can be computed automatically (so it extends to the 200 test cases without hand labelling).
4. For each group, check the metric that follows from it exists in Section 4; add one if not.
5. Write the groups and their rules into the pre-registration.

**Likely slices** (our guess from what we already know; the dev discovery confirms or replaces them):

| Likely failure group | Slice rule (automatic) | Metric that follows |
|---|---|---|
| Citation-poor orders: few or no resolvable precedents | Order has under 2 resolved citations | M10 on the slice; M9 and M15 coverage; abstention M33 |
| Fact-poor orders: short facts part, few dates | Facts part under 150 words, or under 2 dated events | M22 with n, M12 slot fill, M33 |
| BNS-era orders | Offence on or after 2024-07-01 | M14, M10 on BNS-era; C5, C17 |
| Hindi and scanned bundles | T2 kinds K2-K8 with Devanagari share above 0.3 | M20 per script, M22, M23 escalation |
| Courts with unusual order formats | Courts where the splitter's clean rate is below the median, or where facts and reasoning are merged | Per-court C1; M5 label sensitivity |
| Statutory-bar cases (NDPS, UAPA, PMLA) | Sections in the bar list | M38 on `BAR_APPLIES`; M1 for factor 11 |
| Many-accused orders | More than 3 accused in the facts | M4 parity factor; M13 |
| Long inputs | Facts over the context budget share | M47 context use; RAG failure point 3 |

### 5.11 Automatic failure taxonomy

Two layers, both computed from the run files by `eval/failure_analysis.py` (stub).

**Layer 1: the plan's eleven error classes** (`ErrorType` in `eval/failure_analysis.py`): WRONG_ROUTE_OR_OCR, WRONG_SPLIT_OR_TYPE, WRONG_SECTION_OR_DATE, UNSUPPORTED_FACT, MISSED_FACTOR, MISGROUNDED_AUTHORITY, WRONG_TRANSFER, OVERRULED_CITED, STALE_AFTER_UPDATE, MISSED_OBJECTION, WRONG_RIGHTS_FLAG.

**Layer 2: the seven RAG failure points** (Barnett et al., "Seven Failure Points When Engineering a Retrieval Augmented Generation System", arXiv:2401.05856, January 2024; an arXiv preprint, re-verified for this plan; cited on the L14 slide, "4 out of 7 failure points are after a successful retrieval"), mapped to our pipeline stages and to the existing error classes:

| Failure point | Meaning (Barnett et al.) | Our pipeline stage | How we detect it automatically | Error class |
|---|---|---|---|---|
| FP1 Missing content | The question cannot be answered from the documents, yet the system answers | Store coverage; Sutradhar slot assessment; Vakeel abstention | A slot is MISSING (or the store is knocked out) but a confident claim was emitted | UNSUPPORTED_FACT |
| FP2 Missed the top-ranked documents | The answer is in the documents but ranks too low | Hybrid retrieval and filters in Sutradhar | Gold G2 document exists in the index but is not in the top-10 | MISGROUNDED_AUTHORITY (miss) |
| FP3 Not in context | Retrieved documents do not make it into the generation context | Evidence pack assembly, token budget, B2's 8K truncation | Gold document retrieved but absent from the pack Vakeel received | MISSED_FACTOR / MISGROUNDED_AUTHORITY |
| FP4 Not extracted | The answer is in the context but the model fails to use it | Vakeel drafting; Peshkar extraction | Pack contained a G1-relevant paragraph or the dossier quote exists, but the brief or field omits or contradicts it | MISSED_FACTOR, WRONG_SECTION_OR_DATE |
| FP5 Wrong format | The model ignores a requested format | Schema-constrained output; citation rendering; DOCX sections | Schema invalid, citation not rendered from metadata, missing required section | (new tag: FORMAT) |
| FP6 Incorrect specificity | The answer is too general or too specific | Relaxation of filters to an offence group; transfer qualification | A relaxed filter was used and the authority is outside the section family; CHANGED precedent without qualification | WRONG_TRANSFER, MISGROUNDED_AUTHORITY |
| FP7 Incomplete | The answer omits information that was available | Factor picker; repair step; List of Dates | Available timeline event or answerable factor absent from the output | MISSED_FACTOR |

The ingestion stages (route, split, type) and the later stages (stale claims, missed objections, wrong rights flag) are outside the seven RAG failure points; they use Layer 1 only. A third overlay groups failures by MAST's three groups (system design, inter-agent misalignment, task verification; Cemri et al., NeurIPS 2025 D&B, [link](https://neurips.cc/virtual/2025/poster/121528)) for the multi-agent discussion. The failure-taxonomy figure (Figure 4) shows Layer 1 and Layer 2 side by side for Full, B0 and B4.

A small addition needed: a `FORMAT` tag, since the plan's eleven classes have no home for FP5.

## 6. Results presentation (paper-style templates)

### 6.0 Where the numbers come from

The runners in `src/vakeel_sahayak/eval/runners/` take an `out_dir` and save one JSON per case as it finishes. The output layout below is proposed here (the runners are stubs, so nothing fixes it yet) and is written into the pre-registration:

- Raw outputs: `data/eval/runs/<job>/<system>/run<r>/<case_id>.json`, plus `MANIFEST.json` (Section 2.2). On Ada the same tree lives under `results/` (`configs/paths.yaml`) and is copied back.
- Scored per-case files: `data/eval/scored/<job>/<system>.parquet` (one row per case and run, one column per metric).
- Table sources: `data/eval/tables/table<k>_<name>.csv`, written by the scoring step; the report reads only these files, never raw outputs.
- Figures: `data/eval/figures/fig<k>_<name>.{pdf,png}` with the CSV each one plots.

Every table cell has the form `mean [lo, hi]` (95% paired-bootstrap interval of the difference from Full, or of the mean for the row) and every table has the columns "n", "runs", "Evaluated object" (L12) and, where a G-label is involved, "coverage" and "label source".

### 6.1 Table 1: main results

File: `data/eval/tables/table1_main.csv`. Source jobs: `rq1_full`, `rq1_b2_b3`, plus B0L, B0S and B6 jobs (to add to `configs/eval/runs.yaml`).

| System | Evaluated object | n / runs | Factor recall (M1) | Factor precision, lenient (M2) | F1 (M3) | Unsupported-fact rate (M6) | Recall@10 G2 (M10) [coverage] | Fabricated citations (M9) | Overruled cited (M15) | Tokens/case (M44) | Store calls/case | pass^3 (M29) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B6 expert rule | none | 200 / 1 | (not used, Section 3.1) | | | | n/a | | | 0 | 0 | |
| B0 single pass | (b) | 200 / 3 | | | | | n/a | | | | 0 | |
| B0S single pass, 4B | (b) | 200 / 1 | | | | | n/a | | | | 0 | |
| B0L single pass, 32B | (b) | 200 / 1 | | | | | n/a | | | | 0 | |
| B1 single RAG | (c) | 200 / 3 | | | | | | | | | 1 | |
| B2 whole-order | (c) | 200 / 1 | | | | | | | | | 1 | |
| B3 naive chunks (best on dev) | (c) | 200 / 1 | | | | | | | | | 1 | |
| B4 all stores | (d) | 200 / 3 | | | | | | | | | | |
| B5 learned router (if run) | (d) | 100 / 1 | | | | | | | | | | |
| **Full** | (d) | 200 / 3 | | | | | | | | | | |
| Argue-all-twelve reference (null agent) | none | 200 | 1.00 | | | n/a | n/a | n/a | n/a | 0 | 0 | |

Footer: the open-120 and blind-80 results are shown as two sub-columns for each headline metric; contamination split (pre vs post Qwen3 release) as a third row group; the p-value or "CI excludes 0" mark per Section 5.3.

### 6.2 Table 2: retrieval-only analysis

File: `data/eval/tables/table2_retrieval.csv`. Source: `eval/retrieval_only.py` (stub), laptop; the Sutradhar row needs an Ada run. Rows are cumulative (each adds one thing to the previous row), following plan 15.7.

| # | Configuration | Chunking | Section expansion | Reasoning-only | Factor filter | Graph expansion (S5) | Orchestration | Recall@10 overall | Recall@10 BNS-era | MRR | nDCG@10 | Orders with >= 1 resolved citation (coverage) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1a-1e | Single store, naive chunking (fixed 512; 512 + overlap; recursive; semantic; page) | naive | no | no | no | no | none | | | | | |
| 1f, 1g | Proposition units; late chunking (S16) | variant | no | no | no | no | none | | | | | |
| 2 | Whole-order embeddings | whole | no | no | no | no | none | | | | | |
| 3 | Structure-aware chunks, plain hybrid | structure-aware | no | no | no | no | none | | | | | |
| 4 | + section-family expansion | structure-aware | yes | no | no | no | none | | | | | |
| 5 | + reasoning-only paragraphs | | yes | yes | no | no | none | | | | | |
| 6 | + factor filter | | yes | yes | yes | no | none | | | | | |
| 7 | + citation-graph expansion to the SC root (S5) | | yes | yes | yes | yes | none | | | | | |
| 8 | Every store fused (B4's retriever) | | | | | | RRF | | | | | |
| 9 | Sutradhar plans (no drafting) | | | | | | 14B plan | | | | | |
| 9b | Row 9 with S1, S2, S3, S4, S6 policies | | | | | | variants | | | | | |
| Knock-outs (A10) | Row 9 minus one store at a time: slot-fill rate (M12) instead of recall | | | | | | | slot-fill per store | | | | |

Footer: external sanity check on IL-PCSR (recall and MRR) for rows 3 and 6, if the data is available and licensed.

### 6.3 Table 3: architecture variants

File: `data/eval/tables/table3_variants.csv`.

| ID | Variant | Priority | n / runs | G1 recall | F1 | Unsupported-fact rate | Objection recall (G4) where relevant | Tokens/case | Store calls | Wall-clock s/case | Cost per passed case (M31) | Difference from Full [CI] | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Full | reference | | 200 / 3 | | | | | | | | | 0 | |
| S1 ... S17 (one row per variant run; arms listed separately: S3 has two, S7 two, S9 two, S12 two, S14 several) | | must / should / could | 100 / 1 | | | | | | | | | | supports / does not support / not resolved |

### 6.4 Table 4: ablations

File: `data/eval/tables/table4_ablations.csv`. Source job: `ablations` (A1-A4, A6-A9), `a5_extractors`, `a10_knockouts`, and the new arms.

| ID | What is removed or changed | Capability | n | Metric group | Full | Ablation | Difference [95% CI] | Holm-adjusted result |
|---|---|---|---|---|---|---|---|---|
| A1 | No dossier | reasoning, tools | 100 | M6, M7 | | | | |
| A2 | No check-and-repair | reasoning | 100 | M6, M33 | | | | |
| A2b | Self-critique only | reasoning | 100 | M6 | | | | |
| A3 | No tools | tool calling | 100 | M7, M26, M38 | | | | |
| A4 | Plain retrieval | RAG | 100 | M10, M14 | | | | |
| A5 | Extractor: tuned 4B, base 4B, prompted 32B; clean and noisy | fine-tuning | 400 inputs | M22 | | | | |
| A6 | Fixed router | agentic | 100 | M1, M12 | | | | |
| A7 | Free planner | agentic | 100 | M1, M12 | | | | |
| A8, A9 | No sparring; neither (completes the 2x2 with A2) | agentic | 100 | M36, M6 | | | | |
| A8b, A8c, A8d | Sampling-only critic; no isolation; three-role review | agentic | 100 | M36 | | | | |
| A10 | Store knock-outs (rows per store) | RAG | 100 | M12, M34 | | | | |
| A11a, A11b | Munshi hierarchy re-read vs sequential; stopping variants | agentic | 100 | M23, M18 | | | | |
| A12 | Contracts, + prior, prior alone | agentic | 100 | M1, M31 | | | | |
| A13 | Output format (three arms) | tools, fine-tuning | 400 | M22, M26 | | | | |
| A14 | Plan reuse on/off | batch | 100 | M39 | | | | |
| A15 | Injection defences (three arms) | safety | 60 x 3 | M43 | | | | |
| A16 | Graph expansion on/off | RAG | retrieval | M10 | | | | |

The sparring 2x2 is also shown as its own small table: rows (verifier on/off), columns (opponent on/off), cell values unsupported-fact rate and objection recall; the cells are Full, A8, A2, A9.

### 6.5 Table 5: ingestion by input kind

File: `data/eval/tables/table5_ingestion.csv`. Source: `rq2_full`, `rq2_vision`, pipelines P1-P7.

| Input kind | n pages / bundles | P1 text layer | P2 OCR all | P3 Docling | P4 vision all | P5 fixed cascade | P6 no split/label | P7 image-only | **Munshi** |
|---|---|---|---|---|---|---|---|---|---|
| K1 born-digital | | | | | | | | | |
| K2 scanned | | | | | | | | | |
| K3 degraded | | | | | | | | | |
| K4 photo | | | | | | | | | |
| K5 Hindi or mixed | | | | | | | | | |
| K6 legacy Hindi fonts | | | | | | | | | |
| K7 handwriting (if built; plan T2 renders K1-K6) | | | | | | | | | |
| K8 bundle | | | | | | | | | |
| K9 locked | n/a: scored as "asks counsel, never guesses" | | | | | | | | |
| K10 non-PDF | | | | | | | | | |

Each cell holds four numbers: CER (M20), field accuracy with n (M22), escalation share (M23), GPU-seconds per page. Footer rows: boundary F1 and document-type accuracy (M21), questions per bundle, ladder regret (M24), results by noise type, Devanagari vs transliterated (script intervention), native vs translated Hindi.

### 6.6 Table 6: per-feature results (F1-F8)

File: `data/eval/tables/table6_features.csv`.

| Feature | Test set | Comparator | Metric 1 | Metric 2 | Metric 3 | Full / feature | Comparator | Difference [CI] | Claim | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| F1 Sparring | T1 / G4 | One-call list; A2, A8, A9 | Objection recall | Precision | Unsupported replies | | | | C28 | |
| F2 Incremental redraft | T3 | Full regeneration | Stale-claim rate | Tokens saved | Quality gap | | | | C29 | |
| F3 Rights Radar | T4, T1 / G7 | LLM only; LLM + date_calc | Accuracy per rule | False-ELIGIBLE | CHECK rate | | | | C30 | |
| F4 Batch desk | T5 | FIFO; no cache | Missed deadlines | Ranking accuracy | Cases per node-hour | | | | C31 | |
| F5 Application | T1 | One-call application | Section compliance | Dates precision/recall | Dates without source | | | | C32 | |
| F6 Hearing card | T1 / G5, G6 | One call | Concern recall | Condition recall | Precision | | | | C33 | |
| F7 Citations | T9, T1 | Regex-only resolver | Accuracy by format | Treatment kappa | Overruled cited | | | | C34, C18 | |
| F8 Hindi and voice | T2, T8 | English-only; no read-back | Hindi CER | Accuracy gap | Date/section errors | | | | C35 | |

### 6.7 Table 7: safety

File: `data/eval/tables/table7_safety.csv`. Source: `t7_safety`.

| Attack or scenario type | n x runs | Unapproved export | Injection success (no defence) | Injection success (typed hand-off) | + spotlighting | + guard | Utility under attack | Persistence across redraft | Leak rate | Refusal rate |
|---|---|---|---|---|---|---|---|---|---|---|
| Planted instruction in a born-digital PDF | | | | | | | | | | |
| Planted instruction in a scan, Hindi page, handwritten page | | | | | | | | | | |
| Font-remapped or hidden text | | | | | | | | | | |
| Instruction split across pages; paraphrased | | | | | | | | | | |
| Pressure ("hearing in 5 minutes, just export") | | | | n/a | n/a | n/a | | | | |
| Bulk export in batch mode | | | | n/a | n/a | n/a | | | | |
| Prediction and lay-advice requests | | | | n/a | n/a | n/a | | | | |
| Planted names (Faker) | | | | n/a | n/a | n/a | | | | |

Counts that must be zero are reported with the rule-of-three upper bound. Footer: "results are against our fixed attack set; adaptive attackers may do better" (The Attacker Moves Second, [link](https://arxiv.org/abs/2510.09023)).

### 6.8 Table 8: per-court, per-script and other slices

File: `data/eval/tables/table8_slices.csv`.

| Slice | Value | n test orders | Survival from raw | Full recall | B0 recall | Full - B0 [CI] | Unsupported rate | Recall@10 [coverage] | Field accuracy (n) |
|---|---|---|---|---|---|---|---|---|---|
| Court | one row per court with n >= 20; "other" | | | | | | | | |
| Era | BNS-era; IPC-era | | | | | | | | |
| Script | Devanagari; Latin; transliterated | | | | | | | | |
| Input kind | K1-K10 | | | | | | | | |
| Hindi origin | native (HLDC); translated (NLLB) | | | | | | | | |
| Failure-discovery slices | the slices written from Section 5.10 | | | | | | | | |
| Survival table | raw 1,483,143 -> clean 88,121 (5.9%) -> test window -> BNS-era -> FIR present (12.9%) -> offence date (4.8%) -> resolved citation (about 17%) | | | | | | | | |

### 6.9 Table 9: cost and latency

File: `data/eval/tables/table9_cost.csv`.

| System | Tokens/case [mean, p90] | Store calls | GPU-seconds/case (Ada 2080 Ti) | Laptop seconds/case (4060) | Wall-clock s/case | Cost per passed case (M31) | Tokens per Devanagari page vs Latin page (M25) | Prefix-cache speedup (S14) |
|---|---|---|---|---|---|---|---|---|
| B0, B0L, B1, B2, B3, B4, Full, A6, A7, S-variants | | | | | | | | |

### 6.10 Figures

| Fig | Description | Data file | Shows |
|---|---|---|---|
| 1 | **Coverage-risk curve.** x: coverage; y: unsupported-fact rate among emitted claims. Curves for Full, S3 arms, A2, A2b; single points for B0, B1, B4, B6 | `fig1_coverage_risk.csv` | Claims C2, C6, C15; "score the refusal" (L12) |
| 2 | **Cost-quality frontier.** x: tokens per case (log); y: factor recall; points at budgets of 4, 8, 16 calls for Full, A7, B4, with CIs | `fig2_frontier.csv` | C4, C9 |
| 3 | **Tokens-per-case distribution.** Violin or ECDF per system, with p90 and budget-hit marks | `fig3_tokens.csv` | Cost, loop risk (L14: non-determinism, cost of the loop) |
| 4 | **Failure-taxonomy bars.** Layer 1 (eleven classes) and Layer 2 (seven RAG failure points) for Full, B0, B4 | `fig4_failures.csv` | Failure analysis (course minimum) |
| 5 | **Ingestion: escalation vs accuracy.** x: share of pages escalated to vision; y: field accuracy; points for P1-P7 and Munshi at several thresholds; the oracle route as a reference | `fig5_escalation.csv` | C19, C20, C22 |
| 6 | **Per-court forest plot.** Full minus B0 recall with CI for each court with n >= 20, pooled estimate at the bottom | `fig6_court_forest.csv` | C41 |
| 7 | **Faithfulness-correctness grid.** The four cells of Section 4.2 as stacked bars per system | `fig7_faithful_correct.csv` | The "middle row" (L12) |
| 8 | **Reliability.** Per-case pass count out of 3 for Full and B4 (histogram), pass@3 and pass^3 | `fig8_reliability.csv` | C40 |
| 9 | **Sparring 2x2 interaction plot** | `fig9_sparring.csv` | C7, C8, C28 |
| 10 | **Progress curve.** Share of required slots filled by step, for Full, S1, S3, A6, A7 | `fig10_progress.csv` | Reasoning-trace analysis (M30, M32) |

### 6.11 Qualitative case-study boxes (6 to 8)

Each box shows: input excerpt, what each system did (B0, B4, Full), the trace (plan, store calls, repairs), the outcome, and the metric that did or did not catch it. Chosen automatically by `eval/failure_analysis.py::pick_case_studies` from the typed errors, not by hand-picking best cases, with the selection rule written in the pre-registration.

1. A success: a BNS-era case where the transfer flag and section-family expansion find an IPC-era precedent.
2. A grounding failure: an unfaithful but corroborated claim (the middle row of Section 4.2).
3. A repair that worked, and one that flagged NEEDS_REVIEW instead of inventing support.
4. A Hindi bundle: routes per page, an escalation to vision, an unreadable page and the question asked.
5. A change set: the charge sheet is filed, which claims became stale, which stayed word for word.
6. A Rights Radar case on a threshold edge (day 59, 60, 61).
7. An injection attempt in a scanned page and what the typed hand-off did.
8. A failure of Full that B0 got right, with its failure-point label.

### 6.12 Outline of the final report or paper

| Section | Contents |
|---|---|
| 1. Introduction | The problem (bail preparation as an engineering problem, plan 1.2); the two RQs; contributions (plan 14.3); positioning as preparation, not prediction (literature review L1) |
| 2. Related work | Agentic and adaptive RAG; routing and multi-agent orchestration; debate and critique; truth maintenance and memory; document ingestion; Indian legal NLP; agent evaluation. The closest work per contribution (literature review section 7, edit 17), including that the routing papers route among LLMs, not legal stores |
| 3. System | Six agents, ten stores, evidence contracts, gates (plan 3-11) |
| 4. Evaluation design | Claims (Section 1 of this plan); what is evaluated; constructs; benchmarks in five components; leakage control; pre-registration |
| 5. Systems compared | B0-B6, A-ablations, S-variants |
| 6. Results | Tables 1-9 and Figures 1-10, in the order RQ1, RQ2, features, safety, slices, cost |
| 7. Analysis | Failure taxonomy, case studies, reasoning traces, what the null results mean |
| 8. Limitations and threats | Section 6.13 |
| 9. Conclusion and future work | Plan section 20; user study; trained routers and stoppers |
| Appendices | Pre-registration; version log; checklists and contracts; label agreement; the full claims table with verdicts |

### 6.13 Threats to validity

| Threat | What it is | What we do | What remains |
|---|---|---|---|
| **Circularity** | Gold labels (G1, G3-G7) come from keyword rules and a labeler on the same orders the systems read; the factor tagger that builds paragraph metadata is the same family of rules as the labeler. T4 scenarios and the Radar are written from the same acts | System input is the facts part only (8-word-overlap check); non-Qwen labeler; agreed labels; label-source sensitivity; B6 does not reuse the tagger; T4 written by someone who did not write the Radar | Shared blind spots between rules and Llama remain; the Radar's legal readings are not independently verified |
| **Contamination** | Qwen3 and the labeler may have seen public court orders | Post-release subset; blind slice preferably post-release; memorisation probe | Release date is an upper bound on the cutoff, not a measurement; pre-release orders cannot be cleared |
| **Selection bias from clean splits** | Only 5.9% of orders split cleanly; courts differ (Madhya Pradesh 0 BNS-era orders, Kerala 3); glued-word text | Survival table; per-court slices; forest plot; claims limited to the surviving strata | Results may not generalise to orders that do not split cleanly |
| **Label noise and coverage** | FIR numbers 12.9%, offence dates 4.8%, citation resolution about 17%; both labelers can err | Coverage columns; per-field n; agreed labels; sensitivity; no pooled headline from thin fields | Recall@10 rests on a biased subset of citations |
| **Offline stand-in models versus real models** | Unit tests and offline runs use an offline LLM, an offline NLI and a word-glossary translator; real models are written against library APIs and not yet tested on GPUs | All reported numbers come from real model runs on Ada and the laptop; offline runs are used only for tests; the version log names the model of every result | Real-model paths were never run at the time of writing; surprises are expected |
| **Constructed data** | T2-T5, T7, T8 are built by us (rendered, Faker names, TTS audio, NLLB Hindi); layouts may be too regular; Hindi from NLLB is translationese | Native HLDC reported separately when available; degradation types varied (Augraphy); scripted counsel stated to be more cooperative than real counsel | Transfer to real photographed files is not shown |
| **Translation effects** | NLLB and IndicTrans2 add translationese; Hindi to English translation sits inside the pipeline | Report native vs translated; keep the Hindi original beside the English; script-intervention condition | Hindi legal register is under-tested |
| **Checker validity** | MiniCheck and DeBERTa NLI are learned models validated on other domains; constructed negatives are easy | Verbatim-span check beside them; F/C table; different checkers for the system and for evaluation | Subtle legal entailment errors may be missed |
| **Single-run limits** | Ablations at n = 100 with one run; pass^3 on 50 cases | Interval widths reported; "not resolved" when the interval is wide; three runs where it matters | Small effects cannot be claimed |
| **Dev-set size** | 50 dev orders fix thresholds | Margins rounded; uncertainty stated | Thresholds may be mis-set |
| **Researcher degrees of freedom** | Many systems and metrics | Pre-registration; families; deviations list; blind slice | Not a substitute for an independent replication |
| **No user study** | Level 4 is a proxy only | Section 4.9 | No claim about lawyer time or outcomes |

## 7. Run plan and budget

### 7.1 Capacity: what 3-4 weeks and three accounts allow

Assumptions (all from plan 17 unless marked): one 4x RTX 2080 Ti node per account, interactive sessions of at most 6 hours with about 5 useful hours, about 2M tokens per node-hour for the 14B, about 0.8M for the 32B, about 800 vision pages per node-hour. The deadline is 3-4 weeks from 24 October 2026, so weeks are counted from Monday 26 October. The system cannot run end to end yet (the LangGraph flow, the API and the export modules are stubs, `progress.md` section 0 A), and the evaluation modules are stubs, so the first week is spent on code, not on runs.

| Week | Dates | Sessions per account | Nominal node-hours (3 accounts, 5 h) |
|---|---|---|---|
| 1 | 26 Oct to 1 Nov | 2 (dev only) | 30 |
| 2 | 2 to 8 Nov | 4 | 60 |
| 3 | 9 to 15 Nov | 6 | 90 |
| 4 | 16 to 22 Nov | 5 | 75 |
| Total | | | **255 nominal** |

Plan 17 applies a 30% buffer for failed or lost sessions, so **about 180 node-hours are usable**. The original plan's own estimate is 219 (with the API teacher) to 279 node-hours for 8 weeks, so even the original plan does not fit in 3-4 weeks without cuts, and the literature-derived variants add more. Section 7.3 states the cuts.

**The one number to measure first:** tokens per case of Full. Plan 17 uses 150K tokens as the per-case budget cap. If the real mean is nearer 100K, every Full-based job shrinks by about a third. Measure it on 10 dev cases in week 1 and re-run the arithmetic below.

### 7.2 Every experiment run

"Target" is the size in this plan; "Floor" is the shrunk size (samples and runs only, never a dropped feature). Node-hours are Ada interactive node-hours. The arithmetic for new items is tokens divided by 2M per node-hour. Tier A is must, B is should, C is could.

| # | Job | Systems / arms | Size (target) | Tokens or basis | Plan 17 nh | Target nh | Floor size | Floor nh | Tier | Needs |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Teacher dossiers | Qwen3-32B or API model | 4K train orders | 12K tokens each | 60 (0 with API) | 0 (API) / 60 | 3K orders | 0 / 45 | A | Week-1 teacher pilot |
| 2 | QLoRA (batch job, not interactive) | Extractor, 3 runs | about 2K pairs | about 100 GPU-h | batch | batch | 2 runs | batch | A | Job 1 |
| 3 | Failure-mode discovery and dev tuning | Full, B0 on 50 dev + 10 bundles; thresholds; δ and ε | 60 inputs x 2 | 150K per case | 20 | 20 | same | 20 | A | A runnable Full |
| 4 | RQ1 main | Full, B0, B1, B4 x 3 runs; B2, B3 x 1 | 200 cases | Full 150K cap | 82 | 82 | Full, B4: 2 runs; B0, B1: 3 runs | 57 | A | Freeze |
| 5 | B0L, B0S, B6 | 32B single pass; 4B single pass (laptop); rule baseline | 200 cases | 10K each; 32B at 0.8M/nh | not in plan | 2.5 | same | 2.5 | A | none |
| 6 | Ablations A1, A3, A4, A6, A7 | one run each | 100 cases | 125K | 31.25 | 31.25 | 60 cases | 18.75 | A | Freeze |
| 7 | Sparring 2x2: A2, A8, A9 | one run each | 100 cases | 125K | 18.75 | 18.75 | 100 cases (kept) | 18.75 | A | Freeze |
| 8 | A5 extractors | tuned 4B, base 4B, prompted 32B; clean and noisy | 400 inputs | 12K | 6 | 6 | 250 inputs | 4 | A | Jobs 1, 2 |
| 9 | RQ2 vision pages and full system | P4 on 1,500 pages; Munshi escalations; full on bundles | 2,400 pages; 100 bundles | 800 pages per nh; 150K per bundle | 10.5 | 10.5 | 70 bundles | 7 | A | Munshi; T2 |
| 10 | F2 change sets | incremental vs full regeneration | 180 updates + 60 no-op | | 18 | 18 | 100 updates + 40 no-op | 12 | A | T3 |
| 11 | F1, F5, F6 baselines and assembly | one-call baselines | 200 cases | | 6.5 | 6.5 | 120 cases | 4 | A | Export modules |
| 12 | F3 baselines | LLM only; LLM + date_calc | 2 x 500 scenarios | 20K | 10 | 10 | 2 x 300 | 6 | A | T4 |
| 13 | F4 no-cache | one shard | T5 | | 5 | 5 | same | 5 | A | T5 |
| 14 | T6 tool calling and T7 safety | 3 runs each | 150 questions; 60 scenarios | | 2 + 9 | 11 | same | 11 (safety is never cut) | A | T6, T7 |
| 15 | **New must:** S8 (A2b) self-critique only | 1 arm | 100 cases | 125K | | 6.25 | same | 6.25 | A | Switch `repair_mode` |
| 16 | **New must:** S9 (A8b) sampling-only critic | 1 arm | 100 | 125K | | 6.25 | same | 6.25 | A | `critic_mode` |
| 17 | **New must:** S10 (A8c) no isolation | 1 arm | 100 | 125K | | 6.25 | same | 6.25 | A | `abhiyojak_isolation` |
| 18 | **New must:** S1 self-critique retrieval | 1 arm | 100 | 175K | | 8.75 | 60 cases | 5.25 | A | `retrieval_policy` |
| 19 | **New must:** S3 stopping (A11b) | 2 arms | 100 | 150K each | | 15 | 60 cases | 9 | A | `stopping` |
| 20 | **New must:** S7 (A11a) gap re-read | 2 arms | 100 bundles | mostly laptop | | 1 | same | 1 | A | `munshi_gap_policy` |
| 21 | **New must:** S15 (A13) output formats | 2 extra arms | 400 inputs + T6 | | | 5 | 250 inputs | 3 | A | `output_format` |
| 22 | **New must:** S17 (A15) defences | 4 arms | 60 scenarios x 3 | 20K | | 7 | same | 7 | A | `defence` flags |
| 23 | **New must:** budget sweep for the frontier | Full, A7, B4 at 2 extra budgets (75K, 300K) | 60 cases | 260K per case per system | | 23 | Full and B4, 60 cases | 16 | A | Switches budgets |
| 24 | **New must:** citation faithfulness by removal | Full | 50 cases | about 6M | | 3 | same | 3 | A | none |
| 25 | **Should:** S2 adaptive depth | 1 arm | 100 | 100K | | 5 | 60 | 3 | B | |
| 26 | **Should:** S6 (B5, A12) learned router | 2 arms | 100 | 125K | | 12.5 | 60 | 7.5 | B | Store-prior labels (laptop) |
| 27 | **Should:** S12 topology | 2 arms | 100 | 125K | | 12.5 | 60 | 7.5 | B | Graph or driver |
| 28 | **Should:** S14 plan cache, prefix cache, scheduling | 3 sub-jobs | 100-case batch; T5 | | | 12 | 100-case batch | 8 | B | T5 |
| 29 | **Should:** S16 proposition chunking on a sample | | 5K paragraphs | | | 0.5 | same | 0.5 | B | |
| 30 | **Should:** paraphrase and fault-injection robustness | Full | 50 cases x (2 paraphrases + 1 fault) | 150K | | 11.25 | 30 cases | 6 | B | |
| 31 | **Should:** abstention under knock-outs | Full, B1 | 3 stores x 40 cases | 125K | | 7.5 | 24 cases | 4.5 | B | A10 |
| 32 | **Could:** S11 three-role and debate | 2 arms | 100 | 150K | | 7.5 | cut | 0 | C | |
| 33 | **Could:** S13 workflow search | grid on dev, test winner | 50 dev x 12 workflows; 100 test | 100K | | 36 | cut | 0 | C | |
| | **Totals** | | | | **219 (with API teacher)** | **Tier A: 303; Tier B: 61.25; Tier C: 43.5; all: about 408** | | **Tier A: 229; Tier B: 37; Tier C: 0** | | | |

Totals, recomputed from the rows: Tier A target = 219 (the plan's jobs 1 and 3-14 with the API teacher) + 2.5 (job 5) + 81.5 (jobs 15-24) = **303**; Tier A floor = 163.5 (jobs 3-14 at floor, job 1 at 0) + 2.5 + 63 (jobs 15-24 at floor) = **229**; Tier B target 61.25, floor 37; Tier C target 43.5, floor 0. All tiers at target: about 408. These are planning figures; the pre-registration recomputes them from the measured tokens per case.

Laptop work (4060, no time limit): the plan's 90 hours, plus about 30 more: store-prior labels (S6), chunk-variant embeddings (S16), MiniCheck for the extra arms, the retrieval-only runs and S4/S5 (no Ada), the T2 extras (transliterated Hindi), the memorisation probe. About 15 hours a week overnight, as in the plan, or more.

### 7.3 Order of runs and weekly plan

| Order | Week | Runs | Why this order |
|---|---|---|---|
| 0 | 1 | Items needing no GPU or only the laptop: metric and stats code, T1 builder, null-agent audit, retrieval-only analysis rows 1-7 and S4, S5, S16 (laptop), T4, T5, T6, T7 builders, pre-registration draft | They are independent of the unfinished graph and unblock everything |
| 1 | 1 | Job 1 (teacher pilot and dossiers, or API), job 2 (QLoRA batch), job 3 (10-case token measurement, then failure discovery on 60 inputs) | Dev is the only set we may look at; the measurements decide the floor |
| 2 | start of week 2 | **Freeze**: commit `prereg-v1`, tag the code; blind ids hashed | After this nothing is tuned |
| 3 | 2 | Jobs independent of Full: B0, B0L, B0S, B1, B2, B3, B6 (job 4 baselines, job 5), A5 (job 8), F3 baselines (job 12), F1/F5/F6 one-call baselines, T2 pipelines P1-P3, P5-P7 and RQ2 vision (job 9) | They do not need the whole system, and flatten the peak (plan 17) |
| 4 | week 3 | RQ1 main Full and B4 (job 4), the sparring 2x2 and S8-S10 (jobs 7, 15-17), ablations (job 6), S1, S3 (jobs 18, 19), the frontier sweep (job 23) | The saved Full outputs are the reference for all ablations |
| 5 | week 3 | S7, S15, S17 (jobs 20-22), safety T6/T7 (job 14), F2 (job 10), F4 (job 13) | Smaller and independent |
| 6 | week 4 | Should jobs 25-31 in the order 26, 27, 28, 30, 31, 25, 29; could jobs 32, 33 only if time remains | Run only what the budget allows |
| 7 | week 4 | Score the open 120, error analysis, case studies, then **open the blind slice once**, then tables and figures | Section 5.8 |
| 8 | week 4 | Write-up | The report text can be drafted in parallel from week 3 |

Dependencies on unfinished code (from `progress.md`): the full-system runs need either the LangGraph flow or a plain driver. **Proposal:** write a thin evaluation driver that calls the agents in sequence the way the offline case-0007 runs did, with gates auto-approved by a scripted counsel in evaluation mode, and test the real gate code separately in T7. This removes the dependency of the evaluation on `orchestration/graph.py`. The cost is that S12's orchestrated-topology arm is then about the driver, not the graph; this is noted in the report.

### 7.4 What is cut first if time runs short

The team rule is: shrink samples and runs, never drop a feature's evaluation. In order:

1. Tier C jobs (32, 33): reported as related work, with a sentence saying they were not run.
2. Move every Tier B job to its floor size; then drop Tier B jobs in the order 25, 29, 31, 28, 27 (the S12 arms and plan reuse), keeping job 26, 30.
3. Shrink Tier A samples to floor (Full and B4 at 2 runs; ablations A1, A3, A4, A6, A7 at 60 cases; F2 at 100 updates; F3 at 300 scenarios). Intervals widen accordingly; Section 5.4 says what can then be resolved.
4. If tokens per case turn out near the 150K cap, shrink further: Full and B4 at 150 cases with 2 runs; the frontier sweep to Full and B4 only (already at floor); S1 and S3 to 40 cases.
5. Never cut: safety (job 14), the sparring 2x2 (jobs 7, 15-17 are needed for C7, C8, C13), the blind slice, the null-agent audit, the pre-registration, the failure discovery (job 3).
6. If the API teacher is not allowed: add 45 to 60 node-hours for job 1 and cut Tier B entirely.

Risk statement: with 180 usable node-hours the Tier A floor (about 229) does not fit unless the measured tokens per case is under about 120K. That is the largest risk to this plan, repeated in Section 9.

## 8. What exists vs what to build

Method: each file under `src/vakeel_sahayak/eval/`, `testsets/` and `finetune/` was opened, and `raise NotImplementedError` was searched across the repository. In `eval/`, 56 of 64 Python files are stubs (the other 8 are empty `__init__.py` files); in `testsets/` 13 of 14; in `finetune/` 6 of 7. The tests are written but were not run for this plan (the team rule is not to run tests while modules are stubs). Per `progress.md` 5c, `tests/unit/eval` (about 148 test functions in 9 files) and `tests/unit/finetune` (about 77 test functions in 6 files, plus helpers) fail until the code exists; `tests/unit/testsets` has about 108 test functions in 10 files.

### 8.1 What already exists and the evaluation can use

| Existing and implemented | Where | Used for |
|---|---|---|
| Switch object with A1-A10, P5, P6 | `orchestration/switches.py` | All ablations |
| B4 and A7 logic (reciprocal-rank fusion, free planner) | `agents/sutradhar/baselines.py` | B4, A7 |
| Fixed router (A6) | `agents/sutradhar/fixed_router.py` | A6 |
| Slot rules, relaxation, contracts runtime, factor picker, chat router | `agents/sutradhar/slot_rules.py`, `relaxation.py`, `contracts_runtime.py`, `factor_pick.py`, `chat_router.py` | Full; S1-S4 start from these |
| Abhiyojak isolation allow-list | `agents/abhiyojak/isolation.py` | A8c, C8 |
| Claim splitting and repair | `agents/vakeel/claims.py`, `work.py`, `agent.py` | A2, S8 |
| Munshi ladder, page index, gap checks, bundle split, classification, questions | `ingestion/ladder.py`, `pageindex.py`, `gaps.py`, `bundles.py`, `classify.py`, `questions.py` | RQ2, S7 |
| Retrieval cache and urgency, scheduler, queue | `batch/cache.py`, `urgency.py`, `scheduler.py`, `queue.py` | F4, S14 |
| Truth maintenance (dependencies, staleness, redraft) | `truth_maintenance/*` | F2 |
| Rights Radar (7 rules) | `rights/*` | F3 |
| Order splitter, section extraction, factor tagger, date splits, leakage, citation graph and good-law check, rule-based gold G1-G7 | `pipelines/*` | Gold labels, splits |
| The ten stores and store tools | `stores/*`, `tools/*` | All retrieval |
| Models layer incl. offline stand-ins, labeler client, NLI, embeddings | `models/*` | Everything (real-model paths untested) |
| Privacy boundary, injection guard, leak check | `privacy/*` | T7, S17 |
| Week-0 data: Open India Law sample, statutes, concordance, splits, feasibility report | `data/interim/*` | T1 inputs, coverage numbers |

Known gaps in what exists: the model-assisted order-splitter rescue raises `NotImplementedError` (needs the labeler client); only a 2,000-order store build has been run; model weights are not downloaded; HLDC is blocked; the CrPC, NDPS s.37 and bailable/cognisable tables are missing; PyMuPDF is not installed (16 ingestion tests skip). These affect T1, T2 and the retrieval-only analysis directly.

### 8.2 What is a stub, and the test that expects it

| Area | Module | Status | Tests |
|---|---|---|---|
| Metrics | `eval/metrics/factor_scores.py`, `unsupported_fact.py`, `retrieval.py`, `ingestion.py`, `tool_calling.py`, `rights.py`, `agentic.py`, `safety.py`, `stats_helpers.py` | stub | `tests/unit/eval/test_metrics.py` (27) |
| Statistics | `eval/stats/bootstrap.py`, `wilcoxon.py`, `holm.py` | stub | `test_stats.py` (16) |
| Baselines | `eval/baselines/b0_single_pass.py`, `b1_single_rag.py`, `b2_whole_doc.py`, `b3_naive_chunking.py`, `b4_all_stores.py`, `full_system.py`, `chunking_variants.py` | stub | `test_baselines.py` (18), `test_chunking_variants.py` (6) |
| Ablations | `eval/ablations/a1_...py` to `a10_...py` | stub | `test_ablation_runs.py` (10), `test_registries.py` (17) |
| Ingestion pipelines | `eval/ingestion/p1_...py` to `p6_...py`, `munshi_full.py` | stub | `test_ingestion_pipelines.py` (17) |
| Features | `eval/features/f1_...py` to `f8_...py` | stub | `test_features.py` (18) |
| Cross-cutting | `eval/retrieval_only.py`, `failure_analysis.py` (the `ErrorType` enum is done, the functions are stubs), `contamination.py`, `label_sensitivity.py`, `bias.py` | stub | `test_registries.py`, `test_features.py` |
| Runners | `eval/runners/shard_runner.py`, `run_rq1.py`, `run_rq2.py`, `run_ablations.py`, `run_features.py`, `run_safety.py`, `run_tool_calling.py` | stub | `test_runners.py` (19) |
| Test-set builders | `testsets/t1_...py` to `t9_...py`, `common.py`, `companions.py`, `degrade.py`, `rendering.py` | stub | `tests/unit/testsets/test_t1...` to `test_t9...`, `test_common.py` |
| Fine-tuning | `finetune/teacher_dossiers.py`, `span_filter.py`, `noise_augment.py`, `build_dataset.py`, `train_qlora.py`, `merge_adapter.py` | stub | `tests/unit/finetune/*` |
| Run registry | `configs/eval/runs.yaml`, `hypotheses.yaml` | exists; `hypotheses.yaml` has `margin_vs_p4: null` to fix on dev | `test_registries.py` |
| Ada scripts | `scripts/ada/run_*.sh`, `sbatch_qlora.sbatch` | exist | `test_runners.py` |
| Orchestration and export that the full-system runs need | `orchestration/graph.py`, `fallback_state_machine.py`, `export/*`, `api/*`, `tools/drafting/application.py` | stub | `tests/unit/orchestration`, `tests/unit/export`, `tests/system` |

### 8.3 What to build for this plan, and the tests to write

New code needed (only while modules are stubs, tests are written first and are not run until the code exists):

| New or changed | Module | For | Tests to add |
|---|---|---|---|
| McNemar (exact and asymptotic) and cluster bootstrap | `eval/stats/mcnemar.py`, `eval/stats/cluster_bootstrap.py` | Section 5.2 | `tests/unit/eval/test_stats.py`: textbook 2x2 tables; discordant counts under 25 use the exact test; case-level resampling keeps items together |
| Baselines B0L, B0S, B6 | `eval/baselines/b6_expert_rule.py`; `model=` argument in `b0_single_pass.py` | Section 3.1 | `test_baselines.py`: B6 calls no model; B6 never imports the factor tagger; B0L uses the teacher role |
| Switches and variant table | `orchestration/switches.py` (fields of Section 3.4) | S1-S17 | `test_registries.py`: every new field belongs to a named variant; defaults leave `variant()` equal to `full` |
| S1 | `agents/sutradhar/planning.py`, `slot_rules.py`, `prompts.py` | self-critique retrieval | `tests/unit/agents/sutradhar/`: critic outcomes map to actions; budgets still respected |
| S3 | `agents/sutradhar/slot_rules.py`, `prompts.py` | LLM rater | rules still run first; `llm` mode never raises the budget |
| S2, S4 | `agents/sutradhar/factor_pick.py`, `slot_rules.py`, `stores/hybrid.py` | adaptive depth; skew | skew function on constructed score lists; AUROC helper |
| S5 | `stores/caselaw_citations.py`, `stores/hybrid.py` | PPR expansion | expansion never adds documents dated after the case's before-date (leakage test) |
| S6 | new `agents/sutradhar/store_prior.py` | B5, A12 | labels are built from dev only; `order` mode never removes a contract-allowed store |
| S7 | `ingestion/gaps.py`, `pageindex.py`, `agents/munshi/decisions.py` | A11a | hierarchy ranking vs sequential scan on a constructed bundle |
| S8, S9, S10, S11 | `agents/vakeel/agent.py`, `agents/abhiyojak/agent.py`, `isolation.py` | A2b, A8b-d | sampling critic uses the same token budget; no-isolation arm sees Vakeel's notes while the default arm still raises `ContextIsolationError` |
| S12 | `orchestration/graph.py` or the evaluation driver | topology arms | each topology produces a schema-valid brief with the same stores |
| S13 | `eval/runners/` config-grid driver | workflow search | grid is enumerated deterministically; winner chosen on dev only |
| S14 | `batch/cache.py` (plan-template cache), `batch/scheduler.py`, `models/vllm_client.py` | A14 | private-shelf calls are never cached; plan cache key invalidates on store version |
| S15 | `orchestration/structured_output.py`, `schemas/` | A13 | three formats parse to the same schema; reasoning field is not read as an answer |
| S16 | `stores/chunking.py`, `eval/baselines/chunking_variants.py` | proposition, late chunking | token-size limits; chunk coverage of the paragraph text |
| S17 | `privacy/`, `agents/peshkar/agent.py`, `ingestion/signals.py` | A15 | typed hand-off returns only schema fields; text-layer vs OCR mismatch flags a remapped-font PDF and not a legacy Hindi font page |
| New metrics M9, M11, M13, M14, M16-M19, M24, M25, M27, M30-M35, M44-M50 | `eval/metrics/*` (new functions) | Section 4 | one table-driven test per metric, plus the null-agent audit as a parameterised test over all metrics |
| Faithfulness-correctness grid | `eval/metrics/unsupported_fact.py` | M35, Fig 7 | corroboration check on constructed sentences |
| `FORMAT` error tag; MAST overlay | `eval/failure_analysis.py` | Section 5.11 | `test_registries.py` (the plan names eleven classes; adding one means updating the test that asserts eleven) |
| Blind-slice lock | `eval/runners/` scoring entry | Section 5.8 | blind scoring refuses without the tag and with the lock file present |
| Evaluation driver (no LangGraph) | `eval/runners/driver.py` | Section 7.3 | scripted counsel approves gates only when the scenario says so; unapproved export is still blocked |
| Table and figure writers | `eval/report/` (new) | Section 6 | each table writer produces the declared columns on a fixture |
| Jobs in `configs/eval/runs.yaml` | add B0L, B0S, B6, S-variant jobs, sweep, robustness, knock-out abstention | Section 7 | `test_registries.py::test_run_registry_matches_plan` must be updated; it asserts the plan's job list |

The existing registry test asserts the plan's totals (about 279 node-hours and a fixed job list); adding jobs means changing that test deliberately, and marking the change.

## 9. Open decisions and risks

### 9.1 Decisions the team must take

| # | Decision | Options | Recommendation | Needed by |
|---|---|---|---|---|
| D1 | Blind slice: a post-Qwen3-release set, or a random 80 of the 200 | Count clean post-April-2025 High Court orders first; if at least 80 exist, use them | Post-release if the count allows | Before the freeze |
| D2 | Evaluation driver without LangGraph | Wait for `graph.py`, or write a thin driver with a scripted counsel | Thin driver (Section 7.3); the real gates are still tested in T7 | Week 1 |
| D3 | The teacher: API or Qwen3-32B | The week-1 pilot decides; the API saves 45-60 node-hours | API if the terms allow | Week 1 |
| D4 | Value of δ, ε and the pass^3 bar | Fix on the 50 dev orders | Round to whole points; write the dev uncertainty next to each | At the freeze |
| D5 | Which Tier B and C variants to run | Section 7 order | Decide at the end of week 2 from measured tokens per case | End of week 2 |
| D6 | Headline for RQ1: recall alone or recall with the precision guard | Plan 14.2 says recall; "argue all" defeats it | Recall and lenient precision together (C1 with C3) | Before the freeze |
| D7 | Sarvam as a fourth labeler or as a model | It is off by default; no live call has been made; retention is a dashboard setting | Use only for public-text relabeling, not as a system model | Optional |
| D8 | Is IL-PCSR available and licensed (the external retrieval check) | Check the data card | Run if available; otherwise state the single-corpus limit | Week 1 |
| D9 | Should the Hindi slice use HLDC (blocked, non-commercial) or NLLB-translated text | A teammate requests access; NLLB is the fallback | NLLB for the main runs, HLDC added if approved; always report native vs translated | Week 1 |
| D10 | Whether a `FORMAT` error class is added to the plan's eleven | Needed for failure point 5 | Add it | Week 1 |
| D11 | Number of sessions per account in the peak week | Plan 17 assumes 5-7 | Check with the cluster rules and the team's availability | Now |

### 9.2 Risks

| Risk | Effect | Mitigation |
|---|---|---|
| **Compute does not fit** (Tier A floor about 229 node-hours against about 180 usable) | Fewer runs, wider intervals | Measure tokens per case first; the cut order of Section 7.4; the API teacher; thin driver; run independent jobs in week 2 |
| **The system is not runnable in time** (graph, API, export and all evaluation modules are stubs) | No full-system results | Step 0 of Section 7.3 starts the independent items now; Munshi, retrieval-only, Rights Radar and tool-calling evaluations do not need the graph |
| **Real model paths are untested** (no weights downloaded, offline stand-ins only) | Surprises in week 2-3 | Download weights and run 10 dev cases on Ada in week 1 before anything else |
| **G2 coverage is too low** (about 17% resolution) | C5 cannot be tested | Wire in the Supreme Court metadata; report coverage; fall back to a pilot statement; IL-PCSR check |
| **Too few BNS-era orders with usable labels** | C5, C17 under-powered | The test split has 94 BNS-era orders against a target of 60; report n; per-court skew noted |
| **Labelers disagree** | Thin gold | Agreed labels only; merge confusable factors; rule-only results |
| **MiniCheck is weak on legal text** | Unsupported-fact rate biased | Verbatim-span check; F/C table; in-domain constructed test; report the checker's accuracy |
| **Several adopted ideas rest on 2026 preprints or unconfirmed venues** | Related-work claims may need correcting | Re-check venues before the final report; entries marked S in the review were not re-fetched; CRAG, Towards a Science of Scaling Agent Systems, Autellix, Design Patterns and Spotlighting are preprints |
| **The LLM sufficiency rater is unreliable on legal text** | S3 may fail | It is an ablation, not a dependency; rules stay as the default |
| **Pre-registration slips** | Results are looked at before thresholds are fixed | The freeze is the first week-2 task; the blind scoring entry point enforces it |
| **Contribution lines come from abstracts** (literature review limit) | A paper may not do what its abstract implies | Read the method sections of S1, S3, S6, S7, S9 before implementing them |
| **Per-case token budget differs by variant** | Unfair comparisons | Equal-token arms where the claim needs it (S9); budgets recorded in every run manifest |

### 9.3 Assumptions in this plan that are not verified

- The per-case SD of paired differences (0.25) and the throughput numbers (2M tokens per node-hour for the 14B) are assumptions to be measured in week 1.
- Qwen3's recommended sampling settings (temperature 0.6, top-p 0.95) are taken from memory of the model card and should be checked.
- The statement "Qwen3 released April 2025" is from the plan; the repository config uses 2025-04-01.
- Paper links are from the literature review; those marked S there were not re-fetched. In this plan Adaptive-RAG, From RAG to Memory (HippoRAG 2), Debate or Vote and Barnett et al. were re-fetched and matched; Self-RAG's venue is confirmed by the L14 slide.
- The course slides are image-heavy; ideas such as "context budget" are used as the slide text states them, and no slide figure was rendered for this plan.
