# plan.md (v3): NyayaSahayak, Verified Bail Preparation for Legal-Aid Counsel

> **One-line pitch.** A two-stage agentic system. It turns a High Court bail case file into a **verified dossier**, then into a **grounded bail brief** in which every claim links to a record fact or a retrieved authority. The main research question asks whether verification improves grounding, and **what each verifier failure policy costs in omitted valid grounds** (the verification tax). An exploratory question asks whether a **recodification bridge** can carry IPC-era precedent across to BNS-era cases.
>
> **Constraints.**
> - No paid services: every model is open-weight and runs on the IIIT Ada cluster or our workstation, and every corpus and tool is free.
> - The work fits in 8 weeks.
> - A lawyer approves every output.
>
> **Companion docs.**
> - [`proposal.md`](proposal.md) is the TA-facing summary. Its numbers match this plan exactly.
> - [`datasets_sources.md`](datasets_sources.md) lists data and papers.
> - [`pipeline_research.md`](pipeline_research.md) covers the landscape.
> - Items marked **[verify]** are legal details for the legal reviewer to confirm (§5.3).

---

## 1. Users and problem

**Primary user: High Court legal-aid panel counsel and junior advocates.** These are lawyers on High Court Legal Services Committee panels, or juniors in small criminal practices. They prepare **regular-bail applications in one High Court** under CrPC 439 / BNSS 483 **[verify]**. Their caseload is high and they have little research support.

We chose a High Court user because the public data exists at High Court level: bail orders, linked earlier orders, and precedents. That keeps user and data aligned. District-level LADCS counsel are a natural extension and are listed under future work.

**Problems they face:**
1. Case facts are spread across several earlier orders.
2. Since 1 July 2024, the right code (IPC or BNS, CrPC or BNSS) depends on dates, so section numbers are easy to get wrong.
3. Finding recent High Court authority on parity, delay or custody takes hours.
4. General-purpose LLMs invent facts and precedents.

**Why it matters.** Undertrials made up 75.8% of India's prison population at the end of 2022 (NCRB, *Prison Statistics India 2022*).

**What the users need, and how we measure it:**

| Need | System feature | Metric |
|---|---|---|
| Trust every fact | Each dossier field and brief claim links to a source span | Unsupported-claim rate (against the source text) |
| No fake or wrong authorities | Authorities come only from the retrieved corpus; each is checked for support, ratio and good law | Misgrounded rate, bad-law rate, untagged-citation rate |
| Correct sections | Date-aware statute tool | Temporal-correctness rate |
| Don't lose favourable grounds | Bail-factor checklist; verifier policies that repair or escalate instead of deleting silently | Answerable-factor recall; omission rate; silent-drop rate |
| Know the other side's case | Prosecutor-critic report | Recall of prosecution and court-adverse factors |
| Know when the system is unsure | Explicit `UNSUPPORTED` / `AMBIGUOUS` / `USER_STATED` statuses; "needs counsel" items | Abstention precision; escalation burden and precision |
| Ask about the file quickly | Grounded counsel chat | Tool-call accuracy and refusals on the scripted chat set (E5) |

**Non-users:** accused persons, the public and judges. The system prepares; it does not advise or predict outcomes. The chat is for counsel only.

---

## 2. Research questions

**RQ1 (main): grounding and the verification tax.** For High Court regular-bail preparation, does generating arguments from a verified dossier, with a verification loop, improve grounding over a matched-compute self-refining agent? And what does each verifier failure policy cost in omitted valid grounds?

- **RQ1a: grounding.**
  - *Comparisons:* the full system vs B3 (ReAct + Self-Refine at the same token budget) and B1 (single-pass RAG).
  - *Measures:* answerable-factor recall and the unsupported-claim rate.
- **RQ1b: the verification tax.** When the verifier (D5) rejects a claim or authority, the reviser (D6) applies one of four policies (§4.1):
  - **V1 delete**;
  - **V2 repair**;
  - **V3 escalate**;
  - **V4 repair → escalate, plus a missing-factor check**.

  We measure each policy on three axes:
  - **hallucination**: unsupported content presented as supported. Escalated claims are counted separately as the *shown-unverified rate*.
  - **omission**: at claim and at factor level.
  - **escalation burden**: "needs counsel" items per brief, and escalation precision.

  In defense work the errors are asymmetric. A fabricated authority embarrasses counsel, while a dropped valid ground can keep an undertrial in custody.

**RQ2 (exploratory): the recodification bridge.** New FIRs cite BNS sections, but most bail case law discusses the IPC sections they replaced. For BNS-era cases, we ask two questions:
- Does concordance-aware retrieval recover the IPC-era precedents the court actually cited? It is compared against fair baselines (§6).
- Does a *transfer check* flag precedents whose provision was split, merged or reworded?

RQ2 is labelled exploratory because the BNS-era test subset is small (est. 25–40 cases). We report n and CIs.

**Critic vs verifier: an ablation, not an RQ.** A2 (no verifier) and A3 (no critic) test whether the gains come from verification or from adversarial critique. This is an inference-time analogue of Kim's (2026, arXiv 2608.01559) training-time finding: there, the verification environment, not competition, drove the gains in adversarial legal self-play.

**Hypotheses**
- **H1 (RQ1a).** The full system beats B3 on answerable-factor recall and has a lower unsupported-claim rate (validated MiniCheck, §6). All baselines get the same 12-factor checklist in their prompt, so the gain is **net of the checklist**. A10 (no planner) isolates the planner itself.
- **H2 (RQ1b).** V1 gives the lowest hallucination rate but the highest omission rate. V4 has lower omission than V1, and its hallucination is non-inferior to V1's within a pre-registered margin δ.
  - **Burden guard.** So that H2 cannot be met by escalating everything, it counts as supported only if two further conditions hold:
    - V4's escalation burden (needs-counsel items per brief) is **below V3's**, i.e. repair reduces escalations;
    - V4's **escalation precision is ≥ p**.
  - p is pre-registered at the freeze, from the pilot. Both conditions are reported with CIs, outside the Holm family.
- **H3 (RQ2, exploratory).** On the BNS-era subset, section-family expansion raises recall@10 of court-cited *offence-specific* precedents over unfiltered dense retrieval and a popularity baseline. We also expect a non-trivial share of naive transfers across `CHANGED` provisions to produce a wrong argument.

**Thresholds and pre-registration.**
- Thresholds, the margin δ and the minimum detectable effect come from a **full-loop pilot on all 30 dev cases** in week 5.
- They are pre-registered at the freeze, as a tagged git commit whose SHA-256 is recorded (or on OSF).
- A null result on any hypothesis is still a finding.

**Component evaluations** are reported but are not research questions:
- the fine-tuned extractor vs a prompted 32B model (A6);
- span-checked extraction vs "just ask an LLM" schema filling (A12), which tests whether the dossier pipeline beats simply prompting an LLM with the schema;
- the statute resolver (E3);
- citation-resolution coverage.

---

## 3. Scope

| In | Out (future work, §11) |
|---|---|
| Regular bail in **one** High Court (Delhi HC unless the week-0 check says otherwise), with a second HC only as a fallback | Anticipatory bail, trials, appeals, district courts |
| English orders from 2025–26, covering both IPC-era and BNS-era offences (stratified) | Hindi, FIR OCR, eCourts scraping |
| **Excluded:** sexual-offence, POCSO and juvenile matters (declined at intake and excluded from E1, §7) | Those matters, once identity-protection handling is designed and approved |
| Case file = the order's facts plus earlier orders linked by **FIR number + police station** and by CNR | Raw FIRs and charge sheets (not public) |
| **Input:** case-file PDFs and/or a chat description from counsel, plus a **grounded counsel chat** for clarifying questions and questions about the file | Lay-user chat, open-ended legal Q&A |
| **Case list:** create, open or resume a case; status; an "items need attention" count; per-case isolation | Groups, folders, tags, filters, linked cases, bulk views, accounts, reminders |
| Pseudonymisation → per-case index → two agents → two human gates, in a minimal Streamlit UI with streamed progress | Judge simulator, cross-session memory, edit propagation, GraphRAG, a separate query classifier, real client files |

---

## 4. System

```
 Input per case: PDF upload and/or chat description          (public or synthetic files in evaluation)
 Minimal case list (§4.5): create / open / resume; status; "items need attention" count
   │
   ▼
 INTAKE (R0)
   PDF → text (OCR fallback) | chat text as is → PII pseudonymisation (local encrypted map) → per-case index (S4)
   matter-type check: sexual-offence / POCSO / juvenile → declined with a message
   │
   ▼
 COURT-RECORDS AGENT
   R1 Segment + NER        rhetorical-role model, InLegalNER
   R2 Extract              fine-tuned Qwen3-4B (QLoRA); dossier JSON with a source span for every field
   R3 map_section ⚙        IPC↔BNS / CrPC↔BNSS by offence date → AMBIGUOUS if unclear; joins S1
   R4 date_calc ⚙          timeline, custody days, BNSS 479 check
   R5 Span verify          DeBERTa-v3 NLI: does the span entail the field? If not → re-extract once → UNSUPPORTED
   CHAT                    ask_user: ≤3 clarifying questions (answers → USER_STATED);
                           counsel's questions → case_lookup / statute_lookup / map_section / date_calc, cited; else abstain
   ── HUMAN GATE 1: counsel checks and corrects the dossier ──
   ▼
 DEFENSE AGENT (Qwen3-14B-AWQ)
   D1 Factor planner       12-factor checklist → favourable / adverse, each with fact IDs and provisions
   D2 Retrieve             per factor, the agent picks tools: S1 statute lookup · S2 bail-store query · S3 search;
                           section-family expansion (IPC↔BNS); hard date cutoff
   D3 Draft                one ground per factor; each sentence cites [F#] facts and [A#] authorities
   D4 Prosecutor critic    objections, counter-authorities, missed favourable facts
   ── branch point: V1–V4 all start from this pre-verification draft ──
   D5 Verifier ⚙+NLI       claim support (DeBERTa NLI) · ratio vs obiter · good-law keywords · statute validity
                           · transfer status (SAME_TEXT / CHANGED / NEW) · untagged case-name/section check
   D6 Revise               ≤2 rounds under policy V1/V2/V3/V4; open issues listed
   ── HUMAN GATE 2: counsel approves; only then can the brief be exported ──
 ⚙ = deterministic tool

 KNOWLEDGE STORES (built offline, read-only at run time)
   S1 Statute Store        ≈1,000 rows: text, punishment, bailable/cognizable, IPC↔BNS links, our CrPC↔BNSS bail mapping
   S2 Bail Records Store   est. 8–12K verified past bail orders as rows (built by the fine-tuned extractor)
   S3 Precedent index      role-labelled chunks of HC/SC judgments (BM25 + BGE-M3)
   S4 Per-case index       built at upload time from the user's own file
```

**Design rules**
1. **Deterministic tools** handle dates, statute mapping and citation rendering.
2. **The drafter can only cite dossier field IDs `[F#]` and retrieved document IDs `[A#]`.**
   - The citation text is rendered from corpus metadata, so *fabricated citation metadata is prevented by construction*.
   - The drafter can still write a case name or section in free text. D5 therefore runs a regex/NER post-check for case names, neutral or reporter citations, and section mentions outside tags. Any hit counts as **fabrication**.
   - The remaining risks are misgrounding and bad law, and D5 checks those too.
3. **Uncertainty is never hidden.** `UNSUPPORTED`, `AMBIGUOUS`, `USER_STATED` and "needs counsel: unverified" are all shown to the user.
4. **Bounded loops.** Each loop has a step and token budget, and the full trace is logged.
5. **The model never sees real names.**
   - Intake replaces them with consistent pseudonyms (Accused-1, Co-accused-2, Victim-1).
   - The mapping is kept in an encrypted local store per case.
   - Real names are restored only in what counsel sees.
6. **No GraphRAG.**
   - The statute set is small enough for a table with a short list of links.
   - Open India Law has no citation graph.
   - Routing is done by the agent's tool choice, which we already measure, not by a separate classifier.

### 4.1 Components in brief

- **R0 Intake.**
  - **Text:**
    - PyMuPDF for PDFs with a text layer, with Tesseract or docTR OCR as fallback and a per-page quality check.
    - Non-English files are flagged, not processed.
  - **PII:**
    - InLegalNER (PETITIONER, RESPONDENT, JUDGE, LAWYER, WITNESS, OTHER_PERSON) plus Microsoft Presidio, with custom recognisers for phone numbers, Aadhaar-style 12-digit numbers, PAN, email and addresses.
    - Recall is measured on the 40 planted-PII documents in E5.
  - **Index:** chunks of ≤400 tokens, BGE-M3 embeddings, and an in-memory FAISS index (S4). S4 is used to find source spans and for chat look-ups.
  - **Matter-type check:** the section list and keywords flag sexual-offence, POCSO and juvenile matters, which are declined (§7).
- **Chat (counsel only).**
  - **Inputs:** counsel can start a case from a typed description, add one to uploaded PDFs, or ask questions. Each input becomes a source document of type `court_order` or `user_text`.
  - **Clarifying questions.**
    - Critical fields are the offence date, sections, arrest or custody date, court and co-accused status.
    - If any is missing, the agent asks at most 3 targeted questions through `ask_user`.
    - Whatever is still missing is marked `UNSUPPORTED`, and the pipeline continues.
  - **Trust level.**
    - A fact taken from `user_text` cannot be checked against a court record, so R5 only confirms that the extractor captured what the user wrote.
    - Such fields are marked `USER_STATED` and labelled as such in the brief.
    - If a court order added later contradicts a user statement, the field becomes `AMBIGUOUS` and both values are shown.
  - **Counsel's questions.**
    - Examples: custody days, charge-sheet status, "what does s.479 say?".
    - The agent answers through `case_lookup` (dossier and S4 span), `statute_lookup`, `map_section` or `date_calc`.
    - Every answer cites `[F#]`, an S1 row or a computed value.
  - **Abstention.**
    - If no tool result supports an answer, the chat says so instead of guessing.
    - It refuses outcome predictions and advice framed for laypeople.
    - It abstains on out-of-scope matters such as anticipatory bail, other courts, or Hindi files.
  - **`ask_user` in automated runs**, with the same policy for every system, including B2 and B3:
    - In E1 runs, `ask_user` returns "unknown", and the field is marked `UNSUPPORTED`.
    - In E6, a scripted responder answers only from the stripped E1 input. It uses a pre-written answer key per case and returns "unknown" for anything not in it.
  - **Evaluation:** the E5 chat set (116 queries, §5.2) and E6. Not an RQ.
  - **Interactive, not instant:** the full loop takes minutes per case, so the UI streams progress ("extracting… verifying… drafting…").
- **R1:** the OpenNyAI / IL-TUR rhetorical-role model and InLegalNER (`opennyaiorg/en_legal_ner_trf`). The RR model was trained on Supreme Court judgments, so week 0 measures its accuracy on bail orders (§5.1c).
- **Dossier fields (about 15).** Each field has a `value`, a `source_span` and one status: `VERIFIED` / `COMPUTED` / `UNSUPPORTED` / `AMBIGUOUS` / `USER_STATED` / `USER_ASSERTED` (the last means corrected by counsel at Gate 1). The fields are:
  - parties;
  - FIR number, police station and date;
  - offence date;
  - sections as written and as resolved;
  - arrest date and custody days;
  - whether a charge sheet was filed, and its date;
  - trial stage;
  - earlier bail applications and their outcomes;
  - co-accused bail status;
  - antecedents;
  - prosecution objections recorded in earlier orders;
  - health, age and family circumstances;
  - authorities cited in the record.
- **R3 `map_section`.**
  - It is built on the IPC2BNS-Verify concordance and its date-of-transition enforcement, which we credit, checked row by row against the NCRB/BPRD tables.
  - IPC2BNS-Verify's CrPC→BNSS coverage is thin, so we **hand-build the CrPC↔BNSS mapping for the bail provisions (~80 rows)**, spot-checked by the legal reviewer.
  - The substantive code is decided by the offence date.
  - For pending matters, the procedural code follows the BNSS s.531 savings clause **[verify]**.
  - **Only clear rules are encoded; everything else returns `AMBIGUOUS`.**
- **S1 Statute Store.**
  - One row per section: code, section, text, maximum and minimum punishment, bailable, cognizable, triable by, effective date, the mapped section, and links (`proviso_of`, `exception_to`, `see_also`, `maps_to`).
  - It answers questions like "what does s.479 say?" with a table lookup plus one hop along the links.
- **S2 Bail Records Store.**
  - A structured table of past bail orders. Each row records:
    - court, date and outcome;
    - sections as written and as mapped;
    - which of the 12 factors were argued, raised or accepted;
    - a link to the source text.
  - Only rows that pass the span verifier are kept.
  - It lets the agent query, for example, "granted orders, parity accepted, offence family cheating, before date X" before doing any semantic search.
- **D1 bail-factor checklist (12 factors).** The checklist is also the annotation scheme (§5).
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
  - A hand-built **factor → provision map** (12 rows, reviewed by the legal reviewer) links each factor to the provisions that govern it.
  - The factors come from the Supreme Court's general bail guidelines, such as *Satender Kumar Antil v. CBI* (2022) and *Sanjay Chandra v. CBI* (2012) **[verify]**.
  - **All baselines receive the same checklist in their prompt** (§6).
- **D2 corpus (S3).**
  - Open India Law judgments, plus AWS High Court PDFs converted to text, limited to the chosen HC and the SC.
  - Chunked by rhetorical role, so ratio paragraphs are marked.
  - Retrieval is a structured S2 filter, then vector search over those orders' chunks (§4.4).
  - **Hard cutoff: only documents dated before the case's order date.** The order itself, every document citing it, and every order sharing its FIR + police station are excluded (§5.2).
- **D5 checks for each claim `[F#]` / `[A#]`.**
  1. **Support.** DeBERTa-v3-large NLI on (claim, cited span or paragraph). Qwen3-14B only splits sentences into claims and drives repair; it does not judge support.
  2. **Ratio.** The paragraph is ratio, not submissions or obiter (RR label).
  3. **Good law, best effort.** A rule-based search of later corpus documents for "overruled / per incuriam / distinguished" near a mention of the authority. We train no treatment classifier, because there are no Indian labels.
  4. **Statute validity.** Any statute referenced is valid for the offence date (R3).
  5. **Transfer status.** Unqualified reliance on a `CHANGED` authority is rejected.
  6. **Untagged citations.** A regex/NER check for untagged case names, citations and sections (design rule 2).
- **Verifier failure policies (RQ1b).**
  - **V1 Delete:** drop the failing claim or authority (the standard behaviour).
  - **V2 Repair:** re-retrieve support (up to 2 attempts) or rewrite the claim to what the record or authority actually supports. Drop it only if repair fails.
  - **V3 Escalate:** keep the claim, mark it "needs counsel: unverified", and list it in the open issues.
  - **V4 Repair → escalate + missing-factor check:** V2, then V3 on failure, plus a critic pass asking "which favourable checklist factor is missing or was dropped?".
  - **Branching.** For each case and run, D1–D4 run once. All four policies then start from that same pre-verification draft. Policy differences are therefore caused by the policy alone, and the shared draft saves ≈48 node-hours (§8).
  - **Claim IDs** are tracked through D6. A claim that is rewritten keeps its ID and counts as *kept (modified)*, not as omitted.
  - **Claim-level omission:** a claim in the pre-verification draft that is absent from the final brief and not listed in the open issues, and that the *evaluation* checker (MiniCheck, §6; not D5) judges supported.
  - **Validation:** a hand audit of ~100 claims removed by V1 checks this definition.
  - **Factor-level omission:** an E1-gold factor (argued by the defense and answerable) that is present before verification and absent after.
  - **Silent drop:** any omission not listed in the open issues.
  - **Primary level.** In the pilot we measure how often V1 removes a whole factor. If this happens in under 5% of briefs, claim-level omission becomes the primary H2 measure, to avoid a floor effect.
- **Recodification bridge (RQ2).**
  - **Query expansion.** D2 expands each query to the whole **section family** (BNS 318(4) ↔ IPC 420 and so on), using the S1 concordance links.
  - **Transfer status.** Each retrieved authority gets one, computed from the concordance type and the old and new texts:
    - `SAME_TEXT`: the precedent transfers;
    - `CHANGED`: split, merged or reworded. The authority is flagged "interprets the old wording", shown with a diff, and may be used only with a qualification;
    - `NEW`: no IPC equivalent.
  - **Verification.** Transfer statuses are hand-checked for the sections in E1, and the legal reviewer spot-checks 10 of them.
  - **Procedural test case:** CrPC 436A → BNSS 479, the one-third rule for first-time offenders **[verify]**.
- **Citation resolution.** This applies only to authorities *mentioned in the record*, and to scoring baselines.
  - An extractor finds neutral citations, "(YYYY) V SCC P"-style cites, and case name + year.
  - These are fuzzy-matched against corpus metadata.
  - **The resolution rate is reported as coverage.** SCC and AIR mappings are proprietary, so coverage will be partial.

**Where the agent makes decisions** (this is what makes it agentic):
- **D2:** which tool to call for each factor, with which arguments, and whether to re-query.
- **D6:** for each failed claim under V2 or V4, whether to re-retrieve or rewrite, and when to stop, within ≤2 rounds.
- **Chat:** which tool answers a question, or whether to abstain.
- **Hand-off:** when to ask counsel through `ask_user`, and what to escalate.

A11 replaces the D2 decisions with a fixed script to measure their value.

### 4.2 Tools

| Tool | Args | Class |
|---|---|---|
| `pseudonymise` | text | pure |
| `ask_user` | question (max 3 per case) | interaction |
| `case_lookup` | case_id, field or query (dossier + S4 span) | read (current case only) |
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

**The mock state-changing tools.** These exist so the **unsafe-action rate can actually be tested**. They are sandboxed and only log calls. Any call made without approval is a violation. We report both **attempted** violations, which is the primary measure, and blocked ones, since the code blocks them all.

**Minefields (forbidden events)**
- Any mock state-changing call without approval.
- Inventing a CNR, case name, citation or section (an untagged mention, or one absent from the corpus).
- Processing a declined matter type (sexual-offence / POCSO / juvenile) beyond intake.
- Real (un-pseudonymised) names appearing in logs or traces.
- Facts from one case appearing in another case's dossier, brief or chat answer.
- The agent creating or deleting cases (only the UI can).
- An outcome prediction or lay-style advice in the chat or brief.
- Following an instruction embedded in a document.

**Tool-call gold.**

| Source | Annotated expected calls |
|---|---|
| E5 scenarios and chat queries | Tool and arguments, or "refuse/abstain" |
| E3 | `map_section` and `date_calc` arguments and outputs |
| E4 gold dossiers | Expected `map_section` calls for each section, and `date_calc` for custody |

Tool-call accuracy follows BFCL: the right tool, plus schema-valid and correct arguments.

**Injected tool failures** (in E5): timeout ×2, empty result ×2, schema error ×2, wrong-era section ×2. The recovery rate is the share in which the agent retries, falls back or escalates correctly.

### 4.3 Models (all open-weight; vLLM on Ada, or local)

Hardware details are in §8.1. All figures marked est. are measured in week 1.

| Role | Model | Precision / placement | Memory (est.) |
|---|---|---|---|
| Coordinator, D1, D3, D4, D6, chat; **all baselines** | **Qwen3-14B-AWQ** (non-thinking mode) | AWQ int4 weights, FP16 activations; TP=2 on 2× 2080 Ti; 2 instances per node | ~10 GB of weights (~5 GB/GPU), leaving ~50K KV tokens per instance. 32K native context; every call ≤24K tokens. |
| Silver teacher; "larger prompted model" in A6 | **Qwen3-32B-AWQ** | TP=4 (whole node) | ~20 GB of weights, leaving ~60K KV tokens |
| R2 extractor | **Qwen3-4B + QLoRA**; Qwen3-8B variant if it fits | Train: 4-bit base, FP16 compute, gradient checkpointing, 1× 2080 Ti. **Serve: merged, then AWQ/GPTQ int4 on 1× 2080 Ti** (4 instances per node), or int4 on the 4060. FP16 serving does not fit: ~8 GB of weights leaves only ~9K KV tokens. | ~2.5 GB int4, leaving ~45K KV tokens (≈4 concurrent 10.5K-token requests) |
| R5, D5 NLI | DeBERTa-v3-large NLI | FP16, sharing the GPUs with vLLM (capped at ~80% of memory) | ~0.9 GB |
| Retrieval | BM25 + BGE-M3; bge-reranker | FP16, co-located; FAISS in RAM | ~2–3 GB |
| **Evaluation judge** | **Mistral-Small-3.2-24B-Instruct**, a *text-only* community int4 quant (AWQ / GPTQ / AutoRound; the model is multimodal). Turing support and vLLM tokenizer mode (`mistral` vs HF) are checked in week 1. This is a different family from Qwen. | TP=4 | ~14 GB of weights. Fallback: Llama-3.1-8B-Instruct, FP16, TP=2 |
| **Evaluation claim checker** | MiniCheck-Flan-T5-Large (Tang et al., EMNLP 2024). This is a different family from the DeBERTa verifier. | FP16, 1 GPU or the 4060 | ~1.6 GB |
| Offline demo fallback | Qwen3-8B, 4-bit | Local 4060 | ~5 GB |

**Model choices**
- **No 70B model.** A 4-bit 70B model is ~35–40 GB of weights, which leaves no KV cache in 44 GB.
- **A 14B generator rather than 32B.** At TP=2, two copies fit on a node, roughly doubling throughput. The 32B model at TP=4 also pays all-reduce over PCIe.
- **Qwen3-30B-A3B (MoE) is not in the plan.** It would be faster, but AWQ-MoE support on Turing is uncertain, so it stays an untested option.
- **Non-thinking mode in every role.** Thinking mode would multiply output tokens beyond the budget. The reasoning structure lives in the pipeline instead.
- **Turing caveats.**
  - FlashAttention-2 is not available for sm_75 in stock vLLM, so long prefill is slower.
  - AWQ and Marlin kernel support on sm_75 has varied across vLLM versions, so we pin a working version in week 1 (check g).
  - Fallbacks: GPTQ int4; llama.cpp with GGUF; or Qwen3-8B in FP16 at TP=2.

**Fine-tuning (FT1)**
- **Data.**
  - Qwen3-32B silver-labels ~3K candidate orders (~15K input + ~3K output tokens per order across both tasks), producing two outputs per order:
    - a dossier from the *stripped* input, built exactly as at test time;
    - S2 factor tags from the full order.
  - Only examples where R5 verifies every field are kept, est. 1.2–1.8K orders at a 40–60% yield.
  - All E1 cases are excluded, by CNR and by FIR + police station.
- **Setup.**
  - QLoRA, 4-bit, r=16, 2 epochs, FP16 compute with gradient checkpointing.
  - Unsloth or PEFT with chunked cross-entropy, to keep the 151K-vocabulary logits within 11 GB.
  - 3 runs on Qwen3-4B (0.5K / 1K / all pairs, for a learning curve).
  - 1 run on Qwen3-8B if it fits at an ~8K sequence length. This run is **non-blocking**: the extractor decision in week 4 uses the 4B runs only.
  - BF16 fallback for FP16 instability: the 3 Qwen3-4B runs on the 4060 take ≈3 days continuous (108M tokens at an assumed 400 tok/s).
- **Why fine-tune.**
  - The tuned extractor makes corpus-scale S2 affordable on this hardware. Over all est. 20K bail orders, the 32B teacher would take ≈295 node-hours, against ≈30 for the tuned 4B in int4 (§8).
  - It also runs on the 8 GB workstation, est. ≈5 days for the whole corpus there.
  - This is the "small tuned model matches a larger prompted one" comparison.
- **Evaluation (A6).** The four variants are fine-tuned 4B (and 8B), base 4B, prompted 14B and prompted 32B. They are compared on:
  - field F1 and span-support precision on E4-test;
  - S2 size and precision;
  - node-hours per 1K orders.
- **A12: "just ask an LLM" (no span check).** The prompted 14B (the B0 model) and 32B models get the case file plus the dossier schema and fill it in one pass. No source spans are requested and R5 does not run. This is the approach counsel could take on their own. It is scored on E4-test against the same models *with* spans and R5 (from A6) on:
  - field F1;
  - **wrong-value rate**: filled values that disagree with the gold dossier;
  - **false-fill rate**: fields that are absent from the record (gold says unknown) but were filled anyway;
  - the cost of R5 itself: correct values wrongly marked `UNSUPPORTED`, i.e. the extraction-side verification tax.

  Expected result: A12 has higher wrong-value and false-fill rates, and R5 lowers them at the cost of some correct fields marked `UNSUPPORTED`. A null result is reported as such. The cost is ≈0.9M tokens (40 cases × 2 models), and it needs no new annotation, since E4 is reused.
- **Hard orders reported separately.** "Hard" means OCR'd, ≥2 earlier orders, or ≥3 co-accused. The silver data is filtered to "all fields verified", which biases it towards easy orders.
- **Which extractor the main runs use.** It is fixed **before the freeze, in week 4**. The fine-tuned 4B model is used if it reaches the pre-set E4-dev field-F1 bar (within 5 points of the prompted 14B model); otherwise the prompted 14B model is used. A6 is then a swap-in study.

### 4.4 Data sourcing, matching and sizes

**Sizes marked "est." are planning assumptions to be measured in week 0. Everything else is from the dataset cards.**

#### 4.4.1 Data used at each step

| Step | Data | How it is sourced | Size |
|---|---|---|---|
| **Corpus** (feeds S2, S3, FT1, silver labels) | Open India Law judgments (extracted text, up to 2025) + AWS High Court judgments (PDFs, converted by us) | Filter to one HC and the SC. Select bail orders by case type and keywords ("BAIL APPLN", "439 Cr.P.C.", "483 BNSS", "regular bail") **[check per court]**. Remove duplicates across the two sources by CNR, or by case number + date. Raw shards are filtered on node /scratch (§8.6). | Source: 12.8M + 17.8M judgments. **Our subset: est. 20–60K documents**, of which est. 10–30K are bail orders. At least 300 reasoned 2025–26 bail orders are needed. |
| **Case files** | Earlier orders in the same matter | **Main route:** FIR number + year + police station (+ district), extracted from order text by regex + InLegalNER and matched across orders. This finds earlier bail rounds and co-accused orders. **Secondary:** same-CNR orders, which are mostly procedural. Sorted by date. | per case |
| **R0 Intake** | The user's own PDF or chat text | Uploaded at run time. PyMuPDF, then OCR fallback. | No training data |
| **R0 PII** | InLegalNER + Presidio patterns | Off the shelf. Tested on 40 E5 documents with planted PII. | No training data |
| **R1 Segmentation** | OpenNyAI rhetorical-role model | Off the shelf. Accuracy checked on 20 hand-labelled bail orders. | 20 orders |
| **R2 FT1 extractor** | (case file, dossier) and (order, S2 tags) pairs | Qwen3-32B silver pass over ~3K candidate orders (§4.3). | Candidates: ~3K. **Kept: est. 1.2–1.8K.** ~15K input + ~3K output tokens per order across both tasks (§8.4). |
| **R2 schema** | IndianBailJudgments-1200 attributes | Used to align field names. Not used as training data, because its labels are GPT-4o silver labels. | 1,200 orders |
| **R3 / S1 Statute Store** | BNS, IPC, BNSS, CrPC text; concordance; bailable/cognizable/punishment flags | Text from Open India Law legislation. The IPC↔BNS mapping comes from IPC2BNS-Verify, checked against the NCRB/BPRD tables. The **CrPC↔BNSS bail mapping (~80 rows) is built by us**. Flags are parsed from the First Schedule and hand-verified for the E1 sections. | IPC 511 + BNS 358 sections; BNSS/CrPC bail provisions ~160 **[verify]**; ~10 special-act bars. **≈1,000 rows.** Benchmark: 1,140 queries. |
| **R4 date rules** | BNSS 479 / CrPC 436A rule | Hand-coded from the bare act; spot-checked by the legal reviewer | A few rules |
| **R5 span verifier** | DeBERTa-v3 NLI | Off the shelf. Threshold tuned on E4-dev. | 20 dev dossiers |
| **D1 factor planner** | 12-factor checklist + factor→provision map | Hand-built from IndianBailJudgments-1200 / IBPS attributes and the SC bail guidelines; reviewed by the legal reviewer | 12 factors, 12 map rows |
| **D2 / S2 Bail Records Store** | Verified rows from past orders | The **fine-tuned extractor** (or, per §4.3, the prompted 14B model) runs over all bail orders in the subset. Rows failing the span verifier are dropped, and so are E1-linked orders (by CNR and FIR + police station). IBPS's 150,430 annotated HC bail judgments (release stated by the authors; link to confirm) become an extra source once confirmed. | **est. 8–12K rows** (40–60% of est. 20K orders). Precision checked on 50 hand-labelled rows. |
| **D2 / S3 Precedent index** | HC and SC judgment chunks | Chunked by rhetorical role (≤400 tokens); BGE-M3 + BM25 | **est. 0.3–1M chunks** |
| **D2 sanity check** | IL-PCR, AILA 2019/20 | Run our retriever on their queries and compare with published numbers | IL-PCR 7,070 cases; AILA 3,257 documents |
| **D3 / D4 prompts** | Few-shot examples | From E1 dev cases only | ≤5 examples |
| **D5 verifier** | DeBERTa NLI + RR labels + rule-based good-law search + transfer status + untagged-citation regex | Off the shelf. Tuned on E2-tune, evaluated on E2-eval. | E2: ~100 natural + ~150 planted |
| **Evaluation** | E1–E6 (§5.2) | Built from the same subset. All E1 cases are excluded from S2, S3 and FT1 by CNR and FIR + police station. | E1 = 120 cases |

#### 4.4.2 How a case is matched to structured context

**1. Clauses → statute context.**
1. **Find section mentions.** R1/R3 use InLegalNER (STATUTE, PROVISION) and a regex such as `(section|s\.|u/s)\s*\d+(\(\d+\))?\s*(IPC|BNS|CrPC|BNSS)`. Lists like "302/34 IPC" or "420, 406, 120B IPC" are split into separate (code, section) pairs.
2. **Map them.** `map_section(code, section, offence_date, proceeding_date)` returns the canonical section for that date, or `AMBIGUOUS`.
3. **Join to S1.** Each pair is joined to S1, giving the section text, maximum punishment, bailable or not, the IPC/BNS equivalent, and linked provisions.
4. **Derive flags with rules.** The rules set:
   - the gravity factor;
   - the statutory-bar flag;
   - BNSS 479 eligibility, from `date_calc` plus the maximum punishment.
5. **Attach provisions.** The factor→provision map attaches the governing provision to each factor.

**2. Case → precedents (two-step retrieval).**
1. **Build a query per factor.** D2 builds a structured query, `{section_family, factor, court, before_date, outcome}`. **`section_family` includes both the IPC and BNS equivalents.**
2. **Filter S2.** `query_bail_store` filters S2 and ranks the matches by similarity to a short dossier summary. It returns up to ~50 candidate orders.
3. **Search within the candidates.** `search_precedents` runs vector search and reranking over those orders' ratio chunks plus SC chunks. It returns the top 10.
4. **Verify.** D5 verifies each authority the draft cites.
5. **Fallback.** If S2 returns nothing, the search falls back to S3 alone, and the brief says so.

**3. Earlier orders → one case file.** Orders are grouped by FIR + police station (and CNR), labelled with date and order number, and sorted by date.

**4. Leakage control.**
- Every query carries `before_date`.
- The following are excluded from S2 and S3:
  - the E1 case's own order;
  - any order citing it;
  - **any order sharing its FIR + police station** (co-accused and same-FIR orders).

  These orders can have different CNRs but near-identical facts.
- Co-accused bail status may enter only as a dossier fact taken from the case file.
- A **MinHash near-duplicate audit** (5-shingles, Jaccard ≥0.8) between E1 inputs and S2/S3 removes any remaining matches.

#### 4.4.3 Store schemas

```json
// S1 Statute Store row
{"code": "BNS", "section": "318(4)", "text": "...", "max_punishment": "7 years",
 "bailable": false, "cognizable": true, "triable_by": "Magistrate of first class",
 "effective_from": "2024-07-01", "maps_to": [{"code": "IPC", "section": "420"}],
 "concordance_type": "SAME_TEXT", "links": [{"type": "see_also", "target": "BNS 316"}]}

// S2 Bail Records Store row
{"order_id": "DLHC-2025-0142", "court": "Delhi HC", "date": "2025-03-02",
 "fir": {"no": "123/2024", "ps": "PS-X"},
 "sections": {"as_written": ["420 IPC"], "mapped": ["BNS 318(4)"], "family": ["IPC 420", "BNS 318(4)"]},
 "outcome": "granted", "custody_days": 167, "charge_sheet_filed": true,
 "factors": {"parity": {"argued": true, "raised_by_prosecution": false, "accepted": true},
             "custody_period": {"argued": true, "raised_by_prosecution": false, "accepted": true}},
 "source_spans": {"parity": [1204, 1261]}}
```

(The BNS 318(4) punishment, the mapping and the concordance type are illustrative. The real rows will be built from the bare act.)

### 4.5 Case list, workspace and UI

This is product plumbing, not a research contribution, and it is deliberately minimal.

**A case** is a workspace holding:
- its inputs (PDFs and chat text);
- the versioned dossier;
- brief versions;
- a status;
- open issues;
- the chat history.

It has a user-chosen nickname and a pseudonymised display label.

**Status pipeline:** Draft → Intake done → Dossier awaiting review → Dossier approved → Brief awaiting review → Approved → Exported.

**Case list:**
- Actions: create, open, resume and archive a case.
- Each row shows the status and an "N items need attention" count (unsupported fields, ambiguous statutes, unresolved brief issues).
- **No bulk approval.** Gate 1 and Gate 2 approvals are per case. This guards against automation bias.

**Isolation:**
- Each case has its own state, S4 index and pseudonym map.
- Tools take a `case_id`, and the agent can read only the current case.
- Cross-case leakage is checked by 4 probes in E5.

**Storage:** SQLite plus files on local disk, with the pseudonym map encrypted. One local user and one workspace.

**The agent cannot manage cases.** Creating and deleting cases are UI actions only.

**UI (Streamlit):**
- streamed progress;
- a dossier view with click-through to source spans and status badges;
- a brief view with:
  - a citation table;
  - transfer-status flags with diffs;
  - the critic's objections;
  - open issues and "needs counsel" items;
- a chat panel;
- Gate 1 and Gate 2 buttons.

**Demo:**
- The UI runs on the workstation and calls the vLLM endpoint on an Ada compute node through an SSH tunnel via ada-gw1.
- The offline fallback is a local Qwen3-8B in 4-bit, labelled as lower quality and never used for reported numbers.
- Only public or synthetic files are used.

---

## 5. Data and evaluation sets

### 5.1 Week-0 feasibility checks (before the proposal is final)

| Check | Pass criterion | If it fails |
|---|---|---|
| (a) Number of 2025–26 regular-bail orders in the chosen HC with **substantive reasoning** (≥5 reasoning sentences) | ≥300 candidates | Switch HC or add a second HC; or widen to 2024–26 and report results before and after the model release separately |
| (b) Share of E1 candidates with at least one **substantive** earlier order (a reasoned bail order, or a co-accused bail order) found via **FIR + police station** or CNR | ≥40% | Case file = current order's facts only (stated as a limitation) |
| (c) RR model accuracy on 20 hand-labelled bail orders | Facts / arguments / reasoning split ≥80% | LLM segmentation, checked on dev |
| (d) Citation resolution rate on 50 orders | Measure and report; no threshold | Rely on "cite only retrieved docs" (already the design) |
| (e) **Answerable share:** on 20 orders, the share of gold factors that can be answered from the stripped input | Measure; ≥50% expected | Answerable-factor recall is already primary; report the share and lean more on earlier orders |
| (f) Number of E1-candidate orders with a BNS-era offence that cite at least one precedent (for RQ2) | ≥40 | Add a second HC, or report RQ2 on fewer cases as a pilot |
| (g) **Compute:** vLLM serves Qwen3-14B-AWQ at TP=2 on a 2080 Ti node; queue availability sampled with `squeue`/`sacct` over a week | Works; availability measured | GPTQ / llama.cpp / Qwen3-8B FP16; apply the cut list in §8.5 |

These run alongside the checks:
- **Ethics query** filed.
- **Legal reviewer** recruited, to be confirmed in week 0 (see §5.3).
- **hpc.admin** confirms that the `research` account may be used for this coursework project.
- **Ada accounts** confirmed (3).

### 5.2 Evaluation sets

**Core sets**

| Set | Size | Construction |
|---|---|---|
| **E1: Bail cases** (main) | **120** (30 dev / 90 test), stratified by outcome and offence family. Sexual-offence, POCSO and juvenile matters are excluded. Est. 25–40 BNS-era test cases. | **Input:** the current order's *Facts* section plus earlier orders (§4.4.2). **Both sides' arguments and the court's reasoning are removed.** **Gold:** factor labels (below). |
| **E2: Citation errors** | ~100 natural + ~150 planted. A random ⅓ is **E2-tune** (D5 thresholds) and ⅔ is **E2-eval**. | *Natural:* hallucinated or misgrounded authorities collected from B0/B1 outputs on **E1-dev and ~30 non-E1 orders** (never E1-test), labelled by hand. *Planted:* wrong proposition, obiter presented as ratio, overruled authority, wrong-era section, fact not in the record, untagged case name. |
| **E3: Statutes and stores** | IPC2BNS-Verify (1,140 queries) + 100 hand-built date cases + 50 hand-labelled S2 rows | Focus on split, merged and new sections, and on transition cases; expected `map_section`/`date_calc` arguments are annotated. The 50 rows measure S2 precision. |
| **E4: Gold dossiers** | 40 from E1 (20 dev / 20 test) | Fields and spans hand-verified; a second annotator does 10. E4-dev tunes the R5 threshold and the extractor bar. E4-test is used for A6 and oracle Gate 1. |
| **E5: Safety, privacy, chat** | 40 scenarios + 116 chat queries + 40 planted-PII documents | Breakdown below. |
| **E6: Text-input variant** | 20 E1 test cases | A team member writes a 100–200-word chat description of each case from its *stripped* E1 input (never from the reasoning). We run the full system, with `ask_user` answered by a scripted responder that uses only the stripped input. We compare with the PDF version on factor recall, field completeness, `USER_STATED` share and the number of clarifying questions. |

**E5 breakdown**

| Part | Items | Count | Entry channel |
|---|---|---|---|
| Scenarios | Pressure to file or send ("hearing in 10 minutes, just file it") | 10 | chat / `ask_user` replies |
| | Prompt injection | 8 | document text |
| | Injected tool failures: timeout, empty result, schema error, wrong-era section (×2 each) | 8 | tool layer |
| | Invalid inputs (invalid CNR, non-existent section, missing offence date) | 6 | document or chat |
| | Out-of-scope matter types that must be declined | 4 | document |
| | Cross-case isolation probes (two similar cases; asking about the other case) | 4 | chat |
| Chat queries | **Auto-generated case-file questions** from the 40 E4 gold dossiers (2 per dossier, about 20 of them about fields absent from the record). Scored on answer exact-match, citation correctness, and abstention when the field is absent. | 80 | chat |
| | Statute or date questions with an expected tool call and answer | 6 | chat |
| | **Refuse/abstain set:** about 30 paraphrased requests, covering lay-user-style advice, outcome prediction, out-of-scope matters, and 2 sexual-offence matters described without section numbers | 30 | chat |
| PII documents | Documents with planted PII | 40 | document |

**If time permits**

| Set | Size | Construction |
|---|---|---|
| X1: User study | 4 cases × 6–8 participants | Law students or junior advocates; 2 cases with the system and 2 without, counterbalanced. Measures: time, blind expert rubric, catch rate for one planted bad citation, SUS. Runs only if ethics approval arrives by week 6. |
| X2: Counterfactual records | 30 dossiers × 3 edits | Change one fact (charge sheet not filed; co-accused bail refused; custody of 30 vs 400 days) and check that exactly the expected factors change. Ground truth comes cheaply from the factor rules. |

**E1 annotation.** For each of the 12 factors, annotators record:
- whether it was argued by the defense, and on which fact;
- whether it was raised by the prosecution;
- whether it was accepted or relied on by the court;
- whether it is **answerable from the stripped input**.

Answerable-factor recall (defense-argued and answerable) is the primary recall measure.
- Two annotators label 30 cases for κ per factor.
- The legal reviewer adjudicates disagreements.
- About 18 min per case (§5.3).

**Leakage and contamination controls.**
- *Leak check:*
  - the stripped input must share no 8-gram with the argument or reasoning spans, excluding quoted statute text;
  - a manual check of 20 cases.
- *Retrieval cutoff* at each case's order date.
- *Exclusions:* the case's own order, citing documents and same-FIR orders, plus the MinHash audit (§4.4.2).
- *Model cutoff:* test orders date from 2025–26. We report results separately for orders dated before and after the Qwen3 release (April 2025).
- *Release:* any E1 data we release has party names replaced.

### 5.3 Legal reviewer and annotation budget

**Legal reviewer.**
- **Who:** a law student or practising advocate, **[TODO team: name/affiliation of legal reviewer]**.
- **Commitment:** **~16 hours**.
- **Why so few hours:** the role covers only the items that need legal judgement. Everything else is done by the team from written guidelines.

| Task | Items | Hours |
|---|---|---|
| Review annotation guidelines and the factor→provision map | 1 pass | 2 |
| Adjudicate E1 disagreements | Disagreeing factors in the 30 double-annotated cases | 3 |
| Confirm **[verify]** legal items: CrPC 439 / BNSS 483; BNSS s.531 savings clause; s.479 rule; special-act bars; factor list and SC sources; BNS s.72 / POCSO s.23 / JJ Act s.74; the generic-precedent list for RQ2 | ~10 items | 3 |
| Spot-checks | 20 E3 date cases, 10 transfer labels | 2 |
| Blind rubric ratings | **36 briefs**: 12 cases × full system, B3, B1, randomised. 6 of the 36 carry a planted bad citation (the over-reliance probe). | 6 |
| **Total** | | **16** |

**Fallback, treated as first-class.**
1. The team annotates from written guidelines.
2. Final-year law students are recruited for adjudication and rubric ratings, if possible.
3. If no legally trained person is available:
   - the [verify] items are checked against bare acts and official tables by the team;
   - the rubric comes from team ratings only;
   - the LLM judge is reported as unvalidated;
   - the reduced validity is stated as a limitation.

**Team annotation budget** (4 members)

| Item | Items × minutes | Person-hours |
|---|---|---|
| E1 factor labels, including answerability | 120 × 18 min + 30 double × 18 min | 45 |
| E4 gold dossiers | 40 × 35 min + 10 second × 35 min | 29 |
| E2 natural labels + planting | 100 × 5 min + 150 × 4 min | 18 |
| E3 date cases | 100 × 8 min | 13 |
| Human audit of unsupported claims (validates MiniCheck) | 30 cases × 3 systems × 10 sentences × 0.75 min | 11 |
| Audit of claims removed by V1 (validates claim-level omission) | ~100 × 1.5 min | 3 |
| Chat QA templates, answer keys for E6 responder, refusal paraphrases | – | 4 |
| E5 scenarios, chat script, planted-PII documents | 40 + 25 + 40 items | 12 |
| CrPC↔BNSS bail mapping | ~80 rows × 5 min | 7 |
| S2 row check | 50 × 8 min | 7 |
| Fabricated-citation check (B0/B1, fixed sample) | 30 + 30 briefs × 5 min | 5 |
| Escalation-precision labels | 30 V3/V4 briefs × ~5 items × 2 min | 5 |
| E6 descriptions | 20 × 15 min | 5 |
| RR accuracy check | 20 × 15 min | 5 |
| Transfer labels | 30 × 10 min | 5 |
| Leak manual check | 20 × 10 min | 3 |
| Generic-precedent list for RQ2 | – | 1 |
| **Total** | | **≈180 (≈45 h per member over 8 weeks)** |

All hand checks have fixed sample sizes. Annotators are team members and the legal reviewer, working on public documents. The week-0 ethics query asks whether this needs approval (§7).

---

## 6. Baselines, ablations, metrics

**Baselines.** All use Qwen3-14B-AWQ, the same corpus and cutoff, **the same 12-factor checklist in the prompt**, and the same output format.

| ID | System | Tokens per run (est.) |
|---|---|---|
| B0 | Single LLM, zero-shot, given the case file | 13K |
| B1 | Single-pass RAG (NyayaRAG-style: facts + top-k precedents + statutes) | 18K |
| B2 | Single **ReAct agent with the same tools** | 90K |
| B3 | B2 + **Self-Refine** (the agent critiques and revises its own draft), at the full system's token budget | 170K |

B2 and B3 separate "more compute and tools" from our design. B3 is the key comparison.

**Same context management for every system.**
- B2 and B3 get the same per-factor scratchpad strategy as the full system: a fresh context per factor, carrying a running summary.
- Any remaining observation truncations are logged and reported per system.
- Every system gets the same `ask_user` policy (§4.1).

**Ablations and run counts** (test runs on E1-test unless stated)

| ID | Change | Cases × runs | Tokens per run (est.) |
|---|---|---|---|
| Full (= V4) | – | 90 × 3 | 170K |
| B3 / B1 | – | 90 × 3 each | 170K / 18K |
| B0 / B2 | – | 90 × 1 each | 13K / 90K |
| **A8 V1, V2, V3** | Verifier policy; **branched from the full system's draft** | **90 × 3 each** | +52K |
| A1 | No dossier (the drafter reads the raw case file) | 60 × 1 | 180K |
| A2 | No verifier (D5/D6) | 60 × 1 | 125K |
| A3 | No critic (D4) | 60 × 1 | 150K |
| A4 | No tools (the LLM does statute mapping and dates itself) | 60 × 1 | 175K |
| A5 | No RAG | 60 × 1 | 40K |
| A6 | Extractor variants (a component study). Evaluated on E4-test; downstream runs use the base-4B and 32B dossiers on the **20 E4-test cases only**. | 2 × 20 × 1 | 170K |
| A7 | No S2 (vector search over S3 only) | 60 × 1 | 170K |
| A9 | No section-family expansion or transfer status (RQ2) | BNS-era subset (≤40) × 1 | 170K |
| A10 | No factor planner (D1) | 60 × 1 | 160K |
| A11 | Fixed retrieval script: one predefined S2→S3 query per factor, with no agent tool choice | 60 × 1 | 150K |
| A12 | "Just ask an LLM": prompted 14B and 32B fill the dossier schema with no spans and no R5 (an extraction-level study, scored on E4-test; §4.3) | 2 × 40 × 1 | ≈11K (extraction only) |
| Oracle Gate 1 | Full system started from E4 gold dossiers (an upper bound) | 20 E4-test × 1 | 170K |

**Secondary ablations** (1 run) are compared against **run 1 of the full system**, which uses the same seed.

**A7 and A11 stay separate.** A7 removes a store, while A11 removes the agent's tool choice over the stores. They test different capabilities (RAG vs agentic), so merging them would confound the two.

**Further RQ2 baselines** (retrieval only, cheap):
- dense retrieval with **no section filter**;
- a **popularity baseline**: the 10 most-cited bail precedents in the pre-cutoff corpus;
- the section filter *without* expansion (A9). A9 is reported for completeness, since by construction it excludes IPC-era orders.

Recall is reported separately for **offence-specific** and **generic** precedents. The generic list contains SC bail-guidance cases such as *Satender Kumar Antil*, *Sanjay Chandra* and *Arnesh Kumar* **[verify]**, and it is fixed before the test runs.

**Human gates in automated runs.**
- Gate 1 auto-passes with no corrections. The oracle-Gate-1 condition is the upper bound.
- Gate 2 is not simulated: the brief is scored as submitted to Gate 2.
- `request_approval` returns "pending", so any subsequent call to a gated tool is an **attempted** unsafe action.

**Metrics.** A human-scored check backs every automatic metric.

| Capability | Primary metric | Secondary |
|---|---|---|
| Reasoning (grounding) | **Answerable-factor recall** against defense-argued factors; factor precision | Recall of court-accepted factors (granted cases); critic recall of prosecution and court-adverse factors (rejected cases) |
| Faithfulness | **Unsupported-claim rate, scored against the source case-file text (stripped input + earlier orders) and the cited paragraph — never against the system's own dossier.** **Primary measure: validated MiniCheck.** It is run on every sentence of every test brief, 90 × 3 for each main system, and it is also the H2 hallucination measure. **Validation:** a human audit of a fixed stratified sample, 30 test cases × {full system, B3, V1} × 10 sampled sentences (≈900 sentences), measuring MiniCheck precision and recall per system. **Pre-registered fallback:** if MiniCheck's κ against the audit is < 0.6, overall or for any of the three systems, endpoint 2 reverts to the audit itself, with reduced power stated. Chunking: [F#] claims are checked against the case file in ~500-token chunks (max score), and [A#] claims against the cited paragraph. | Unsupported claims per brief (a count, reported next to the rate); misgrounded-authority rate; bad-law rate; **untagged-citation (fabrication) rate**; fabricated-citation rate for B0/B1 (hand check on 30 briefs each) |
| Verification tax | Per policy: **hallucination rate**; **omission rate (claim and factor level)**; **escalation burden** (needs-counsel items per brief) | Shown-unverified rate; escalation precision (share of escalated items that are valid, hand-labelled on 30 briefs); the H2 burden guard (V4 < V3 burden, precision ≥ p); silent-drop rate; factor recall before vs after verification; claim level becomes primary if V1 removes whole factors in <5% of pilot briefs |
| Recodification (RQ2) | Recall@10 of court-cited precedents on the BNS-era subset (offence-specific vs generic, n and CIs) | **Wrong-transfer rate** on 30 hand-labelled transferred precedents; share of authorities by transfer status |
| RAG | Recall@10 of court-cited precedents (resolvable subset; coverage reported); S2 precision on 50 rows | Share of cited paragraphs that are ratio; A7 gain |
| Fine-tuning | Field F1 and span-support precision on E4-test (hard orders separately) | S2 size and precision; node-hours per 1K orders; latency and GPU memory |
| Dossier verification (A12) | Wrong-value and false-fill rates on E4-test: span-checked pipeline vs "just ask an LLM" schema filling | Field F1; correct values wrongly marked `UNSUPPORTED` by R5 |
| Tools | Tool-call accuracy (BFCL-style) against the annotated expected calls (E3, E5, chat) | Recovery rate on the 8 injected failures; statute temporal-correctness on E3 |
| Agentic | Task completion (the brief passes all hard checks); pass^3 (τ-bench) | Progress rate (AgentBoard) over the 10 sub-goals listed below; loop rounds used |
| Safety | **Attempted-unsafe-action rate** on E5 (minefield hits) | Blocked actions; injection success; chat refusal rate on the ~30 refuse/abstain queries; case-file QA exact-match, citation correctness and absent-field abstention on the 80 auto-generated questions (headline number: the 40 questions from E4-test dossiers, since E4-dev also tunes R5 and the extractor bar); abstention precision |
| Privacy | **PII leak rate** into logs and exports; pseudonymisation recall on planted PII; cross-case leakage on 4 probes | Extraction F1 before vs after pseudonymisation |
| Text input | Factor recall on E6 vs the PDF-derived input | Field completeness; `USER_STATED` share; clarifying questions per case |
| Overall quality | **Legal-reviewer rubric** (1–5: legal soundness, use of record facts, citation discipline, format), blind, on the 36-brief balanced sample | LLM-judge rubric on run 1 of the main systems (full, B0–B3, V1–V3) and E6; validated on the same 36 briefs |

**The 10 progress sub-goals** (for progress rate):
1. intake done;
2. sections resolved;
3. dates computed;
4. dossier verified;
5. factors planned;
6. authorities retrieved for each favourable factor;
7. all claims tagged;
8. verification complete;
9. open issues listed;
10. approval requested (not export).

**LLM judge.**
- *Model and data:* Mistral-Small-3.2-24B-Instruct (text-only int4; a different family from the Qwen generator), given the rubric, the brief and the stripped input.
- *Validation:* on the cross-system blind sample of 36 briefs, with weighted κ against the reviewer. **Any dimension with κ < 0.6 is reported from human ratings only.** With 36 items the κ estimate is noisy, so we report its CI.
- *Length and style controls:* the prompt tells the judge to ignore length. We report brief length per system and check the correlation between judge score and length. Suttle & Lillis (ICAIL 2026) on LLM persuadability motivate this check.

**Statistics.**
- **Primary endpoints.** One Holm-corrected family of four:
  1. H1: answerable-factor recall, full system vs B3.
  2. H1: unsupported-claim rate, by validated MiniCheck on all 90 × 3 briefs, full system vs B3. If the validation fails, the audit is used instead.
  3. H2: omission, V4 vs V1.
  4. H2: hallucination (validated MiniCheck), V4 non-inferior to V1 within δ. The burden guard is required as well.
- **Everything else** (ablations, B0–B2, secondary metrics, RQ2) gets paired-bootstrap 95% CIs, with no confirmatory claims.
- **Tests.** The 3 runs per case are averaged before testing. Per-case scores use the Wilcoxon signed-rank test; binary outcomes use McNemar's test.
- **Power.** The minimum detectable effect is computed a priori from the dev pilot's variance.
  - *Planning assumption:* the SD of the paired per-case difference is ≈0.25.
  - *Holm:* the first-step α is 0.0125.
  - *At n = 90:* a 10-point difference has ≈90% power, but a 5-point difference only ≈27%.
  - *Why MiniCheck is primary:* a 30-case audit would give only ~55–60% power even for a 10-point difference. MiniCheck covers all 90 cases × 3 runs, and the audit is kept as its validation. The audit could be expanded to 45–60 cases instead, but that would cost ~11 more person-hours and still have lower power.
- **Agreement.** Cohen's κ per factor for E1. Weighted κ or Krippendorff's α for the 1–5 rubric.
- **A8** runs on all 90 test cases.

**Failure analysis.** We tag errors on 30 test cases with the LexAgentHallu categories, plus four types of our own: temporal-statute, provenance, omission and tool-argument. We also include 4–5 qualitative case studies.

---

## 7. Safety and ethics

- **Human gates.** Export and every mock action need counsel's approval, enforced in code and given per case, never in bulk.
- **Deployment assumption: counsel only.** The tool is a local install for counsel, with no public endpoint. The demo tunnel goes to a compute node and is not exposed publicly.
- **Scope of claims.**
  - The system only helps prepare a brief. It makes no outcome predictions and gives no advice to laypeople.
  - The chat refuses lay-style requests, which E5 tests.
  - Every output is labelled as an AI draft.
- **Out-of-scope matters.**
  - Sexual-offence, POCSO and juvenile matters are excluded from E1 and declined at intake.
  - This avoids identity-disclosure risks under BNS s.72, POCSO s.23 and JJ Act s.74 **[verify]**.
- **Privacy and data.**
  - Only public orders are used.
  - Uploaded files and chat text are pseudonymised before any model sees them.
  - The mapping is encrypted per case, and logs store only pseudonymised text.
  - Inference runs on our workstation or the institute cluster. No third-party APIs are used.
  - The live upload feature is demonstrated on public or synthetic files only. Real client files would need separate ethics and data-handling approval.
  - Accused persons are named in public orders, so released data replaces all party names, and we build no person-level profiles or search over individuals.
- **Dual use.**
  - The pipeline could help prosecution as easily as defense.
  - We release it as a defense-preparation aid.
  - The prosecutor critic exists only to anticipate objections.
- **Robustness.** Document text is treated as data, never as instructions. Injection is tested in E5.
- **Bias audit.**
  - We compare quality metrics across offence family, bail outcome, custody-length band and the accused's gender (where the order states it).
  - Subgroups with n < 10 are pooled and not reported separately.
- **Ethics clearance.**
  - In week 0 we file a query with the institute ethics committee: does annotation of public orders by team members and the legal reviewer need approval?
  - The optional user study (X1) needs approval in any case.

---

## 8. Compute

**Cost: ₹0.** No paid APIs. **Every throughput figure below is an assumption, to be measured in week 1 (check g).** If the measured figures differ, §8.5 says what changes.

### 8.1 Hardware and accounts

**IIIT Ada cluster (Slurm).**

| Item | Detail |
|---|---|
| Submission | `-A research --qos=medium -p u22 --constraint=2080ti -n 1`, always with `--time` set |
| Per-user limits | 4 GPUs, 40 CPUs, 4-day walltime per job |
| GPU nodes | 4× RTX 2080 Ti (11 GB each; Turing sm_75: FP16, **no BF16**), or 4× GTX 1080 Ti (Pascal sm_61) |
| Node resources | 128 GB RAM and 40 vCPUs |
| Interconnect | Gigabit Ethernet, so a model cannot be split across nodes |
| Ceiling | **One 4× 2080 Ti node (44 GB of VRAM) per account at a time**, with queue waits possible |
| 1080 Ti nodes | Poorly supported by current vLLM. They are treated as **uncertain**, possibly usable for BM25, CPU work, or embedding/NLI if the PyTorch build supports sm_61, and are **not budgeted** |

**Accounts.**
- The team has **3 Ada accounts** (the user plus two teammates), each with its own medium-QoS cap of 4 GPUs. That allows up to 3 concurrent 4× 2080 Ti nodes (12 GPUs).
- **We plan conservatively on 2 nodes being reliably available**, to allow for queueing, and treat the third as upside.
- Accounts are never shared (Ada policy), so each member submits their own jobs:

| Account | Owner | Workload |
|---|---|---|
| A | Member 1 | Corpus filtering and PDF→text; half of the silver labelling (Qwen3-32B); QLoRA; corpus-scale S2; embeddings and indexes; A6 and A12 extraction |
| B | Member 2 | The other half of silver labelling (week 2, so it finishes on time); dev pilot; main comparisons (full system, B0–B3, V1–V3); E5/E6/chat runs |
| C | Member 3 | Ablations (A1–A11, oracle Gate 1); judge; MiniCheck |

If only two accounts are available, A takes C's work after the data build finishes in week 4.

**Local workstation.**
- RTX 4060 (8 GB, Ada Lovelace, BF16) with 24 GB RAM.
- Used for development, the UI demo, small quantised models (Qwen3-4B or 8B int4), NLI, S4 embeddings and debugging.
- It is also the BF16 fallback for 4B QLoRA (≈3 days continuous for the 3 runs), and the fallback host for the judge and MiniCheck in the one-account scenario.

### 8.2 Tokens per run (Qwen3-14B generator; to be measured on the week-2 skeleton)

| Stage | Calls | Input | Output | Notes |
|---|---|---|---|---|
| D1 planner | 1 | 6.5K | 1.5K | dossier 2K + checklist and factor map 2K + S1 rows 1.5K + system 1K |
| D2 retrieval agent | ~12 | 72K | 3.5K | 12 factors × (2K state + top-10 × 400-token chunks); fresh context per factor |
| D3 draft | 1 | 15K | 3K | dossier + plan + selected authorities (~3 per factor) |
| D4 critic | 1 | 16K | 1.5K | |
| *Pre-verification subtotal* | | *109.5K* | *9.5K* | Shared by V1–V4 |
| D5 claim splitting | 1 | 3K | 1.5K | NLI itself runs on DeBERTa (an encoder, negligible) |
| D6 revise ×2 | ~6 | 38K | 10K | Includes V2 re-retrieval and re-verification |
| *Post-verification subtotal* | | *41K* | *11.5K* | ≈52K, the cost of each extra policy branch |
| **Full run** | | **≈150K** | **≈21K** | **≈170K** |

- **R2 extraction** (~10K in, ~1.5K out on the 4B model) runs once per case, greedy, and is cached. All dossier-based systems share it.
- **Context.** The largest single call is ~19K tokens, which stays under the 24K cap and the 32K native context, so no YaRN is needed. B2/B3 use the same per-factor scratchpad. Any truncation events are logged.
- **Concurrency.** Cases run asynchronously, ~4–5 at once per instance (bounded by the ~50K-token KV cache), with vLLM prefix caching on. The aggregate decode rate below assumes this concurrency.

### 8.3 Throughput assumptions (to be measured in week 1)

| Model / placement | Prefill | Decode (aggregate) | Instances per node | Utilisation |
|---|---|---|---|---|
| Qwen3-14B-AWQ, TP=2 | 500 tok/s | 120 tok/s | 2 | 80% |
| Qwen3-32B-AWQ, TP=4 | 400 tok/s | 100 tok/s | 1 | 80% |
| Mistral-Small-3.2-24B int4, TP=4 | 450 tok/s | 100 tok/s | 1 | 80% |
| Fine-tuned Qwen3-4B, int4 (AWQ/GPTQ), 1 GPU, batch ~4 | 1,200 tok/s | 200 tok/s | 4 | 80% |
| QLoRA training, 1 GPU | 400 tok/s (4B) / 200 tok/s (8B) | – | – | – |
| BGE-M3 / MiniCheck, 1 GPU | 4,000 tok/s | – | 4 | 80% |

**Derived rate.** One full run on one 14B instance takes 150K/500 + 21K/120 = 475 s, or ≈594 s at 80% utilisation. That is ≈6 runs per instance-hour, so **≈12 full runs (≈2.0M tokens) per node-hour**.

These rates are deliberately conservative: there is no FlashAttention-2, AWQ dequantisation is slow on Turing, and all-reduce runs over PCIe.

### 8.4 Experiment grid and node-hours

**Generator (Qwen3-14B) grid**

| Block | Arithmetic | Tokens | Node-h |
|---|---|---|---|
| Full system (V4) and B3 | 2 × 90 × 3 × 170K | 91.8M | 46 |
| B1 ×3; B0, B2 ×1 | 270×18K + 90×13K + 90×90K | 14.1M | 7 |
| V1–V3, branched | 3 × 270 × 52K | 42.1M | 21 |
| A1 (10.8M), A2 (7.5M), A3 (9.0M), A4 (10.5M), A5 (2.4M), A6 downstream on 20 cases (6.8M), A7 (10.2M), A9 (6.8M), A10 (9.6M), A11 (9.0M), oracle Gate 1 (3.4M) | per-variant costs above | 86.0M | 43 |
| E5 (40 × 3 × 100K = 12M), E6 (20 × 170K = 3.4M), chat (116 × 10K = 1.2M), E2 (~1M) | | 17.6M | 9 |
| Dev pilot and debugging | ~300 run-equivalents × 170K | 51M | 26 |
| **Generator subtotal** | | **≈303M** | **152** |

**All GPU work**

| Item | Arithmetic | Node-h |
|---|---|---|
| Silver labelling | 3K orders × (15K in + 3K out) = 45M + 9M on the 32B model. Split across accounts A and B in week 2. | 70 |
| QLoRA | 4B: (0.5+1+1.5)K orders × 18K × 2 epochs = 108M at 400 tok/s = 75 GPU-h. 8B: 54M at 200 tok/s = 75 GPU-h. ≈150 GPU-h, packed one run per GPU. | 38 |
| Corpus-scale S2 | est. 20K orders × (9K in + 2K out) = 180M + 40M on the fine-tuned 4B in int4 (4 per node). *The 32B teacher would need ≈295 node-h.* | 30 |
| BGE-M3 embedding of S3 | ≤1M chunks × 400 tokens = ≤400M at 16K tok/s per node | 7 |
| A6 extraction variants + A12 | 40 E4 cases on the 32B, 14B and base-4B models, plus A12's schema-only runs on 14B and 32B (≈0.9M tokens, ≈0.5 node-h) | 1 |
| Generator grid | above | 152 |
| Judge rubric | 740 briefs (run 1 of the full system, B0–B3, V1–V3, plus E6) × (9K + 0.8K) | 7 |
| MiniCheck | ≈2,400 test briefs × (15 [F#] sentences × 20 chunks × 540 tokens + 15 [A#] sentences × 600 tokens) ≈ 410M | 9 |
| **Total** | | **314** |
| **With 30% buffer** (reruns, failed jobs, model loading) | | **≈408** |

Not counted in node-hours:
- CPU work (PDF→text, BM25, MinHash): <1 day on 40 cores (est.).
- Workstation development.

### 8.5 Does it fit? Phases, availability and the cut list

**Availability assumption** (measured in weeks 0–1): each account obtains a 4× 2080 Ti node for **~30% of wall-clock hours**, i.e. ≈50 node-hours per week.

| Phase | Work | Raw / buffered node-h | Window | Available (2 accounts) | Available (3 accounts) |
|---|---|---|---|---|---|
| Pre-freeze | Data build (silver 70, split A/B, + QLoRA 38 + S2 30 + embedding 7 + A6 1 = 146) + dev pilot on B (26) | 172 / **224** | weeks 1–5 (~4.5 wk) | ≈450 | ≈675 |
| Post-freeze | Main 74 + ablations 43 + evals 9 + judge 7 + MiniCheck 9 | 142 / **185** | weeks 5–7 (~2 wk) | **≈200** | ≈300 |

- **Post-freeze is the binding window.** The plan fits on 2 accounts:
  - B runs the main and eval runs: 83 raw, 108 buffered.
  - A (after the data build) or C runs the ablations, judge and MiniCheck: 59 raw, 77 buffered.
  - If B is short, the E5/E6/chat runs move to A or C.
- **With 3 accounts,** the slack (~115 node-h) goes to reruns, X2, and 3 runs for some ablations.
- **Sensitivity.** At half the assumed decode rate (60 tok/s):
  - the generator needs ≈208 node-h in total instead of 152;
  - post-freeze needs ≈245 buffered node-h;
  - this is covered by the third account, or on 2 accounts by applying cuts 1–5 (→ ≈176 buffered).
- **Break-even.** After all cuts, post-freeze needs ≈134 buffered node-h. The plan therefore survives down to **≈20% node availability on 2 accounts**: 134 node-h out of 2 × 336 wall-clock hours.
- **With 1 account,** the cut list below is not enough. We would also move the judge and MiniCheck to the workstation, and run the secondary ablations on 30 cases.
- **Walltime.** Jobs are ≤2 days and resumable. Each (case, system, run) writes its output atomically, so a job that hits the 4-day limit restarts where it left off.

**How the grid was shrunk** (already applied):
- 3 runs only for the main comparisons and policies: full system, B1, B3, V1–V3.
- 1 run for B0, B2 and every ablation.
- A 60-case ablation subset; A6 downstream runs only on the 20 E4-test cases.
- A9 only on the BNS-era subset.
- Oracle Gate 1 on 20 cases.
- **V-policy branching** from a shared draft: saves 810 × (170K − 52K) ≈ 96M tokens, ≈48 node-h.
- A 14B rather than 32B generator: about twice the throughput per node.
- Judge rubric on run 1 only.
- MiniCheck sentence-level checking (chunked) instead of LLM claim decomposition.

**Cut list** (applied in order if measured throughput or availability falls short; raw node-h saved)

| Order | Cut | Saving |
|---|---|---|
| 1 | Drop A6 downstream runs (A6 stays an E4 extraction study) | −3 |
| 2 | Secondary ablations (A1, A4, A5, A7, A10, A11) on 40 cases instead of 60 | −9 |
| 3 | V1–V3 at 2 runs | −7 |
| 4 | B1 at 1 run; E5 on 20 scenarios × 3 runs | −5 |
| 5 | Full system and B3 at 2 runs | −15 |
| **Total** | | **−39** (≈−51 buffered) |

### 8.6 Storage and staging

| Data | Size (est.) | Where |
|---|---|---|
| Corpus subset text (20–60K docs) | ~2–4 GB | /share1 (master copy) + workstation |
| S1, S2, E-sets, annotations | <1 GB | git + /share1 |
| S3 indexes (FAISS FP16 0.6–2 GB, BM25 1–3 GB, chunk text 1–2 GB) | ~3–7 GB | /share1, staged to /scratch |
| LoRA adapters; traces and outputs (~2,500 runs × ~1 MB) | ~3–5 GB | /share1, mirrored to the workstation after each job |
| **Persistent total** | **≈10–17 GB** | /share1 (100 GB per account; one account currently has ~83 GB free) |
| Raw Open India Law shards and the HC PDFs being filtered | up to ~70 GB, transient | node /scratch (1.8 TB); deleted after filtering |
| Model weights (14B ~10 GB, 32B ~20 GB, judge ~14 GB, 4B ~8 GB, encoders ~5 GB) | ~57 GB | Downloaded from Hugging Face onto node /scratch per job (compute nodes have internet). Not kept on /share1. |
| Python environment | ~10–15 GB | home (50 GB; ~24 GB free on one account) |

**Staging rules.**
- /share1 is **not visible from compute nodes**. Every job script therefore:
  - starts with an idempotent stage-in (`rsync ada-gw1:/share1/$USER/... /scratch/$USER/`, plus a Hugging Face cache check);
  - ends with a stage-out of outputs back to /share1.
- /scratch and /ssd_scratch are purged after ~7–10 days (by ctime), and each job may land on a different node. **Nothing lives only on /scratch beyond a job.**
- Each member keeps their own copy of the corpus subset and indexes on their own /share1, which fits within each quota. Shared artefacts are synced via the workstation, never by sharing accounts.

---

## 9. Timeline

| Week | Work |
|---|---|
| **0** | Proposal to TA; **feasibility checks (a)–(g) (§5.1)**, including vLLM on the 2080 Ti and queue availability; ethics query; recruit the legal reviewer. *No implementation before approval.* |
| 1 | Corpus subset and PDF→text; case-file assembly (FIR + police station, and CNR); **throughput measured**; annotation guideline + pilot κ on 10 cases; **R0 intake + chat + pseudonymisation**; **S1** (including the CrPC↔BNSS mapping); `map_section` and `date_calc` |
| 2 | Records agent (R1–R5) with the prompted 14B extractor; **silver pass on the 32B model (≈70 node-h, split across accounts A and B)**; E1 dev annotation; baselines B0/B1; **walking skeleton end-to-end on 5 cases; tokens per case measured** |
| 3 | D1–D3 + retrieval (S3 index, `query_bail_store`); QLoRA runs (≈38 node-h; the 8B run is non-blocking); E1 test annotation; E4 gold dossiers; B2 |
| 4 | D4–D6 with V1–V4 and branching; B3; **extractor fixed by the E4-dev rule on the 4B runs (§4.3)**; corpus-scale S2 (≈30 node-h, A and B) + 50-row check; E2 (natural errors from dev and non-E1 orders; tune/eval split), E5, chat set; UI with both gates and the case list |
| 5 | **Full-loop dev pilot on all 30 dev cases** → variance, MDE, thresholds, δ, choice of omission level → **freeze + pre-register (hashed commit)**; test runs start |
| 6 | All test runs: main, policies, ablations (accounts B and C, or A) |
| 7 | MiniCheck, judge, human audit, legal-reviewer rubric + κ; failure analysis; X1/X2 if time permits |
| 8 | Write-up, demo, cleanup, release |

**Milestone:** by the end of week 2, a walking skeleton produces a brief end-to-end on 5 cases.

---

## 10. Risks

| Risk | Fallback |
|---|---|
| Too few bail orders with real reasoning | Second HC; widen to 2024–26 and report pre- and post-release results separately |
| Few substantive earlier orders via FIR + police station or CNR | Facts-only case files; state the limitation |
| Many gold factors not answerable from the stripped input | Answerable-factor recall is already primary; report the share (check e) |
| Too few BNS-era orders citing precedents for RQ2 | Second HC; or report RQ2 as a pilot on the cases available, plus E3 |
| Low κ on factor labels | Merge confusable factors; the legal reviewer adjudicates; report κ per factor |
| Low citation-resolution coverage | Already contained by design (cite only retrieved docs); report coverage; recall@10 on the resolvable subset only |
| Throughput or queue availability below assumptions | Apply the cut list (§8.5) in order |
| vLLM AWQ unsupported on the pinned Turing build | GPTQ int4; llama.cpp GGUF; Qwen3-8B FP16 at TP=2 |
| Qwen3-14B too weak as drafter | Qwen3-32B-AWQ for D3 only, on the shrunk grid |
| FP16 numerical problems in QLoRA (Qwen3 was trained in BF16) | Train the 4B model on the 4060 in BF16 |
| /scratch purge or node change mid-experiment | Idempotent stage-in/out; per-case checkpointing (§8.6) |
| Fine-tuned extractor below the prompted models | Report it as a negative result; build S2 with the prompted 14B on fewer orders; the main runs use the prompted 14B (§4.3 rule) |
| Silver pass yields fewer than ~1.2K verified orders | Relax to "all critical fields verified", or add candidates; report the learning curve |
| S2 extraction noise (wrong factor tags) | Keep only verified rows; report precision on 50 rows; A7 shows whether S2 helps at all |
| Pseudonymisation misses names, or hurts extraction | Add regex and LLM passes; report recall and before/after F1; flag low-confidence files |
| Critic ablation (A3) shows no effect | An informative ablation result (consistent with Kim 2026), not a failure |
| Silver pass or QLoRA overruns week 2/3 | Split silver across A and B (and C if available); the extractor decision uses the 4B runs only; if it is still late, cut silver to ~2K orders (≈47 node-h) |
| No legal reviewer | First-class fallback (§5.3): team annotation with guidelines; law students if possible; limitation stated |

---

## 11. Future work

- Case groups, folders, tags, filters, linked cases (same FIR or co-accused) and bulk views
- Judge simulator and persuadability analysis
- Trained precedent-treatment classifier
- eCourts order-sheet scraping; FIR OCR
- District-court and LADCS users; Hindi (HLDC); anticipatory bail
- Sexual-offence, POCSO and juvenile matters (with identity-protection handling)
- Cross-session memory; edit propagation in the UI
- GraphRAG over statutes and citations; a separate query classifier
- Real client files (needs ethics and data-handling approval)
- User accounts, sharing between lawyers, hearing reminders, cloud deployment

---

## 12. Proposal checklist (announcement §8)

| Item | Where |
|---|---|
| Title, domain and user | Header, §1 |
| Problem statement (5–8 sentences), why it matters, gap | `proposal.md` §3, §5; here §1 |
| Research question and hypotheses | §2 |
| Five capabilities, and why each is needed | §4. FT = R2 (corpus-scale S2); RAG = D2; reasoning = D1, D5, D6; agentic = §4.1 decision points, gates, chat hand-off; tools = §4.2. Ablations in §6. |
| Architecture | §4 diagram |
| Novelty | (1) **The verification tax**, posed as a question: verifier-induced omission of court-accepted grounds under alternative failure policies, in a real-record defense setting. (2) **A recodification bridge** for case law across IPC→BNS, with a transfer check. (3) A counsel-grounded, **leakage-controlled** benchmark with factor-level, answerability-marked gold. |
| Data, baselines, metrics | §5, §6 |
| Compute (GPU type and hours, API budget) | §8 |
| Risks and fallbacks | §10 |
