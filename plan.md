# plan.md: NyayaSahayak, a Verified Bail-Preparation Assistant for Legal-Aid Defense Counsel

> An end-to-end agentic system. A **Court-Records Agent** turns a criminal case file into a verified dossier. A **Defense-Preparation Agent** turns that dossier into a grounded, citation-checked bail brief. The system uses RAG, tool calling, multi-step reasoning, and a QLoRA fine-tuned small model, and a lawyer approves every output.
>
> Companion documents: `pipeline_research.md` (datasets, papers, gaps), `ideas.md` (earlier ideation).
> Items marked **[verify]** are legal or factual details the team must confirm, ideally with a law-school collaborator, before the proposal is submitted.

---

## 0. TL;DR

| | |
|---|---|
| **User** | Legal-aid defense counsel (NALSA's Legal Aid Defense Counsel System, LADCS, and DLSA panel lawyers) preparing regular-bail matters for undertrial prisoners. Secondary users: junior advocates, law-clinic students, and Undertrial Review Committee (UTRC) staff. |
| **Problem** | These lawyers carry heavy caseloads and have little research support. Case files are long and scattered across FIRs, order sheets and earlier orders. The IPC→BNS / CrPC→BNSS transition (1 Jul 2024) makes citing the wrong statute easy. General-purpose LLMs invent precedents and facts. |
| **System** | Records Agent (extract → resolve statutes → build timeline → span-verify), then Defense Agent (plan issues → retrieve → draft → prosecutor critique → citation verification → revise), then a human approval gate. |
| **Main RQ** | Does a dossier-grounded, verifier-gated pipeline produce bail grounds that cover more of the court's actual reasoning, with fewer unsupported claims and citations, than single-pass RAG at the same token budget? Does the gain come from *adversarial critique* or from *verification*? |
| **Evaluation** | About 200 post-cutoff High Court bail orders, split into input and gold grounds; about 400 drafts with planted errors; an IPC↔BNS temporal test set; about 80 hand-verified dossiers; about 50 unsafe-action scenarios; and a small within-subjects user study. |
| **Capabilities** | All five. Fine-tuning = local QLoRA dossier extractor. RAG = statute + precedent retrieval with a date cutoff. Reasoning = issue-tree planning and a verify-revise loop. Agentic = multi-agent pipeline with state and human hand-off. Tools = Indian Kanoon, statute mapper, date calculator, span checker. |

---

## 1. Users and the problem

### 1.1 Why this user group (and why not the general public)

- About three-quarters of India's prison population are undertrials (NCRB *Prison Statistics India* **[verify latest figure]**). Many stay in custody mainly because they lack timely, well-prepared bail applications.
- NALSA's **LADCS** (rolled out since 2022 **[verify]**) created public-defender-style offices in districts. These lawyers handle many bail matters at once and have little paralegal or research support.
- Undertrial Review Committees check periodically which undertrials are eligible for release on custody-duration grounds (CrPC 436A → **BNSS 479**, which adds a one-third-of-maximum-sentence rule for first-time offenders **[verify]**). That check is mostly arithmetic and record-keeping, and it is error-prone.
- **We deliberately do not serve accused persons or the public directly.** Giving legal advice to laypeople raises unauthorised-practice and safety concerns. A trained lawyer who reviews every output is the right place for a human in the loop, and this is the core of the safety design.

### 1.2 Personas

| Persona | Context | Jobs to be done | Pain points | What they need from us |
|---|---|---|---|---|
| **P1: Priya, LADCS Assistant Defense Counsel** (primary) | District court, 40–80 active criminal matters, little research support | Prepare a regular-bail application and oral points for tomorrow's hearing | Reading 30–100 page files under time pressure; finding recent HC precedents on parity or delay; checking BNS/BNSS section numbers | A dossier she can check in minutes, grounds tied to record facts, citations she can trust, and clearly marked uncertainties |
| **P2: Arjun, junior advocate at a small criminal practice** (primary) | High Court and sessions practice, drafts for a senior | First draft of a bail petition in the senior's format | Precedent research takes hours; seniors reject drafts that contain a wrong citation | Editable draft, precedent list with the paragraph it relies on, anticipated prosecution objections |
| **P3: Law-clinic student / paralegal volunteer** (secondary) | Supervised by a lawyer; prepares case summaries | Summarise the file and compute custody duration | Doesn't know which facts matter legally | Structured dossier with a bail-factor checklist and explanations |
| **P4: UTRC secretary / DLSA staff** (secondary, stretch) | Reviews undertrial lists | Flag who may be eligible under BNSS 479 / 436A | Manual date calculations across many records | Custody-period calculator driven by the dossier timeline, with the source of every date shown |

**Explicit non-users:** accused persons, victims, the general public, judges. The judge simulator is a stress-testing tool for counsel, not a decision aid for courts.

### 1.3 User needs → requirements → metrics (traceability)

| # | User need | System requirement | How we measure it |
|---|---|---|---|
| N1 | "I must trust every fact in the draft" | Each dossier field and draft claim links to a source span; unsupported claims are blocked or flagged | Unsupported-fact rate; span-support precision |
| N2 | "A fake or wrong citation will embarrass me in court" | Citation verifier: the case exists, supports the claim, and is still good law; statute section is correct for the offence date | CLERC CFP; misgrounded rate; bad-law rate; temporal-correctness |
| N3 | "I have 15 minutes per file" | Dossier review screen, cached retrieval, latency budget | Time-on-task in the user study; p50/p95 end-to-end latency |
| N4 | "Don't make me miss a favourable fact" | Bail-factor checklist; critic asks "what's missing?" | Omission rate; ground-coverage recall |
| N5 | "Tell me what the other side will say" | Prosecutor-critic report shown to the user | Share of the court's adverse grounds anticipated |
| N6 | "Tell me when you're unsure" | Calibrated confidence per field; abstentions stated explicitly | Abstention precision/recall; calibration (ECE) of field confidence |
| N7 | "Client data must not leak" | Local fine-tuned extractor for raw records; PII redaction before any API call; no external writes | PII-leak rate on minefield scenarios |
| N8 | "I want to edit, not start over" | Every artefact is editable; edits propagate (dossier edit → draft regenerates the affected grounds only) | Edit-propagation correctness; SUS usability score |
| N9 | "Is my client eligible for release on custody grounds?" | Deterministic date calculator plus statute rule, both shown | Exact-match accuracy on period calculations |

---

## 2. Research questions and hypotheses

**RQ1 (main).** For regular-bail preparation, does a dossier-grounded, verifier-gated multi-agent pipeline do better than (a) a single LLM and (b) single-pass RAG, at the same token budget, on:
- coverage of the grounds the court actually relied on, and
- the rate of unsupported facts and bad citations?

- *H1:* ground-coverage recall rises by ≥10 points absolute, and unsupported-fact + citation false-positive rates fall by ≥50% relative to single-pass RAG.

**RQ2 (mechanism).** Where does the critique loop's benefit come from: **adversarial content** (prosecutor counter-arguments) or **verification** (fact and citation checking)?

- *H2 (following Kim 2026):* most of the drop in hallucination comes from verification, while adversarial critique mainly improves anticipation of the court's adverse grounds.
- A null result for adversarial critique is still reportable.

**RQ3 (fine-tuning / cost).** Can a QLoRA-tuned 7–8B model running locally extract dossiers as accurately as a frontier API model?

- *H3:* the tuned model gets within 3 F1 points on field extraction at a fraction of the cost, while keeping raw records on local hardware.

**RQ4 (tool vs parametric).** Does a date-aware statute-mapping tool eliminate temporally wrong section citations (IPC vs BNS, CrPC vs BNSS), compared with letting the LLM map sections from its own knowledge?

- *H4:* temporal-correctness ≥ 98% with the tool vs noticeably lower without it, with the largest gap on split, merged and renumbered sections.

---

## 3. Scope

**In scope**
- **Regular bail** in High Courts and Sessions Courts: CrPC 437/439 ↔ BNSS 480/483 **[verify mapping]**.
- Custody-duration eligibility under 436A ↔ BNSS 479.
- English-language judgments and orders.
- Two High Courts with large English bail volumes, e.g. Delhi HC and Allahabad or Punjab & Haryana HC. The final choice depends on corpus quality.
- Inputs:
  - Primary: judgment and order text.
  - Secondary: eCourts order sheets, if the scraper works.
  - Stretch: FIR scans.

**Out of scope (future work)**
- Anticipatory bail (BNSS 482), trials and appeals.
- Hindi input (HLDC, stretch only).
- Advice for the public.
- Automatic filing of any kind.
- Predicting outcomes as a product feature.

**Why regular bail:**
1. A high-volume, high-impact task for the target users.
2. The legal test is fairly structured (a well-known factor set), which makes issue trees feasible.
3. Many short orders are public, and their reasoning gives us gold grounds.
4. It is time-sensitive, so time savings matter to users.

---

## 4. System architecture

### 4.1 Overview

```
                         ┌──────────────────────────────┐
  Lawyer UI  ◄──────────►│  Coordinator (state machine)  │◄──── Trace store (every step, tool call, version)
  (review/edit/approve)  └───────┬──────────────┬───────┘
                                 │              │
             ┌───────────────────▼───┐   ┌──────▼─────────────────────────────┐
             │ COURT-RECORDS AGENT    │   │ DEFENSE-PREPARATION AGENT           │
             │ R1 Ingest & segment    │   │ D1 Issue planner (bail-factor tree) │
             │ R2 Extractor (QLoRA)   │──►│ D2 Retrieval planner (agentic RAG)  │
             │ R3 Statute resolver ⚙  │   │ D3 Drafter                          │
             │ R4 Timeline builder ⚙  │   │ D4 Prosecutor critic                │
             │ R5 Span verifier ⚙     │   │ D5 Citation verifier ⚙              │
             │ → Dossier (v1)         │   │ D6 Reviser (≤3 rounds)              │
             └──────────┬─────────────┘   │ D7 Judge stress-test (optional)     │
                        │  HUMAN GATE 1   └──────────────┬──────────────────────┘
                        │  (dossier check)               │  HUMAN GATE 2 (brief approval)
                        ▼                                ▼
                  Dossier (approved) ───────────► Bail brief + critic report + citation table
   ⚙ = deterministic tool / non-LLM component
```

**Design principles**
1. Deterministic where possible:
   - date arithmetic, statute mapping and citation resolution are **tools**, not LLM guesses;
   - schemas are enforced with JSON-schema validation.
2. Nothing downstream consumes an unverified fact. The drafter can refer only to *dossier field IDs* and *verified retrieval IDs*.
3. There are two human gates, and the user's corrections at Gate 1 flow into the defense stage.
4. There are no state-changing external actions. The system produces documents and never files, sends or contacts anyone. `request_human_approval` is the only "action".
5. The system degrades gracefully: every external dependency has a cache or fallback (§6.4).

### 4.2 Orchestration and state

Orchestration is an explicit state graph: LangGraph, or plain Python with a typed state object. Agentic loops are allowed only at defined points, each with a budget:

| Loop | Decides | Budget | Exit condition |
|---|---|---|---|
| R2↔R5 extraction repair | Re-extract fields the verifier rejected | ≤2 retries per field | Field verified, or marked `UNSUPPORTED` → shown to user |
| D2 retrieval planning | Which queries, filters and tools to use next; when to stop searching | ≤8 tool calls per issue | ≥k verified supporting authorities, or "no authority found" (reported, never invented) |
| D3→D4→D5→D6 critique loop | Revise which grounds, drop which citations | ≤3 rounds; token cap | Verifier passes and no new critic objections, or budget hit (remaining issues listed) |
| Tool-error recovery | Retry, reformulate, fall back to cache, or escalate | ≤2 retries per call | Success, or explicit failure shown to the user |

**Case state (per matter):**
- `dossier` (versioned)
- `issue_tree`
- `retrieval_log`
- `drafts[]`
- `critic_reports[]`
- `verifier_reports[]`
- `user_edits[]`
- `approvals[]`

**Cross-session memory (per user, stretch):** preferred draft format, precedents the user has pinned or rejected, and bench-specific notes the user entered. This memory is never used as a factual source for the draft.

### 4.3 Dossier schema (core artefact)

```json
{
  "case_id": "DLHC-BAIL-2025-0142",
  "fields": [
    {"id": "F7", "name": "offence_sections", "value": [{"code": "BNS", "section": "318(4)"}],
     "source_spans": [{"doc": "order_2025-03-02", "char": [1204, 1261]}],
     "confidence": 0.94, "status": "VERIFIED",
     "resolver_note": "FIR date 2024-09-14 ≥ 2024-07-01 → BNS applies; IPC equivalent 420"},
    {"id": "F12", "name": "custody_start", "value": "2024-09-16", "status": "VERIFIED", "...": "..."},
    {"id": "F13", "name": "custody_days_as_of_hearing", "value": 198,
     "computed_by": "date_calc(F12, hearing_date)", "status": "COMPUTED"},
    {"id": "F19", "name": "criminal_antecedents", "value": null, "status": "UNSUPPORTED",
     "note": "Not mentioned in record — ask counsel"}
  ],
  "timeline": [{"event": "FIR registered", "date": "2024-09-14", "field_refs": ["F3"]}, "..."],
  "cited_prior_cases": [{"citation": "...", "ik_id": "...", "resolved": true}],
  "open_questions": ["Co-accused bail status (parity) not in record"]
}
```

Field set: parties; court; case number / CNR; FIR number and date; police station; offence date; sections, both as written and resolved; arrest and custody dates; previous bail applications and their outcomes; co-accused and their bail status (parity); charge-sheet filed or not (and date); stage of trial; antecedents; the prosecution's stated objections; medical, age or family circumstances; recovery and evidence status; prior cases cited in the record.

This follows the attribute set of IndianBailJudgments-1200 and IBPS (custody duration, antecedents, health, and so on), extended with span provenance.

### 4.4 Components in detail

**R1 Ingest and segment**
- Parse PDF or text. Optional OCR for FIR scans (Tesseract/docTR; ICDAR-2023 FIR dataset for testing).
- Label sentences with the **IL-TUR / OpenNyAI rhetorical-role model**: Facts, Arguments-Petitioner, Arguments-Respondent, Reasoning/Ratio, Decision.
- Run **InLegalNER** (`opennyaiorg/en_legal_ner_trf`) to get candidate entities (STATUTE, PROVISION, PRECEDENT, DATE, CASE_NUMBER, parties, and others).
- Screen for prompt injection: document text is treated only as data (§6.2).

**R2 Extractor (fine-tuned)**
- A QLoRA 7–8B model fills the dossier schema from segmented text and NER candidates, returning JSON with span offsets.
- A frontier API model is the comparison arm for RQ3.

**R3 Statute resolver (tool)** `map_section(code, section, offence_date, proceeding_date)`
- Built on the **IPC2BNS-Verify** concordance CSV, cross-checked row by row against the **NCRB SANKALAN / BPRD** official tables.
- Handles 1:1, split, merged, repealed and new sections (for example, organised crime and petty organised crime have no IPC equivalent **[verify]**).
- Applicability rules:
  - The **substantive** code is decided by offence date (IPC before 1 Jul 2024, BNS on or after).
  - The **procedural** code (CrPC vs BNSS) for pending matters is governed by the **BNSS s.531 savings clause** and the case law interpreting it **[verify with legal expert; encode as explicit rules]**.
  - Ambiguous cases return `AMBIGUOUS` with both candidates and the reason. The UI shows this; the system never picks silently.

**R4 Timeline builder (tool-assisted)**
- The LLM proposes events; `normalize_date` and `date_calc` do all normalisation and arithmetic.
- It computes custody days and checks eligibility against BNSS 479 / 436A thresholds, using the maximum sentence from `statute_lookup`.

**R5 Span verifier**
- For each field, an NLI or entailment check of the (field, value) claim against the cited span, using a small NLI model or an LLM judge with a strict prompt. ALCE-style: the cited span must *entail* the claim.
- Failures go back to R2 (repair loop). If a field still fails, it is marked `UNSUPPORTED`; it is never silently dropped or silently kept.

**Human Gate 1**
- Counsel reviews the dossier. Unsupported or low-confidence fields and `AMBIGUOUS` statutes are highlighted.
- Clicking any field shows its source span.
- Edits are logged: they become `USER_ASSERTED` fields, which are allowed downstream but labelled as such in the brief.

**D1 Issue planner (reasoning)**
- Builds a bail **issue tree** from a factor checklist:
  - gravity and nature of the offence
  - maximum sentence
  - custody period / 479 eligibility
  - charge sheet filed (so custodial interrogation is no longer needed)
  - parity with co-accused
  - antecedents
  - flight risk and roots in the community
  - risk of tampering with witnesses
  - delay in trial
  - health, age or gender circumstances
  - statutory bars (e.g. NDPS s.37, UAPA s.43D(5) twin conditions **[verify]**)
- Each node is instantiated only if dossier fields support it. Nodes are labelled *favourable*, *adverse* or *neutral* for the defense.
- This structure follows LEGIT's issue-tree rubrics, adapted to Indian bail.

**D2 Retrieval planner (agentic RAG)**
- Three indices:
  1. **Statute index**, closed-set: BNS/BNSS/BSA + IPC/CrPC/IEA sections from Open India Law. Retrieval is constrained to real section IDs, following AALawyer's closed-set idea.
  2. **Precedent index**: bail orders and judgments from the AWS Indian HC + SC corpora and Open India Law, chunked **by rhetorical role**, so ratio paragraphs are marked separately from obiter or submissions.
  3. **Dossier index**: the case file itself, for "Ask the file" Q&A.
- Retrieval pipeline:
  - hybrid BM25 + dense (InLegalBERT or BGE-M3), then a cross-encoder reranker;
  - metadata filters for court, date (**hard cutoff = hearing date of the case being evaluated**), offence section, and bench strength;
  - Indian Kanoon API (`ik_search`, `ik_doc`, `ik_citedby`) as a live tool when the local index doesn't cover something.
- The agent chooses queries per issue node, reformulates when results are poor, and stops when it has enough verified support or reports that it found none.

**D3 Drafter**
- Generates the grounds for bail, one per issue-tree node. Every sentence carries `[F#]` dossier refs and `[A#]` authority refs.
- Output format: the user's template, e.g. the numbered grounds of a bail application plus a short synopsis of oral points.

**D4 Prosecutor critic**
- Role: the Public Prosecutor.
- Produces objections from the adverse issue-tree nodes, finds counter-precedents, and names favourable facts the drafter ignored. It is instructed separately from D5 so the two can be ablated independently (RQ2).

**D5 Citation verifier (tool pipeline, not only an LLM)** checks each `[A#]`:
1. *Existence*: resolves to a real document (`ik_doc` or local ID).
2. *Support*: the cited paragraph entails the proposition (NLI or strict judge), and that paragraph is **ratio**, not submissions or obiter (rhetorical-role label).
3. *Good law*: `ik_citedby`, plus a treatment classifier over the citing paragraphs (overruled, distinguished, followed), seeded with **InIRAC** typed edges and **LeCNet** graph neighbours.
4. *Temporal*: the authority is dated before the cutoff, and any statute referenced is valid for the offence date (R3).
5. *Statutory*: section numbers are valid in the stated code.

Failures produce actionable messages for D6: drop, replace or qualify the citation.

**D6 Reviser** applies critic and verifier feedback. It is bounded to 3 rounds. The full diff between versions is kept.

**D7 Judge stress-test (optional)**
- A simulated bench reads the brief plus the critic's objections and lists which grounds it finds weak.
- Used only for the user's preparation and for the robustness analysis (§8.6). **Never shown as a prediction of the outcome.**

**Human Gate 2**
- Counsel reviews the brief alongside:
  - a **citation table** (authority → paragraph → verification status);
  - the **critic report** (anticipated objections plus suggested responses);
  - an **open-issues list** (what the system couldn't verify).
- Export is allowed only after the user approves.

### 4.5 Tool catalogue

| Tool | Args (typed) | Returns | Failure modes handled | Safety class |
|---|---|---|---|---|
| `ik_search` | query:str, doctype:enum, fromdate, todate:date | ranked doc IDs + snippets | rate limit → backoff; outage → local index | read-only |
| `ik_doc` | doc_id:str | text + citeList + citedbyList | 404 → mark unresolved | read-only |
| `ik_citedby` | doc_id:str, limit:int | citing docs + fragments | empty → "no treatment signal" | read-only |
| `local_search` | query, index:enum{statute,precedent,dossier}, filters | chunks + role labels + IDs | – | read-only |
| `statute_lookup` | code:enum{IPC,BNS,CrPC,BNSS,IEA,BSA}, section:str | text, max sentence, bailable/cognizable | invalid section → error (tests argument validity) | read-only |
| `map_section` | code, section, offence_date, proceeding_date | mapped section(s), rule applied, `AMBIGUOUS` flag | split/merge → multiple candidates | read-only |
| `normalize_date` / `date_calc` | str / date, date, unit | ISO date / duration | unparseable → ask user | pure |
| `span_check` | claim:str, doc_id, span | {entails, contradicts, neutral}, score | – | pure |
| `case_status` (mock eCourts) | cnr:str (validated format) | hearings, next date, stage | invalid CNR → error, never guessed | read-only (mock) |
| `redact_pii` | text | redacted text + map | – | pure |
| `request_human_approval` | artifact_id, summary | approve / edit / reject | timeout → stays pending | **gate** |

**No tool can write externally.** "Minefields" (forbidden events, following ToolSandbox) are:
- exporting without approval
- sending unredacted victim or minor PII to an external API
- inventing a CNR or section argument
- stating a predicted outcome as advice
- citing an unresolved authority in the final brief

### 4.6 Models

| Role | Model (primary) | Alternatives / ablation |
|---|---|---|
| Coordinator, D1, D3, D6 | Claude Sonnet 5.5 (API) | open 8B model (cost ablation) |
| D4 critic, D5 support-judge, D7 | Claude Haiku 4.5 (cheaper roles) | same model as drafter (ablation) |
| R2 extractor | **QLoRA Qwen-class or Llama-class 7–8B** (current open release) | frontier API (RQ3 comparison); base 8B without tuning |
| Embeddings / rerank | InLegalBERT, BGE-M3 + a cross-encoder | BM25 only |
| NLI for span checks | small NLI model (DeBERTa-v3 NLI family) | LLM judge |
| **Evaluation judge** | a *different model family* from the generator, to reduce self-preference bias | validated against human labels (§8.5) |

### 4.7 Fine-tuning plan

- **FT1 (main): dossier extractor.**
  - *Data:*
    - about 3–5K bail orders from the AWS HC corpus;
    - silver labels from a frontier model, filtered by the span verifier (only examples where every field is entailed);
    - InLegalNER annotations as extra entity supervision;
    - the IndianBailJudgments-1200 attribute schema used for field alignment.
  - *The gold dev/test sets are hand-verified and never used for training.*
  - *Setup:* QLoRA 4-bit, r=16, α=32, lr 1e-4–2e-4, 2–3 epochs, 8–16K context, JSON-constrained output. Precedent: FactLegalLlama used QLoRA r=16 on a single A100, and our task is narrower.
  - *Compute:* about 6–12 GPU-hours per run on an A100 or L4; 3–4 runs covering data size (1K/3K/5K) and with vs without span-grounded filtering.
- **FT2 (stretch): support and treatment classifier** (claim, paragraph) → {supports, contradicts, irrelevant} plus a treatment label.
  - *Data:* planted perturbations of verified citations, InIRAC typed edges, and LeCNet neighbours.
  - *Model:* a small encoder (InLegalBERT) or a 1–3B LoRA model.

---

## 5. User-centric design

### 5.1 Main user journey (P1, Priya, the evening before a hearing)
1. **Upload** the case bundle (FIR copy, previous orders, order sheet), or paste a CNR, which fetches from the mock eCourts tool.
2. **Dossier view** (about 2 minutes to review):
   - a timeline strip with dates;
   - field cards coloured VERIFIED / COMPUTED / UNSUPPORTED / AMBIGUOUS;
   - clicking a field opens the highlighted source span;
   - a **custody calculator** panel showing 479 eligibility and its working;
   - Priya fixes one field and answers one open question ("co-accused granted bail? yes, on date X").
3. **Approve the dossier** (Gate 1).
4. **Brief view** (about 10 minutes):
   - grounds, each tagged with its factor, underlying facts `[F#]` and authorities `[A#]`;
   - hovering an authority shows the relied-on paragraph and its verification ticks (exists, supports, ratio, good law, date-valid);
   - a side panel lists the **anticipated objections** from the prosecutor critic with suggested replies;
   - an **open issues** list, e.g. "No HC authority found for parity under BNS 318(4); nearest is the IPC 420 line, shown with a caveat".
5. **Edit** freely. Editing a fact re-runs only the affected grounds and re-verifies them.
6. **Approve and export** (Gate 2), producing DOCX/PDF plus a citation annex. There is no auto-filing.
7. **Ask the file**: a grounded Q&A panel over the dossier and case documents, e.g. "when was the charge sheet filed?". Answers carry span citations and abstain when the answer isn't in the record. This is the chatbot, scoped to counsel's own case file.

### 5.2 Design rules drawn from user needs
- **Show provenance everywhere** (N1, N2). No claim appears without a clickable source.
- **Make uncertainty explicit** (N6). Use the four statuses, calibrated confidence, and "not in record" instead of guessing.
- **The user is the authority** (N8). User edits override model output and are labelled `USER_ASSERTED` in the brief.
- **Put important things first** (N3). The dossier shows risky or uncertain fields first; the brief shows unverified items first.
- **Counter automation bias.** Reviewing is framed as checking ("3 items need your attention"). Low-confidence items can't be approved in bulk.
- **Plain language.** Every rejection message says *why* (e.g. "This case was distinguished by X (2023) on this point").
- **Accessibility and low bandwidth.** A lightweight web UI (Streamlit or Gradio for the prototype). Works with a cached corpus when offline. English UI; Hindi is future work.

### 5.3 How users are brought into the project
- **Week 1:** 3–5 short interviews with legal-aid lawyers or law-clinic students (NALSAR is nearby; IIIT-H may have contacts) **[confirm feasibility]** to validate the personas, the factor checklist and the dossier fields. Findings are recorded in `docs/user_research.md`.
- **Week 7:** a small within-subjects user study (§8.7).
- If lawyers aren't available, use law students or clinic volunteers and state this as a limitation.

---

## 6. Robustness, safety and ethics

### 6.1 Failure modes and guards
This summarises `pipeline_research.md` §1.

| Risk | Guard | Metric |
|---|---|---|
| Fabricated citation | D5 existence check; unresolved citations can't be exported | CLERC CFP |
| Misgrounded citation (real case, wrong proposition) | D5 support check + ratio check | Misgrounded rate (human-labelled sample) |
| Overruled or distinguished authority | `ik_citedby` + treatment classifier | Bad-law rate on planted set |
| Wrong-era statute (IPC vs BNS) | R3 date-aware resolver; `AMBIGUOUS` status | Temporal-correctness |
| Fact not in the record | Drafter can only reference `[F#]`; R5 verifies | Unsupported-fact rate |
| Favourable fact omitted | D1 checklist + critic "missing facts" pass | Omission rate |
| Arithmetic error (custody days) | `date_calc` only | Exact match |
| Prompt injection inside documents | Document text is placed in delimited data blocks; tools are read-only and allow-listed; an injection classifier and heuristics flag imperative text aimed at the model | Injection success rate on planted docs |
| OCR or format noise | Normalisation; the verifier catches drift | Accuracy under perturbation (§8.6) |
| Tool outage / rate limit | Cache, then local index, then an explicit "couldn't verify" | Recovery rate; no silent failures |
| Invalid tool arguments | JSON-schema validation before the call; error returned to the agent | BFCL-style AST accuracy |
| Runaway loops or cost | Per-loop and per-case token and step budgets | Budget-hit rate; cost per case |
| Judge simulator swayed by style | Not used as ground truth; tested for robustness | Persuadability delta |
| Evaluation leakage | Retrieval corpus cut off at hearing date; target order and its `citedby` set removed | Leakage audit log |
| Training-data memorisation | Test orders dated after model cutoffs; results reported pre- vs post-cutoff | Split comparison |

### 6.2 Safety policy (enforced in code, not only in prompts)
- **Never:** file or send anything; contact anyone; present outcome predictions as advice; output victim identity in sexual-offence or POCSO matters (s.72 BNS / s.228A IPC **[verify]**); cite unresolved authorities.
- **Always:** label AI-generated drafts; keep the full trace; require Gate 2 before export.
- **PII:** `redact_pii` runs before any external API call. Raw records are processed by the local FT1 model where possible. That privacy requirement is the *user-driven reason for fine-tuning*.

### 6.3 Fairness and ethics
- We use only **public judgments and orders**. There is no real client data. User-study cases are public or synthetic.
- **Bias audit:** compare output quality (coverage, unsupported rate) across offence families, courts, and custody-length bands. Report judge-simulator disparities as a limitation, not a feature.
- **Framing:** the system supports *preparation*. It doesn't predict outcomes, and it doesn't replace counsel.
- Get institute ethics clearance before any user study with human participants **[check IIIT-H process]**.

### 6.4 Graceful degradation
- Indian Kanoon unavailable → local AWS HC/SC index, flagged "verified against local corpus (coverage X%)".
- Rhetorical-role model fails on a document → treat all paragraphs as non-ratio, so support checks become more conservative.
- Extractor JSON invalid → constrained decoding and retry, then a frontier fallback, then "manual entry needed".

---

## 7. Data plan

### 7.1 Sources

| Purpose | Dataset | Use |
|---|---|---|
| Main case corpus | **AWS Indian HC Judgments** (17.8M, CC BY 4.0), **AWS Indian SC**, **Open India Law** | Bail orders for evaluation and the precedent index |
| Live retrieval / citation graph | **Indian Kanoon API** (`cites:` / `citedby:`) | D2, D5 |
| Statutes | **Open India Law** section-level enactments (BNS/BNSS/BSA/IPC/CrPC/IEA) | Statute index, `statute_lookup` |
| IPC↔BNS mapping | **IPC2BNS-Verify** CSV + **NCRB SANKALAN / BPRD** tables | R3 + RQ4 test set |
| Bail attributes | **IndianBailJudgments-1200**, **IBPS** schema, **HLDC** bail subset | Dossier schema design; silver labels; stretch Hindi |
| Segmentation / NER | **IL-TUR** RR and L-NER, **OpenNyAI** models, **InLegalNER** | R1 |
| Structured legal knowledge | **InIRAC** (IRAC fields, event chains, typed edges), **LeCNet** (citation graph) | D5 treatment seeds; timeline schema |
| Statute prediction | **PROSLEX**, **ILSI/LeSICiN** | Extra RQ4 cases (fact → section → era) |
| Retrieval benchmarks | **IL-PCR** (µF1@K), **AILA 2019/20**, **IL-PCSR** | Checking the D2 retriever against published baselines |
| Case metadata | **DDL judicial data** (81M district cases) | Realistic distributions of timelines and sections for synthetic tests; eligibility-calculator tests |
| Order sheets | **openjustice-in eCourts scraper** | Secondary input (if feasible) |
| FIR scans | **ICDAR-2023 FIR dataset** | Stretch: OCR ingestion test |
| Transferable evaluation designs | CLERC, LegalBench (rule application), Large Legal Fictions, overruling pairs (JURIX 2025), J1-EVAL, LegalAgentBench, ToolSandbox | Metric definitions; false-premise probes; agent-evaluation design |

### 7.2 Evaluation sets (all with known ground truth)

| Set | Size | Construction | Annotation |
|---|---|---|---|
| **E1: Bail grounds** (RQ1, RQ2) | 200 orders (40 dev / 160 test) | Regular-bail orders from 2 HCs, **hearing date after the latest model cutoff where possible** (2025–26, BNSS era), stratified by offence family and outcome (granted/rejected). The RR model splits each into **input** (facts + both sides' arguments) and **gold** (court's reasoning). | 2 annotators turn the reasoning into a list of grounds labelled with factor type and polarity; report Cohen's κ on 25%; a third person adjudicates. Gold precedents = authorities the court cited. |
| **E2: Planted-error drafts** (D5, RQ2) | 400 drafts | Take verified system drafts and inject one error each: fabricated citation, real citation with wrong proposition, obiter-as-ratio, overruled/distinguished authority, repealed IPC section for a post-2024 offence, wrong custody days, fact not in the record. Plus 20% clean controls. | Ground truth comes from construction; spot-check 10% by hand. |
| **E3: Temporal statutes** (RQ4) | ~1,140 IPC2BNS-Verify queries + 200 hand-built cases | Hand-built cases: fact pattern + offence date + proceeding date, focused on split, merged, new and repealed sections and the s.531 transition cases | Mapping checked against NCRB tables; transition rules checked by a legal expert **[verify]** |
| **E4: Gold dossiers** (RQ3) | 80 cases (20 dev / 60 test), drawn from E1 | Hand-filled dossier with span offsets and timeline | 2 annotators on 20 cases for κ / field-level agreement |
| **E5: Minefields and robustness** | ~50 scenarios + perturbed copies of 40 E1 cases | Scenarios: PII request, "file this now", missing CNR, invalid section, tool outage, injected instruction in a document. Perturbations: OCR noise, date-format variants, reordered paragraphs, missing pages. | Expected safe behaviour specified in advance |
| **E6: User study** | 4 cases | 2 grant-type and 2 reject-type public orders, with the reasoning hidden | Expert rubric for brief quality |

**Leakage protocol:**
- For each E1 case, the retrieval corpus is filtered to documents dated **before** the hearing date.
- The order itself, and every document that cites it, are removed.
- All filtering is logged.

---

## 8. Evaluation plan

### 8.1 Baselines

| ID | System | Purpose |
|---|---|---|
| B0 | Single frontier LLM, zero-shot: "draft bail grounds from these facts" | Lower bound, no harness (the announcement explicitly allows this) |
| B1 | B0 + single-pass RAG (top-k precedents + statutes, NyayaRAG-style) | Standard RAG |
| B2 | SAMVAD-style multi-agent debate (defense ↔ prosecution ↔ judge) without verifier or dossier | Closest prior Indian system |
| B3 | Tuvey & Sen-style argument generation | Published Indian argument-generation baseline |
| **Ours** | Full pipeline | – |

All systems get the **same token budget** per case, and the same retrieval corpus and cutoff.

### 8.2 Ablations (one per capability the RQs depend on)

| Ablation | Removes | Tests |
|---|---|---|
| A1 − dossier | Drafter reads raw text instead of the verified dossier | Value of the Records Agent |
| A2 − verifier (D5) | Critic only | RQ2 |
| A3 − adversarial critic (D4) | Verifier only | RQ2 |
| A4 − both D4 and D5 | Single-pass drafting from the dossier | RQ1 |
| A5 − tools | LLM does statute mapping, date maths and citation "recall" itself | RQ4 + tool value |
| A6 − RAG | No retrieval; parametric knowledge only | RAG value |
| A7 − role-aware chunking | Plain fixed-size chunks | Retrieval design |
| A8 − issue planner | Drafter without the D1 tree | Reasoning value |
| A9 − FT1 | Base 8B / frontier API as extractor | RQ3 |
| A10 − DB coverage | Verifier with 25/50/100% of the corpus | Ovcharov-style coverage sensitivity |

### 8.3 Metrics by capability and module

| Capability / module | Metric | Definition / source |
|---|---|---|
| **Records: extraction** (FT + reasoning) | Field-level P/R/F1 (exact + normalised); span-support precision; unsupported-field rate; ECE of field confidence | E4 gold; ALCE-style NLI entailment |
| **Records: timeline** | (event, date) tuple F1; date-normalisation accuracy; Kendall τ of event order; custody-days exact match; 479 eligibility accuracy | TempEval-3-style + E4 |
| **Statute resolver** (tool) | Section F1; **temporal-correctness rate**; repealed-section citation rate; abstention precision/recall on `AMBIGUOUS` | E3 |
| **Retrieval** (RAG) | Precedent recall@k / nDCG@10 against court-cited authorities; µF1@K on IL-PCR (sanity check vs published numbers); statute retrieval accuracy | E1, IL-PCR |
| **Argument quality** (reasoning) | **Ground-coverage recall** (share of gold grounds matched, Key-Point-Analysis style, matching by LLM judge validated against humans); adverse-ground anticipation (share of court's adverse grounds raised by the critic); **omission rate** of favourable dossier facts (after Zhang et al.'s 3-ply metrics); issue-tree coverage (LEGIT-style) | E1 |
| **Faithfulness / citations** | **Unsupported-fact rate** (FActScore-style atomic claims vs dossier/sources); **CLERC CR / CP / CFP**; **misgrounded rate** (Magesh typology); bad-law rate | E1, E2 |
| **Verifier** | Detection P/R/F1 per error type; steps and cost per check; performance vs DB coverage | E2 |
| **Draft quality (rubric)** | 1–5 rubric: legal soundness, use of record facts, citation discipline, procedure and format, suitable voice for court (last three from "Are LLMs Court-Ready?"); Wachsmuth cogency sub-dimensions (acceptability, relevance, sufficiency) | E1 sample, LLM judge + humans |
| **Agentic** | Task completion (brief passes all hard checks); AgentBoard-style **progress rate** over required sub-goals (dossier verified → issues planned → authorities verified → brief approved); loop rounds used; budget-hit rate; **pass^k** (k=3) reliability, τ-bench style | E1 |
| **Tool calling** | BFCL-style **AST accuracy** (right tool, valid arguments, correct types); irrelevance detection (no call when none is needed); error-recovery rate on injected tool failures; redundant-call rate | Traces on E1 + E5 |
| **Safety** | **Unsafe / unapproved action rate** = minefield hits / scenarios (ToolSandbox-style); PII-leak rate; injection success rate; unapproved-export count (must be 0) | E5 |
| **Robustness** | Relative drop in key metrics under perturbation | E5 perturbed E1 |
| **Efficiency** | Tokens and cost per case; p50/p95 latency; local vs API share | All runs |
| **User** | Time-on-task; expert-rated brief quality; planted-error catch rate (automation-bias probe); SUS; trust-calibration survey | §8.7 |

### 8.4 Statistics
- Paired comparisons on the same cases:
  - paired bootstrap 95% CIs;
  - Wilcoxon signed-rank for per-case continuous scores;
  - McNemar for binary outcomes.
- Holm correction across the main hypotheses.
- 3 runs per configuration (temperature > 0) for pass^k and variance; report mean ± std.
- Pre-register H1–H4 thresholds in `docs/prereg.md` before running the test set. Develop only on dev splits.

### 8.5 Validating the LLM judge
- The judge is a different model family from the generator.
- Two humans label ~80 (case, output) items for ground matching, claim support, and the rubric.
- Report **Cohen's κ** (not raw % agreement; Thakur et al. 2024), Krippendorff's α for the rubric, and Spearman ρ.
- If κ < 0.6 on a dimension, that dimension is reported **only** on human-labelled data.
- Check position and verbosity bias: swap order, and pad outputs with filler.

### 8.6 Robustness and judge-simulator analysis
- Run E5 perturbations on the full system and on B1.
- Judge-simulator persuadability (Suttle & Lillis):
  - style-only rewrites (same content, more rhetoric);
  - swapping argument order;
  - offence-label swaps with identical facts.
- Report how much the simulator's assessments shift. This justifies not treating D7 as ground truth.

### 8.7 User study (small, within-subjects)
- **Participants:** 6–10 law students, clinic volunteers or junior advocates (plus 1–2 practising lawyers if possible).
- **Task:** prepare bail grounds for 2 cases *with* the system and 2 *without*, counterbalanced (Latin square).
- **Measures:**
  - time-on-task;
  - brief quality scored blind by an expert rubric;
  - **planted-error catch rate**: one planted bad citation in the system's output tests over-reliance;
  - SUS;
  - a short trust and usefulness questionnaire;
  - qualitative interview (5 minutes).
- **Honest scope:** small N, so results are directional and reported with CIs and individual data points.

### 8.8 Failure analysis
- Categorise all errors on 40 test cases using the **LexAgentHallu** taxonomy (legal vs agent-procedure errors), plus our own types: temporal-statute, provenance, omission, tool-argument.
- Show 4–6 qualitative case studies: a success, a critic-caught error, a verifier miss, an `AMBIGUOUS` statute, and a case where the system disagreed with the court and why.

---

## 9. Compute and budget

| Item | Estimate | Notes |
|---|---|---|
| FT1 QLoRA runs | 3–4 runs × 6–12 GPU-h ≈ **25–45 GPU-h** (A100 40GB or L4) | Colab Pro, Kaggle, or IIIT-H cluster; plus ~5 GPU-h inference |
| FT2 (stretch) | ~5 GPU-h | Small encoder / 1–3B LoRA |
| Silver-label generation (frontier) | ~4K orders × ~15K tokens ≈ **60M tokens** in | Cut with prompt caching of the fixed schema and instructions |
| Main experiments | 160 test cases × (5 systems + 10 ablations) × 3 runs × ~40K tokens ≈ **290M tokens** | Largest cost. Reduce by running ablations on a 60-case subset and using cheaper models for critic and verifier roles. Target ≈ **100–150M tokens total**. |
| Judge evaluation | ~20M tokens | Different model family |
| Indian Kanoon | Within the ₹10k/month non-commercial credit | Cache every `ik_doc` call |
| Embedding and indexing | ~1–2M chunks on 1 GPU for a few hours | Index only the 2 chosen HCs + SC, bail-related subset |

Before the proposal, fill in exact cost using **current API prices** for the chosen models. Keep a live budget tracker in `experiments/budget.csv`.

---

## 10. Timeline (8 weeks + proposal)

Workstreams for a team of 4 (adjust as needed):
- **W-R** Records Agent
- **W-D** Defense Agent
- **W-E** Evaluation & data
- **W-U** UI, users & infrastructure

| Week | W-R | W-D | W-E | W-U |
|---|---|---|---|---|
| **0** | **Proposal to TA. No implementation until approved.** | | | |
| 1 | Download corpora; RR + NER pipeline on the sample | Statute index; IPC2BNS-Verify vs NCRB check | Select E1 orders; annotation guidelines; pilot κ on 10 cases | User interviews; personas confirmed; UI wireframes |
| 2 | Dossier schema v1; frontier extractor; `date_calc`, `map_section` | Precedent index (role-aware chunks, date filters); `ik_*` tools + cache | Annotate E1 dev + E4 dev; build E3 | Coordinator state graph; trace store |
| 3 | R5 span verifier + repair loop | D1 issue planner; D3 drafter; B0/B1 baselines | E1 test annotation; start E2 generator | Dossier review UI (Gate 1) |
| 4 | Silver-label generation for FT1 | D4 critic; D5 verifier (existence, support, ratio, citedby) | E2 complete; E5 scenarios; judge-validation labels | Brief UI + citation table (Gate 2) |
| 5 | **FT1 QLoRA runs** + evaluation on E4 | D6 revise loop; B2/B3 baselines | Dev-set tuning ends; **freeze and pre-register** | "Ask the file" Q&A; export |
| 6 | **Main experiments + ablations on test sets (all streams)** | | | |
| 7 | Robustness (E5) | Judge-simulator analysis | Stats, judge κ, failure taxonomy | **User study** |
| 8 | **Write-up** (paper format), demo video, repo cleanup, limitations | | | |

**Milestones:**
- End of week 2: end-to-end "walking skeleton" on 5 cases.
- End of week 5: frozen system.
- End of week 6: all numbers in.

---

## 11. Risks and fallbacks

| Risk | Likelihood | Fallback |
|---|---|---|
| Gold grounds noisy (low κ) | Med | Narrow to one HC and one offence family (e.g. cheating/NDPS); tighten the guideline; report κ honestly |
| Not enough post-cutoff BNSS-era orders in the corpus | Low–Med | Top up from Indian Kanoon (2025–26); otherwise report pre/post-cutoff splits separately |
| eCourts scraping blocked | High | Judgment and order text only; mock `case_status` built from DDL-style metadata |
| RR model poor on HC bail orders (short, unstructured) | Med | Annotate 100 orders for a quick fine-tune of the RR classifier, or use LLM segmentation checked on dev |
| s.531 transition rules legally unclear | Med | Encode only clear rules; everything else → `AMBIGUOUS` and escalate to the user. Makes a good qualitative section. |
| FT1 doesn't reach parity | Med | Still reportable (RQ3 negative). Keep frontier extraction with PII redaction as the production path. |
| API budget overrun | Med | Ablations on a 60-case subset; cheaper models for critic and verifier; aggressive caching |
| No lawyers for the user study | Med | Law students / clinic; state as a limitation |
| Critic ablation shows no effect | Med | That is an RQ2 finding (consistent with Kim 2026), not a failure |

---

## 12. Deliverables and repo layout

```
lma-group-project/
├── plan.md  pipeline_research.md  ideas.md
├── docs/            proposal.pdf, user_research.md, annotation_guidelines.md, prereg.md, ethics.md
├── data/            raw/ (gitignored), processed/, eval/{E1..E6}/, splits.json, leakage_log.jsonl
├── src/
│   ├── records/     ingest.py, segment.py, extract.py, statute_resolver.py, timeline.py, span_verify.py
│   ├── defense/     planner.py, retrieve.py, draft.py, critic.py, cite_verify.py, revise.py, judge_sim.py
│   ├── tools/       ik_api.py, statute.py, dates.py, ecourts_mock.py, pii.py, schemas/
│   ├── rag/         index_build.py, hybrid_search.py, rerank.py
│   ├── orchestrator/ graph.py, state.py, budgets.py, trace.py
│   └── ui/          app.py
├── finetune/        ft1_extractor/ (data_gen.py, train_qlora.py, config.yaml), ft2_support/
├── eval/            metrics/, judges/, run_baselines.py, run_ablations.py, stats.py, user_study/
└── experiments/     configs/, results/, budget.csv
```

**Final deliverables:**
- working prototype with the two human gates
- the evaluation sets E1–E5 and annotation guidelines
- all experiment configs and traces
- a workshop-style paper
- a demo

---

## 13. Proposal checklist (from announcement §8)

| Required item | Where in this plan |
|---|---|
| Title | Header: *NyayaSahayak: Verified Bail Preparation for Legal-Aid Defense Counsel* |
| Domain and target user | §1.1–1.2 |
| Problem statement (5–8 sentences) | Condense §0 + §1.1 |
| Research question | §2 (RQ1 main; RQ2–4 supporting) |
| Why it matters | §1.1 (undertrials, LADCS workload, BNS transition) |
| What's missing in existing approaches | `pipeline_research.md` §0: outcome-only evaluation (OBJECTION, SAMVAD, AgentsCourt); no raw-record dossiers; no IPC→BNS work; no Indian citation verifier |
| Five capabilities and why each is needed | §0 table + §4.4/4.7; ablations in §8.2 |
| Architecture diagram | §4.1 |
| Expected novelty | (1) first span-verified dossier → defense pipeline for Indian bail; (2) separating verification from adversarial critique (RQ2); (3) date-aware IPC↔BNS resolver and test set; (4) grounded-coverage evaluation against real court reasoning, with leakage controls |
| Dataset / evaluation environment | §7 |
| Baselines | §8.1 |
| Metrics incl. capability-specific and safety | §8.3 |
| Compute plan | §9 |
| Risks and fallbacks | §11 |

---

## 14. Decisions the team needs to make before the proposal

1. **Which two High Courts?** Delhi HC vs Allahabad or P&H. Base the choice on the volume of English bail orders in the AWS corpus from 2025–26.
2. **Offence scope:** all regular-bail matters, stratified, or one offence family (lower annotation noise, weaker generality).
3. **API model and budget ceiling.** Fix before the compute section is final.
4. **Legal collaborator:** can we get a law-school contact (e.g. a NALSAR clinic) for the s.531 rules, guideline review and the user study?
5. **FT2 in or out:** include only if weeks 1–4 are on schedule.
