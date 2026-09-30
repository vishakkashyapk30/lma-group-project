# Data Sources, Benchmarks & Baseline Papers

Reference list for the project in `plan.md`: a records agent and a defense-preparation agent for regular-bail preparation.

**Columns**
- **Role**: how the plan uses each item.
- **E1–E6**: the evaluation sets defined in `plan.md` §7.2.

**Markers**
- **[U]**: link, size or release status not confirmed.
- **Gated**: you need to register or accept terms before downloading.

Links were checked on 2026-10-01.

---

## 1. Core corpora (primary data)

| # | Source | What it contains | Size | License | Role in our system | Link |
|---|---|---|---|---|---|---|
| 1.1 | **Open India Law** (vaquill) | SC and HC judgments (1950–2025); 22K enactments split into about 1.1M sections; tribunal metadata; Parquet | 12.8M judgments | see repo | **Primary.** Statute index and `statute_lookup` (BNS/BNSS/BSA/IPC/CrPC/IEA); main judgment corpus | https://github.com/vaquill-AI/open-india-law · HF: https://huggingface.co/datasets/vaquill/open-india-law |
| 1.2 | **Indian High Court Judgments** (AWS Open Data, Dattam Labs) | PDFs plus JSON/Parquet metadata from 25 HCs, synced regularly | about 17.8M | CC BY 4.0 | Adds recent (2025–26) bail orders for E1 that 1.1 lacks; remove duplicates against 1.1 | https://registry.opendata.aws/indian-high-court-judgments/ · https://github.com/vanga/indian-high-court-judgments |
| 1.3 | **Indian Supreme Court Judgments** (AWS / Kaggle) | SC judgments 1950–2025 with metadata | all SC | CC BY 4.0 | Supplements the precedent index | https://registry.opendata.aws/indian-supreme-court-judgments/ · https://www.kaggle.com/datasets/vangap/indian-supreme-court-judgments |
| 1.4 | **DDL Judicial Data** (Development Data Lab) | District-court eCourts metadata: filing, hearing and decision dates, acts and sections, disposition | 81.2M cases (about 10M criminal) | CC BY-NC-SA 4.0 | Realistic timeline and section distributions; custody-calculator tests; data for the mock `case_status` tool | https://www.devdatalab.org/judicial-data |
| 1.5 | **NyayaAnumana** (COLING 2025) | SC, HC, tribunal, district and daily-order cases with outcome labels; explanation subset | 702,945 | [U] | Extra corpus; source of daily orders | https://huggingface.co/datasets/L-NLProc/NyayaAnumana-Classification-Data · https://huggingface.co/datasets/L-NLProc/NyayaAnumana-Explanation-Data |
| 1.6 | **FIR_Dataset_ICDAR2023** | Scanned FIRs, handwritten and printed, with boxes for statutes, police station and complainant | 544 images | MIT | Stretch goal: test OCR ingestion | https://github.com/LegalDocumentProcessing/FIR_Dataset_ICDAR2023 |

**Inspiration only (not a data source):** Adalat AI, https://www.adalat.ai/. It builds courtroom transcription and workflow tools for Indian courts, but has no public dataset.

---

## 2. Statutes & IPC→BNS / CrPC→BNSS mapping

| # | Source | What | Format | Role | Link |
|---|---|---|---|---|---|
| 2.1 | **NCRB SANKALAN** | Official correspondence tables and comparisons | PDF / web | **Ground truth** for the statute resolver (R3) | https://www.ncrb.gov.in/uploads/SankalanPortal/Index.html |
| 2.2 | **BPRD comparison summaries** | BNS↔IPC and BNSS↔CrPC comparisons | PDF | Ground truth for R3 | https://bprd.nic.in/uploads/pdf/COMPARISON%20SUMMARY%20BNS%20to%20IPC%20.pdf · https://bprd.nic.in/uploads/pdf/Comparison%20summary%20BNSS%20to%20CrPC.pdf |
| 2.3 | **IPC2BNS-Verify** | Concordance CSV (1:1, split, merged and repealed sections); IPC and BNS bare acts as JSONL; CrPC→BNSS; 1,140-query benchmark | CSV / JSONL, MIT | `map_section` backbone; part of **E3**. Check every row against 2.1 and 2.2 | https://github.com/MS-406/IPC2BNS-Verify |
| 2.4 | Community mappings | IPC→BNS CSV; IPC/CrPC/IEA → BNS/BNSS/BSA as JS arrays | CSV / JS | Cross-check only | https://huggingface.co/datasets/nandhakumarg/IPC_and_BNS_transformation · https://github.com/Vikram016/IPC |

---

## 3. Bail & statute-prediction datasets

| # | Dataset | What | Size | Role | Link |
|---|---|---|---|---|---|
| 3.1 | **IndianBailJudgments-1200** | Bail orders with 20+ attributes (sections, custody, antecedents, outcome). Labelled by GPT-4o, with 12.5% checked by experts | 1,200 | Template for the dossier schema; silver labels | https://github.com/SnehaDeshmukh28/IndianBailJudgments-1200 · https://arxiv.org/abs/2507.02506 |
| 3.2 | **HLDC** (Findings ACL 2022) | Hindi district-court documents with a bail-prediction subset | about 900K docs / 176K bail | Stretch goal: Hindi | https://github.com/Exploration-Lab/HLDC · https://aclanthology.org/2022.findings-acl.278/ |
| 3.3 | **IBPS** (Indian Bail Prediction System) | HC bail judgments annotated for age, health, antecedents, custody and reasoning | 150,430 | Schema reference (data release [U]) | https://arxiv.org/abs/2508.07592 |
| 3.4 | **PROSLEX** (ICAIL 2026) | Facts with expert labels for 7 IPC sections, plus explanation spans | 1,623 docs | Extra **E3** cases (fact → section → which code applies) | https://github.com/subinay494/Legal_Statute_Prediction_Explanation · https://arxiv.org/abs/2608.08830 |
| 3.5 | **ILSI / LeSICiN** (AAAI 2022) | Statute identification across 100 IPC sections | about 66K [U] | Extra **E3** fact patterns | https://github.com/Law-AI/LeSICiN |

---

## 4. Segmentation, NER, structure & timelines

| # | Dataset / model | What | Role | Link |
|---|---|---|---|---|
| 4.1 | **IL-TUR** (ACL 2024) | 8 Indian tasks: L-NER, rhetorical roles, CJPE, BAIL, LSI, PCR, summarisation, MT. CC BY-NC-SA | Rhetorical-role (RR) and NER models; sanity-check benchmarks | https://exploration-lab.github.io/IL-TUR/ · https://aclanthology.org/2024.acl-long.618/ |
| 4.2 | **InLegalNER** + `en_legal_ner_trf` | 14 legal entity types; spaCy model, F1 91.08; Apache-2.0 | R1 entity candidates | https://huggingface.co/datasets/opennyaiorg/InLegalNER · https://huggingface.co/opennyaiorg/en_legal_ner_trf |
| 4.3 | **Rhetorical roles** (Kalamkar et al., LREC 2022) / **LegalSeg** | Sentence roles incl. Arg-Petitioner / Arg-Respondent / Ratio | Split E1 orders into input and gold; chunking by role | https://github.com/Legal-NLP-EkStep/rhetorical-role-baseline |
| 4.4 | **InIRAC** (Falkor-IRAC) | IRAC fields, procedural event chains, typed precedent edges (DISTINGUISHES, CONFLICTS_WITH). CC BY 4.0 | Timeline schema; seed labels for treatment classification | https://huggingface.co/datasets/joyboseroy/inIRAC · https://github.com/joyboseroy/falkor-irac |
| 4.5 | **IMLJD** | 498A / DV Act / 482-quashing judgments with outcomes and a knowledge graph (KG). CC BY 4.0 | Extra criminal cases | https://huggingface.co/datasets/joyboseroy/imljd |
| 4.6 | **LexChronos** (AILaw @ AAAI 2026) | SC event timelines; synthetic gold labels | Baseline for timeline extraction (data [U]) | https://arxiv.org/abs/2603.01651 |
| 4.7 | **PredEx** (Findings ACL 2024) | Judgment prediction with 15K+ expert explanations | Related work; explanation-style reference | https://github.com/ShubhamKumarNigam/PredEx |
| 4.8 | **Aalap instruction set** (Gated) | 22K instructions incl. timeline, argument and issue drafting | Extra fine-tuning data (FT1) | https://huggingface.co/datasets/opennyaiorg/aalap_instruction_dataset |
| 4.9 | **CivilSum** (SIGIR 2024) / **InLSum** (JUST-NLP 2025) | Judgment → summary pairs | Optional: dossier summary | https://github.com/ra-MANUJ-an/CivilSum · https://aclanthology.org/2025.justnlp-main.2/ |

---

## 5. Retrieval & citation graphs

| # | Dataset | What | Metric | Role | Link |
|---|---|---|---|---|---|
| 5.1 | **IL-PCR / U-CREAT** (Findings ACL 2023) | Indian prior-case retrieval | µF1@K | Sanity check on the retriever (D2) against published numbers | https://github.com/Exploration-Lab/IL-PCR · https://arxiv.org/abs/2307.05260 |
| 5.2 | **IL-PCSR** (EMNLP 2025) | Joint precedent and statute retrieval | – | Retrieval benchmark | https://arxiv.org/abs/2511.00268 |
| 5.3 | **AILA 2019/2020** (FIRE) | Retrieve precedents and statutes from fact scenarios | MAP / P@k | Retrieval benchmark | https://zenodo.org/records/4063986 · https://sites.google.com/view/aila-2020/task-1-precedent-statute-retrieval |
| 5.4 | **LeCNet** (JUST-NLP 2025) | Indian citation graph, 26K nodes / 67K edges. CC BY 4.0 | – | Citation-graph features for the good-law check (D5) | https://zenodo.org/records/17105199 · https://aclanthology.org/2025.justnlp-main.4/ |

---

## 6. Transferable benchmarks (non-Indian)

### 6.1 Citation, hallucination, RAG
| Benchmark | What | What we borrow | Link |
|---|---|---|---|
| **CLERC** (NAACL-F 2025) | US citation retrieval plus analysis generation; 1.84M docs | **CR / CP / CFP** citation metrics; benchmark recipe | https://huggingface.co/datasets/jhu-clsp/CLERC · https://arxiv.org/abs/2406.17186 |
| **Large Legal Fictions** (reglab) | Verifiable questions about US cases, with hallucination labels | False-premise probes | https://huggingface.co/datasets/reglab/legal_hallucinations · https://github.com/reglab/legal_hallucinations |
| **Who Checks the Citations?** | Brief excerpts with injected citation errors | Design of the planted-error set **E2** | https://arxiv.org/abs/2606.21155 |
| **Overruling pairs** (JURIX 2025) | 236 US Supreme Court overruling pairs | Template for an Indian "good law" test | https://github.com/lizhang-AIandLaw/Do-LLMs-Truly-Understand-When-a-Precedent-Is-Overruled |
| **LegalBench-RAG** | Span-level retrieval, contracts | Character-level retrieval P/R | https://github.com/zeroentropy-ai/legalbenchrag |

### 6.2 Legal reasoning & arguments
| Benchmark | What | What we borrow | Link |
|---|---|---|---|
| **LegalBench** (NeurIPS 2023) | 162 tasks built around IRAC (issue, rule, application, conclusion), incl. rule application and overruling | Task design | https://huggingface.co/datasets/nguha/legalbench |
| **LAM:ECHR** | ECHR argument spans labelled by actor and type | Labels for argument roles | https://github.com/trusthlt/mining-legal-arguments |
| **CAIL2023-ArgMine** | Prosecution–defense argument pairs (Zh) | Design of critic–drafter pairing | https://github.com/china-ai-law-challenge/CAIL2023 |
| **LeCaRDv2** (SIGIR 2024) | Criminal case retrieval (Zh) | Relevance criteria | https://github.com/THUIR/LeCaRDv2 |
| **LexGLUE / CaseHOLD** | Legal NLU; picking the correct holding | Related work | https://huggingface.co/datasets/coastalcph/lex_glue · https://huggingface.co/datasets/casehold/casehold |
| **Oyez/ConvoKit**, **LaCour!** | Oral-argument transcripts (no Indian equivalent) | Related work | https://convokit.cornell.edu/documentation/supreme.html · https://huggingface.co/datasets/TrustHLT/LaCour |

### 6.3 Legal agent benchmarks
| Benchmark | What | What we borrow | Link |
|---|---|---|---|
| **J1-ENVS / J1-EVAL** (ACL 2026) | 6 interactive legal environments; task success plus procedural compliance | Agent evaluation design | https://github.com/FudanDISC/J1Bench |
| **LegalAgentBench** (ACL 2025) | 37 tools, 300 tasks; keyword-based progress | Tool-use evaluation design | https://github.com/CSHaitao/LegalAgentBench |
| **AgentCourt** (ACL-F 2025) | Adversarial lawyer agents, 550 cases | Adversarial-loop comparison | https://github.com/relic-yuexi/AgentCourt · https://huggingface.co/datasets/youzi517/AgentCourt |
| **AgentsCourt / SimuCourt** (EMNLP-F 2024) | Court-debate agents, 420 judgments | Multi-agent debate design | https://github.com/Zhitao-He/AgentsCourt |
| **OBJECTION "Natural Innocent"** (EMNLP 2026) | Cases for testing guilty bias | Guilty-bias probe for the judge simulator (D7) | https://arxiv.org/abs/2609.02158 |

### 6.4 Tool-calling & agent-safety benchmarks (metric definitions)
| Benchmark | Metric we adopt | Link |
|---|---|---|
| **BFCL** (Berkeley Function Calling Leaderboard) | AST accuracy of tool calls; irrelevance detection; state checks across multi-turn exchanges | https://gorilla.cs.berkeley.edu/leaderboard.html |
| **τ-bench** | pass^k reliability | https://github.com/sierra-research/tau-bench |
| **ToolSandbox** | Milestones and **minefields** (unsafe-action rate) | https://github.com/apple/ToolSandbox |
| **AgentBoard** | Progress rate over subgoals | https://github.com/hkust-nlp/AgentBoard |
| **ToolEmu** / **Agent-SafetyBench** | Risk and failure rates for unsafe actions | https://arxiv.org/abs/2309.15817 · https://huggingface.co/datasets/thu-coai/Agent-SafetyBench |

---

## 7. Tools & APIs the agents call

| Tool | Use | Notes | Link |
|---|---|---|---|
| **Indian Kanoon API** | `ik_search`, `ik_doc`, `ik_citedby` | ₹10K/month free credit for non-commercial use (after verification); supports `cites:` and `citedby:` | https://api.indiankanoon.org/documentation/ · https://api.indiankanoon.org/pricing/ |
| **openjustice-in eCourts toolkit** | Scrape order sheets and case status | No official eCourts API; check terms of service | https://github.com/openjustice-in |
| **OpenNyAI library** | NER, rhetorical roles, summaries | – | https://github.com/OpenNyAI/Opennyai |
| **InLegalBERT** (ICAIL 2023) | Embeddings / encoder | Pretrained on 5.4M Indian SC and HC documents | https://huggingface.co/law-ai/InLegalBERT |
| eyecite / CourtListener citation lookup | Design reference only | **US only.** We need to build an Indian citation parser | https://free.law/projects/eyecite/ · https://www.courtlistener.com/help/api/rest/citation-lookup/ |

---

## 8. Baseline papers (systems we compare against, `plan.md` §8.1)

| ID | Paper | Venue | What we reimplement as the baseline | Link |
|---|---|---|---|---|
| B0 | Plain frontier LLM, zero-shot | – | Lower bound with no scaffolding around the model | – |
| B1 | **NyayaRAG**: Nigam et al. | IJCNLP-AACL 2025 | Single-pass RAG (facts + statutes + top-k precedents) | https://aclanthology.org/2025.ijcnlp-long.92/ · https://github.com/ShubhamKumarNigam/NyayaRAG |
| B2 | **SAMVAD**: Devadiga et al. | arXiv 2025 | Indian multi-agent courtroom debate without verification (**closest prior work**) | https://arxiv.org/abs/2509.03793 |
| B3 | **Automated Argument Generation from Legal Facts**: Tuvey & Sen | arXiv 2023 | Indian argument generation without grounding | https://arxiv.org/abs/2310.05680 |
| FT ref | **Aalap**: Tiwari et al. | arXiv 2024 | Reference for the fine-tuned Indian legal 7B model (gated) | https://arxiv.org/abs/2402.01758 · https://huggingface.co/opennyaiorg/Aalap-Mistral-7B-v0.1-bf16 |
| FT ref | **FactLegalLlama / TathyaNyaya**: Nigam et al. | AACL 2025 | QLoRA setup and compute reference | https://arxiv.org/abs/2504.04737 |
| FT ref | **INLegalLlama / NyayaAnumana**: Nigam et al. | COLING 2025 | Indian legal LLM baseline | https://aclanthology.org/2025.coling-main.738/ |
| Timeline ref | **LexChronos**: Tummepalli & Anish | AILaw @ AAAI 2026 | Baseline for agentic timeline extraction | https://arxiv.org/abs/2603.01651 |

---

## 9. Papers that motivate the research questions

| Paper | Venue | Why it matters to us | Link |
|---|---|---|---|
| Kim: *Does the Competitive Component of Adversarial Self-Play Improve Legal Reasoning?* | arXiv 2026 | Found that verification, not competition, drives the gains. Motivates **RQ2** | https://arxiv.org/abs/2608.01559 |
| **OBJECTION!** Lawyer agents mitigate guilty bias | EMNLP 2026 | A defense agent evaluated on verdicts only; its grounding is untested | https://arxiv.org/abs/2609.02158 |
| Magesh et al.: *Hallucination-Free?* | J. Empirical Legal Studies 2025 | "Misgrounded" citations; commercial legal RAG hallucinates 17–33% | https://arxiv.org/abs/2405.20362 |
| Dahl et al.: *Large Legal Fictions* | J. Legal Analysis 2024 | Hallucination rates of 58–88% on case-specific questions | https://arxiv.org/abs/2401.01301 |
| **AALawyer**: Huang et al. | ACL 2026 | Retrieval over a closed set of statutes (our statute index) | https://aclanthology.org/2026.acl-long.633/ |
| **LexAgentHallu**: Zhou et al. | EMNLP 2026 | Hallucination taxonomy for legal agents (used for failure analysis) | https://arxiv.org/abs/2609.09754 |
| Ovcharov: *Citation Grounding Measures the Oracle* | arXiv 2026 | Measured hallucination depends on how complete the citation database is, so we report coverage | https://arxiv.org/abs/2606.00898 |
| Zhang, Savelka & Ashley: *Precedent overruled?* | JURIX 2025 | LLMs fail to detect overruling. Motivates the good-law check | https://arxiv.org/abs/2510.20941 |
| Suttle & Lillis: *Persuadability of LLMs as Legal Decision Tools* | ICAIL 2026 | Metrics for robustness of the judge simulator | https://arxiv.org/abs/2604.26233 |
| Juvekar et al.: *Are LLMs Court-Ready?* (Indian) | arXiv 2025 | Rubric axes: procedure and format, citation discipline, register suited to the court | https://arxiv.org/abs/2510.17900 |
| **LEGIT**: Lee et al. | ACL 2026 | Rubrics based on issue trees. Basis for our issue planner and coverage metric | https://arxiv.org/abs/2512.01020 |
| Zhang et al.: *Faithfulness & Abstention for 3-ply Legal Arguments* | ICAIL-W 2025 | Metrics for how many available facts an argument uses, and for omitted facts | https://arxiv.org/abs/2506.00694 |
| Zhang & Ashley: *Reflective Multi-Agent Legal Argument* | ICAIL-W 2025 | Reflective critique loop for argument generation | https://arxiv.org/abs/2506.02992 |
| **CaseGen**: Li et al. | arXiv 2025 | Drafting defense statements, with a validated LLM judge | https://arxiv.org/abs/2502.17943 |
| **Falkor-IRAC**: Bose | arXiv 2026 | Precedent verification backed by an Indian IRAC graph | https://arxiv.org/abs/2605.14665 |
| **IBPS**: Srivastava et al. | arXiv 2025 | Indian bail prediction; prediction only, no argument drafting | https://arxiv.org/abs/2508.07592 |
| **ASP2LJ**, **SimCourt**, **LegalWorld** | arXiv 2025–26 | Further courtroom and legal-agent simulations | https://arxiv.org/abs/2506.18768 · https://arxiv.org/abs/2508.17322 · https://arxiv.org/abs/2606.18728 |
| Liu et al.: *LLM Agents in Law* (survey) | arXiv 2026 | Related-work overview | https://arxiv.org/abs/2601.06216 |

---

## 10. Evaluation-method papers (metric sources)

| Metric / method | Paper | Link |
|---|---|---|
| Citation recall / precision (NLI-based) | **ALCE**: Gao et al., EMNLP 2023 | https://arxiv.org/abs/2305.14627 |
| Attribution (AIS / AutoAIS) | Rashkin et al. 2023; Bohnet et al. 2022 | https://arxiv.org/abs/2112.12870 · https://arxiv.org/abs/2212.08037 |
| Atomic-fact support | **FActScore**: Min et al., EMNLP 2023 | https://arxiv.org/abs/2305.14251 |
| RAG faithfulness | **RAGAS**: Es et al., EACL 2024 | https://arxiv.org/abs/2309.15217 |
| Argument quality taxonomy | Wachsmuth et al., EACL 2017 | https://aclanthology.org/E17-1017/ |
| Argument coverage | Key Point Analysis: Bar-Haim et al., ACL 2020 | https://arxiv.org/abs/2005.01619 |
| LLM-judge validation (use κ) | Thakur et al., GEM 2025 | https://arxiv.org/abs/2406.12624 |
| LLM judges | G-Eval (EMNLP 2023); Prometheus 2 (EMNLP 2024) | https://arxiv.org/abs/2303.16634 · https://arxiv.org/abs/2405.01535 |
| Temporal awareness | TempEval-3: UzZaman et al., SemEval 2013 | https://arxiv.org/abs/1206.5333 |
| Legal event ordering | **LexTime**: Barale et al., EMNLP-F 2025 | https://arxiv.org/abs/2506.04041 |
