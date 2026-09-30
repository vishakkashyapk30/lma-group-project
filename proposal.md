# Project Proposal: LMA Group Project 2026

## NyayaSahayak: Verified Bail Preparation for Legal-Aid Counsel

- **Team:** Harshita Kumari, Satvik Rao, Shravani K, Vishak Kashyap K
- **Domain:** Legal (Indian criminal procedure)

---

## 1. Summary

We will build a two-stage agentic system for Indian High Court regular-bail matters.

1. A **Court-Records Agent** turns a case file into a *verified dossier*. Every fact in the dossier is linked to a span of the source text.
2. A **Defense-Preparation Agent** turns that dossier into a *grounded bail brief*. Every claim in the brief cites either a dossier fact or an authority retrieved from a legal corpus.

The user creates a case in a dashboard and supplies either case-file PDFs or a plain-text description of the case. The system pseudonymises personal data locally, builds an index of the file, and streams its progress while it works. A lawyer checks and approves the output at two points. The system combines all five capabilities: QLoRA fine-tuning, RAG, multi-step reasoning, agentic control, and tool calling.

Our research asks three questions. Does verification make generated bail arguments better? What does verification cost in valid arguments that get silently dropped? And can a *recodification bridge* carry IPC-era precedent across to BNS-era cases? We test them on real bail orders, with the answer-bearing text removed from the input, using gold labels of what defense counsel argued and what the court accepted. Every model is open-weight and self-hosted, and we use no paid APIs.

---

## 2. Domain and target user

**Domain.** Regular bail in one Indian High Court: CrPC s.439, now BNSS s.483.

**Primary users**
- Legal-aid panel counsel attached to High Court Legal Services Committees.
- Junior advocates in small criminal practices who draft High Court bail applications.

These users handle many bail matters with little research support. They must work from case records scattered across several court orders.

**Secondary user.** Law-clinic students preparing case summaries under supervision.

**Not users**
- **Accused persons and the public.** The system gives no advice to laypeople.
- **Judges.** The system does not predict outcomes.

A trained lawyer reviews every output. This human-in-the-loop design is central to our safety plan.

---

## 3. Problem statement

Preparing a bail application means pulling scattered facts out of earlier court orders. These include custody dates, charge-sheet status, bail history, and the bail status of co-accused. The lawyer must then argue them against the legal factors courts weigh, with supporting precedent. Since 1 July 2024 the Bharatiya Nyaya Sanhita (BNS) and BNSS have replaced the IPC and CrPC, so the correct section numbers now depend on the offence date and on transition rules. Section-number errors are easy to make and easy to miss. General-purpose LLMs invent facts and precedents: studies report 58–88% hallucination on case-specific legal questions (Dahl et al., 2024), and 17–33% even in commercial legal RAG tools (Magesh et al., 2025). Existing Indian legal-AI systems generate judgment predictions, explanations, or courtroom debates. They are scored on the *outcome*, and nobody checks whether each argument is grounded in the record and in valid authority. No existing system separates the benefit of verifying claims from the benefit of adversarial critique, even though recent work suggests verification is what matters (Kim, 2026). A system that is useful to legal-aid counsel must therefore be *verifiably grounded*, *temporally correct about statutes*, and *explicit about uncertainty*.

---

## 4. Research question and hypotheses

**RQ1 (main).** For High Court regular-bail preparation, does generating arguments from a verified dossier, with a verification loop, produce briefs that:
- (a) cover more of the bail factors that defense counsel actually argued and the court accepted, and
- (b) contain fewer unsupported facts and misgrounded authorities?

We compare against single-pass RAG and against a single tool-using agent that critiques and revises its own drafts (Self-Refine) at matched compute.

**RQ2 (the verification tax).** Verification reduces hallucination, but does it do so by silently dropping valid grounds that counsel argued and the court accepted? In defense work the errors are asymmetric: a fabricated authority embarrasses counsel, while a dropped valid ground can keep an undertrial in custody. We compare three verifier failure policies (delete, repair, escalate) and a combined policy that repairs first, then escalates, and never drops silently. We plot hallucination rate against omission rate for each.

**RQ3 (the recodification bridge).** New FIRs cite BNS sections, but most bail case law discusses the IPC sections they replaced. For BNS-era cases, does concordance-aware retrieval recover the IPC-era precedents the court actually cited, and does a *transfer check* (is the provision unchanged, or was it split, merged or reworded?) prevent arguments that lean on a precedent that no longer applies?

**Secondary ablation.** Is the benefit of the critique loop due to **verification** or to **adversarial critique** (a prosecutor agent)? Kim (2026, arXiv 2608.01559) found that the verification environment, not competition, drove the gains in adversarial legal self-play. We test whether that holds for Indian bail.

**Hypotheses**
- **H1:** the full system beats both baselines on factor recall and unsupported-fact rate.
- **H2:** deleting failed claims gives the lowest hallucination rate but the highest omission rate. Repair-then-escalate keeps hallucination close to the delete policy while cutting the omission rate.
- **H3:** concordance-aware retrieval raises recall@10 of court-cited precedents on the BNS-era subset, and a non-trivial share of naive transfers across changed provisions would produce a wrong argument.
- **H4 (secondary):** most of the hallucination reduction comes from verification, and the prosecutor critic mainly improves anticipation of adverse grounds.

Numeric thresholds are set from a pilot on 10 dev cases and pre-registered before the test set is run. A null result on any hypothesis is still a finding.

**Component evaluations (reported, but not part of the RQs)**
- A fine-tuned 8B extractor compared with a prompted 70B-class model.
- Accuracy of the date-aware statute resolver.
- Citation-resolution coverage.

---

## 5. Why it matters and what is missing

**Why it matters**
- Undertrial prisoners make up the large majority of India's prison population.
- Delayed or poorly prepared bail applications directly prolong detention.
- Legal-aid lawyers carry the heaviest load with the least support.
- The IPC→BNS transition has introduced a new, systematic source of errors.

**What is missing in existing approaches**

| Existing work | Gap |
|---|---|
| Indian judgment prediction / RAG: NyayaRAG (IJCNLP-AACL 2025), PredEx (ACL-F 2024), IBPS bail prediction (2025) | Predict outcomes. They don't generate defense arguments, and they don't check whether cited precedents actually support the claims. |
| Courtroom multi-agent simulations: SAMVAD (Indian, 2025), AgentCourt (ACL-F 2025), AgentsCourt (EMNLP-F 2024), OBJECTION (EMNLP 2026) | Evaluated on the verdict, not on argument grounding. Adversarial loops are never separated from verification. |
| Legal hallucination work: Magesh et al. (JELS 2025), CLERC (NAACL-F 2025), LegalCiteBench (2026) | Measures hallucination, mostly on US law. There is no pipeline for Indian criminal records. |
| Indian timeline and fact extraction: LexChronos (AAAI-W 2026), TathyaNyaya (2025) | Synthetic gold data or clean judgment text. No verification of extracted facts against their source spans. |
| IPC→BNS recodification | Existing work maps or retrieves *statute sections* across the change (IPC2BNS-Verify; a 2026 local multi-agent statute RAG; BNS/BNSS in an Indian legal RAG corpus). We found none that carries *case law* across it or flags when an IPC-era precedent no longer transfers. This was a quick search, so a full related-work check comes before any "first" claim. |
| Verification in legal generation | Measured on hallucination only. Its cost in silently omitted valid arguments is unmeasured, although general self-correction work shows verifiers can break correct answers (arXiv 2602.02416). |

---

## 6. The five capabilities: why each is needed and how we measure it

| Capability | Where it appears | Why the problem needs it | Metric | Ablation |
|---|---|---|---|---|
| **Fine-tuning** | QLoRA 7–8B dossier extractor (R2) | Extraction is the high-volume step. A small tuned model is cheaper and faster than a 70B model and runs on one small GPU. | Field-level F1 on gold dossiers; span-support precision; latency / GPU memory | Fine-tuned 8B vs base 8B vs prompted 70B-class |
| **RAG** | Statute store + bail records store + precedent index, hybrid retrieval, hard date cutoff (D2) | Each ground must rest on real statutes and precedents that are valid at the order date | Recall@10 of court-cited precedents; share of cited paragraphs that are *ratio* (the binding part of the judgment) | No retrieval; no bail store |
| **Reasoning** | Bail-factor planner (D1); verify-and-revise loop (D5–D6) | Legal factors must be mapped to record facts, and each claim checked before the brief is final | Factor recall/precision vs counsel's grounds; unsupported-fact rate; per-round analysis of revisions | No dossier; no verifier; no critic |
| **Agentic** | Two agents, bounded loops, state tracking, two human gates | The work has several stages. Some claims must be repaired or escalated, and some decisions must go to a human. | Task completion; pass^3 reliability; progress rate over sub-goals | Single agent (B2 / B3 baselines) |
| **Tool calling** | Statute mapper and lookup, date calculator, bail-store query, corpus search, span checker, pseudonymiser, approval gate, mock filing tools | Date arithmetic and section mapping must be deterministic, not guessed by the LLM | Tool-call accuracy (right tool + schema-valid arguments); error recovery; **unsafe-action rate** | LLM does mapping and dates itself |

---

## 7. Proposed system

```
 Input, per case: PDF(s) and/or a plain-text description   (cases are managed in a dashboard)
   │
   ▼
 INTAKE (R0)   PDF → text (OCR fallback) | free text → PII pseudonymisation (local map) → per-case index
                missing critical fields → up to 3 clarifying questions
   │
   ▼
 COURT-RECORDS AGENT
   R1 Segment + NER         rhetorical-role model (OpenNyAI / IL-TUR), InLegalNER
   R2 Extract (QLoRA 8B)    ~15-field dossier; every field carries a source span
   R3 map_section  [tool]   IPC↔BNS, CrPC↔BNSS by offence date; unclear → AMBIGUOUS; joins the statute store
   R4 date_calc    [tool]   timeline, custody days, BNSS s.479 undertrial check
   R5 Span verifier         NLI entailment of each field; on failure: re-extract once, else UNSUPPORTED
   ─── HUMAN GATE 1: counsel reviews and corrects the dossier ───
   ▼
 DEFENSE-PREPARATION AGENT
   D1 Factor planner        12-factor bail checklist → favourable / adverse factors, linked to dossier facts and provisions
   D2 Retrieve              the agent picks tools: statute lookup · bail-store query · vector search; concordance-aware (IPC↔BNS); only docs dated before the order
   D3 Draft                 one ground per factor; every sentence cites [F#] facts and [A#] authorities
   D4 Prosecutor critic     objections, counter-authorities, favourable facts the draft missed
   D5 Verifier              claim support (NLI) · ratio vs obiter · good-law keywords · statute validity · transfer check
   D6 Revise                ≤2 rounds; policy: repair, then escalate; never drop a claim silently
   ─── HUMAN GATE 2: counsel approves; export is possible only after approval ───

 KNOWLEDGE STORES (built offline, read-only at run time)
   S1 Statute Store        ~1,000 rows: text, punishment, bailable/cognizable, IPC↔BNS links
   S2 Bail Records Store   ~2–3K verified past bail orders as structured rows
   S3 Precedent index      role-labelled chunks of HC/SC judgments (BM25 + dense)
   S4 Per-case index       built at upload time from the user's own file
```

**Key design decisions**

1. **Cite only what was retrieved.** The drafter may cite only dossier field IDs and retrieved document IDs, and the citation text is filled in from corpus metadata. Fabricated authorities are impossible by construction, so the remaining risks are misgrounding and bad law, which D5 checks.
2. **Deterministic tools for dates and statutes.** The statute resolver uses the IPC2BNS-Verify concordance, checked against the official NCRB/BPRD tables. Only clear transition rules are encoded; everything else returns `AMBIGUOUS` and is escalated to the user.
3. **Uncertainty is shown, never hidden.** Dossier fields carry one of six statuses: `VERIFIED`, `COMPUTED`, `UNSUPPORTED`, `AMBIGUOUS`, `USER_STATED` (from the user's own text, which cannot be checked against a court record) and `USER_ASSERTED` (entered or corrected by counsel).
4. **Testable safety.** Mock state-changing tools (`file_application`, `send_to_client`) exist in the sandbox behind the approval gate. They let us measure the unsafe-action rate, which would otherwise be zero by construction.
5. **Models: all open-weight, served with vLLM on our GPUs.**
   - Drafter, planner and critic: a 30–70B-class instruct model.
   - Extractor: an 8B QLoRA model.
   - NLI checks: DeBERTa-v3.
   - Retrieval: BGE-M3 / InLegalBERT, plus a reranker.
   - Evaluation judge: a model from a *different* family than the generator, validated against human labels.
6. **Personal data is pseudonymised before any model sees it.** Names are replaced with consistent pseudonyms (Accused-1, Co-accused-2, Victim-1) using InLegalNER plus Microsoft Presidio patterns. The mapping is kept in an encrypted local store per case. Real names are restored only in what counsel sees, and victim and minor identities are never restored. We measure pseudonymisation recall on documents with planted personal data.
7. **Structured stores instead of GraphRAG.** The statute set is small enough for a table with links (S1). A structured table of verified past bail orders (S2) lets the agent filter by offence family, factor and outcome before doing semantic search. The agent chooses its tools, so we don't need a separate query classifier, and tool-call accuracy already measures routing.
8. **Case workspace and dashboard.** Users can create many cases, each with its own state, index and pseudonym map. A dashboard lists them with status, next hearing date and an "items need attention" badge, and supports filtering and user-defined groups (folders or tags). Approvals are per case, with no bulk approval. Cases are isolated from each other, and cross-case leakage is measured. The agent cannot create, delete or regroup cases. This is product plumbing capped at about 4 person-days. Linked cases (same FIR or co-accused) are a stretch goal.
9. **Plain-text input.** A case can start from a typed description or question. If critical fields are missing, the agent asks at most 3 clarifying questions. Questions that only need the statute store or date tool, such as "what does s.479 say?", are answered directly with citations and no brief.
10. **Interface.** A minimal Streamlit UI streams progress (a 70B-class model takes minutes per case, so this is interactive, not instant) and shows two views:
   - a dossier view with click-through to source spans;
   - a brief view with a citation table, the critic's objections, and a list of open issues.

**Two design ideas that carry the research**

1. **Verifier failure policies (RQ2).** When the verifier rejects a claim or authority, the reviser follows one of four policies: *delete* (the standard), *repair* (re-retrieve support or rewrite to what the record supports), *escalate* (keep it, mark "needs counsel"), or *repair, then escalate, plus a critic pass asking which favourable factor is missing*. An **omission** is a factor that counsel argued and the court accepted that is missing from the final brief. A **silent drop** is a factor present before verification and absent after it, without being listed in the open issues.
2. **Recodification bridge (RQ3).** Retrieval expands each query to the whole section family (BNS 318(4) ↔ IPC 420), so IPC-era precedents are found for BNS-era cases. Each retrieved authority gets a transfer status: `SAME_TEXT` (the precedent transfers), `CHANGED` (split, merged or reworded, so it is flagged "interprets the old wording", shown with a diff, and used only with a qualification), or `NEW` (no IPC equivalent). The bridge reuses the statute store's concordance links and the bail store's section families.

---

## 8. Expected novelty

1. **The verification tax.** Verification loops are usually judged on the hallucinations they remove. We measure what they cost in valid grounds silently dropped, which matters more in defense work, and show a repair-then-escalate policy that keeps the safety gain without the silence. Our factor-level gold labels make omission directly measurable, which is what makes this study possible.
2. **A recodification bridge.** Since July 2024, FIRs cite BNS sections while almost all bail case law discusses the IPC. We carry IPC-era precedent across to BNS-era cases and flag provisions that changed, so an old precedent isn't used unqualified. Existing work maps or retrieves statute sections, not case law (subject to a full related-work check).
3. **A counsel-grounded, leakage-free benchmark.** Bail orders restate counsel's submissions, so a naive setup leaks the answer into the input. We strip them and score against factor-level labels of what was argued and what was accepted. An optional counterfactual-record test checks that the arguments really follow the record.

The critic-vs-verifier comparison is a secondary ablation that replicates Kim (2026) in a new domain, and the open-model, reproducible setup is a strength, not a novelty claim.

---

## 9. Data and evaluation environment

**Sources** (all free and open)

| Source | Use |
|---|---|
| **Open India Law** (12.8M SC/HC judgments; 1.1M statute sections; CC BY 4.0) | Main corpus; statute index (BNS, BNSS, IPC, CrPC) |
| **Indian High Court Judgments** (AWS Open Data; 17.8M PDFs + metadata keyed by CNR; CC BY 4.0) | 2025–26 bail orders (we convert the PDFs to text); earlier orders in each case, linked by CNR |
| **IPC2BNS-Verify** concordance + **NCRB/BPRD** official comparison tables | Statute resolver and its test set |
| **IndianBailJudgments-1200**, **IBPS** | Design of the dossier schema |
| **IL-TUR** rhetorical-role and NER models, **InLegalNER**, **LeCNet**, **InIRAC** | Segmentation, entity candidates, extra citation and good-law signals |
| **IL-PCR**, **AILA 2019/20** | Checking our retriever against published baselines |

### Data sourcing, matching and sizes

Sizes marked "est." are planning assumptions that we will measure in week 0. The rest come from the dataset cards.

| Step | Data | How it is sourced | Size |
|---|---|---|---|
| **Corpus** (feeds the stores, fine-tuning and silver labels) | Open India Law judgments (text) + AWS High Court judgments (PDFs we convert) | Filter to one High Court and the Supreme Court. Select bail orders by case type and keywords. Remove duplicates across the two sources by CNR or case number + date. | Sources: 12.8M + 17.8M judgments. **Our subset: est. 20–60K documents.** Need ≥300 reasoned 2025–26 bail orders. |
| **Intake and PII** | The user's PDF; InLegalNER + Presidio patterns | Text layer or OCR. Off-the-shelf detectors, tested on 40 documents with planted PII. | No training data |
| **Segmentation** | OpenNyAI rhetorical-role model | Off the shelf; accuracy checked on 20 hand-labelled bail orders | 20 orders |
| **Fine-tuning data** | (case file, dossier) pairs | The 70B model labels ~5K candidate orders. We keep only those where the span verifier confirms every field. All E1 cases are excluded by CNR. Inputs are built exactly as at test time. | Candidates est. ~5K; **kept est. 2–3K**; ~20M training tokens per epoch (est.) |
| **Statute Store (S1)** | BNS, IPC, BNSS, CrPC text, concordance, punishment and bailable flags | Text from Open India Law. Mapping from IPC2BNS-Verify, checked against the NCRB/BPRD tables. Flags parsed from the First Schedule and hand-verified for the sections that appear in E1. | IPC 511 + BNS 358 sections, BNSS/CrPC bail provisions ~160, ~10 special-act bars: **≈1,000 rows**. 1,140 benchmark queries. |
| **Bail Records Store (S2)** | Verified rows from past orders | The same 70B pass also extracts which of the 12 factors were argued, raised and accepted. Rows that fail verification are dropped. | **est. 2–3K rows**; precision checked on 50 hand-labelled rows |
| **Precedent index (S3)** | Chunks of HC and SC judgments | Chunked by rhetorical role (≤400 tokens), embedded with BGE-M3, plus BM25 | **est. 0.3–1M chunks** |
| **Factor planner** | 12-factor checklist and a factor→provision map | Hand-built from IndianBailJudgments-1200 / IBPS attributes and the Supreme Court bail guidelines; reviewed by the legal collaborator | 12 factors |
| **Retriever sanity check** | IL-PCR, AILA 2019/20 | Run our retriever on their queries and compare with published numbers | 7,070 cases; 3,257 documents |

**How a case is matched to structured context**

1. **Clauses → statutes.**
   - Section mentions are found with InLegalNER and a regex, and lists such as "420, 406, 120B IPC" are split into (code, section) pairs.
   - `map_section` converts each pair to the canonical section for the offence date, or returns `AMBIGUOUS`.
   - The pair is then joined to S1, which gives the section text, maximum punishment, bailable or not, and the IPC/BNS equivalent.
   - Rules derive the gravity flag, the statutory-bar flag and BNSS 479 eligibility.
2. **Case → precedents.**
   - For each bail factor, D2 builds a structured query: offence family, factor, court, date cutoff, outcome. The offence family includes both the IPC and BNS equivalents, so a BNS 318(4) case also finds earlier IPC s.420 orders.
   - `query_bail_store` filters S2 and returns up to ~50 candidate orders.
   - Vector search and reranking over those orders' ratio chunks, plus Supreme Court chunks, return the top 10.
   - D5 then verifies every authority the draft cites.
3. **Earlier orders → one case file.** Orders are grouped by CNR and sorted by date.

**Evaluation sets**, all with known ground truth:

| Set | Size | What it tests |
|---|---|---|
| **E1: Bail cases** (main) | 120 (30 dev / 90 test), stratified by outcome and offence type | End-to-end brief quality; the RQ |
| **E2: Citation errors** | ~100 real errors taken from baseline outputs + ~150 planted errors | Verifier detection |
| **E3: Statutes and stores** | 1,140 concordance queries + 100 hand-built cases that depend on dates + 50 hand-labelled S2 rows | Statute tool accuracy; S2 extraction precision |
| **E4: Gold dossiers** | 40 (drawn from E1) | Extraction; fine-tuning |
| **E5: Safety and privacy** | 40 scripted scenarios + 40 documents with planted PII + 10 case-management scenarios | Unsafe actions, prompt injection, tool errors, pseudonymisation recall, cross-case leakage |
| **E6: User study** (optional) | 4 cases × 6–8 participants | Usefulness; over-reliance |
| **E8: Counterfactual records** (optional) | 30 dossiers × 3 edits | Change one fact (charge sheet not filed, co-accused bail refused, custody of 30 vs 400 days) and check that exactly the expected factors change |
| **E7: Text-input variant** | 20 E1 test cases rewritten as 100–200-word free-text descriptions (written from the stripped input only) | Factor recall vs the PDF-derived input; field completeness; clarifying questions |

**How E1 is built**

- *Input:* the facts section of the current order, plus the earlier orders in the same case.
- *Removed from input:* both sides' arguments and the court's reasoning. An overlap check confirms nothing leaks through.
- *Gold labels:* for each of 12 bail factors (e.g. custody period, parity with co-accused, charge sheet filed, antecedents, statutory bar), annotators mark whether it was argued by the defense, raised by the prosecution, or accepted by the court.
  - Two annotators label 30 cases so we can report Cohen's κ.
  - A legal collaborator reviews the guidelines and resolves disagreements.
  - Estimated effort is about 40 person-hours.

**Leakage and contamination controls**

- Retrieval is limited to documents dated before each case's order date.
- The case's own order, and every document that cites it, are excluded.
- Test orders date from 2025–26, after model training cutoffs where possible.

---

## 10. Baselines

All baselines use the same open model, corpus, cutoff and token budget.

| ID | Baseline | Controls for |
|---|---|---|
| B0 | Single LLM, zero-shot, given the raw case file | Lower bound, no scaffolding around the model |
| B1 | Single-pass RAG, NyayaRAG-style (facts + top-k precedents + statutes) | Standard RAG |
| B2 | Single ReAct agent with the same tools | Tool access |
| B3 | B2 + Self-Refine at the full system's token budget | Extra compute and self-critique (**key comparison**) |

**Ablations**
- A1: no dossier (the drafter reads the raw case file)
- A2: no verifier
- A3: no critic
- A4: no tools (the LLM does statute mapping and date arithmetic itself)
- A5: no RAG
- A6: extractor variants (fine-tuned 8B / base 8B / 70B)
- A7: no bail records store (vector search only)
- A8: verifier policy V1 delete / V2 repair / V3 escalate / V4 repair → escalate + missing-factor check (RQ2)
- A9: no concordance expansion or transfer status (RQ3)

---

## 11. Metrics

| Area | Metrics |
|---|---|
| **Argument quality** (RQ a) | **Factor recall and precision** against the factors defense counsel argued; recall of court-accepted factors (granted cases); critic's recall of prosecution and court-adverse factors (rejected cases); omission rate of favourable dossier facts |
| **Faithfulness** (RQ b) | **Unsupported-fact rate**: atomic claims checked against the dossier with NLI, plus a 20% human audit; misgrounded-authority rate; bad-law rate; fabricated-citation rate for B0/B1 (checked by hand) |
| **RAG** | Recall@10 of court-cited precedents, on the subset we can resolve, with coverage reported; share of cited paragraphs that are ratio; S2 row precision; gain from S2 (A7) |
| **Fine-tuning** | Field F1 and span-support precision on E4; latency and GPU memory |
| **Tool calling** | Tool-call accuracy (BFCL-style: right tool, schema-valid arguments); recovery rate on injected tool failures; statute temporal-correctness on E3 |
| **Agentic** | Task completion (brief passes all hard checks); pass^3 reliability (τ-bench); progress rate over sub-goals (AgentBoard) |
| **Safety** | **Unsafe / unapproved action rate** on E5, following ToolSandbox "minefields"; prompt-injection success rate; abstention precision |
| **Privacy** | **PII leak rate** into logs and exports; pseudonymisation recall on planted PII; **cross-case leakage rate**; extraction F1 before vs after pseudonymisation |
| **Text input** | Factor recall on E7 vs the PDF-derived input; field completeness; clarifying questions per case |
| **Overall quality** | Blind **lawyer rubric** (1–5: legal soundness, use of record facts, citation discipline, format) on 30 test cases; an LLM judge on all cases, **validated against the lawyer ratings with Cohen's κ**. Dimensions with κ < 0.6 are reported from human ratings only. |
| **Verifier** | Detection precision, recall and F1 on E2, with real and planted errors reported separately |
| **Verification tax** (RQ2) | **Hallucination rate vs omission rate** for each verifier policy (a trade-off curve); silent-drop rate; factor recall before and after verification |
| **Recodification bridge** (RQ3) | Recall@10 of court-cited precedents on the BNS-era subset, with vs without concordance expansion; **wrong-transfer rate** on 30 hand-labelled transferred precedents; share of authorities by transfer status |
| **Counterfactual** (E8, optional) | Sensitivity (expected factor changes detected) and specificity (no unexpected changes) |

**Statistics**
- Paired bootstrap 95% confidence intervals.
- Wilcoxon signed-rank test for per-case scores and McNemar's test for binary outcomes, with Holm correction.
- 3 runs per configuration.
- The minimum detectable effect is reported.

**Qualitative analysis.** We will tag errors on 30 test cases:
- using the LexAgentHallu taxonomy;
- plus four types of our own: temporal-statute, provenance, omission and tool-argument errors.

We will also present 4–5 case studies, covering successes, failures and ambiguous statutes.

---

## 12. Safety and ethics plan

- **Human in the loop.** Both export and every mock action need explicit approval from counsel. This is enforced in code, not only in prompts.
- **Clear framing.** The system supports preparation only:
  - it makes no outcome predictions and gives no advice to laypeople;
  - every output is labelled as an AI draft.
- **Privacy.** All inference runs locally. Uploaded files and typed descriptions are pseudonymised before any model sees them. The mapping is encrypted per case, and logs store only pseudonymised text. Victim and minor identities are always suppressed in sexual-offence matters. We use only public court orders, and any evaluation data we release is anonymised. The live upload feature is demonstrated on public or synthetic files only, since real client files would need separate ethics and data-handling approval.
- **Robustness to documents.** Document text is treated as data, never as instructions. Prompt injection is tested in E5.
- **Bias audit.** We will report quality differences across offence types, bail outcome and custody-length bands.
- **Ethics clearance.** We will file the institute application in week 0 for the annotators and the optional user study.

---

## 13. Compute plan

**API budget: none.** No paid APIs or services. Everything runs on our own GPUs.

| Item | Workload | Estimated GPU-hours (A100-80GB equivalent) |
|---|---|---|
| QLoRA fine-tuning of the 8B extractor | 2–3 runs | 20–35 |
| Silver dossier labels and S2 rows (70B-class, vLLM, one pass per order) | ~5K candidate orders × ~9K tokens ≈ 45M tokens in | 10–20 |
| Main experiments | 90 cases × 5 systems × 3 runs + 60 cases × ~11 ablations and policy variants × 3 runs, ~40K tokens each ≈ 130M tokens | 50–95 |
| LLM judge + NLI checks | ~10M tokens | 5–10 |
| Embedding and indexing (S3 + S1; 1 HC + SC subset) | est. 0.3–1M chunks | 3–5 |
| **Total** | | **~90–165 GPU-hours** (+30% buffer for reruns) |

Estimates will be confirmed in week 1 by measuring vLLM throughput on our hardware. If the 70B-class model is too slow for the full grid, we will:
- run the ablations on a 60-case subset;
- use a smaller critic and verifier;
- serve quantised models.

---

## 14. Timeline (8 weeks)

| Week | Milestones |
|---|---|
| 0 | TA approval. **Feasibility checks:** number of bail orders with real reasoning; availability of earlier orders by CNR; rhetorical-role accuracy on bail orders; citation-resolution rate; number of BNS-era orders that cite precedents (needed for RQ3). Ethics filing; legal collaborator confirmed. |
| 1 | Corpus subset and PDF-to-text conversion; case-file assembly; vLLM running; annotation guidelines and pilot κ; intake and pseudonymisation; statute store (S1); statute and date tools |
| 2 | Records Agent end-to-end; start the silver pass that feeds S2 and fine-tuning; E1 dev set annotated; baselines B0 and B1. **Pilot → pre-register thresholds.** |
| 3 | Planner, retrieval (S3, bail-store query) and drafter; S2 verified and hand-checked on 50 rows; E1 test set annotated; E4 gold dossiers; baseline B2 |
| 4 | Critic, verifier and revise loop; baseline B3; silver labels; E2 and E5 built; UI with both human gates and the case dashboard (~4 person-days) |
| 5 | Fine-tuning runs; **system frozen** |
| 6 | All baselines and ablations on the test set |
| 7 | Lawyer rubric, judge validation, user study (if approved), failure analysis |
| 8 | Paper-style write-up, demo, code and data release |

---

## 15. Risks and fallback plans

| Risk | Fallback |
|---|---|
| Too few 2025–26 bail orders with substantive reasoning (target ≥300 candidates) | Add a second High Court, or widen to 2024–26 and report results before and after the model cutoff separately |
| Earlier orders often not linked by CNR | Case file = facts of the current order only; stated as a limitation |
| Rhetorical-role model performs poorly on bail orders | Segmentation by LLM, checked on the dev set |
| Low annotator agreement on factor labels | Merge factors that annotators confuse; collaborator resolves disagreements; κ reported per factor |
| Low citation-resolution coverage (commercial law-report mappings are not open) | Already contained: the system cites only retrieved documents. Report coverage; compute recall only on the subset we can resolve. |
| Too few BNS-era orders citing precedents for RQ3 | Add a second High Court, or report RQ3 as a pilot on the cases available, plus E3 |
| Dashboard work eats research time | Hard cap of ~4 person-days; if late, groups become simple tags and linked cases are dropped |
| Free-text descriptions are too vague | Clarifying questions (max 3); unresolved fields marked `UNSUPPORTED`; E7 quantifies the drop |
| Silver pass yields fewer than ~2K verified rows | Relax to "all critical fields verified" or process more orders; report the fine-tuning learning curve |
| Bail-store rows contain wrong factor tags | Keep only verified rows; report precision on 50 hand-checked rows; ablation A7 shows whether the store helps |
| Pseudonymisation misses names or hurts extraction | Add regex and LLM passes; report recall and before/after F1; flag low-confidence files for manual review |
| Fine-tuned extractor doesn't match the 70B model | Report it as a negative result; use the 70B extractor in the prototype |
| Critic shows no effect | This is the H2 outcome, not a failure |
| No legal collaborator or ethics approval in time | Drop the user study; recruit final-year law students as annotators and raters; stated as a limitation |

---

## 16. Deliverables

1. A working prototype: both agents, both human gates, plain-text and PDF input, and a Streamlit UI with a case dashboard and groups.
2. Evaluation sets E1–E5 (anonymised) with annotation guidelines.
3. Code, configs and full agent traces for every experiment.
4. A workshop-style paper covering problem, related work, method, experiments, ablations, failure analysis and limitations.
5. A demo video.

**Out of scope (future work):** judge simulation, a trained precedent-treatment classifier, GraphRAG, a separate query classifier, real client files, user accounts and sharing, hearing reminders, eCourts scraping, FIR OCR, district courts, Hindi, and anticipatory bail.

---

## Key references

- Dahl et al. *Large Legal Fictions.* J. Legal Analysis, 2024. arXiv:2401.01301
- Magesh et al. *Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools.* JELS, 2025. arXiv:2405.20362
- Kim. *Does the Competitive Component of Adversarial Self-Play Improve Legal Reasoning?* arXiv:2608.01559, 2026
- Nigam et al. *NyayaRAG.* IJCNLP-AACL, 2025
- Devadiga et al. *SAMVAD.* arXiv:2509.03793, 2025
- Chen et al. *AgentCourt.* Findings of ACL, 2025. arXiv:2408.08089
- Jeong & Lee. *OBJECTION! Lawyer Agents Mitigate Guilty Bias in LJP.* EMNLP, 2026. arXiv:2609.02158
- Hou et al. *CLERC.* Findings of NAACL, 2025. arXiv:2406.17186
- Joshi et al. *IL-TUR.* ACL, 2024
- Yao et al. *ReAct.* ICLR, 2023. arXiv:2210.03629
- Madaan et al. *Self-Refine.* NeurIPS, 2023. arXiv:2303.17651
- Lu et al. *ToolSandbox.* Findings of NAACL, 2025. arXiv:2408.04682
- Patil et al. *Berkeley Function Calling Leaderboard (BFCL).* ICML, 2025
- Zhou et al. *LexAgentHallu.* EMNLP, 2026. arXiv:2609.09754
- Thakur et al. *Judging the Judges.* 2024. arXiv:2406.12624

The full dataset and paper catalogue is in `datasets_sources.md`.
