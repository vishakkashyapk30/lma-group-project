# Court-Records Agent → Defense-Preparation Agent: Research Landscape & Pipeline Ideas

Compiled 2026-10-01 from web searches. Links were checked unless marked **[U]** (unverified). Mentions of BNSS section numbers should be checked against the bare act.

> **Note:** this is the research landscape. The system design and scope in §1 and §3 were an early draft. They are **superseded by `plan.md` (v2)**, which cuts the judge simulator, the treatment classifier, the full citation graph and several RQs.

---

## 0. Findings that should shape the project

1. **Nobody builds verified dossiers from raw Indian criminal records.** Every Indian legal-NLP paper starts from clean judgment text: TathyaNyaya, NyayaRAG, PredEx, LexChronos. No paper extracts from FIRs, order sheets, or the charge-sheet facts recited in a judgment, with a source span behind every fact.
2. **Defense and bail argument generation is scored on the verdict, not on grounding.** OBJECTION (EMNLP 2026), SAMVAD, AgentsCourt and CaseGen all measure the outcome. None checks whether the argument's facts and citations are actually supported.
3. **There is no IPC→BNS paper in NLP venues.** Almost every Indian dataset is labelled with IPC sections, and nobody has addressed which code applies to an offence based on its date. There is a machine-readable concordance (IPC2BNS-Verify) and an official NCRB/BPRD table.
4. **India has no citation verifier and no labels for precedent treatment** (overruled, distinguished, per incuriam). The US has CLERC, CourtListener and LegalCiteBench. India has only LeCNet (an untyped citation graph) and InIRAC (a few typed edges).
5. **Adversarial self-play may help only because it verifies.** Kim (2026) reports a controlled negative result: the gain comes from the verification environment, not from the competition. That turns "does the prosecutor critic help?" into a clean research question.
6. **LLM judges can be swayed by style** (Suttle & Lillis, ICAIL 2026), and LLM judgment prediction carries a **guilty bias** (OBJECTION: 82.9% false-guilty). Any judge-simulator component needs robustness tests. It should not be used as the ground truth.
7. **Hallucination rates depend on how complete the citation database is** (Ovcharov 2026: 15–21% vs 0.1–1.1%). Any verifier result must report database coverage alongside it.
8. **Practical constraints:**
   - No public FIR text corpus exists; the ICDAR FIR dataset is scanned images.
   - Charge sheets are not public.
   - eCourts has no official API. The options are the free openjustice-in scraper, or paid third-party APIs, which we exclude.
   - **No paid APIs.** The Indian Kanoon API is paid per request, so it is excluded. So are all paid LLM APIs.
   - Open India Law has **no citation graph**, and the AWS HC dump is **PDF only**. We therefore build our own Indian citation extractor and citation graph from the corpus text, merged with LeCNet. All models are self-hosted open-weight models.
   - eyecite and CourtListener only handle US citations, so you need your own Indian citation parser.

---

## 1. The end-to-end system

```
 INPUTS: judgment / bail order text, order sheets (eCourts scrape), FIR scan (optional), client notes
   │
   ▼
┌──────────────────────── COURT-RECORDS AGENT ────────────────────────┐
│ 1. Ingest & segment   OCR (FIR) · rhetorical-role segmenter          │
│ 2. Extract            parties, sections, dates, custody, prior cases │
│                       (InLegalNER + LLM/QLoRA extractor)             │
│ 3. Statute resolver   IPC↔BNS / CrPC↔BNSS by OFFENCE DATE  [tool]    │
│ 4. Timeline builder   events → normalised dates → custody-days calc │
│ 5. Span verifier      each field ↔ source span (NLI); unsupported → │
│                       flagged, never silently kept                   │
│ OUTPUT: Dossier JSON  {field, value, source_span, confidence}        │
└──────────────────────────────────┬───────────────────────────────────┘
                                   ▼
┌────────────────────── DEFENSE-PREPARATION AGENT ─────────────────────┐
│ 6. Issue planner      bail-factor / issue tree (gravity, custody,    │
│                       antecedents, parity, flight risk, 479/436A…)   │
│ 7. Retriever          statutes (closed-set, AALawyer-style) +        │
│                       precedents (local HC/SC corpus), with a        │
│                       DATE CUTOFF = order date                        │
│ 8. Drafter            grounds, each tied to dossier facts + citations │
│ 9. Prosecutor critic  attacks grounds, finds missing counter-facts   │
│ 10. Citation verifier exists? · says what's claimed? · ratio vs      │
│                       obiter? · still good law (citedby treatment)?  │
│ 11. Revise loop       bounded rounds; stop when verifier passes       │
│ 12. (Optional) Judge simulator: stress test only, not ground truth    │
│ 13. HUMAN GATE        lawyer approves before anything leaves the     │
│                       system; no filing tools exist at all            │
└──────────────────────────────────────────────────────────────────────┘
```

**Tools (all sandboxed or mocked):**

| Tool | Purpose |
|---|---|
| `search_precedents(query, court, fromdate, todate)` | Search the local corpus |
| `get_doc(id)` | Fetch one document |
| `resolve_citation(citation)` | Map a citation string to a document in the corpus |
| `citedby(id, before)` | Documents that cite a given document, from our citation graph |
| `statute_lookup(code, section)` | Look up statute text |
| `map_section(code, section, offence_date)` | IPC↔BNS / CrPC↔BNSS mapping by offence date |
| `case_status(cnr)` | Mock eCourts case status |
| `date_calc(start, end)` | Date arithmetic |
| `span_check(claim, doc_id)` | Check a claim against a source span |
| `request_human_approval(artifact)` | Approval gate |

"Unsafe actions" are defined as minefields, following ToolSandbox:

- emitting an unverified citation as final
- inventing a CNR or section argument
- leaking victim PII, which matters especially in 376/POCSO-type cases
- presenting an outcome prediction as advice
- bypassing the approval gate

### What makes it watertight: failure modes and their guards

| Failure mode | Guard in the system | How it's measured |
|---|---|---|
| Fabricated case citation | Verifier resolves every citation via `resolve_citation`; unresolved ones are dropped or flagged | CLERC CFP (citation false-positive rate) |
| Real case cited for a proposition it doesn't support ("misgrounded", Magesh) | NLI check of the claim against the retrieved paragraph; ratio vs obiter from the rhetorical-role label | Misgrounded rate on a human-labelled sample |
| Repealed or wrong-era section (IPC vs BNS) | Date-aware `map_section`; the dossier holds offence date and FIR date | Temporal-correctness rate |
| Overruled or distinguished precedent | `citedby` (local graph) + treatment classifier over citing paragraphs | Bad-law citation rate |
| Argument uses a "fact" not in the record | Drafter may only cite dossier field IDs; verifier rejects free facts | Unsupported-fact rate (FActScore-style) |
| Defense-favourable fact omitted (costly in defense work) | Issue planner checklist; critic asked "what did we miss?" | Dossier-fact utilisation / omission rate (Zhang et al. 3-ply) |
| Wrong date arithmetic (custody days, 479/436A thresholds) | Only the `date_calc` tool does arithmetic, never the LLM | Exact-match accuracy of period calculations |
| **Evaluation leakage**: the target judgment, or cases citing it, sit in the retrieval corpus | Corpus cutoff at the order date; exclude the target doc and its `citedby` set | Leakage audit |
| **Memorisation**: the LLM has seen the judgment during training | Test set drawn from orders after the model's cutoff (2025–26 BNSS-era HC bail orders) | Compare pre-cutoff vs post-cutoff splits |
| Judge simulator swayed by style | Position-swap and style-only rewrite tests; never used as the primary metric | Persuadability metrics (Suttle & Lillis) |
| LLM-judge scores unreliable | ~50–80 items rated by 2 humans; report Cohen's κ, not % agreement | κ / Krippendorff α |
| Verifier looks good only because the DB is complete | Report DB coverage; vary it in an ablation | Ovcharov-style coverage curve |
| Fairness / bias | Report outcome-simulation disparity across offence types and custody length; framed as preparation support | Disparity table + limitations section |

---

## 2. Research ideas that fit this pipeline

Each idea can be the main research question with the others as supporting infrastructure. They are kept short on purpose, for ideation.

### Idea A: Verified dossiers from raw criminal records
- **RQ:** Does extract-then-verify with span grounding and tool-based date arithmetic beat single-pass long-context extraction on field accuracy, timeline accuracy and unsupported-fact rate? Can a QLoRA 7–8B extractor match a prompted 70B-class open model?
- **Gap:** LexChronos is limited to Supreme Court judgments, uses synthetic gold data and has no verification. TathyaNyaya explicitly excludes fact extraction from raw records.
- **Data:**
  - InLegalNER (14 entity types)
  - InIRAC (event chains)
  - DDL judicial data (81M district case records with dates, sections and disposition), which serves as gold metadata
  - ICDAR-2023 FIR scans (statute and field boxes)
  - eCourts order sheets via openjustice-in
- **Metrics:** field-level F1; (event, date) tuple F1; Kendall τ on ordering; custody-period exact match; unsupported-fact rate; tool-call accuracy.
- **Risk:** Order-sheet scraping may be brittle. Fallback: judgments plus DDL metadata only.

### Idea B: Temporal statute grounding (IPC→BNS, CrPC→BNSS)
- **RQ:** Does a date-aware section-mapping tool plus closed-set statute RAG reduce temporally wrong or non-existent citations, compared with plain RAG and with a prompted large open model?
- **Gap:** No NLP paper exists on this; the only related work is a law-review article (Mohanty & Stephen, *Statute Law Review* 2025).
- **Data:**
  - IPC2BNS-Verify (a CSV covering 1:1, split, merged and repealed sections, plus a 1,140-query benchmark; check it against NCRB)
  - NCRB SANKALAN / BPRD official tables
  - PROSLEX (1,623 expert-labelled docs, 7 IPC sections)
  - ILSI / LeSICiN fact patterns, relabelled with offence dates
- **Metrics:** section F1; temporal-correctness rate; repealed-section citation rate; abstention precision on the hard cases (split or merged sections).
- **Note:** This is the cheapest and most clearly novel idea. It works as a component inside any of the others.

### Idea C: Dossier-grounded bail argument generation
- **RQ:** Given only the facts-and-arguments portion of a real bail order, does a dossier-grounded, verifier-gated pipeline produce grounds that cover more of the court's actual reasoning, with fewer unsupported claims, than single-pass RAG at equal token budget?
- **Gap:**
  - OBJECTION, SAMVAD and CaseGen score only the outcome or text overlap.
  - Tuvey & Sen (2023) report 63% overlap with no grounding, which makes a good weak baseline.
  - LEGIT-style issue trees have not been built for Indian bail.
- **Data:**
  - Post-July-2024 High Court bail orders (Open India Law; AWS Indian HC Judgments, 17.8M PDFs, CC BY 4.0, converted to text ourselves)
  - IndianBailJudgments-1200 (attribute schema; GPT-4o labels with only 12.5% expert-checked, so treat them as silver)
  - HLDC bail subset (176K, Hindi)
  - IBPS (150K bail judgments; data release **[U]**)
  - The IL-TUR rhetorical-role model, used to split *facts/arguments* from *reasoning/ratio*
- **Gold:** Split each order with the rhetorical-role model. The input is facts and arguments. The target is the court's grounds, turned into an issue tree by 2 annotators, with κ reported.
- **Metrics:**
  - ground-coverage recall against the court's grounds (Key-Point-Analysis style)
  - precedent recall@k against the precedents the court actually cited
  - CLERC CR/CP/CFP
  - unsupported-fact rate
  - omission rate
  - rubric scores (the three failure axes from "Are LLMs Court-Ready?"), with an LLM judge validated by κ
- **Baselines:** single LLM; LLM + RAG (NyayaRAG-style); SAMVAD-style multi-agent debate.

### Idea D: Critic as opponent vs critic as verifier
- **RQ:** In a defense-drafting loop, does the gain from a "prosecutor" agent come from adversarial content (counterarguments) or from verification (fact and citation checking)?
- **Design:** Four arms at equal token budget:
  - no critic
  - verifier-only critic
  - opponent-only critic (instructed not to check citations)
  - both
- **Gap:** Kim (2026) found a negative result for competition in self-play. AgentCourt and ASP2LJ claim gains from adversarial loops without this separation. A clean, cheap ablation, and publishable as workshop-level work.
- **Data and metrics:** Same as Idea C. Adds per-round trajectory analysis: which critique types lead to which fixes. That analysis covers the "analyse intermediate steps" requirement.

### Idea E: Indian citation verification and precedent treatment ("Shepardizing")
- **RQ:** Can an agent using `citedby` retrieval plus a small fine-tuned treatment classifier detect planted bad citations (fabricated, misattributed, overruled, repealed-statute) in defense drafts better than an LLM self-check?
- **Gap:**
  - No Indian equivalent of CLERC, "Who Checks the Citations?" or the overruling-pairs work.
  - LeCNet has no treatment labels.
  - Detection F1 in the US is only about 55% at about 15 agent steps per excerpt.
- **Data:**
  - LeCNet (26K-node Indian citation graph)
  - InIRAC typed edges (DISTINGUISHES, CONFLICTS_WITH)
  - our own citation graph, built from corpus text with an Indian citation extractor (replaces the paid Indian Kanoon `citedby`)
  - IL-PCR
  - A self-built planted-error set: 300–500 drafts with injected errors, so ground truth is known
- **Metrics:** detection precision, recall and F1 per error type; steps and cost per check; results as a function of DB coverage (reporting coverage is required).

### Idea F: Robustness of the judge simulator
- **RQ:** How much do LLM bail-judge simulators move on style-only rewrites, argument order, or offence-type cues? Does a structured factor-checklist judge reduce that?
- **Gap:** Suttle & Lillis give persuadability metrics, and OBJECTION shows guilty bias. Neither has been tested on Indian bail.
- **Why it's secondary:** It is mostly an evaluation and safety contribution. It could be a strong analysis section rather than the main RQ.

### Idea G: Small fine-tuned model vs large prompted model on narrow parts of the pipeline
- **RQ:** Does a QLoRA 7–8B model match a much larger prompted open model on specific sub-tasks, such as dossier field extraction, statute mapping or treatment classification, at a fraction of the cost?
- **Precedent:**
  - Aalap: Mistral-7B, LoRA, 22K instructions, 4×A100 for 86 h
  - FactLegalLlama: Llama-3-8B, QLoRA, 1×A100 for about 38 h
  - A narrower task needs far less compute.
- **Use:** This is best as the fine-tuning component of Idea A or E, not as a standalone project.

---

## 3. Recommended combination (for the proposal)

**Title sketch:** *Verified Bail Preparation for BNSS-era Criminal Cases: Dossier-Grounded Defense Drafting with Separated Adversarial and Verification Critique*

- **Main RQ (C + D):** Does a dossier-grounded, verifier-gated defense pipeline cover more of the court's actual grounds with fewer unsupported claims than single-pass RAG? Is the gain from adversarial critique or from verification?
- **Supporting modules, evaluated on their own but more lightly:**
  - A (dossier extraction quality)
  - B (temporal statute resolver)
  - E-lite (a citation verifier tested on a planted-error set)
- **Analysis section:** F (judge-simulator robustness).

| Capability | Why the problem needs it | Metric | Ablation |
|---|---|---|---|
| Fine-tuning | A cheap, local extractor or statute mapper handles volume and keeps sensitive records on local hardware (privacy) | Field F1 vs 70B-class model; GPU memory and latency per case | QLoRA 8B vs prompted 70B-class vs base 8B |
| RAG | Grounds must cite real statutes and precedents | Precedent recall@k, CLERC CR/CP/CFP | No-RAG; dense-only vs role-aware chunking |
| Reasoning | Issue planning, and applying bail factors to facts | Ground-coverage recall; LEGIT-style issue coverage; per-round critique analysis | No planner; no revise loop |
| Agentic | Multi-stage records → defense workflow with a bounded critique loop and a human gate | Task completion; progress rate (AgentBoard) | Single agent vs pipeline, same token budget |
| Tool calling | Date-aware statute mapping, citation resolution, date arithmetic | BFCL-style AST accuracy; error recovery; minefield (unsafe-action) rate | Tools removed (LLM does mapping and arithmetic itself) |

**Evaluation sets, all with known ground truth:**
1. 150–200 post-cutoff HC bail orders split into input and gold grounds, with 2 annotators on the gold (Ideas C and D).
2. 300–500 planted-error drafts (Idea E-lite).
3. IPC2BNS-Verify, plus about 200 hand-checked date-sensitive cases (Idea B).
4. 50–100 dossiers with hand-checked fields and timelines (Idea A).
5. About 50 scripted "minefield" scenarios, such as a PII request, a missing CNR, a user asking the system to file, or a missing tool (safety).

**Compute (rough):**
- **Fine-tuning:** 1 QLoRA run on 7–8B for a narrow extraction task. About 5–15 GPU-hours on an A100/L4 (Colab or Kaggle); a few runs for ablations.
- **LLM inference:** about 30–60K tokens per case × 200 cases × about 6 configs ≈ 40–70M tokens. All of it runs on self-hosted open models via vLLM, with no paid APIs. A smaller model for the critic and verifier roles cuts GPU time.
- **Retrieval and citations:** a local corpus and our own citation graph, with no paid legal APIs.

**Main risks and fallbacks:**
- **Gold grounds too noisy.** Use a narrower slice: one High Court, one offence family (e.g. NDPS or 420/cheating), regular bail only.
- **Scraping blocked.** Use the AWS HC dump plus DDL metadata only.
- **Critic gains null.** That is still a result (it matches Kim 2026), so the paper survives.

---

## 4. Dataset catalogue

### Indian corpora and records
| Dataset | What | Size | License | Link |
|---|---|---|---|---|
| Open India Law (vaquill) | SC + HC judgments, 22k enactments split into sections | 12.8M judgments | – | github.com/vaquill-AI/open-india-law |
| Indian HC Judgments (AWS) | PDFs + metadata, 25 HCs, synced regularly | ~17.8M | CC BY 4.0 | registry.opendata.aws/indian-high-court-judgments |
| Indian SC Judgments (AWS/Kaggle) | 1950–2025 | all SC | CC BY 4.0 | registry.opendata.aws/indian-supreme-court-judgments |
| DDL Judicial Data | District-court eCourts metadata: dates, acts/sections, disposition | 81.2M cases (~10M criminal) | CC BY-NC-SA 4.0 | devdatalab.org/judicial-data |
| openjustice-in | eCourts case-status and order-sheet scraper | tool | – | github.com/openjustice-in |
| NyayaAnumana | Outcome-labelled cases incl. daily orders (COLING 2025) | 703K | – | HF: L-NLProc/NyayaAnumana-* |
| FIR_Dataset_ICDAR2023 | FIR scans with field and statute boxes | 544 images | MIT | github.com/LegalDocumentProcessing/FIR_Dataset_ICDAR2023 |

### Bail, statutes, IPC→BNS
| Dataset | What | Size | Link |
|---|---|---|---|
| HLDC (Findings ACL 2022) | Hindi district-court docs with a bail subset | ~900K docs / 176K bail | github.com/Exploration-Lab/HLDC |
| IndianBailJudgments-1200 | 20+ attributes; GPT-4o labels, 12.5% expert-checked | 1,200 | github.com/SnehaDeshmukh28/IndianBailJudgments-1200 |
| IBPS | HC bail judgments with custody, antecedents, reasoning | 150K | arXiv 2508.07592 (data **[U]**) |
| PROSLEX (ICAIL 2026) | Expert statute labels + explanation spans, 7 IPC sections | 1,623 | github.com/subinay494/Legal_Statute_Prediction_Explanation |
| ILSI / LeSICiN (AAAI 2022) | Statute identification, 100 IPC sections | ~66K **[U size]** | github.com/Law-AI/LeSICiN |
| IPC2BNS-Verify | Concordance CSV (split/merged/repealed), bare acts JSONL, 1,140-query benchmark | – | github.com/MS-406/IPC2BNS-Verify |
| NCRB SANKALAN / BPRD tables | Official IPC↔BNS, CrPC↔BNSS comparisons (PDF) | – | bprd.nic.in (comparison-summary PDFs) |

### Extraction, structure, argument
| Dataset | What | Size | Link |
|---|---|---|---|
| InLegalNER | 14 legal entity types; spaCy model F1 91 | – | HF: opennyaiorg/InLegalNER, opennyaiorg/en_legal_ner_trf |
| Rhetorical roles (Kalamkar 2022) / LegalSeg | Sentence roles incl. Arg-Petitioner / Arg-Respondent / Ratio | – | github.com/Legal-NLP-EkStep/rhetorical-role-baseline |
| InIRAC (Falkor-IRAC) | IRAC fields, procedural event chains, typed precedent edges | 511 | HF: joyboseroy/inIRAC |
| IMLJD | 498A / DV / 482-quashing judgments with outcomes + KG | 3,613 | HF: joyboseroy/imljd |
| LexChronos (AAAI-W 2026) | SC event timelines (synthetic gold) | 2,000 | arXiv 2603.01651 (data **[U]**) |
| PredEx (Findings ACL 2024) | Prediction + expert explanations | 15K+ | github.com/ShubhamKumarNigam/PredEx |
| Aalap instructions | Incl. timeline, argument and issue drafting | 22K | HF: opennyaiorg/aalap_instruction_dataset (gated) |
| IL-TUR (ACL 2024) | 8 Indian tasks incl. BAIL, LSI, PCR, RR | – | exploration-lab.github.io/IL-TUR |

### Retrieval and citations
| Dataset | What | Link |
|---|---|---|
| IL-PCR / U-CREAT (Findings ACL 2023) | Prior-case retrieval, µF1@K | github.com/Exploration-Lab/IL-PCR |
| IL-PCSR (EMNLP 2025) | Joint precedent + statute retrieval | arXiv 2511.00268 |
| AILA 2019/2020 (FIRE) | Precedent + statute retrieval from facts | zenodo.org/records/4063986 |
| LeCNet (JUST-NLP 2025) | Indian citation graph, 26K nodes / 67K edges | zenodo.org/records/17105199 |

### Transferable (non-Indian) benchmarks
| Dataset | Use for us | Link |
|---|---|---|
| CLERC (NAACL-F 2025) | Recipe for citation retrieval + analysis generation; CR/CP/CFP metrics | HF: jhu-clsp/CLERC |
| Large Legal Fictions | False-premise and hallucination probes | HF: reglab/legal_hallucinations |
| Overruling pairs (JURIX 2025) | Template for an Indian overruled-precedent test | github.com/lizhang-AIandLaw/Do-LLMs-Truly-Understand-When-a-Precedent-Is-Overruled |
| LegalBench | Rule application, issue spotting, overruling task | HF: nguha/legalbench |
| LAM:ECHR | Argument spans by actor (applicant/state/court) | github.com/trusthlt/mining-legal-arguments |
| CAIL2023-ArgMine | Prosecution–defense argument pairs from trials (Zh) | github.com/china-ai-law-challenge/CAIL2023 |
| LeCaRDv2 (SIGIR 2024) | Criminal case retrieval (Zh) | github.com/THUIR/LeCaRDv2 |
| AgentCourt (ACL-F 2025) | Adversarial lawyer agents, 550 cases | github.com/relic-yuexi/AgentCourt |
| AgentsCourt / SimuCourt (EMNLP-F 2024) | Court-debate agents, 420 judgments | github.com/Zhitao-He/AgentsCourt |
| J1-ENVS / J1-EVAL (ACL 2026) | Interactive procedural legal environments | github.com/FudanDISC/J1Bench |
| LegalAgentBench | 37 tools, 300 tasks; tool-use evaluation design | github.com/CSHaitao/LegalAgentBench |
| OBJECTION "Natural Innocent" (EMNLP 2026) | Guilty-bias test cases | arXiv 2609.02158 |
| Oyez / ConvoKit, LaCour! | Oral-argument transcripts (no Indian equivalent) | convokit.cornell.edu · HF: TrustHLT/LaCour |

---

## 5. Key papers, grouped

**Agents and courtroom simulation:**
- AgentCourt (ACL-F 2025, 2408.08089)
- AgentsCourt/SimuCourt (EMNLP-F 2024)
- J1-ENVS (ACL 2026, 2507.04037)
- LegalAgentBench (2412.17259)
- SAMVAD, an Indian courtroom simulation and **the closest prior work** (2509.03793)
- SimCourt (2508.17322)
- ASP2LJ (2506.18768)
- OBJECTION (EMNLP 2026, 2609.02158)
- Persuadability of LLM legal decision tools (ICAIL 2026, 2604.26233)
- Kim, adversarial self-play negative result (2608.01559)
- Multi-agent deliberation in law (2606.30906)
- GRACE (2609.23726)
- Survey (2601.06216)

**Argument generation and evaluation:**
- Zhang & Ashley, reflective multi-agent 3-ply arguments (2506.02992)
- 3-ply faithfulness and abstention metrics (2506.00694)
- LEGIT issue-tree rubrics (ACL 2026, 2512.01020)
- Tuvey & Sen, Indian argument generation (2310.05680)
- CaseGen, incl. defense statements (2502.17943)
- LAMUS (2603.08286)
- "Are LLMs Court-Ready?", Indian (2510.17900)
- Falkor-IRAC (2605.14665)
- Wachsmuth et al. 2017, argument quality taxonomy
- Key Point Analysis (2005.01619)

**Hallucination and citation:**
- Magesh et al., JELS 2025 (2405.20362)
- Dahl et al., J. Legal Analysis 2024 (2401.01301)
- CLERC (NAACL-F 2025)
- LegalBench-RAG (2408.10343)
- LexAgentHallu (EMNLP 2026, 2609.09754)
- AALawyer (ACL 2026)
- Who Checks the Citations? (2606.21155)
- LegalCiteBench (2605.10186)
- Overruled-precedent understanding (JURIX 2025, 2510.20941)
- Citation Grounding Measures the Oracle (2606.00898)
- LegalHalluLens, risk direction (2606.18021)

**Indian legal LLMs:**
- NyayaRAG (IJCNLP-AACL 2025)
- PredEx (ACL-F 2024)
- NyayaAnumana/INLegalLlama (COLING 2025)
- TathyaNyaya/FactLegalLlama (2504.04737)
- IL-TUR (ACL 2024)
- Aalap (2402.01758)
- IBPS (2508.07592)
- IndianBailJudgments-1200 (2507.02506)
- InLegalBERT (ICAIL 2023, 2209.06049)

**Extraction and timelines:**
- LexChronos (2603.01651)
- LexTime (EMNLP-F 2025, 2506.04041)
- LexKairos (2608.09106 **[U]**)
- InLegalNER (2211.03442)

**Evaluation methodology:**

| Area | Papers |
|---|---|
| Attribution | ALCE (2305.14627); AIS / AutoAIS |
| Factuality | FActScore (2305.14251); RAGAS (2309.15217) |
| LLM judges | G-Eval; Prometheus 2 (2405.01535); Thakur et al., judge validation, use κ (2406.12624) |
| Tool use | BFCL; τ-bench pass^k (2406.12045); ToolSandbox milestones and minefields (2408.04682); AgentBoard progress rate (2401.13178) |
| Safety | ToolEmu (2309.15817) |
| Temporal | TempEval-3 temporal awareness |

---

## 6. Verification status of items from `ideas.md`

- **Confirmed by these searches:**
  - AgentCourt: ACL Findings 2025
  - AgentsCourt/SimuCourt: EMNLP Findings 2024
  - J1-Bench is really **J1-ENVS / J1-EVAL**, ACL 2026
  - Magesh et al.: JELS 2025, not 2024
  - Dahl et al.: J. Legal Analysis 2024
  - AALawyer: ACL 2026
  - LexAgentHallu: EMNLP 2026
  - NyayaAnumana/INLegalLlama: COLING 2025
  - InLegalBERT: ICAIL 2023
  - AILA: on Zenodo
  - HLDC bail subset: 176K
  - PredEx: 15K+
  - NyayaRAG: IJCNLP-AACL 2025
  - IL-PCR/U-CREAT: Findings ACL 2023
  - IPC→BNS tables: NCRB/BPRD
  - IndianBailJudgments-1200: GPT-4o labels, only 12.5% expert-checked, so treat as silver
- **Not yet confirmed:** Harvey "LAB"; LegalSeg venue; exact ILSI size. The dedicated verification pass was stopped before it finished.
