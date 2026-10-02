# Project Proposal: LMA Group Project 2026

## NyayaSahayak: Verified Bail Preparation for Legal-Aid Counsel

- **Team:** Harshita Kumari, Satvik Rao, Shravani K, Vishak Kashyap K
- **Domain:** Legal (Indian criminal procedure) 

## 1. Summary

Two agents for High Court regular bail:

1. A **Court-Records Agent** turns a case file into a *verified dossier* (every fact linked to a source span). Counsel uploads PDFs and/or describes the case in a chat, answers clarifying questions and asks cited questions about the file.
2. A **Defense-Preparation Agent** turns the dossier into a *grounded bail brief*: every claim cites a dossier fact or a retrieved authority.

Counsel approves at two code-enforced gates. Models are open-weight and run on the IIIT Ada cluster or our workstation; we use no paid APIs.

## 2. Domain and target user

**Domain:** regular bail in one High Court (CrPC s.439, now BNSS s.483). **Users:** legal-aid panel counsel and junior advocates drafting bail applications under heavy caseloads from records spread across several orders; supervised law-clinic students as secondary users. **Not users:** accused persons, the public and judges. The chat is for counsel only, and the system never predicts outcomes.

## 3. Problem statement

Preparing a bail application means pulling scattered facts (custody dates, charge-sheet status, earlier bail rounds, co-accused bail) out of earlier court orders and arguing them against the factors courts weigh, with precedent. Since 1 July 2024 the BNS and BNSS have replaced the IPC and CrPC, so the correct section depends on the offence date and transition rules, while most bail case law still discusses the old IPC sections. General-purpose LLMs invent facts and authorities: US-law studies report 58–88% hallucination on case-specific questions (Dahl et al., 2024) and 17–33% in commercial legal RAG tools (Magesh et al., 2025). Indian legal-AI systems mostly predict outcomes or simulate courtroom debate, and are scored on the verdict, not on whether arguments are grounded in the record and valid authority. Verification loops can cut hallucination, but a verifier that silently drops a valid defense ground has a real cost, and this omission side of the trade-off is rarely measured in legal argument generation. We also found no work that carries IPC-era case law to BNS-era cases or flags when an old precedent no longer transfers. Counsel need a system that is verifiably grounded, temporally correct about statutes, explicit about uncertainty, and honest about what its verification removes.

## 4. Research questions and hypotheses

**RQ1 (main): grounding and the verification tax.** Does arguing from a verified dossier, with a verification loop, improve grounding over a self-refining agent with the same compute? What does each verifier failure policy cost in omitted valid grounds?

- **(a) Grounding:** full system vs B3 (ReAct + Self-Refine) and B1 (single-pass RAG).
- **(b) Verification tax:** a rejected claim is handled by **V1** delete, **V2** repair, **V3** escalate to counsel, or **V4** repair-then-escalate plus a missing-factor check. Each is scored on hallucination, omission and escalation burden. Errors are asymmetric: a fabricated authority embarrasses counsel, but a dropped valid ground can keep an undertrial in custody.

**RQ2 (exploratory): the recodification bridge.** For BNS-era cases, does concordance-aware retrieval recover the IPC-era precedents the court cited, and does a *transfer check* flag precedents whose provision changed?

**Hypotheses**

- **H1:** the full system beats B3 on answerable-factor recall and on the unsupported-claim rate (validated MiniCheck, with a human-audit fallback). Every baseline gets the same 12-factor checklist, so any gain is net of the checklist.
- **H2:** V1 has the lowest hallucination and the highest omission. V4 omits less than V1 while staying non-inferior on hallucination (pre-registered margin), but only if its escalation burden is below V3's and its escalation precision is ≥ p (pre-registered). This means escalating everything cannot satisfy H2.
- **H3 (exploratory):** on the BNS-era subset, section-family expansion beats unfiltered dense retrieval and a popularity baseline on recall@10 of court-cited *offence-specific* precedents.

**Critic vs verifier** is only an ablation (A2 vs A3): an inference-time analogue of Kim's (2026) training-time finding. **Thresholds** come from a 30-dev-case pilot and are pre-registered (hashed commit) at the week-5 freeze.

## 5. Why it matters and what is missing

Undertrials were 75.8% of India's prisoners at the end of 2022 (NCRB, *Prison Statistics India 2022*). Poorly prepared bail applications prolong detention.

| Existing work | Gap |
|---|------------|
| NyayaRAG, PredEx, IBPS; SAMVAD, AgentCourt, OBJECTION | These predict outcomes or simulate courtrooms and are judged on verdicts. SAMVAD grounds its arguments in retrieved text, but none of these prepares counsel's case from records. |
| Zhang, Gray, Savelka & Ashley (2025); RARR (2023); Huang et al. (2024) | These cover factor use and abstention, attribution vs preservation, and self-correction that hurts. None measures omission caused by a verifier. |
| IPC2BNS-Verify; a local statute RAG (2026) | These map *statute sections*. We found none that carries *case law* across, but the search was quick, so a full check comes before any "first" claim. |

## 6. The five capabilities

| Capability | Where; why needed | Metric (ablation) |
|---|----------|------|
| **Fine-tuning** | A QLoRA Qwen3-4B extractor builds the bail store for the whole court subset in ≈30 node-h (the 32B teacher would need ≈295) and runs on the 8 GB workstation | E4 field F1 (hard orders separately); S2 size and precision (A6) |
| **RAG** | Date-cut statute, bail and precedent stores: authority valid at the order date | Recall@10 of court-cited precedents (A5, A7) |
| **Reasoning** | Factor planner; span check; verify-revise loop | Factor recall; unsupported claims; false-fill rate (A1–A3, A10, A12) |
| **Agentic** | Tool choice per factor; repair vs escalate; stopping; hand-off via chat and gates | Task completion; pass^3; progress rate (B2/B3, A11) |
| **Tool calling** | Deterministic `map_section`, `date_calc`; store queries; `ask_user`; gated mock filing tools | Accuracy vs annotated calls; recovery; **attempted-unsafe-action rate** (A4) |

## 7. Proposed system

```
Input: PDF upload and/or chat            (minimal case list: create / open / resume)
INTAKE  PDF→text (OCR) | chat → pseudonymise PII → per-case index
        sexual-offence / POCSO / juvenile matters → declined
COURT-RECORDS AGENT
  R1 Segment + NER        rhetorical-role model, InLegalNER
  R2 Extract              fine-tuned Qwen3-4B; ~15 fields, each with a span
  R3 map_section  [tool]  IPC↔BNS, CrPC↔BNSS by offence date; else AMBIGUOUS
  R4 date_calc    [tool]  custody days, BNSS s.479 check
  R5 Span verifier        DeBERTa NLI; re-extract once, else UNSUPPORTED
  CHAT                    ≤3 clarifying questions; cited answers to counsel
  == HUMAN GATE 1: counsel corrects the dossier ==
DEFENSE-PREPARATION AGENT (Qwen3-14B)
  D1 Factor planner       12-factor checklist → favourable / adverse
  D2 Retrieve             tool choice per factor; IPC↔BNS family expansion;
                          only documents dated before the order
  D3 Draft                every sentence cites [F#] facts, [A#] authorities
  D4 Prosecutor critic    objections, counter-authorities, missed facts
  D5 Verifier             NLI support, ratio/obiter, good law, statute
                          validity, transfer status, untagged citations
  D6 Revise               ≤2 rounds under policy V1–V4; open issues listed
  == HUMAN GATE 2: counsel approves; export only after approval ==
STORES  S1 statutes (≈1,000 rows) · S2 bail-order rows (est. 8–12K) · S3 chunks
```

**Design decisions** (details in `plan.md` §4)

1. **Citations.** The drafter may cite only retrieved IDs, and citation text is rendered from metadata, so fabricated citation metadata is prevented by construction. A post-check counts any untagged case name or section as a fabrication.
2. **Deterministic tools.** They build on the IPC2BNS-Verify concordance, checked against NCRB/BPRD, plus our own CrPC↔BNSS bail mapping. Unclear cases return `AMBIGUOUS`.
3. **Statuses.** Each fact is marked `VERIFIED`, `COMPUTED`, `UNSUPPORTED`, `AMBIGUOUS`, `USER_STATED` (typed in chat; no record behind it, so labelled in the brief) or `USER_ASSERTED`.
4. **Counsel-only chat.** Answers cite the case file, S1 or `date_calc`; the chat abstains outside scope and never predicts or advises laypeople. Mock filing tools are gated, and each case is isolated.

**Verifier policies.** All four policies branch from **the same pre-verification draft**, so any differences come from the policy alone. **Omission** (at claim and factor level) means content that was valid before verification, absent after it, and not listed in the open issues. Claim IDs are tracked, so a rewritten claim counts as kept. **Escalation burden** is the number of escalated items per brief, together with their precision. The **shown-unverified rate** is reported separately from hallucination.

**Recodification bridge.** Queries expand to the section family (e.g. BNS 318(4) ↔ IPC 420). Each authority is tagged `SAME_TEXT` (transfers), `CHANGED` (diff shown; qualified use only) or `NEW`.

## 8. Expected novelty

1. **The verification tax, posed as a question.** We aim for the first measurement of verifier-induced omission of court-accepted grounds under alternative failure policies, in a real-record defense setting.
2. **A recodification bridge** that carries IPC-era case law to BNS-era cases and flags changed provisions (subject to a full related-work check).
3. **A counsel-grounded, leakage-controlled benchmark** with factor-level labels restricted to factors answerable from the stripped input.

## 9. Data and evaluation environment

**Sources** (all free): Open India Law (judgments to 2025, statutes), AWS Indian HC Judgments (PDFs, CNR metadata), IPC2BNS-Verify, NCRB/BPRD tables, IndianBailJudgments-1200, IBPS, IL-TUR, InLegalNER.

**Corpus and stores** (est. = measured in week 0; `plan.md` §4.4). One HC plus the SC (est. 20–60K documents). Case files link earlier orders mainly by **FIR number + police station**, since a new bail application gets a new CNR. Qwen3-32B silver labels on ~3K orders yield est. 1.2–1.8K fully verified fine-tuning pairs; the tuned extractor then builds S2 (est. 8–12K rows).

| Set | Size | Tests |
|---|----------|----|
| **E1: Bail cases** | 120 (30 dev / 90 test); sexual-offence, POCSO and juvenile matters excluded; est. 25–40 BNS-era test cases | RQ1, RQ2 |
| **E2: Citation errors** | ~100 real (from baselines on dev and non-E1 orders) + ~150 planted; ⅓ for tuning, ⅔ for evaluation | Verifier; real and planted reported separately |
| **E3: Statutes and stores** | 1,140 concordance queries + 100 date cases + 50 S2 rows | Tool accuracy; S2 precision |
| **E4: Gold dossiers** | 40 (20 dev / 20 test) | Extraction; oracle Gate 1 |
| **E5: Safety and chat** | 40 scenarios (pressure, injection, tool failures, invalid input, out of scope, cross-case); 116 chat queries (80 generated from E4 dossiers, 6 statute/date, 30 to refuse); 40 PII documents | Attempted unsafe actions, recovery, refusals, PII recall |
| **E6: Text input** | 20 test cases rewritten as chat descriptions from the stripped input | Factor recall vs PDF input |
| *If time permits* | X1: user study (4 cases × 6–8 people). X2: counterfactual records (30 × 3 edits). | |

**E1 construction.** The *input* is the current order's facts plus earlier orders. Both sides' arguments and the court's reasoning are *removed*; a leak check requires no 8-gram overlap with the removed text, and 20 cases are checked by hand. The *gold* labels mark each factor (Appendix A) as argued, raised or accepted, and as **answerable from the input**. κ is measured on 30 double-annotated cases. **Leakage controls:** retrieval sees only documents dated before the order; the case's own order, documents citing it, and same-FIR orders are excluded from the fine-tuning data, S2 and S3; MinHash near-duplicate audit; 2025–26 test orders, split by the Qwen3 release date.

**Legal reviewer** (~16 h): guidelines, E1 adjudication, **[verify]** items, spot-checks, and blind ratings of 36 briefs (12 cases × full system, B3 and B1; 6 contain planted bad citations). **Fallback:** the team annotates from guidelines, adds law students if possible, and states the limitation. Team annotation totals ≈180 person-hours (`plan.md` §5.3).

## 10. Baselines and ablations

All use Qwen3-14B, the same corpus and cutoff, and **the same 12-factor checklist**.

| ID | Baseline | Controls for |
|---|--------|------|
| B0 | Zero-shot LLM | Lower bound |
| B1 | Single-pass RAG (NyayaRAG-style) | Standard RAG |
| B2 | ReAct agent with the same tools | Tool access |
| B3 | B2 + Self-Refine, matched token budget | Compute, self-critique (**key**) |

**Ablations** (1 run on a 60-case test subset unless noted): A1 no dossier · A2 no verifier · A3 no critic · A4 no tools · A5 no RAG · A6 extractor variants (on E4; downstream on 20 E4-test cases) · **A12 "just ask an LLM"**: prompted 14B/32B fill the dossier schema with no spans or span check (on E4) · A7 no bail store · A10 no planner · A11 fixed retrieval script · **A8 policies V1–V4 (all 90 cases, 3 runs)** · A9 no section-family expansion or transfer status (BNS-era subset; also compared with unfiltered dense retrieval and the 10 most-cited precedents) · oracle Gate 1 from gold dossiers (20 cases).

**Automated runs.** Gate 1 auto-passes and Gate 2 is not simulated. `request_approval` returns "pending", so any gated call counts as an attempted unsafe action. `ask_user` returns "unknown"; in E6, a scripted responder answers from the stripped input only. All systems share the same per-factor context strategy. Single-run ablations are compared with run 1 of the full system, using the same seed.

## 11. Metrics

| Area | Metrics |
|---|------------|
| **Grounding** | **Answerable-factor recall** (primary) and precision against defense-argued factors; court-accepted recall; critic recall of adverse factors |
| **Faithfulness** | **Unsupported-claim rate, scored against the source case file and the cited paragraph, never against the system's dossier.** Primary measure: **MiniCheck** (not the verifier's family) on all briefs, validated by a human audit of 900 sentences (30 cases × full system, B3, V1). If κ < 0.6 for any system, the audit is used instead. Also: misgrounded, bad-law and untagged-citation rates. |
| **Verification tax** | Per policy: hallucination, shown-unverified rate, **omission (claim and factor level)**, escalation burden and precision. Claim level is primary if V1 drops whole factors in <5% of pilot briefs. |
| **Recodification** | Recall@10 for offence-specific vs generic precedents, with n and CIs; wrong-transfer rate on 30 labelled transfers |
| **Components** | Recall@10 (coverage reported); S2 precision; E4 field F1, wrong-value and false-fill rates (A6, A12); tool-call accuracy; recovery; task completion; pass^3 |
| **Safety** | **Attempted-unsafe-action rate** (blocked attempts reported too); injection success; chat refusals; PII leaks; cross-case leakage |
| **Overall** | Reviewer rubric (1–5) and planted-citation catch rate on 36 blind briefs. An LLM judge scores run 1 of the main systems and is validated by weighted κ; any dimension with κ < 0.6 is reported from human ratings only. |

**Statistics.** The primary endpoints form one Holm family of four tests. Two test H1 (full system vs B3), on recall and on MiniCheck-unsupported claims. Two test H2 (V4 vs V1), on omission and on hallucination non-inferiority. The 30-case audit alone would have been underpowered, which is why MiniCheck is the primary measure. Everything else gets paired-bootstrap 95% CIs. Runs are averaged per case before Wilcoxon or McNemar tests. The MDE is set from the pilot. Assuming a paired-difference SD of ≈0.25 at Holm α=0.0125 and n=90, power is ≈90% for a 10-point gain and ≈27% for a 5-point gain. Rubric agreement uses weighted κ or Krippendorff's α. Failure analysis tags 30 cases with LexAgentHallu categories plus our own types, and adds 4–5 case studies.

## 12. Safety and ethics plan

**Approval and framing.** Counsel approves each case before export or any mock action, and this is enforced in code. The system makes no predictions and gives no lay advice; the chat refuses lay-style requests (E5). Outputs are labelled as AI drafts. Sexual-offence, POCSO and juvenile matters are declined at intake (BNS s.72, POCSO s.23, JJ Act s.74 **[verify]**).

**Privacy and use.** Text is pseudonymised before inference using encrypted name maps, and only public orders are used. Released data replaces all party names, including the accused's, and we build no profiles. We assume a counsel-only local install with no public endpoint. **Dual use:** the pipeline could help prosecution, so we release it as a defense aid.

**Robustness, bias, ethics.** Documents are treated as data, never as instructions. We compare quality across offence type, outcome, custody band and gender, pooling any group with n < 10. In week 0 we will ask the institute whether annotation needs approval; X1 needs approval regardless.

## 13. Compute plan

**API budget:** INR 0. All throughput figures are **assumptions, measured in week 1** (derivation in `plan.md` §8).

**Hardware and models.** IIIT Ada (`-A research --qos=medium`) gives us 3 accounts, never shared, each capped at **one 4× RTX 2080 Ti node** (11 GB per GPU; Turing, so no BF16). We plan on 2 nodes, with the third as upside: A runs the data build and fine-tuning; B the pilot and main runs; C the ablations and judge. A 4060 workstation (8 GB) handles development and the demo. The generator is **Qwen3-14B-AWQ** (TP=2, 2 instances per node). Qwen3-32B-AWQ (TP=4) is the silver teacher and A6 model, and the Qwen3-4B QLoRA extractor is served in int4. Evaluation uses a Mistral-Small-3.2-24B judge and MiniCheck. We use no 70B model, because its ~35–40 GB of weights would leave no room for the KV cache. **Tokens per run:** ≈170K for the full system (`plan.md` §8.2); 13K / 18K / 90K / 170K for B0–B3; +52K for each of V1–V3.

**Node-hours.** We *assume* 500/120 tok/s (prefill/decode) per instance at 80% utilisation, which gives **≈12 runs (2.0M tokens) per node-hour**.

| Item | Generator tokens | Node-h |
|-----------|----|---|
| Full system and B3 (2 × 90 × 3 × 170K) | 91.8M | 46 |
| B0, B1, B2 | 14.1M | 7 |
| V1–V3, branched (810 × 52K) | 42.1M | 21 |
| Ablations | 86.0M | 43 |
| E2, E5, E6, chat | 17.6M | 9 |
| Pilot and debugging | 51M | 26 |
| Silver labels (3K × 18K tokens) · QLoRA · corpus S2 (int4 4B) · other (embeddings, A6, judge, MiniCheck) | – | 70 · 38 · 30 · 24 |
| **Total** | **≈303M generator tokens** | **314 node-h, all GPU work (≈408 with 30% buffer)** |

**Does it fit?** We assume ~30% node availability per account, about 50 node-h a week, with 4–5 concurrent cases per instance. Pre-freeze work needs 224 buffered node-h, against ≈450 from 2 accounts. Post-freeze needs 185, against ≈200 from 2 accounts or ≈300 from 3. **Sensitivity:** at half the decode rate, post-freeze needs ≈245, which the third account or cuts 1–5 cover. After all cuts, 2 accounts are enough down to ≈20% availability. **Already shrunk:** only the full system, B1, B3 and V1–V3 get 3 runs; ablations use 60 cases; policy branching saves 48 node-h; the judge scores 1 run. **Further cuts, in order:** drop A6 downstream (−3); secondary ablations on 40 cases (−9); V1–V3 at 2 runs (−7); B1 at 1 run and a smaller E5 (−5); full system and B3 at 2 runs (−15).

**Storage.** About 10–17 GB lives on /share1 and is staged to node /scratch for each job (staging and purge rules in `plan.md` §8.6).

## 14. Timeline (8 weeks)

| Week | Milestones |
|---|------------|
| 0 | Approval; feasibility checks (a)–(g) (`plan.md` §5.1); ethics query; reviewer; hpc.admin OK for coursework use |
| 1 | Corpus and case files; **throughput measured**; guidelines and pilot κ; intake, chat, S1, tools |
| 2 | Records Agent; **silver pass** (A/B); E1 dev labels; B0/B1; skeleton |
| 3 | D1–D3, S3; QLoRA (8B non-blocking); E1 test labels; E4; B2 |
| 4 | D4–D6, V1–V4; B3; **extractor fixed** (E4-dev rule); corpus S2; E2, E5; UI |
| 5 | Pilot → thresholds → **freeze and pre-register**; test runs start |
| 6 | All test runs |
| 7 | Judge, audit, reviewer ratings, failure analysis; X1/X2 if time permits |
| 8 | Write-up, demo, release |

## 15. Risks and fallback plans

| Risk | Fallback |
|---|---|
| Too few usable orders; low κ or citation coverage | Second HC or 2024–26; merge factors; RQ2 as a pilot |
| Throughput, queue or AWQ problems; weak 14B | Ordered cuts (§13); GPTQ or llama.cpp; 32B for D3 |
| FP16 QLoRA unstable; weak extractor | BF16 on the 4060; report the negative result |
| No legal reviewer | Team annotation from guidelines; limitation stated |

## 16. Deliverables

(1) A Streamlit prototype (both agents and gates, chat, case list); (2) E1–E6 with guidelines; (3) code, Slurm scripts and traces; (4) a workshop-style paper and a demo video.

**Out of scope:** case groups, judge simulation, GraphRAG, real client files, eCourts scraping, district courts, Hindi, anticipatory bail.

## Glossary

**CNR:** eCourts case number. **FIR + PS:** first information report + police station. **Ratio / obiter:** binding reasoning / passing remarks. **RR:** rhetorical role. **NLI:** entailment check. **pass^3:** solved in all 3 runs. **AWQ / TP:** 4-bit quantisation / tensor parallelism.

## Appendix A: The 12 bail factors (also the annotation scheme)

(1) gravity and punishment; (2) custody period; (3) charge sheet filed; (4) trial delay; (5) parity with co-accused; (6) antecedents; (7) flight risk; (8) witness tampering; (9) weak prima facie case; (10) health, age, gender or family; (11) statutory bar (NDPS s.37, UAPA s.43D(5), PMLA s.45) **[verify]**; (12) BNSS s.479 / CrPC s.436A.

## Key references

Dahl et al., JLA 2024 (arXiv:2401.01301) · Magesh et al., JELS 2025 (arXiv:2405.20362) · Zhang, Gray, Savelka & Ashley, ASAIL@ICAIL 2025 (arXiv:2506.00694) · Gao et al., *RARR*, ACL 2023 · Huang et al., ICLR 2024 (arXiv:2310.01798) · Kim, arXiv:2608.01559 · Nigam et al., *NyayaRAG*, IJCNLP-AACL 2025 · Devadiga et al., *SAMVAD*, arXiv:2509.03793 · Yao et al., *ReAct*, ICLR 2023 · Madaan et al., *Self-Refine*, NeurIPS 2023 · Tang et al., *MiniCheck*, EMNLP 2024 · NCRB, *Prison Statistics India 2022*. Full catalogue: `datasets_sources.md`.
