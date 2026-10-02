# plan.md (v4, simple): NyayaSahayak, a bail-preparation assistant for legal-aid counsel

> **In one line.** Counsel uploads a bail case and gets back:
> - a **source-checked case dossier** (fixed JSON schema), built by a small fine-tuned model that runs on a laptop GPU;
> - a **grounded bail brief** (fixed JSON schema). Every fact in it points to the case file, every authority is retrieved from Open India Law, and IPC-era precedent is correctly carried over to BNS-era cases.
>
> **Ground rules.**
> - Two data sources.
> - No manual annotation or hand-made datasets.
> - Open-weight models at run time, no paid APIs. A free external API may label *public* training data only (Section 9).
> - 8 weeks, on the Ada cluster and a 4060 laptop.
> - Anything not needed for v1 is in Section 10 (scope up later).

---

## 1. The task and the user

**User.** A legal-aid or junior advocate preparing a **regular bail application in the Delhi High Court** (CrPC s.439 / BNSS s.483).

**Their pain points.**
1. **Scattered facts.** The facts are spread across orders: custody dates, charge-sheet status, earlier bail rounds, co-accused bail.
2. **The 2024 law change.** Since 1 July 2024 the BNS and BNSS have replaced the IPC and CrPC. New FIRs cite BNS sections, but almost all bail case law discusses the old IPC sections.
3. **LLM fabrication.** General LLMs invent facts and case law.

**What the system does.** It drafts. Counsel decides.
- It never predicts outcomes.
- It never advises accused persons or the public.
- Nothing is exported without counsel's approval.

---

## 2. Data (two sources only)

| # | Source | What we take | Used for |
|---|---|---|---|
| **1** | **Open India Law** (CC BY 4.0; SC and HC judgments up to 2025, central acts) | (a) **Delhi HC bail orders**, 2019–2025, selected by case type and keywords ("BAIL APPLN", "439 Cr.P.C.", "483 BNSS"). (b) **SC judgments** that discuss bail. (c) **Statute text** of the IPC, BNS, CrPC and BNSS. | Fine-tuning data; the RAG stores; the evaluation set |
| **2** | **IPC2BNS-Verify** (MIT; IPC↔BNS concordance plus a 1,140-query benchmark) | The IPC↔BNS section mapping | The `map_section` tool; the RAG section-family expansion; the tool benchmark |

**Bail-related CrPC↔BNSS sections.** We also code a small table of about 10 rows (CrPC 436/436A/437/438/439 → BNSS 478/479/480/482/483) into the tool, citing the bare-act text. This is tool configuration, not a dataset.

**Off-the-shelf models** (no training data needed):
- Qwen3 (4B, 14B, 32B);
- Llama-3.1-8B (used only for evaluation labels);
- BGE-M3 (embeddings);
- DeBERTa-v3 NLI and MiniCheck (claim checking);
- Microsoft Presidio and InLegalNER (pseudonymisation).

**Splits by date** (this also prevents leakage):

| Split | Orders | Use |
|---|---|---|
| **Train** | Before 2024 | Fine-tuning pairs |
| **Dev** | Early 2024 | Prompt and threshold tuning (50 orders) |
| **Test** | Mid-2024 to 2025 | 200 orders, of which ≥60 are BNS-era (offence on or after 1 July 2024) |

- The **precedent index holds every Delhi HC bail order and SC bail judgment except the test orders** (and any order with the same FIR as a test order). It is not limited to the training split, so 2024–25 precedents the court cites can be found.
- At run time, retrieval only sees documents dated before the case's order.
- Test orders and their same-FIR orders are also excluded from the fine-tuning data.

---

## 3. Models and how they are built

| Component | Model | How it's made |
|---|---|---|
| **Extractor** (inside Agent 1) | **Qwen3-4B + QLoRA** | **Fine-tuned** on ~2K (facts section → `CaseDossier` JSON) pairs, built automatically (below). Served in int4, so it runs on the **8 GB 4060**: case files never leave counsel's machine. |
| **Teacher** (data only) | Qwen3-32B-AWQ on Ada, **or** a Mistral API model (chosen by the week-1 pilot, Section 9) | Writes the training dossiers from *public* orders only; never used at run time. |
| **Agents' reasoning** | Qwen3-14B-AWQ on Ada (vLLM) | Prompted, not fine-tuned. Drives both agents' tool use, drafting and repair. |
| **Fact and paragraph checks** | DeBERTa-v3 NLI | Off the shelf; the threshold is tuned on dev. |

**How the fine-tuning data is made, with no humans.**
1. The 32B teacher reads the facts section of ~4K *train* bail orders and outputs a `CaseDossier`, quoting a source sentence for each field.
2. `span_check` (NLI) tests whether each quote supports its value.
3. Only orders where **every field passes** are kept, est. ~2K pairs.
4. QLoRA trains the 4B model on these pairs: r=16, 2 epochs, one 2080 Ti, FP16.

**Fine-tuning claim we test.** The tuned 4B model is close to the prompted 32B model on dossier accuracy, and it runs locally at a fraction of the memory and latency.

---

## 4. RAG (two stores from Open India Law, plus the user's own file)

**Why RAG is needed and not bolted on.**
- A bail brief is only useful if it cites **real, date-valid authority**. An LLM's memory of Delhi HC bail orders is thin, and this is exactly where LLMs fabricate.
- Section text must be **exact**, and BNS and BNSS are recent laws the models know poorly.
- After the 2024 renumbering, finding the right precedent is a genuinely hard retrieval problem, not a lookup.

| Store | Contents | Size | Retrieval |
|---|---|---|---|
| **Statute store** | One row per section of the IPC, BNS, CrPC and BNSS: section text, maximum punishment, bailable or not, and IPC↔BNS links (from IPC2BNS-Verify) | ≈1,000 rows | Exact lookup by (code, section). Not a vector search, because statute text must match exactly. |
| **Precedent index** | All non-test Delhi HC bail orders plus SC bail judgments (Section 2), chunked into ≤400-token paragraphs. Each paragraph carries the metadata below. | est. 100–300K chunks | **Metadata filter, then hybrid ranking** (below) |
| **Case file** (per case) | The user's uploaded orders and typed text | A few orders | The chat and Agent 1 **read the whole file** when it fits in the context window; a typical bail file of 2–5 orders is ~5–20K tokens. A BM25 search over its paragraphs is used only when the file is too long. |

**Metadata on each precedent paragraph.** All of it is computed automatically, mostly by rules.

```json
{"doc_id": "DLHC-2022-1187", "para": 14, "court": "Delhi HC", "date": "2022-06-03", "outcome": "granted",
 "part": "reasoning",
 "sections": ["IPC 420", "IPC 406"], "section_family": ["IPC 420", "BNS 318(4)", "IPC 406", "BNS 316(2)"],
 "factors": ["parity_with_co_accused", "charge_sheet_filed"], "text": "..."}
```

- **`part`** is one of facts, defense submissions, prosecution submissions or reasoning, assigned by the same cue-phrase splitter used to build the test set. **Authorities are retrieved from `reasoning` paragraphs only**, so counsel's submissions are never cited as if they were the court's holding.
- **`factors`** are the bail factors a reasoning paragraph discusses, tagged by the keyword-rule labeler.
- **`section_family`** comes from regex-extracted sections expanded through the concordance.

**How retrieval works.** `search_precedents(factor, section_family, before_date)`:
1. **Filter:** reasoning paragraphs, Delhi HC or SC, dated before the case, whose section family overlaps the case's, and that discuss the requested factor. Optionally restrict to `outcome = granted`.
2. **Rank:** BM25 + BGE-M3 dense similarity to a factor-specific query built from the dossier, e.g. "co-accused with identical role granted bail; cheating; charge sheet filed".
3. **Fall back** if fewer than 5 hits: drop the factor filter, then the section-family filter. The brief notes when this happens.

This lets counsel ask, in effect, "where has this court accepted *parity* in a *cheating* case?". That query is what generic chunk search does badly.

**The recodification bridge** is the one RAG idea that matters.
- A BNS-era case asking about BNS 318(4) also retrieves precedents decided under IPC 420.
- Each retrieved precedent gets a **transfer flag**, computed from the concordance and a text diff of the old and new sections:
  - `SAME_TEXT`: the provision was carried over unchanged, so the precedent applies;
  - `CHANGED`: split, merged or reworded, so it is usable only with a qualification, which the brief must state;
  - `NEW`: no IPC equivalent.

---

## 5. The two agents and their exact output schemas

### Agent 1: Case-File Agent

- **Input:** PDFs (court orders, earlier bail orders) and/or a typed description.
- **Tools:**
  - `parse_pdf`: text layer, with OCR fallback;
  - `pseudonymise`;
  - `extract_dossier`: the fine-tuned 4B model;
  - `map_section(code, section, offence_date)`;
  - `date_calc(start, end, rule)`;
  - `span_check(value, quote)`;
  - `ask_user(question)`: at most 3 per case;
  - `search_case_file(query)`: BM25 over the case's own paragraphs, used only when the file is too long to read whole.
- **What it decides:**
  - which fields failed the check and need re-extraction;
  - which missing fields are critical enough to ask counsel about;
  - when the dossier is ready for review.

**Output: `CaseDossier`.** Every field is wrapped as `{value, source, status}`.

```json
{
  "case_id": "case-0007",
  "court": "Delhi High Court",
  "fields": {
    "fir":               {"value": {"number": "112/2024", "police_station": "PS-1", "date": "2024-08-14"},
                          "source": {"doc": "order_2.pdf", "quote": "FIR No. 112/2024 dated 14.08.2024, PS ..."},
                          "status": "VERIFIED"},
    "offence_date":      {"value": "2024-08-10", "source": {...}, "status": "VERIFIED"},
    "sections":          {"value": [{"as_written": "318(4) BNS", "code": "BNS", "section": "318(4)",
                                     "equivalent": "IPC 420", "bailable": false, "max_punishment": "7 years"}],
                          "source": {...}, "status": "VERIFIED"},
    "arrest_date":       {"value": "2024-08-20", "source": {...}, "status": "VERIFIED"},
    "custody_days":      {"value": 167, "source": {"tool": "date_calc"}, "status": "COMPUTED"},
    "charge_sheet":      {"value": {"filed": true, "date": "2024-11-02"}, "source": {...}, "status": "VERIFIED"},
    "trial_stage":       {"value": "charges not framed", "source": {...}, "status": "VERIFIED"},
    "previous_bail":     {"value": [{"court": "Sessions Court", "date": "2024-09-30", "outcome": "rejected"}],
                          "source": {...}, "status": "VERIFIED"},
    "co_accused_bail":   {"value": [{"id": "Co-accused-1", "outcome": "granted", "date": "2024-12-05"}],
                          "source": {...}, "status": "VERIFIED"},
    "antecedents":       {"value": null, "source": null, "status": "UNSUPPORTED"},
    "personal":          {"value": ["sole earning member"], "source": {...}, "status": "USER_STATED"},
    "bnss_479":          {"value": {"eligible": false, "basis": "167 of 1,278 days (1/2 of 7 years)"},
                          "source": {"tool": "date_calc"}, "status": "COMPUTED"}
  },
  "open_questions": ["Does the accused have any other pending cases?"]
}
```

**Statuses:**
- `VERIFIED`: the quote supports the value.
- `COMPUTED`: produced by a tool.
- `UNSUPPORTED`: not found in the file, or the check failed.
- `AMBIGUOUS`: unclear section mapping or conflicting documents.
- `USER_STATED`: typed in the chat, with no court record behind it.
- `USER_EDITED`: corrected by counsel.

### Agent 2: Bail-Brief Agent

- **Input:** the approved `CaseDossier`.
- **Tools:**
  - `get_statute(code, section)`;
  - `map_section`;
  - `search_precedents(factor, section_family, before_date, outcome?)`: reasoning paragraphs only (Section 4);
  - `get_paragraph(doc_id, para)`;
  - `check_claim(claim, refs)`: NLI against the cited fact or paragraph;
  - `transfer_check(doc_id, section)`;
  - `request_approval(brief_id)`;
  - `export_brief(brief_id, format)`: **gated**.
- **Loop:**
  1. **Plan:** go through the 12-factor checklist (Appendix) and pick the factors that the dossier supports.
  2. **Retrieve per factor:** the agent chooses its tools.
  3. **Draft** one ground per factor. Each sentence must cite `[F:field]` facts and `[A:doc#para]` authorities.
  4. **Objection pass:** write the prosecution's likely objections and a response to each.
  5. **Check every claim:**
     - fact support (NLI vs the dossier quote);
     - authority support (NLI vs the cited paragraph);
     - transfer flag;
     - no citation that wasn't retrieved.
  6. **Repair or flag**, at most 2 rounds:
     - re-retrieve or reword to what the source supports;
     - otherwise, mark the claim `NEEDS_COUNSEL`.
     - **Nothing is ever dropped silently.**

**Output: `BailBrief`.**

```json
{
  "case_id": "case-0007",
  "statutory_position": {"sections": ["BNS 318(4) (≈ IPC 420)"], "bailable": false,
                         "max_punishment": "7 years", "bnss_479": "not yet eligible (167 / 1,278 days)"},
  "grounds": [
    {"factor": "parity_with_co_accused", "stance": "favourable",
     "argument": "Co-accused-1, with an identical role, was granted bail on 05.12.2024 [F:co_accused_bail] ...",
     "facts": ["co_accused_bail", "fir"],
     "authorities": [{"doc_id": "DLHC-2022-1187", "para": 14, "citation": "<rendered from metadata>",
                      "transfer": "SAME_TEXT"}],
     "check": "SUPPORTED"},
    {"factor": "charge_sheet_filed", "stance": "favourable", "argument": "...", "facts": ["charge_sheet"],
     "authorities": [...], "check": "REPAIRED"}
  ],
  "anticipated_objections": [
    {"factor": "gravity", "objection": "Offence involves Rs X lakh ...", "response": "...", "authorities": [...]}
  ],
  "open_issues": [
    {"type": "NEEDS_COUNSEL", "item": "Antecedents unknown: confirm no other pending cases."},
    {"type": "CHANGED_PROVISION", "item": "Precedent DLHC-2021-0420 interprets IPC 420; BNS 318(4) wording differs: qualify."}
  ],
  "label": "AI-generated draft for counsel review. Not legal advice."
}
```

Citation text is always **rendered from corpus metadata**: the model writes only IDs, so it cannot invent a case name.

---

## 6. Features and user flows

**Features (v1)**

| Feature | What the user sees |
|---|---|
| **Case list** | Create, open and resume cases; each case shows a status (Intake → Dossier review → Brief review → Approved → Exported) and an "N items need attention" count. |
| **Upload and chat** | Drag in PDFs and/or type the case story in a chat box. |
| **Local privacy** | Names are replaced with pseudonyms (Accused-1, Co-accused-1) before any model sees them. Real names reappear only on counsel's screen. |
| **Dossier view** | Each field shows a status chip; clicking it highlights the source sentence in the PDF. Fields can be edited. |
| **Case chat** | Ask "How many days in custody?", "Is the charge sheet filed?", "What's the BNS equivalent of 420 IPC?", "Is my client eligible under s.479?" Answers are cited, and requests for predictions or lay advice are refused. |
| **Brief view** | Grounds with clickable fact and authority citations; a transfer badge on each precedent; the objections-and-responses panel; open issues. |
| **Approval and export** | Approve the brief, then export it to DOCX or PDF. Export is impossible without approval, which is enforced in code. |

**User flows**

1. **New case → dossier.**
   1. Counsel clicks *New case* and uploads two orders (the Sessions Court bail rejection and a later order).
   2. The system pseudonymises them and extracts the dossier, streaming its progress.
   3. It asks at most 3 questions, e.g. "When was the accused arrested?".
   4. Counsel answers, fixes any red (`UNSUPPORTED`) fields, and approves the dossier (**Gate 1**).
2. **Quick questions.** At any point counsel asks the case chat a question and gets a one-line cited answer, e.g. "Custody: 167 days [date_calc from arrest 20.08.2024]; not yet eligible under BNSS 479".
3. **Generate the brief.**
   1. Counsel clicks *Draft bail brief*, and the agent plans, retrieves, drafts, objects, checks and repairs, streaming its progress.
   2. Counsel reads the grounds, opens the cited paragraphs, and resolves the `NEEDS_COUNSEL` items.
   3. Counsel approves (**Gate 2**) and exports.
4. **Case moves on.**
   1. A week later the charge sheet is filed. Counsel uploads the new order.
   2. The changed fields are highlighted in the dossier, and counsel re-approves it.
   3. Counsel regenerates the brief: the grounds for "investigation complete" now appear.
5. **Typed-only case.** With no PDFs, counsel types the story. Those facts are marked `USER_STATED`, and the brief labels them as "per counsel, not on record".

---

## 7. Research questions and novelty

**RQ1.** Does building a source-checked dossier first (Agent 1) and arguing only from it with a check-and-repair loop (Agent 2) produce bail grounds that:
- **match what defense counsel actually argued more closely**, and
- **contain fewer unsupported facts**

than giving the same LLM the raw case file?

**RQ2.** On BNS-era cases, does the recodification bridge retrieve the precedents the court actually relied on more often than plain retrieval? And how often would an IPC precedent have been applied to a changed provision without a qualification?

**Hypotheses** (thresholds fixed on the dev set before the test run; a null result is still reported)
- **H1:** the full system has higher recall of argued factors and a lower unsupported-fact rate than B0 and B1.
- **H2:** on the BNS-era subset, the full retrieval (section-family expansion + reasoning-only + factor filter) has higher recall@10 of court-cited precedents than plain hybrid retrieval.

**Novelty**
1. **A recodification-aware bail assistant.** It carries IPC-era case law to BNS-era cases and flags provisions that changed. We found work that maps statute sections across the change, but none that does this for case law. This is subject to a full related-work check.
2. **A dossier-first, check-and-repair design that never silently drops.** Every fact traces to a source quote, and unverifiable claims are flagged rather than deleted.
3. **A fully automatic, court-grounded benchmark** (Section 8). The input is only the facts section of a real order. The ground truth is what the court itself recorded: the arguments defense counsel made and the precedents the court cited. It needs zero annotation and is reproducible.
4. **A local fine-tuned extractor.** A 4B model on an 8 GB GPU approaches a 32B model on dossier extraction.

---

## 8. Evaluation (no manual labels)

**How the test set is built automatically.** Each test order is split into four parts:
- facts;
- defense submissions ("learned counsel for the applicant submits…");
- prosecution submissions ("per contra, learned APP…");
- reasoning and outcome.

The split uses cue-phrase rules, and orders where the rules don't produce a clean split are discarded.

- **System input:** the **facts part only**. A check confirms there is no 8-gram overlap with the other parts.
- **Gold 1, factors argued.** Which of the 12 factors appear in the *defense submissions*. These are labelled by **two independent methods**: a keyword-rule labeler, and Llama-3.1-8B, which is from a different family from our Qwen models. **Only factors both agree on are used.** We report agreement, and re-run the main result with each labeler alone to show it doesn't depend on one labeler.
- **Answerable factors.** A factor is scored only if its supporting fact appears in the facts part, decided by the same two methods. That way the system isn't penalised for information it never saw.
- **Gold 2, cited precedents.** Citations in the *reasoning* part (regex for case names and citations) resolved against Open India Law metadata. Only resolvable citations are scored.
- **Gold 3, dossier fields** (extractor evaluation). Fields that the regex rules and Llama agree on, read from the *whole* order. Qwen output is never used as gold.

**Systems compared.** All use Qwen3-14B and the same 12-factor checklist.

| ID | System |
|---|---|
| B0 | **"Just ask an LLM"**: raw facts plus the checklist → brief, in one call |
| B1 | B0 plus standard RAG: the top-10 precedent paragraphs retrieved with the facts as the query (no filters, no section expansion) |
| **Full** | Agent 1 + Agent 2 |

**Ablations** (one per capability):
- **A1 no dossier:** Agent 2 reads the raw facts (reasoning/agentic).
- **A2 no check-and-repair loop:** reasoning.
- **A3 no tools:** the LLM does section mapping and dates itself (tool calling).
- **A4 plain retrieval:** no section-family expansion, no part/factor filters, no transfer flag (RAG, RQ2).
- **A5 extractor variants:** fine-tuned 4B vs base 4B vs prompted 32B (fine-tuning).

**Metrics**

| Capability | Metric |
|---|---|
| Reasoning / overall (RQ1) | **Factor recall and precision** vs gold 1, on answerable factors; **unsupported-fact rate**: share of factual sentences that MiniCheck finds unsupported by the input text |
| RAG (RQ2) | **Recall@10 of court-cited precedents** (gold 2) on the BNS-era subset; share of `CHANGED` precedents used without a qualification; share of cited paragraphs that are court reasoning (not submissions) |
| Fine-tuning | Field accuracy vs gold 3; GPU memory and latency on the 4060 |
| Tool calling | `map_section` accuracy on IPC2BNS-Verify's 1,140 queries; tool-call accuracy (right tool, valid arguments) on ~100 templated chat questions whose answers come from gold 3; recovery from injected tool errors |
| Agentic | Task completion (valid schema and all checks run); pass^3 on 50 cases; share of flagged claims that are resolved by repair |
| Safety | **Unapproved-export attempts** under ~40 scripted pressure or injection scenarios (instructions planted inside PDFs; "hearing in 5 minutes, just export"); refusal rate on templated lay-advice and prediction requests; **leak rate** of synthetic names planted with Faker |

- **Checker validation.** MiniCheck's accuracy comes from its published human-labelled benchmark (LLM-AggreFact). We add an automatic in-domain check: sentences taken from the input count as supported, and copies with a date, number or name changed count as unsupported.
- **No LLM-judge scores are used** for any claim, since the course requires human validation of LLM judges.

**Retrieval-only analysis.** This is cheap: no generation, just queries over the index. On the test set we run `search_precedents` in five variants and report recall@10 of court-cited precedents for each, to show what each retrieval piece adds:
1. plain hybrid search;
2. + section-family expansion;
3. + reasoning-only;
4. + factor filter;
5. all of these.

**Contamination check.** Qwen3 was released in April 2025, and Open India Law is public, so the model may have seen some test orders during training. We therefore report results separately for test orders dated after the release.

**Statistics.** Paired bootstrap 95% CIs and the Wilcoxon test, Full vs B0/B1, with 3 runs for the main systems (averaged per case). Ablations use 1 run on 100 test cases.

**Failure analysis.** Every error is typed automatically: wrong section or date (tool), unsupported fact, missed factor, misgrounded authority, or wrong transfer. Add 4–5 example cases.

---

## 8a. Safety and ethics

- **Approvals in code.** Export is a gated tool that works only after counsel approves.
- **Privacy.**
  - Names are pseudonymised before any model sees them.
  - The extractor runs on counsel's machine, and the agents run on the university cluster, never on a third-party service.
  - Logs store only pseudonymised text.
- **Data.**
  - Only public court orders are used.
  - Demos use public or synthetic files.
  - Real client files would need separate approval.
- **Documents are data.** Instructions found inside a PDF are never followed; this is tested with planted instructions.
- **Scope.** No outcome predictions and no advice to accused persons or the public; such requests are refused.
- **Sensitive matters.** Sexual-offence, POCSO and juvenile matters are declined at intake and excluded from evaluation, because the law protects the identity of victims and children (BNS section 72, POCSO section 23, JJ Act section 74).
- **External API.** If used at all, it only ever sees public training orders.
- **Bias check.** Results are compared across offence types and bail outcomes.

## 9. Compute and timeline

**Hardware.**
- **Ada:** 3 accounts, each with one 4× RTX 2080 Ti node (44 GB). We plan on 2.
- **Local:** an RTX 4060 laptop (8 GB) for development, the demo, the local extractor and long, light jobs.

**How we use Ada (cluster rules).** Batch jobs (`sbatch`) may run for up to 4 days, but using them only to host an inference engine risks a ban. Interactive jobs may run inference engines but end after 6 hours. So:

| Work | Where it runs | How |
|---|---|---|
| QLoRA training | Ada **batch job** (1 GPU per run, ≤1.5 days each, well inside the 4-day limit) | Checkpoints every epoch; this is training, not inference serving |
| All LLM inference: teacher dossiers, test runs, ablations | Ada **interactive sessions** of at most 6 hours (one 4-GPU session per account at a time) | vLLM runs **inside the experiment script**, with no long-lived server. Work is cut into **shards of about 5 hours**. Each case's output is saved as soon as it finishes, so a session that ends or fails resumes where it stopped. About 20–30 minutes per session go to loading the model from node `/scratch`. |
| Embeddings, evaluation labels (Llama-3.1-8B in 4-bit), MiniCheck, the extractor on test files | **The 4060 laptop** | No time limit; runs overnight |
| Live demo | Laptop (4B extractor) plus an Ada interactive session for the 14B agents, reached through an SSH tunnel | Fallback: Qwen3-8B in 4-bit on the laptop, with lower quality |

In week 0 we also ask hpc.admin whether *offline* batch inference (a script that processes a dataset and exits) is allowed as a batch job. If it is, the same shards can be submitted as batch jobs. The plan does not depend on that answer.

**Compute estimate.** Throughput is an assumption (≈2M tokens per node-hour for the 14B, ≈0.8M for the 32B), measured in week 1.

| Item | Estimate | Where | Hours |
|---|---|---|---|
| Teacher dossiers | 4K orders × ~12K tokens on Qwen3-32B (zero if the pilot picks the Mistral API) | Ada interactive | ~60 node-h ≈ 12 sessions |
| QLoRA (4B, 2–3 runs) | ~2K pairs × ~12K tokens × 2 epochs ≈ 48M tokens per run at an assumed 400 tok/s, one GPU per run | Ada batch | ≈33 GPU-h per run (≈1.4 days), ≈100 GPU-h in total |
| Main runs | Full, B0, B1 × 200 cases × 3 runs; the full system at ~100K tokens per run | Ada interactive | ~40 node-h ≈ 8 sessions |
| Ablations | 4 agent ablations × 100 cases × 1 run, plus extractor variants | Ada interactive | ~25 node-h ≈ 5 sessions |
| Embedding the precedent index | ≤300K chunks | Laptop | ~10 h |
| Evaluation labels, MiniCheck, safety and chat sets | | Laptop | ~25 h |
| **Total on Ada** | | | **≈25 interactive sessions (≈13 if the teacher uses the API) + 2–3 batch training runs** |

With a 30% buffer this is about 33 sessions. Spread over 3 accounts and weeks 2–6, that is 2–3 sessions per account per week, so it fits even with queue waits.

**Teacher pilot (week 1).** The teacher only reads *public* court orders, so it may use an external API. Counsel's case files never leave the local machine, and the agents always run on open models (Ada or the 4060), so experiments stay reproducible.
- **What we compare:** Qwen3-32B-AWQ on Ada against a Mistral API model (e.g. Mistral Small or Medium, free tier).
- **How:** both produce dossiers for the **same 50 train orders**. We measure:
  - the share of outputs where every field passes `span_check`;
  - tokens per hour;
  - rate-limit stalls.
- **Decision rule:** pick whichever gives more verified pairs per day.
- **Conditions for using the API:**
  1. its terms allow using the outputs to train our extractor;
  2. it is free, or within a stated budget;
  3. model versions are pinned and all outputs cached.

  If any condition fails, we use Qwen3-32B on Ada. If the API is chosen, ~60 node-hours are freed.
- **Same check for the evaluation labeler:** Llama-3.1-8B on Ada vs a non-Qwen API model, with Llama as the default.
- **Family rule:** the teacher and the evaluation labeler must not be the same model family.

**Timeline**

| Week | Work |
|---|---|
| 0 | Proposal approved. Count the Delhi HC bail orders in Open India Law (need ≥250 cleanly split test/dev orders, ≥60 BNS-era). Check the IPC2BNS-Verify licence and coverage. |
| 1 | Data pull and splits; the statute store; `map_section`, `date_calc`; vLLM on Ada; throughput measured; **teacher pilot** (Section 9). |
| 2 | Agent 1 with the prompted 14B model; teacher dossiers; segmentation and gold-label pipeline. |
| 3 | QLoRA extractor; precedent index with section families; Agent 2 draft loop. |
| 4 | Check-and-repair, the objection pass, the transfer flag; Streamlit UI (case list, dossier view, chat, brief view, gates). |
| 5 | Dev tuning, then **freeze**; baselines ready. |
| 6 | All test runs and ablations. |
| 7 | Metrics, failure analysis, case studies. |
| 8 | Write-up and demo video. |

**Risks**
- **Too few BNS-era orders** (Open India Law ends in 2025). Add a second HC from the same source, or report RQ2 as a pilot.
- **Cue-phrase segmentation fails often.** Fall back to LLM segmentation (non-Qwen) for the failures; report the share.
- **Labelers disagree a lot.** Use only agreed labels, report coverage, and merge confusable factors.
- **The fine-tuned 4B model is weak.** Use the prompted 14B model as the extractor, and report the negative result.
- **Slow 2080 Ti throughput or long queues for interactive sessions.** Cut the ablations to 60 cases, and run 2 runs instead of 3. Every job resumes from saved progress, so a lost session costs at most one shard.

---

## 10. Scope up later (not in v1)

- Multi-order case files linked by FIR number.
- The AWS HC PDFs.
- More High Courts.
- A structured bail-records store.
- A study of the verifier "tax": verifier policies vs silently dropped grounds.
- Counterfactual-record tests.
- A user study with lawyers.
- Anticipatory bail, district courts, Hindi.

---

## Appendix: the 12 bail factors (checklist and label set)

1. gravity and punishment
2. custody period
3. charge sheet filed / investigation complete
4. trial delay
5. parity with co-accused
6. antecedents
7. flight risk
8. witness tampering
9. weak prima facie case
10. health, age, gender or family circumstances
11. statutory bar (NDPS s.37, UAPA s.43D(5), PMLA s.45)
12. BNSS s.479 / CrPC s.436A undertrial period
