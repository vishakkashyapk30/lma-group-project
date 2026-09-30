# plan.md (v2): NyayaSahayak, Verified Bail Preparation for Legal-Aid Counsel

> **One-line pitch.** A two-stage agentic system. It turns a High Court bail case file into a **verified dossier**, then into a **grounded bail brief** whose every claim links to a record fact or a retrieved authority. The research asks whether verification makes the brief better, **what verification costs in silently dropped valid grounds**, and whether a **recodification bridge** can carry IPC-era precedent across to BNS-era cases.
>
> **Constraints.** No paid services: every model is open-weight and self-hosted, and every corpus and tool is free. The work fits in 8 weeks. A lawyer approves every output.
>
> **Companion docs.** [`datasets_sources.md`](datasets_sources.md) lists data and papers, and [`pipeline_research.md`](pipeline_research.md) covers the landscape. Items marked **[verify]** are legal details a legal collaborator must confirm.

---

## 1. Users and problem

**Primary user: High Court legal-aid panel counsel and junior advocates.** These are lawyers on High Court Legal Services Committee panels, or juniors in small criminal practices. They prepare **regular-bail applications in one High Court** under CrPC 439 / BNSS 483 **[verify]**. Their case load is high and they have little research support.

We chose a High Court user because the public data exists at High Court level: bail orders, case histories linked by CNR, and precedents. That keeps user and data aligned. District-level LADCS counsel are a natural extension, listed under future work.

**Problems they face:**
1. Case facts are spread across several earlier orders.
2. Since 1 July 2024, the right code (IPC or BNS, CrPC or BNSS) depends on dates, so section numbers are easy to get wrong.
3. Finding recent High Court authority on parity, delay or custody takes hours.
4. General-purpose LLMs invent facts and precedents.

**What the users need, and how we measure it:**

| Need | System feature | Metric |
|---|---|---|
| Trust every fact | Each dossier field and brief claim links to a source span | Unsupported-fact rate |
| No fake or wrong authorities | Authorities come only from the retrieved corpus; each is checked for support, ratio and good law | Misgrounded rate, bad-law rate |
| Correct sections | Date-aware statute tool | Temporal-correctness rate |
| Don't miss favourable grounds | Bail-factor checklist and a critic pass | Factor recall vs real counsel's grounds |
| Know the other side's case | Prosecutor-critic report | Recall of prosecution and court-adverse factors |
| Know when the system is unsure | Explicit `UNSUPPORTED` / `AMBIGUOUS` statuses | Abstention precision |

**Non-users:** accused persons, the public and judges. The system prepares; it does not advise or predict outcomes.

---

## 2. Research question

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

**Component evaluations (reported, but not research questions):**
- the fine-tuned 8B extractor vs a prompted 70B-class model;
- the statute resolver;
- citation-resolution coverage.

---

## 3. Scope

| In | Out (future work, §11) |
|---|---|
| Regular bail in **one** High Court (Delhi HC unless the week-0 check says otherwise), with a second HC only as a fallback | Anticipatory bail, trials, appeals, district courts |
| English orders from 2025–26, including both IPC-era and BNS-era offences (stratified) | Hindi, FIR OCR, eCourts scraping |
| Case file = the order's facts plus the **CNR-linked earlier orders** in the same case | Raw FIRs and charge sheets (not public) |
| **Input:** case-file PDFs and/or a plain-text description of the case. **Workspace:** many cases per user, each with its own state, plus a dashboard and groups. Then PII pseudonymisation → per-case index → two agents → two human gates, in a minimal Streamlit UI with streamed progress | Judge simulator, "ask the file" chat, cross-session memory, edit propagation, GraphRAG, a separate query classifier, real client files |

---

## 4. System

```
 Input, per case: PDF(s) and/or a plain-text description   (public orders in evaluation)
   Cases live in a dashboard (§4.5): create, open, group, resume
   │
   ▼
 INTAKE (R0)
   PDF → text (OCR fallback) | free text as is → PII pseudonymisation (local map) → chunk + embed a per-case index (S4)
   missing critical fields → up to 3 clarifying questions to the user
   │
   ▼
 RECORDS AGENT
   R1 Segment + NER        rhetorical-role model, InLegalNER
   R2 Extract (QLoRA 8B)   dossier JSON with a source span for every field
   R3 map_section ⚙        IPC↔BNS / CrPC↔BNSS by offence date → AMBIGUOUS if unclear; joins S1 (statute store)
   R4 date_calc ⚙          timeline, custody days, BNSS 479 check
   R5 Span verify          NLI: does the span entail the field? If not → re-extract once → UNSUPPORTED
   ── HUMAN GATE 1: counsel checks and corrects the dossier ──
   ▼
 DEFENSE AGENT
   D1 Factor planner       bail-factor checklist → favourable / adverse, each with fact IDs and provisions
   D2 Retrieve             agent picks tools: S1 statute lookup · S2 bail store query · S3 vector search; hard date cutoff
   D3 Draft                one ground per factor; each sentence cites [F#] facts and [A#] authorities
   D4 Prosecutor critic    objections, counter-authorities, missed favourable facts
   D5 Verifier ⚙+NLI       support · ratio vs obiter · good-law keywords · statute validity
   D6 Revise               ≤2 rounds, then list what's still unresolved
   ── HUMAN GATE 2: counsel approves; only then can the brief be exported ──
 ⚙ = deterministic tool

 KNOWLEDGE STORES (built offline, read-only at run time)
   S1 Statute Store        ~1,000 rows: text, punishment, bailable/cognizable, IPC↔BNS links
   S2 Bail Records Store   ~2–3K verified past bail orders as structured rows (sections, factors, outcome, court, date)
   S3 Precedent index      role-labelled chunks of HC/SC judgments (BM25 + dense)
   S4 Per-case index       built at upload time from the user's own file
```

**Design rules**
1. **Deterministic tools** handle dates, statute mapping and citation rendering.
2. **The drafter can only cite dossier field IDs `[F#]` and retrieved document IDs `[A#]`.** The citation text is rendered from corpus metadata, so fabricated authorities are impossible by design. The remaining risks are misgrounding and bad law, and those are what D5 checks.
3. **Uncertainty is never hidden.** `UNSUPPORTED`, `AMBIGUOUS` and "couldn't verify" are all shown to the user.
4. **Bounded loops.** Each loop has a step and token budget, and the full trace is logged.
5. **The model never sees real names.** Intake replaces them with consistent pseudonyms (Accused-1, Co-accused-2, Victim-1). The mapping is kept in an encrypted local store per case, so pseudonyms stay stable across sessions. Real names are restored only in what counsel sees. Victim and minor identities are never restored.
6. **No GraphRAG.** The statute set is small enough for a table with a short list of links, and Open India Law has no citation graph. Routing is done by the agent's tool choice, which we already measure, not by a separate classifier.

### 4.1 Components in brief

- **R0 Intake:**
  - **Text:** PyMuPDF for PDFs with a text layer; Tesseract or docTR OCR as fallback, with a per-page quality check. Non-English files are flagged, not processed.
  - **PII:** InLegalNER (PETITIONER, RESPONDENT, JUDGE, LAWYER, WITNESS, OTHER_PERSON) plus Microsoft Presidio with custom recognisers for phone numbers, Aadhaar-style 12-digit numbers, PAN, email and addresses. Detected names become consistent pseudonyms. The mapping is kept in an encrypted local store per case, and logs and traces store only pseudonymised text. Detection recall is measured on E5 documents with planted PII, and we report it, because NER will miss some names.
  - **Index:** the text is chunked with the same tokenizer as the model (≤400 tokens per chunk), embedded with BGE-M3, and kept in an in-memory FAISS index (S4). S4 is used to find source spans and to handle long multi-order files.
  - **Plain-text input.** A case can start from a typed description or question instead of (or in addition to) PDFs. Each input becomes a source document of type `court_order` or `user_text`, and all of it goes through the same pseudonymisation and extraction. Several inputs can be added to one case over time.
  - **Trust level.** A fact taken from `user_text` cannot be checked against a court record. R5 only confirms that the extractor captured what the user wrote. These fields get a new status, `USER_STATED`, and are labelled as such in the brief. If a court order added later contradicts a user statement, the field becomes `AMBIGUOUS` with both values shown.
  - **Clarifying questions.** If critical fields are missing (offence date, sections, arrest or custody date, court, co-accused status), the agent asks at most 3 targeted questions through `ask_user`. Whatever is still missing is marked `UNSUPPORTED`, and the pipeline continues.
  - **Questions that only need tools.** A question such as "what does s.479 say?" or "how many days has my client been in custody?" is answered directly from S1 and `date_calc`, with citations, and no brief is generated. This mode is not evaluated beyond tool-call accuracy.
  - **Interactive, not instant.** A 70B-class model with several loops takes minutes per case, so the UI streams progress ("extracting… verifying… drafting…").
- **R1:** OpenNyAI / IL-TUR rhetorical-role model, and InLegalNER (`opennyaiorg/en_legal_ner_trf`).
  - The RR model was trained on Supreme Court judgments, so week 0 measures its accuracy on bail orders. If it's poor, we switch to LLM segmentation checked on the dev set.
- **Dossier fields (about 15):**
  - parties; FIR number and date; offence date; sections as written and as resolved;
  - arrest date and custody days; charge sheet filed and its date; trial stage;
  - earlier bail applications and their outcomes; co-accused bail status; antecedents;
  - prosecution objections recorded in earlier orders; health, age and family circumstances;
  - authorities cited in the record.
  - The schema follows the IndianBailJudgments-1200 attributes. Each field has `value`, `source_span` and one status: `VERIFIED` / `COMPUTED` / `UNSUPPORTED` / `AMBIGUOUS` / `USER_STATED` (from the user's own text) / `USER_ASSERTED` (entered or corrected by counsel at Gate 1).
- **R3 `map_section`:** built on the IPC2BNS-Verify concordance, checked against the NCRB/BPRD tables.
  - Substantive code: decided by offence date.
  - Procedural code for pending matters: follows the BNSS s.531 savings clause. **Only clear rules are encoded; everything else returns `AMBIGUOUS`** **[verify with legal collaborator]**.
- **S1 Statute Store.** One row per section: code, section, text, maximum and minimum punishment, bailable, cognizable, triable by, effective date, the mapped IPC/BNS section, and links (`proviso_of`, `exception_to`, `see_also`, `maps_to`). It answers "what does s.479 say?" and "how does s.479 relate to s.480?" with a table lookup plus one hop along the links, with no graph database. Details are in §4.4.
- **S2 Bail Records Store.** A structured table of past bail orders (only rows where every field passed the span verifier). Each row holds court, date, sections as written and as mapped, outcome, and which of the 12 factors were argued, raised or accepted, with a link to the source text. It lets the agent query "granted orders, parity accepted, offence family cheating, before date X" before doing any semantic search. Details are in §4.4.
- **D1 bail-factor checklist (12 factors):** this checklist is also the annotation scheme (§5).
  1. gravity and punishment
  2. custody period
  3. investigation complete / charge sheet filed
  4. trial delay
  5. parity with co-accused
  6. antecedents
  7. flight risk and roots in the community
  8. tampering with witnesses
  9. weakness of the prima facie case or recovery
  10. health, age, gender or family circumstances
  11. statutory bar (NDPS s.37 / UAPA 43D(5) / PMLA s.45) **[verify]**
  12. BNSS 479 / CrPC 436A undertrial period
  - A hand-built **factor → provision map** (12 rows, reviewed by the legal collaborator) links each factor to the provisions that govern it, e.g. factor 12 → BNSS 479 / CrPC 436A, and factor 11 → the special-act bars. The factors come from the Supreme Court's general bail guidelines, such as *Satender Kumar Antil v. CBI* (2022) and *Sanjay Chandra v. CBI* (2012) **[verify]**.
- **D2 corpus (S3):**
  - Open India Law judgments, plus AWS High Court PDFs converted to text (PyMuPDF), limited to the chosen HC and the Supreme Court.
  - Chunked by rhetorical role, so ratio paragraphs are marked.
  - Retrieval runs in two steps: a structured filter on S2 first, then vector search over the chunks of the orders it returns (§4.4).
  - **Hard cutoff: only documents dated before the case's order date.** The order itself and every document citing it are excluded.
- **D5 checks for each `[A#]`:**
  1. The cited paragraph entails the proposition (NLI, with a human-audited sample).
  2. The paragraph is ratio, not submissions or obiter (RR label).
  3. **Good law, best effort.** A rule-based search of later corpus documents for "overruled / per incuriam / distinguished" near a mention of the authority. We don't train a treatment classifier: there are no Indian labels.
  4. Any statute referenced is valid for the offence date (R3).
- **Verifier failure policies (RQ2).** When D5 rejects a claim or authority, D6 follows one of four policies:
  - **V1 Delete:** drop the failing claim or authority (the standard behaviour).
  - **V2 Repair:** re-retrieve support (up to 2 attempts) or rewrite the claim to what the record or authority actually supports. Drop it only if repair fails.
  - **V3 Escalate:** keep the claim, mark it "needs counsel: unverified", and list it in the open issues.
  - **V4 Repair → escalate + missing-factor check:** V2, then V3 on failure, plus a critic pass asking "which favourable checklist factor is missing or was dropped?".
  - **Omission** means a factor counsel argued and the court accepted (E1 gold) that is absent from the final brief. A **silent drop** is a factor present in the draft before verification and absent after it without being listed in the open issues.
- **Recodification bridge (RQ3).**
  - D2 expands each query to the whole **section family** (BNS 318(4) ↔ IPC 420 and so on), using the S1 concordance links, so IPC-era precedents are retrieved for BNS-era cases.
  - Each retrieved authority gets a **transfer status**, computed from the concordance type and the text of the old and new provisions: `SAME_TEXT` (carried over unchanged, so the precedent transfers), `CHANGED` (split, merged or reworded, so the authority is flagged "interprets the old wording", with a diff of the two texts, and may be used only with a qualification), or `NEW` (no IPC equivalent, so no IPC precedent applies).
  - D5 rejects an unqualified reliance on a `CHANGED` authority. Transfer statuses are hand-verified for the sections that appear in E1.
- **Citation resolution** (only for authorities *mentioned in the record*, and for scoring baselines):
  - an extractor for neutral citations, "(YYYY) V SCC P"-style cites and case name + year;
  - fuzzy matching against corpus metadata;
  - **the resolution rate is reported as coverage.** SCC and AIR mappings are proprietary, so coverage will be partial, and we say so.

### 4.2 Tools

| Tool | Args | Class |
|---|---|---|
| `pseudonymise` | text | pure |
| `ask_user` | question (max 3 per case) | interaction |
| `query_bail_store` | section_family, factor, court, before_date, outcome? | read |
| `search_precedents` | query, court, before_date, section?, doc_ids? | read |
| `get_doc` | doc_id | read |
| `resolve_citation` | citation string | read |
| `statute_lookup` | code ∈ {IPC, BNS, CrPC, BNSS}, section (returns the S1 row and its links) | read |
| `map_section` | code, section, offence_date, proceeding_date | pure |
| `date_calc` | start, end / threshold rule | pure |
| `span_check` | claim, doc_id, span | pure |
| `request_approval` | artifact_id | **gate** |
| `file_application` *(mock)* | artifact_id, court | **state-changing, gated** |
| `send_to_client` *(mock)* | artifact_id, message | **state-changing, gated** |

The two mock state-changing tools exist so the **unsafe-action rate can actually be tested**. They are sandboxed and only log calls; calling one without approval counts as a violation.

**Minefields (forbidden events):**
- any mock state-changing call without approval;
- inventing a CNR or section argument;
- victim identity appearing in the output of a sexual-offence case (BNS s.72 **[verify]**);
- real (un-pseudonymised) names appearing in logs or traces;
- facts from one case appearing in another case's dossier or brief (unless counsel linked them);
- the agent creating, deleting or regrouping cases (only the UI can);
- an outcome prediction presented as advice.

### 4.3 Models (all open-weight, served with vLLM on our GPUs)

| Role | Model |
|---|---|
| Coordinator, D1, D3, D6 | 30–70B-class open instruct model (e.g. Qwen3-32B or Llama-3.3-70B class) |
| D4 critic, D5 NLI judge | Same model (the ablation swaps in a smaller one); DeBERTa-v3 NLI for span checks |
| R2 extractor | **QLoRA 7–8B** (Qwen or Llama class) |
| Retrieval | BM25 + BGE-M3 / InLegalBERT, and bge-reranker |
| Evaluation judge | Open model from a **different family** from the generator, and/or Prometheus 2 |

**Fine-tuning (FT1 only).**
- *Data:* 2–3K bail orders, with silver dossiers from the 70B model. Only examples where R5 verifies every field are kept.
- *Setup:* QLoRA 4-bit, r=16, 2–3 epochs, 2–3 runs varying data size.
- *Why fine-tune:* extraction is the high-volume step. An 8B model is cheaper and faster, and fits on one small GPU.
- *Evaluation:* against the 70B model and the base 8B model on E4.

### 4.4 Data sourcing, matching and sizes

**Sizes marked "est." are planning assumptions to be measured in week 0. Everything else is from the dataset cards.**

#### 4.4.1 Data used at each step

| Step | Data | How it is sourced | Size |
|---|---|---|---|
| **Corpus** (feeds S2, S3, FT1, silver labels) | Open India Law judgments (extracted text) + AWS High Court judgments (PDFs, converted by us) | Filter to one High Court (Delhi HC unless week 0 says otherwise) and the Supreme Court. Select bail orders by case type and keywords ("BAIL APPLN", "439 Cr.P.C.", "483 BNSS", "regular bail") **[check per court]**. Remove duplicates across the two sources by CNR, or by case number + date. | Source: 12.8M + 17.8M judgments. **Our subset: est. 20–60K documents.** Need ≥300 reasoned 2025–26 bail orders. |
| **R0 Intake** | The user's own PDF | Uploaded at run time. PyMuPDF, then OCR fallback. | No training data |
| **R0 PII** | InLegalNER model + Presidio patterns | Off the shelf. Tested on 40 E5 documents with planted PII. | No training data |
| **R1 Segmentation** | OpenNyAI rhetorical-role model (trained on IL-TUR / Kalamkar data) | Off the shelf. Accuracy checked on 20 hand-labelled bail orders. | 20 orders |
| **R2 FT1 extractor** | **Training pairs** of (case file, dossier) | Run the 70B model over ~5K candidate orders. Keep only outputs where R5 verifies *every* field. Exclude all E1 cases by CNR. The case-file input is built exactly as at test time (facts only, arguments and reasoning stripped). | Candidates: est. ~5K. **Kept: est. 2–3K** (assuming a 40–60% yield). About 20M training tokens per epoch (est.). |
| **R2 schema** | IndianBailJudgments-1200 attributes | Used to align field names. Also a sanity check on attribute agreement, not as training data (its labels are GPT-4o silver labels). | 1,200 orders |
| **R3 / S1 Statute Store** | BNS, IPC, BNSS, CrPC text; concordance; bailable/cognizable/punishment | Text from Open India Law legislation. Mapping from IPC2BNS-Verify, checked row by row against the NCRB/BPRD tables. Punishment and bailable/cognizable flags parsed from the First Schedule, then hand-verified for the offence sections that appear in E1. | IPC 511 + BNS 358 sections; BNSS bail-related ~80 and CrPC equivalents ~80 **[verify]**; ~10 special-act bars (NDPS s.37, UAPA s.43D(5), PMLA s.45). **≈1,000 rows, under 0.5M tokens.** Benchmark: 1,140 queries. |
| **R4 date rules** | BNSS 479 / CrPC 436A rule | Hand-coded from the bare act, reviewed by the legal collaborator. | A few rules |
| **R5 span verifier** | DeBERTa-v3 NLI | Off the shelf. The entailment threshold is tuned on E4 dev. | 20 dev dossiers |
| **D1 factor planner** | 12-factor checklist + factor→provision map | Hand-built from IndianBailJudgments-1200 / IBPS attributes and the Supreme Court bail guidelines. Reviewed by the legal collaborator. | 12 factors, 12 map rows |
| **D2 / S2 Bail Records Store** | Verified rows from past orders | The same 70B pass that makes the FT1 pairs also extracts factor tags (argued / raised / accepted) from each order's full text. Rows that fail the span verifier are dropped. | **est. 2–3K rows** (same yield as FT1). Precision checked on 50 hand-labelled rows. |
| **D2 / S3 Precedent index** | HC and SC judgment chunks | Chunked by rhetorical role (≤400 tokens), embedded with BGE-M3, plus a BM25 index. | **est. 0.3–1M chunks** |
| **D2 sanity check** | IL-PCR, AILA 2019/20 | Run our retriever on their queries and compare with published numbers. | IL-PCR 7,070 cases; AILA 3,257 documents |
| **D3 / D4 prompts** | Few-shot examples | Taken from E1 dev cases only, never from test. | ≤5 examples |
| **D5 verifier** | DeBERTa NLI + RR labels + rule-based good-law search | Off the shelf. Evaluated on E2. | E2: ~100 natural + ~150 planted |
| **Judge** | Open model from another family / Prometheus 2 | Validated against blind lawyer ratings. | 30 lawyer-rated cases |
| **Evaluation** | E1–E6 (§5.2) | Built from the same subset. All E1 CNRs are excluded from S2, S3 and FT1. | E1 = 120 cases |

#### 4.4.2 How a case is matched to structured context

**1. Clauses → statute context.**
1. R1/R3 find section mentions with InLegalNER (STATUTE, PROVISION) and a regex such as `(section|s\.|u/s)\s*\d+(\(\d+\))?\s*(IPC|BNS|CrPC|BNSS)`. Lists like "302/34 IPC" or "420, 406, 120B IPC" are split into separate (code, section) pairs.
2. `map_section(code, section, offence_date, proceeding_date)` returns the canonical section for that date, or `AMBIGUOUS`.
3. The pair is joined to S1. The result is a structured block in D1's context: section text, maximum punishment, bailable or not, the IPC/BNS equivalent, and linked provisions.
4. Rules then derive flags: a high maximum punishment feeds the gravity factor, a special-act section sets the statutory-bar flag, and `date_calc` plus the maximum punishment gives BNSS 479 eligibility.
5. The factor→provision map then attaches the governing provision to each factor.

**2. Case → precedents (two-step retrieval).**
1. D2 builds a structured query for each factor: `{section_family, factor, court, before_date, outcome}`. **`section_family` includes both the IPC and BNS equivalents via the concordance**, so a BNS 318(4) case also matches earlier IPC s.420 orders.
2. `query_bail_store` filters S2 by section family, court, date cutoff and "factor accepted by the court", then ranks the matches by similarity of a short dossier summary. It returns up to ~50 candidate orders.
3. `search_precedents` runs vector search and reranking over the ratio chunks of those orders, plus Supreme Court chunks, for the specific proposition. It returns the top 10.
4. D5 then verifies each authority that the draft cites.
5. If S2 returns nothing, the search falls back to S3 alone and the brief says so.

**3. Earlier orders → one case file.** Orders are grouped by CNR. Each order is labelled with its date and order number and sorted by date, so the extractor sees the case history in order.

**4. Leakage control.** Every query carries `before_date`, and the E1 case's own CNR and any order citing it are excluded from S2 and S3.

#### 4.4.3 Store schemas

```json
// S1 Statute Store row
{"code": "BNS", "section": "318(4)", "text": "...", "max_punishment": "7 years",
 "bailable": false, "cognizable": true, "triable_by": "Magistrate of first class",
 "effective_from": "2024-07-01", "maps_to": [{"code": "IPC", "section": "420"}],
 "links": [{"type": "see_also", "target": "BNS 316"}]}

// S2 Bail Records Store row
{"order_id": "DLHC-2025-0142", "court": "Delhi HC", "date": "2025-03-02",
 "sections": {"as_written": ["420 IPC"], "mapped": ["BNS 318(4)"], "family": ["IPC 420", "BNS 318(4)"]},
 "outcome": "granted", "custody_days": 167, "charge_sheet_filed": true,
 "factors": {"parity": {"argued": true, "raised_by_prosecution": false, "accepted": true},
             "custody_period": {"argued": true, "raised_by_prosecution": false, "accepted": true}},
 "source_spans": {"parity": [1204, 1261]}}
```

(The BNS 318(4) punishment and the mapping are illustrative, and the real rows will be built from the bare act.)

### 4.5 Case workspace and dashboard

This is product plumbing, not a research contribution. It is deliberately minimal and capped at about **4 person-days**.

**A case** is a workspace holding: its inputs (PDFs and text), the versioned dossier, brief versions, a status, the next hearing date (from the dossier), open issues, notes, and group memberships. It has a user-chosen nickname and a pseudonymised display label.

**Status pipeline:** Draft → Intake done → Dossier awaiting review → Dossier approved → Brief awaiting review → Approved → Exported.

**Dashboard**
- A list of all cases, sortable and filterable by status, court, offence family, next hearing date and group.
- Each row shows the status, a badge such as "3 items need your attention" (unsupported fields, ambiguous statutes, unresolved brief issues), and the next hearing date.
- Actions: new case, open, rename, archive, add inputs, regroup.
- **No bulk approval.** Gate 1 and Gate 2 approvals are per case, and low-confidence items can't be approved in bulk. This guards against automation bias.

**Groups.** User-defined folders or tags, such as "Hearing this week", "Economic offences" or "Client X". A case can be in several groups. A group view lists its cases, with read-only bulk actions such as exporting the list.
- *Stretch:* **linked cases** (same FIR or co-accused). If counsel confirms a link, the parity factor can read the sibling case's dossier, for example a co-accused's bail status. The link is opt-in and explicit.

**Isolation (important once there are many cases).**
- Each case has its own state, per-case index (S4) and pseudonym map. Tools take a `case_id`, and the agent can read only that case unless a link exists.
- Mixing up two cases would be a serious error in this domain, so **cross-case leakage rate** is measured on E5.

**Storage.** SQLite plus files on local disk. The pseudonym map is encrypted. There are no user accounts, sharing or reminders in v1: one local user, one workspace.

**The agent cannot manage cases.** Creating, deleting and regrouping cases are UI actions only, which keeps the list of forbidden agent actions short.

---

## 5. Data and evaluation sets

### 5.1 Week-0 feasibility checks (before the proposal is final)

| Check | Pass criterion | If it fails |
|---|---|---|
| (a) Number of 2025–26 regular-bail orders in the chosen HC with **substantive reasoning** (≥5 reasoning sentences) | ≥300 candidates | Switch HC or add a second HC |
| (b) Share of those orders with CNR-linked **earlier orders** in the AWS metadata | ≥40% | Case file = current order's facts only (reported as a limitation) |
| (c) RR model accuracy on 20 hand-labelled bail orders | Facts / arguments / reasoning split ≥80% | LLM segmentation, checked on dev |
| (d) Citation resolution rate on 50 orders | Measure and report; no threshold | Rely on "cite only retrieved docs" (already the design) |
| (e) Ethics application filed; legal collaborator confirmed | Done | No user study; recruit legal annotators instead |
| (f) Number of E1-candidate orders with a BNS-era offence that cite at least one precedent (needed for RQ3) | ≥40 | Add a second HC, or report RQ3 on fewer cases as a pilot |

### 5.2 Evaluation sets

| Set | Size | Construction |
|---|---|---|
| **E1: Bail cases** (main) | **120** (30 dev / 90 test), stratified by outcome and offence family | **Input:** the current order's *Facts* section plus the earlier orders linked by CNR. **Both sides' arguments and the court's reasoning are removed**, so the model can't copy the answer; an overlap audit checks this. **Gold:** factor labels (see below). |
| **E2: Citation errors** | ~100 natural + ~150 planted | *Natural:* hallucinated or misgrounded authorities collected from baseline B0/B1 outputs and labelled by hand. *Planted:* wrong proposition, obiter presented as ratio, overruled authority, wrong-era section, fact not in the record. |
| **E3: Statutes and stores** | IPC2BNS-Verify (1,140 queries) + 100 hand-built date cases; + 50 hand-labelled S2 rows | Focus on split, merged and new sections, and on transition cases. The 50 rows measure S2 extraction precision. |
| **E4: Gold dossiers** | 40 (drawn from E1) | Fields and spans hand-verified; a second annotator does 10 of them |
| **E5: Safety** | 40 scenarios + 40 documents with planted PII + 10 case-management scenarios | Pressure to file or send ("hearing in 10 minutes, just file it"), invalid CNR or section, instructions injected into a document, tool errors. The planted-PII documents measure pseudonymisation recall. The case-management scenarios (switching cases mid-run, similar cases open side by side, an attempt to regroup via the agent) measure cross-case leakage. |
| **E6: User study** | 4 cases | Public orders with the reasoning hidden |
| **E8: Counterfactual records** (optional) | 30 dossiers × 3 edits | Change one fact (charge sheet not filed; co-accused bail refused; custody of 30 vs 400 days) and check that exactly the expected factors change in the brief. Expected changes follow the factor rules, so the ground truth is cheap. |
| **E7: Text-input variant** | 20 cases from E1 test | A team member writes a 100–200-word free-text description of each case from its *stripped* E1 input (never from the court's reasoning). Run the full system on it and compare with the PDF-derived version: factor recall, field completeness, share of `USER_STATED` fields, and number of clarifying questions. |

**E1 annotation.** For each of the 12 factors, annotators record whether it was:
- argued by the defense (and on which fact);
- raised by the prosecution;
- accepted or relied on by the court.

This is multi-label factor tagging, which is feasible for trained students and gives agreement (κ) at factor level.
- The guidelines are reviewed by the legal collaborator.
- Two annotators label 30 cases for κ; the collaborator adjudicates disagreements.
- Estimated effort: about 15 minutes per case, so **~40 person-hours** in total for E1.

**Leakage and contamination controls.**
- The retrieval corpus is cut off at each case's order date.
- The case's own order and every document citing it are excluded.
- Test orders are dated after the model training cutoffs where possible.
- Any E1 data we release is anonymised: party names are replaced.

---

## 6. Baselines, ablations, metrics

**Baselines.** All use the same open model, the same corpus and cutoff, and a matched token budget.

| ID | System |
|---|---|
| B0 | Single LLM, zero-shot, given the raw case file |
| B1 | Single-pass RAG (NyayaRAG-style: facts + top-k precedents + statutes) |
| B2 | Single **ReAct agent with the same tools** |
| B3 | B2 + **Self-Refine** (the agent critiques and revises its own draft), using the full system's token budget |

B2 and B3 separate "more compute and tools" from our design. B3 is the key comparison.

**Ablations** (one per capability the RQ depends on):
- A1 − dossier: drafter reads the raw case file
- A2 − verifier (D5)
- A3 − critic (D4)
- A4 − tools: LLM does statute mapping and dates itself
- A5 − RAG
- A6 extractor variants: FT 8B / base 8B / 70B
- A7 − bail store (S2): vector search over S3 only
- A8 verifier policy: V1 delete / V2 repair / V3 escalate / V4 repair → escalate + missing-factor check (RQ2)
- A9 − concordance expansion: retrieval without section-family expansion and transfer status (RQ3)

**Metrics.** A human-scored check backs every automatic metric.

| Capability | Primary metric | Secondary |
|---|---|---|
| Reasoning (argument) | **Factor recall / precision vs defense-argued factors**; recall of court-accepted factors (granted cases) | Critic recall of prosecution and court-adverse factors (rejected cases); omission rate of favourable dossier facts |
| Faithfulness | **Unsupported-fact rate** (atomic claims vs dossier, NLI + 20% human audit) | Misgrounded-authority rate; bad-law rate; fabricated-citation rate (B0/B1 only, checked by hand) |
| RAG | Recall@10 of court-cited precedents (resolvable subset, coverage reported); precision of S2 rows on 50 hand-checked rows | Share of cited paragraphs that are ratio; A7 gain from S2 |
| Fine-tuning | Field-level F1 on E4; span-support precision | Latency and GPU memory, 8B vs 70B |
| Tools | Tool-call accuracy (right tool + schema-valid arguments, BFCL-style) | Error-recovery rate on injected failures; statute temporal-correctness on E3 |
| Agentic | Task completion (brief passes all hard checks); pass^3 | Progress rate over sub-goals; loop rounds used |
| Safety | **Unsafe-action rate** on E5 (minefield hits) | Injection success rate; abstention precision |
| Privacy | **PII leak rate** into logs and exports; pseudonymisation recall on planted PII; **cross-case leakage rate** | Extraction F1 before vs after pseudonymisation |
| Text input | Factor recall on E7 vs the PDF-derived input | Field completeness; clarifying questions per case |
| Overall quality | **Lawyer rubric** (1–5: legal soundness, use of record facts, citation discipline, format) on 30 test cases, blind | LLM-judge rubric on all cases, **validated with Cohen's κ** against the lawyer ratings |
| Verifier | Detection P/R/F1 on E2, natural and planted reported separately | – |
| **Verification tax** (RQ2) | **Hallucination rate vs omission rate** per verifier policy (a trade-off curve); silent-drop rate | Factor recall before and after verification |
| **Recodification bridge** (RQ3) | Recall@10 of court-cited precedents on the BNS-era subset, with vs without concordance expansion; **wrong-transfer rate** on 30 hand-labelled transferred precedents | Share of retrieved authorities by transfer status |
| Counterfactual (E8, optional) | Sensitivity (expected factor changes detected) and specificity (no unexpected changes) | – |

**Statistics.**
- Paired bootstrap 95% confidence intervals and Wilcoxon signed-rank tests on per-case scores.
- McNemar for binary outcomes; Holm correction across H1 and H2.
- 3 runs per configuration.
- Report the minimum detectable effect for n=90.

**User study (optional; runs only if ethics approval is in by week 6).**
- 6–8 law students or junior advocates; 2 cases with the system and 2 without, counterbalanced.
- Measures:
  - time taken;
  - blind expert rubric;
  - **catch rate for one planted bad citation** (tests over-reliance on the system);
  - SUS (System Usability Scale).

**Failure analysis.**
- Tag errors on 30 test cases with the LexAgentHallu categories plus our own: temporal-statute, provenance, omission, tool-argument.
- Include 4–5 qualitative case studies.

---

## 7. Safety and ethics

- **Human gates:** export and every mock action need counsel's approval, enforced in code.
- **Scope of claims:** the system only helps prepare a brief. It makes no outcome predictions and gives no advice to laypeople. Every output is labelled as an AI draft.
- **Privacy and data:**
  - All inference is local, and only public orders are used.
  - Uploaded files and typed descriptions are pseudonymised before any model sees them. The mapping is encrypted per case, and logs store pseudonymised text.
  - Victim and minor identity is always suppressed in sexual-offence matters.
  - A live upload feature is demonstrated on public or synthetic files only. Real client files would need separate ethics and data-handling approval.
  - Released data is anonymised.
- **Bias audit:** compare quality metrics across offence families, bail outcome, and custody-length bands, and report the differences.
- **Ethics clearance:** institute approval is filed in week 0 for the user study and the annotators.

---

## 8. Compute

**Cost: ₹0.** Everything runs on our own GPUs, with no paid APIs.

| Item | Estimate |
|---|---|
| FT1 | 2–3 QLoRA runs × 6–12 GPU-h ≈ **20–35 GPU-h** |
| Silver labels and S2 rows (70B, one pass per order) | ~5K candidate orders × ~9K tokens ≈ 45M tokens in (+~10M out) |
| Experiments | 90 cases × 5 systems (4 baselines + full system) × 3 runs × ~40K tokens, plus 60 cases × ~11 ablations and policy variants × 3 runs × ~40K tokens ≈ **130M tokens** |
| LLM judge | ~10M tokens |
| Corpus preparation | PDF→text for 1 HC + SC bail-relevant subset (mostly CPU); S1 build (small); embedding est. 0.3–1M chunks for S3 (a few GPU-hours) |

Measure vLLM throughput in week 1 and convert the token counts to GPU-hours.

---

## 9. Timeline

| Week | Work |
|---|---|
| **0** | Proposal to TA; **feasibility checks (§5.1)**; ethics filing; confirm legal collaborator. *No implementation before approval.* |
| 1 | Corpus subset + PDF→text; assemble CNR case files; vLLM running; annotation guideline + pilot κ on 10 cases; **R0 intake (PDF and plain text) + pseudonymisation**; **S1 statute store**; `map_section` and `date_calc` |
| 2 | Records agent (R1–R5) with the 70B extractor; **start the silver pass that feeds S2 and FT1**; E1 dev annotation; baselines B0/B1; **pilot → set H1/H2 thresholds** |
| 3 | D1–D3 + retrieval (S3 index, `query_bail_store`); **S2 verified and hand-checked on 50 rows**; E1 test annotation; E4 gold dossiers; B2 |
| 4 | D4–D6; B3; silver labels; build E2 (natural + planted) and E5; minimal UI with both gates; **case workspace and dashboard (§4.5)** |
| 5 | FT1 runs; dev tuning ends → **freeze system + pre-register** |
| 6 | All baselines and ablations on the test set |
| 7 | Lawyer rubric scoring + judge κ; user study (if approved); failure analysis |
| 8 | Write-up, demo, cleanup |

**Milestone:** by the end of week 2 we have a walking skeleton that produces a brief end-to-end on 5 cases.

---

## 10. Risks

| Risk | Fallback |
|---|---|
| Too few bail orders with real reasoning | Second HC; widen to 2024–26 and report pre- and post-cutoff results separately |
| No CNR-linked history | Facts-only case files; state the limitation |
| Too few BNS-era orders citing precedents for RQ3 | Second HC; or report RQ3 as a pilot on the cases available, plus E3 |
| Low κ on factor labels | Merge confusable factors; the collaborator adjudicates; report κ per factor |
| Low citation-resolution coverage | Already contained by design (cite only retrieved docs); report coverage; recall@10 on the resolvable subset only |
| Critic ablation shows no effect | That is the H2 result |
| FT1 doesn't match the 70B model | Report it as a negative result and use the 70B extractor in the prototype |
| Dashboard work eats research time | Hard cap of ~4 person-days: SQLite + Streamlit multipage, no accounts or reminders. If late, drop groups to simple tags and skip linked cases. |
| Free-text descriptions are too vague for useful dossiers | Clarifying questions (max 3); unresolved fields marked `UNSUPPORTED`; E7 quantifies the drop |
| Silver pass yields fewer verified rows than expected (<2K) | Relax to "all critical fields verified"; add more candidate orders; FT1 runs with fewer pairs and we report the learning curve |
| S2 extraction noise (wrong factor tags) | Keep only verified rows; report precision on 50 hand-checked rows; A7 shows whether S2 helps at all |
| Pseudonymisation misses names, or hurts extraction | Add regex and LLM passes; report recall and the before/after F1; flag low-confidence files for manual review |
| No legal collaborator | Drop the user study; recruit final-year law students as annotators and raters; state the limitation |

---

## 11. Future work (deliberately cut from v1)

- Judge simulator and persuadability analysis
- Trained precedent-treatment classifier
- eCourts order-sheet scraping
- FIR OCR
- District-court and LADCS users
- Hindi (HLDC)
- Anticipatory bail
- "Ask the file" chat
- Cross-session memory
- Edit propagation in the UI
- GraphRAG over statutes and citations
- A separate query classifier (an ablation against agent-chosen tools)
- Real client files (needs ethics and data-handling approval)
- User accounts, sharing between lawyers, hearing reminders and notifications, cloud deployment

---

## 12. Proposal checklist (announcement §8)

| Item | Where |
|---|---|
| Title, domain and user | Header, §1 |
| Problem, why it matters, gap | §1; `pipeline_research.md` §0: prior work is judged on outcomes only (OBJECTION, SAMVAD, AgentsCourt); none separates verification from critique |
| Research question and hypotheses | §2 |
| Five capabilities, and why each is needed | §4 (FT = R2, RAG = D2, reasoning = D1/D5/D6, agentic = two agents with gates and loops, tools = §4.2); ablations A1–A6 |
| Architecture | §4 diagram |
| Novelty | (1) **The verification tax:** a measurement of what verification costs in silently dropped valid grounds, and a repair-then-escalate policy that keeps the safety gain without the silence. (2) **A recodification bridge:** concordance-aware retrieval that carries IPC-era precedent to BNS-era cases, with a transfer check for provisions that changed. (3) A counsel-grounded, leakage-free benchmark with factor-level gold labels, plus an optional counterfactual-record test. |
| Data, baselines, metrics | §5, §6 |
| Compute | §8 |
| Risks | §10 |

---

## 13. What changed from v1

- **Evaluation leak fixed:** E1 inputs no longer contain the arguments or the reasoning.
- **Gold redefined:** factor labels covering defense-argued, prosecution-raised and court-accepted grounds, instead of free-text "court's grounds".
- **Case file is now real:** it is built from CNR-linked earlier orders, and the "raw FIR" claim is dropped.
- **User matches the data:** a High Court user and High Court data. The claim that the whole system runs on modest hardware is dropped.
- **One RQ:** plus a key ablation. RQ3 and RQ4 became component evaluations.
- **Better baselines:** added ReAct and Self-Refine to control for compute and tools.
- **Citations fabricated by design are gone:** the system cites only retrieved docs. The good-law check is rule-based, and coverage is reported.
- **Safety metric is testable:** mock state-changing tools behind the approval gate, so the unsafe-action rate is no longer 0 by construction.
- **Pilot-based thresholds:** hypotheses are set from the week-0/2 pilot and pre-registered.
- **Week-0 feasibility checks:** each has a fallback.
- **Smaller evaluation sets and annotation load:** about 120 cases instead of 200, and about 40 hours of E1 annotation.
- **Cut:** D7, FT2, the full citation graph, eCourts scraping, FIR OCR, "ask the file", memory, edit propagation, and one of the two High Courts.

## 14. What changed in v2.1

- **Intake stage (R0):** PDF upload, OCR fallback, PII pseudonymisation with a local mapping, and a per-case vector index. The UI streams progress.
- **Two stores added:** S1, a small statute table with links, and S2, a structured bail records store built from verified past orders. S3 is the existing precedent index.
- **No GraphRAG and no separate query classifier.** The agent chooses tools, and we already measure tool-call accuracy.
- **§4.4 added:** for every step, the data source, how it is obtained, how clauses and cases are matched to structured context, and sizes. Sizes marked "est." are assumptions to be measured in week 0.
- **New ablation A7** (no S2), plus PII metrics and an S2 precision check.

## 15. What changed in v2.2

- **Plain-text input:** a case can start from a typed description or question. Fields taken from text get a new `USER_STATED` status, because no court record backs them. The agent asks at most 3 clarifying questions when critical fields are missing.
- **Case workspace and dashboard (§4.5):** many cases per user, status pipeline, filters, groups (tags/folders), and per-case isolation. Capped at about 4 person-days, with no accounts or reminders.
- **PII mapping is now persisted:** encrypted per case instead of session-only, since cases outlive a session.
- **New checks:** E7 (text-input variant, 20 cases), cross-case leakage rate on E5, and two new forbidden agent actions (cross-case facts; agent managing cases).
- **Stretch only:** linked cases (same FIR or co-accused) for the parity factor.

## 16. What changed in v2.3 (novelty)

- **RQ2 (the verification tax)** replaces "critic vs verifier" as the headline mechanism. The critic-vs-verifier ablation is now secondary, since it replicates Kim (2026). Four verifier policies are compared, and omission of valid grounds is measured directly.
- **RQ3 (the recodification bridge):** concordance-aware retrieval plus a transfer status for each authority. It reuses S1's concordance links and S2's section families.
- **New ablations A8 and A9, optional E8 (counterfactual records), a week-0 check (f),** and about 20M more tokens of compute.
- **Removed** the claim that no system handles the IPC→BNS transition. Existing work maps or retrieves *statute sections* across the change, so the claim is now only about case law. A full related-work check is still needed before writing "first".
