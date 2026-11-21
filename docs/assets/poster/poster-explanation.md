# The Vakeel-Sahayak.ai poster, explained from zero to hero

This document walks through every block of the poster *Vakeel-Sahayak.ai: A Multi-Agent Harness for Bail Drafting* (Team Optimus Prompt, LMA Group Project 2026, IIIT Hyderabad), in the order a visitor reads it. It explains every plot, every number and both diagrams, and it answers the questions people tend to ask at a poster stand. The language is kept simple, but nothing is waved away: where the poster simplifies, this document says so and gives the precise version.

Every number here was checked against the project's result files (`docs/results/search/final_report/`, `docs/results/poster/`, `docs/technical-report/technical_report.tex`) and the code. Section 14 lists the few places where the poster's short wording needs a precise footnote.

Contents

1. The 60-second version
2. The title: what "multi-agent harness" means
3. Problem statement (with a crash course in Indian bail law)
4. The research question, word by word
5. Methodology: the four ideas
6. The architecture diagram, box by box
7. The four data boxes
8. The RAG pipeline diagram
9. How the metrics are calculated (the win/tie/loss rule)
10. Results against baselines (the first chart)
11. Architectural experiments (the second chart)
12. Ablation studies (the third chart)
13. Future work, acknowledgment and references
14. Where the poster simplifies: the precise versions
15. Questions people will ask, with answers
16. Number cheat sheet

---

## 1. The 60-second version

**What it is.** Vakeel-Sahayak.ai ("lawyer's assistant") helps legal-aid lawyers in India prepare a regular bail application. It reads the case papers, builds a fact sheet in which every fact points to the page it came from, works out bail rights from the dates, plans what evidence each argument needs, searches typed indexes of court orders and statutes, drafts the arguments with citations, checks every sentence against its source, lets a simulated prosecutor attack the draft, and lists everything it could not support as an open issue for the lawyer. Nothing can be exported until the lawyer approves it, and that rule is in code.

**What was tested.** Whether this structured "harness" of six agents produces better-grounded drafts than seven simpler systems built on the **same** language model (Sarvam-105B). Same model, same facts, same checklist: only the system around the model changes.

**What was found.** The first complete version (the **Base**) did *not* beat the simple baselines. The team read its outputs case by case, found four root causes, built eight candidate fixes (X1 to X8), and chose a final system, **VS-Final** = Base + X1 + X4 + X5 + X7, on 30 development cases. It was confirmed on 20 more, then frozen and tested once on 80 sealed, unseen cases:

- **46 wins, 69 ties, 5 losses** against the seven baselines over 25 quality measures;
- **0 invented citations** (the two strongest baselines invent 95% and 64% of theirs);
- a supported argument for **61%** of the answerable bail grounds (best baseline 23%);
- cited passages that support their sentence **71%** of the time (baselines 10% or less);
- **110** database lookups per case against **188** for the baseline that searches everything;
- **80 of 80** early export attempts blocked before the lawyer's approval.

---

## 2. The title: what "multi-agent harness" means

**"Vakeel-Sahayak.ai"**: *vakeel* is Hindi/Urdu for advocate, *sahayak* means helper. The product helps the advocate; it never replaces the advocate's judgement or signature.

**"A Multi-Agent Harness for Bail Drafting"**: two words need unpacking.

- **Agent.** Here an agent is a component with one narrow job, its own prompt and its own allowed tools. Some agents call the language model; some decisions inside them are pure code (for example the date arithmetic of the Rights Radar). There are six, each named after a role in an Indian court office (section 6).
- **Harness.** The word is chosen on purpose. The project does not try to make the language model smarter. It builds a scaffold of code *around* an ordinary model so that the model cannot hand the lawyer an unchecked sentence: contracts say what each argument needs, a checker tests every sentence, failures become open issues, and approval gates are enforced by code. The research contribution is this scaffold, which is why it is evaluated against simpler scaffolds on the **same** model.

**"Optimus Prompt"** is the team name. The team: Harshita Kumari, Satvik Rao, Shravani K, Vishak Kashyap K.

---

## 3. Problem statement (with a crash course in Indian bail law)

### 3.1 A crash course in the legal words

You need these words to read the rest of the poster.

- **Bail.** Release from custody while the case goes on, usually on conditions (a bond, sureties, reporting to the police). A **regular bail application** asks for release after arrest.
- **Undertrial.** A person in custody whose trial has not finished. They have not been convicted of anything.
- **FIR (First Information Report).** The police record that starts a criminal case. It names the offence sections and often the accused.
- **Remand order.** A court order that keeps the accused in custody for a further period while police investigate.
- **Charge sheet.** The police report filed in court at the end of the investigation.
- **Custody certificate.** A jail document stating how long the person has been in custody.
- **Default bail.** If the police do not file the charge sheet within a fixed period (60 or 90 days, depending on the offence; BNSS section 187(3), formerly CrPC 167(2)), the accused gets a right to bail. Dates decide this, which is why the system counts them with code, not with a language model.
- **Undertrial limit (BNSS section 479).** An undertrial who has spent half the maximum sentence in custody (one third for a first-time offender) should be released. Again: arithmetic on dates.
- **IPC, CrPC to BNS, BNSS.** On 1 July 2024 India replaced the Indian Penal Code and the Code of Criminal Procedure with the Bharatiya Nyaya Sanhita and the Bharatiya Nagarik Suraksha Sanhita. Section numbers changed (IPC 420, cheating, is now BNS 318(4)). Old cases still run under the old codes, new ones under the new codes, and old judgments are cited for new sections. So a lawyer needs a reliable old-to-new map: the **concordance**.
- **Bail factors / grounds.** Courts weigh standard considerations: length of custody, gravity of the offence, flight risk, risk of tampering with witnesses, criminal antecedents, parity with a co-accused already on bail, delay in trial, health/age/family, and statutory bars (for example NDPS section 37 for commercial quantities of drugs). A **ground** is one argued reason for bail on one factor, with its supporting sentences.

### 3.2 The three challenges on the poster

**Unstructured case files.** "About 76% of Indian prisoners are undertrials (NCRB 2022)." The National Crime Records Bureau's *Prison Statistics India 2022* counts 434,302 undertrials among 573,220 prisoners: 75.8%, rounded to 76%. (It was about 74% in 2023, so the year matters.) Their lawyers, often legal-aid panel lawyers, receive the papers as a pile: High Court and Sessions Court orders, a phone photo of the FIR (often in Hindi), remand orders, custody certificates, sometimes all merged into one PDF. Before any drafting, someone must read every page, split the documents, and pull out dates and sections.

**Fragmented legal knowledge.** A brief needs five kinds of knowledge with different shapes:

1. exact statute text (looked up by section number, not by "similarity");
2. the old-to-new section map (a table/graph);
3. what courts have reasoned on each bail factor (hundreds of thousands of paragraphs);
4. citation history (which judgment cites which, and whether it is still good law);
5. the case's own timeline (dates).

"No single search index can serve" all five. A vector index is wrong for an exact section lookup; a paragraph index is wrong for a citation graph. That is why the system has ten **typed** stores (section 6).

**Unreliable generation.** Language models, and even commercial legal AI tools, invent facts and case law. The first reference on the poster (Magesh et al., *Hallucination-Free?*) measured this in leading legal research tools. In a bail brief every sentence must trace back either to the case file or to a verified authority. A fluent but invented sentence can cost a client their liberty and the lawyer their credibility.

### 3.3 "Our users: overburdened legal-aid lawyers"

The intended user is a lawyer, not the public: panel lawyers, junior advocates, supervised legal-aid clinics. Bail preparation is slow (reading the pile, building a list of dates, finding authorities) and legal-aid lawyers carry many files at once, so a source-checked first draft with the gaps already listed saves the scarce resource: the lawyer's time. The system deliberately gives **no outcome predictions, no grant rates and no advice to accused persons or the public.**

---

## 4. The research question, word by word

> *Does a structured multi-agent harness produce better-grounded bail drafts than simpler single-model and retrieval baselines built on the same language model?*

- **Structured multi-agent harness**: the six agents with contracts, checks and gates (sections 5 and 6).
- **Better-grounded**: more of what the draft says is supported by the case facts or by real, relevant authorities, and less is invented. "Grounded" is measured by 25 automatic metrics (section 9), none of which uses a language model as a judge.
- **Simpler single-model and retrieval baselines**: B0 to B6 (section 10). They range from one model call with no search (B0) to searching every index with no plan (B4), plus a rule template with no model at all (B6).
- **Built on the same language model**: everything runs on Sarvam-105B, so a difference cannot be explained by "you used a better model". The only thing that changes is the system around the model.

The second half of the research, which the poster shows in the experiments and ablations, asks *which design decisions account for any gain*.

---

## 5. Methodology: the four ideas

### 5.1 Evidence contracts

"For each of the 12 bail factors, a contract defines the required slots (e.g., a co-accused order or legal authority), the allowed stores, and a call budget."

The twelve factors are: antecedents, charge sheet filed, custody period, flight risk, gravity and punishment, health/age/family, parity with co-accused, statutory bar, trial delay, undertrial period, weak prima facie case, witness tampering.

A contract is a small file per factor. The parity contract, abridged:

```yaml
factor: parity_with_co_accused
applies_if: "a co-accused has been granted bail"
slots:
  co_accused_order: {need: required, stores: [case.docs, case.timeline]}
  role_comparison:  {need: required, stores: [case.docs]}
  authority:        {need: 2, stores: [caselaw.reasoning, caselaw.similar]}
  good_law:         {need: required, stores: [caselaw.citations]}
  likely_objection: {need: 1, stores: [advocacy.objections]}
budget: {store_calls: 8, tokens: 12000}
```

Why this matters: the contract makes "what a good argument needs" explicit and checkable. If a **required** slot cannot be filled (for example the record never says whether the co-accused got bail), that is not papered over with a fluent sentence. It becomes an **open issue** listed for the lawyer. This is the mechanism behind "the record is silent" being shown rather than invented.

### 5.2 Planned retrieval

"Sutradhar queries until the slots are filled or the budget ends, using BM25 and dense rankings fused by reciprocal rank."

- **Sutradhar** (the orchestrator) works factor by factor. For the unfilled slots of a contract it plans a query, runs it on an allowed store, and rates each slot FILLED, WEAK or MISSING by rule checks. If a slot falls short it rewords the query, relaxes filters in a fixed order, follows the citation graph, or tries another allowed store. It stops when the required slots are filled, the budget is spent, or nothing is left to try.
- **BM25** is classic keyword search: it scores a paragraph higher if it contains the query's words, especially rare ones, without over-rewarding long paragraphs.
- **Dense ranking** scores by vector similarity. Precise detail: in the evaluated runs the vectors were **hashed character n-grams** (a cheap, non-neural text vector that catches spelling variants and partial word matches). Neural BGE-M3 vectors were built but not used in these runs.
- **Reciprocal rank fusion (RRF)** merges the two ranked lists without caring about their incompatible score scales. Each paragraph gets the sum over the lists of 1/(60 + its rank in that list); the code uses k = 60, the standard value. A paragraph ranked high by both methods rises to the top.
- **The budget** caps store calls and tokens per factor, so the planner cannot search forever.

### 5.3 Verification

"An NLI checker tests each sentence against its cited source; a failing sentence is repaired; if it still fails, it goes to counsel as an open issue."

- Every sentence the drafter (Vakeel) writes carries a source marker: `[F:field]` for a case fact, `[A:doc#para]` for a paragraph of a cited judgment.
- **NLI (natural-language inference)** is a model that judges whether a source text *entails* (supports) a sentence. Inside the system this is a local DeBERTa NLI model. Fact sentences are checked against the dossier quote; authority sentences against the cited paragraph. Rule checks run too: statute lookup, section mapping, a good-law flag, and "no citation that was not retrieved".
- A failing sentence is reworded to what its source supports, or its authority is re-retrieved. The code allows up to **two** repair rounds (the poster says "repaired once"; see section 14).
- With fix **X4 (strict abstention)**, a sentence that still fails, or that only says "the record is silent", leaves the argument and becomes an open issue for the lawyer. Nothing is dropped silently.
- Citation text is rendered from the corpus metadata, so a case name cannot be invented: an unknown document id is an error.

### 5.4 Counsel in the loop

"Two gates need counsel's approval, one for the dossier and one for the brief. Code blocks export until Gate 2 is passed."

- **Gate 1**: the lawyer confirms the facts (the dossier) before anything is drafted.
- **Gate 2**: the lawyer approves the brief before anything can be exported.
- "In code" means: approvals are written to an append-only event log only with the actor "counsel"; an agent can open a gate but never approve it; export raises an error before Gate 2; and Gate 2 stores a hash of the exact brief, so editing the brief after approval closes the gate again. A rule in a prompt can be ignored by a model; a rule in code can be tested. The test result is on the poster: 80 of 80 early export attempts blocked.

---

## 6. The architecture diagram, box by box

The diagram has two lanes and a shelf of stores.

**Top lane: "Counsel's machine: raw files stay here."** Everything that touches raw client files runs locally.

- **Pairokar (batch desk)** → "ordered files". For an office with hundreds of files, Pairokar orders the work by legal urgency using fixed, explainable rules: first legal deadlines (a default-bail window open or about to open, a section 479 threshold reached or close), then days past a threshold, then custody length. Nothing is learned or guessed.
- **Files, photos, chat, voice** → "pages" → **Munshi (intake)**. Munshi decides how to read each page through a ladder: text layer first, then a layout parser, then clean-up plus OCR (optical character recognition, which turns an image of text into text), then a vision model, and finally "ask counsel". It splits a merged PDF into documents, names their types (FIR, remand order, custody certificate and so on), files dated events, handles Hindi and voice, and asks the lawyer only about what is missing. A page that fails every route is marked unreadable, never guessed.
- "pages, doc types" → **Peshkar (dossier, Rights Radar)**. Peshkar builds the **dossier**, 13 structured fields (FIR, offence date, sections, arrest date, first remand, custody days, charge sheet, trial stage, previous bail, co-accused bail, antecedents, personal circumstances, parties), each with the quoted sentence and page it came from. A field the papers do not support is marked unsupported. Peshkar also builds the **List of Dates** and runs the **Rights Radar**: seven deterministic rules (default bail, the s.479 undertrial limit, notice of appearance, grounds of arrest, production within 24 hours, the Supreme Court's Antil offence category, statutory bars such as NDPS s.37). It is code, so each result names its rule and the dates it used.
- "dossier, quotes" → **Gate 1 (counsel: dossier)**, dashed because it is a human decision.

**Down the right: "approved dossier" → pseudonymise.** Before any text crosses to the hosted model, names become stable aliases (Accused-1, Co-accused-1, Complainant-1), quasi-identifiers (FIR numbers, police stations, villages, vehicle numbers, ages) are replaced, and dates are shifted by a per-case offset. A boundary check refuses any payload that still carries a real name or identifier. The alias map never leaves the machine.

**Middle lane: "Model side: pseudonymised text only."**

- **Sutradhar (plans retrieval)** reads the evidence contract (factor → slots → stores, until budget or sufficiency) and queries the stores, producing "evidence packs per factor".
- **Vakeel (draft, check, repair)** writes one ground per factor from the evidence packs. The loop arrow "check each sentence, repair" is the verification of section 5.3. The arrow down, **"abstain" → Open issues**, is fix X4: unsupported sentences go to the lawyer's list, not into the brief.
- "grounds, replies" → **Abhiyojak (prosecution sparring)**, a simulated public prosecutor. It raises objections against the draft, Vakeel replies, and Abhiyojak marks each reply ANSWERED, PARTLY or UNANSWERED with a reason ("objections, verdicts" arrow back). Its input is an **allow-list** ("allow-listed stores only"): the drafted grounds and authorities, the dossier facts, and its own three stores (objection bank, refusal reasoning in case law, statutes). It never sees Vakeel's plan or reasoning, so it cannot simply agree with it. The project cites literature showing that a critic who reads its partner's reasoning tends to be talked round; isolation is enforced in code and a forbidden key raises an error.
- "draft for approval" → **Gate 2 (counsel: brief)** → "export" → **Brief, objections, open issues**. Export writes four Word files: the bail application, the List of Dates, the objections sheet, and a one-page hearing card (likely questions from the bench with answers, grounds to lead with, conditions courts imposed in similar orders).

**Bottom: "ten typed stores on four shelves."**

| Shelf | Stores | Searched by |
|---|---|---|
| Law | statutes; IPC/CrPC to BNS/BNSS concordance | exact lookup by section; a typed table/graph |
| Case law | reasoning paragraphs; citation graph (with good-law status); similar whole orders | hybrid BM25 + vector; graph walk; vector |
| Advocacy | defence arguments by factor; prosecution objections by factor | search; used for coverage and phrasing, **never cited as authority** |
| Case (private, laptop only) | the client's documents; the timeline; the dossier | search; date queries; field lookup |

Not drawn but always present: an **append-only event log** (SQLite with triggers that refuse UPDATE and DELETE). Every agent step, tool call and approval is an event, so a case can be replayed and audited, and approvals are facts no agent can write.

**Why six agents rather than one big prompt?** Each agent makes one narrow decision that can be tested alone, and the five sub-problems (messy input, differently shaped knowledge, deciding what to fetch, a moving case, scale) do not look alike. The project's own lesson, worth repeating if asked: adding agents did not help until the interfaces between them carried evidence (contracts, sentence checks, objection references). More boxes alone did not help; see sections 11 and 12.

---

## 7. The four data boxes

**115,524: bail orders from Open India Law.** Open India Law is a public corpus of Indian court judgments. The team read 115,988 bail-related High Court orders; 464 were excluded (the test and development orders, and every order sharing an FIR with them), leaving 115,524 that feed the stores. Paragraph splitting gives 161,708 reasoning paragraphs, 114,692 similar-order entries, 70,880 defence arguments, 55,161 prosecution objections and 5,842 citation edges. All public court text; no client data.

**1,426: statute sections.** The statutes store holds 1,426 sections (IPC, CrPC, BNS, BNSS, NDPS and others relevant to bail), built by script from the official texts. A side story worth knowing: when the team rebuilt the First Schedule tables (which list whether each offence is bailable and cognisable) from the official PDFs, the first parser had "bailable" the wrong way round for 27 sections. It was fixed, and cells that cannot be read reliably are left empty instead of guessed. A wrong flag in a legal table is worse than a missing one.

**IPC to BNS concordance.** The old-to-new section map, 554 rows in the store. It records, for example, that IPC 420 maps to BNS 318(4) with the same punishment, while IPC 406 maps to BNS 316(2) and its maximum rose from 3 to 5 years, so a precedent decided under IPC 406 must be qualified. It was verified against the public IPC2BNS-Verify dataset.

**30 + 20 + 80: search + holdout + test.** The evaluation set (called T1) is built from real High Court bail orders:

- **30 search cases**: development orders used to compare designs and choose VS-Final.
- **20 holdout cases**: development orders run once, after the choice, to check it was not luck.
- **80 test cases**: drawn with a fixed seed from 200 test orders, locked by hash before the system was frozen (9 November 2026), and scored once.

The box says "High Court orders from 2024". Precisely: the 50 development orders are dated January to April 2024, and the 80 sealed test orders April to October 2025 (40 of the 80 are under the new BNS codes). See section 14.

**How a test case works.** The system receives only the **facts** section of a real order. The "right answers" come from the **rest of the same order**: which bail factors the defence argued, which the court discussed, what the prosecution objected, which judgments the court cited. No public bail corpus annotated by legal experts exists, so labels come from the orders themselves.

**How the labels were made (no hand labelling, no LLM judge).** Two labelers work independently: keyword-and-date rules, and a hosted model that does not see the rule output. A label enters the **agreed labels** only if both agree **and** the model quotes a verbatim span found in the order. Agreement (Cohen's kappa) is 0.60 on factors and 0.84 on dossier fields. The results were also re-scored with **rule-only labels** as a second source: VS-Final gets 45/70/5 instead of 46/69/5, and all hypothesis verdicts stay the same.

**Leakage guard.** A test order must never be findable in the stores, or the system could copy the answer. Three defences: the 464 orders are excluded from every store; at search time a date filter only lets a case see orders dated **before** it ("Filter before case" in the RAG diagram); and an 8-word overlap check compares each test order's facts with every store paragraph.

---

## 8. The RAG pipeline diagram

RAG (retrieval-augmented generation) means the model writes from retrieved text instead of from memory. The diagram has three columns.

**Built once (offline, before any case):**

1. **Open India Law, 115,524 orders** →
2. **Split into paragraphs** (so a search returns the paragraph that reasons on a point, not a 40-page order) →
3. **Index: BM25 + dense** (both indexes over the same paragraphs) →
4. **Leakage guard: 464 orders out** (section 7).
5. **Statutes, IPC to BNS** come from official texts and the concordance dataset, not from the court orders.

The whole build took about 35 minutes on a laptop and is 1.77 GB.

**Stores (with their sizes):** reasoning 161,708; similar orders 114,692; arguments 70,880; objections 55,161; citation graph 5,842; statutes 1,426; IPC to BNS 554.

**Per bail factor (at run time, for every factor Sutradhar plans):**

1. **Sutradhar: contract (slots, stores, budget).** Which evidence this factor needs and where it may be.
2. **Filter: before case.** Metadata filters: only orders dated before the case, plus section family and factor filters.
3. **Rank: BM25, dense.** Two ranked lists.
4. **Fuse: rank fusion.** RRF merges them.
5. **Slot filled?** A rule check per slot.
   - **yes** → **Evidence pack** → **Vakeel: cited draft**.
   - **no** → **re-query** (reword, relax a filter, follow the citation graph, try another allowed store) and go round again.
   - **budget spent** with the slot still empty → **Open issue for counsel**.

**A worked example.** Take parity with a co-accused. The contract needs the co-accused's bail order (required), a role comparison (required), two authorities, a good-law check and one likely objection. Sutradhar searches the case documents and finds the co-accused's order (filled). It searches reasoning paragraphs filtered to orders before this case, finds High Court paragraphs on parity, fuses the rankings, and follows the citation graph to the Supreme Court judgment those paragraphs rely on (two authorities: filled). The citation store confirms neither has been overruled (good law: filled). If the record never compares the two roles, the role-comparison slot stays empty when the budget ends, and "role of the applicant compared with the co-accused is not in the record" becomes an open issue instead of an invented sentence.

---

## 9. How the metrics are calculated (the win/tie/loss rule)

### 9.1 The formula

For each metric *m* and baseline *B*, on the same *n* orders (cases):

Δ = (1/n) Σᵢ ( mᵢ^VS-Final − mᵢ^B )

In words: for each case, take VS-Final's score minus the baseline's score on that **same** case, and average. Using the same cases for both ("paired") removes the variation between easy and hard cases, which would otherwise swamp the difference between systems.

### 9.2 The bootstrap, in plain words

Δ from 80 cases is one number, but with a different 80 cases it would come out slightly different. How sure are we? We cannot get new cases, so we simulate: draw 80 cases **with replacement** from our 80 (some appear twice, some not at all), recompute Δ, and repeat **10,000 times** (with a fixed random seed, so it is reproducible). The middle 95% of those 10,000 values is the **95% interval** for Δ. If that whole interval is above zero, the improvement is very unlikely to be a fluke of which cases we happened to have.

### 9.3 Holm, precisely

Each metric is compared against seven baselines. With seven tests, the chance that at least one shows a "significant" difference by luck is much higher than 5%. **Holm's correction** fixes this. It sorts the seven comparisons by strength (p-value), tests the strongest at a strict level (0.05/7), the next at 0.05/6, and so on, and stops at the first that fails. The effect is that each comparison must clear a stricter bar than a lone test would. The poster's phrase "the range is widened" is the interval view of the same thing: a stricter level means a wider interval must exclude zero. The correction is done per system and per metric, over the seven baselines.

### 9.4 Win, tie, loss

- **Win**: the corrected interval of Δ lies wholly on the better side of zero ("the whole range favours VS-Final").
- **Loss**: wholly on the worse side.
- **Tie**: the interval contains zero; the difference is too small to call.

"Better side" depends on the metric: for unsupported-fact rate lower is better, for objection recall higher is better.

### 9.5 What *m* can be: the 25 quality metrics

None is scored by a language model acting as a judge.

| Group | Metrics (direction) |
|---|---|
| Bail grounds | factor recall (↑), strict and lenient factor precision (↑), factor F1 (↑), court-discussed recall (↑), unfinished-factor share (↓) |
| Coverage | coverage (↑), answerable coverage (↑) |
| Grounding | unsupported-fact rate M6 (↓), unsupported case-fact rate M6a (↓), unsupported-fact count (↓), doubly unsupported rate (↓) |
| Prosecution objections | objection recall (↑), objection precision (↑) |
| Citations | fabricated-citation rate (↓), citation precision (↑), citation recall (↑), removal changes claim (↑) |
| Authorities | reasoning share (↑), Supreme Court share (↑), dated-before-order share (↑), good-law violation rate (↓), known-treatment share (↑) |
| Retrieval | recall@10 (↑), over-search rate (↓) |

The key definitions, because these are the ones people ask about:

- **Factor recall**: of the bail factors the defence argued in the real order, the share the draft also argues.
- **Coverage**: the share of grounds written without declining (not "needs review", not unanswered, not a refusal).
- **Answerable coverage**: of the factors the facts can actually answer, the share that get a supported argument.
- **M6, unsupported-fact rate**: the share of argument sentences that an independent checker, **MiniCheck** (RoBERTa-Large), does **not** find entailed by the case facts. Important: a legal sentence ("parity is a relevant consideration, as held in X") cannot be entailed by the facts of a case, so M6 counts it as "unsupported". **M6 is not a hallucination rate**; it measures how much of a brief the facts alone support. That is why M6 values are high for every system (0.89 to 1.00).
- **M6a**: the same, on case-fact sentences only: the cleaner check of whether the draft states the facts correctly. VS-Final 0.43.
- **Doubly unsupported rate**: the share of sentences supported neither by the facts nor by the rest of the same order. It does not prove a sentence is legally wrong (an order need not restate every proposition it relies on).
- **Objection recall**: of the objections the real prosecution raised (by bail factor), the share the simulated prosecutor also raised.
- **Fabricated-citation rate**: the share of citations whose document id is not in the index or whose quoted span is not found word for word. It tests that citations **exist**, not that they **support** the sentence.
- **Citation precision / recall** (in the style of ALCE, reference 4): does each cited paragraph support its sentence; is each sentence supported by its citations.
- **Recall@10**: of the precedents the court actually cited (that exist in the index), the share found in the top 10 retrieved.
- **Unfinished-factor share**: the share of planned factors that stop with a required slot still empty.

**Why a separate checker for scoring?** The system checks its own sentences with DeBERTa NLI. Scoring uses a **different** model, MiniCheck, so the system is not graded by its own checker ("grading your own homework").

**What about MRR?** MRR (mean reciprocal rank) was used only in offline retrieval studies of single components, not among the 25 metrics. Retrieval quality in the main evaluation is recall@10.

### 9.6 Cells that are not counted

25 metrics × 7 baselines = 175 comparisons. A comparison is left out if fewer than five cases have both scores ("too few"), or if the baseline cannot produce the metric ("undefined": for example objection recall for a baseline with no prosecutor). On the 80 test cases, 13 were too few and 42 undefined, so **120 comparisons were decided: 46 + 69 + 5 = 120.**

Also important: **wins are comparison outcomes, not cases**, and they are not independent trials. "46 wins" does not mean "46 cases went better". It means 46 metric-by-baseline cells were clearly in VS-Final's favour.

---

## 10. Results against baselines (the first chart)

### 10.1 The baselines

All seven use Sarvam-105B with the same facts and checklist.

| Baseline | What it does | Why it is a fair comparison |
|---|---|---|
| B0 | one model call from the facts; no search | "just ask the model" |
| B1 | top 10 paragraphs from one index, one drafting call | standard single-index RAG |
| B2 | the 3 most similar whole orders, one drafting call | whole-document RAG |
| B3 | B1 with naive chunking (fixed 512 with overlap, recursive, semantic, by page) | the common chunking recipes |
| B4 | every store queried, results fused by rank, no orchestrator | all the same stores and tools, but no plan or contracts |
| B5 | a learned store router, no evidence contracts | a published "agent router" approach |
| B6 | an expert rule checklist (template), no model at all | the "no AI" floor |

B4 and B5 are the strongest because they have access to the same stores as VS-Final; they differ in having no contracts, no planning by contract, and no per-sentence abstention.

### 10.2 Reading the chart

Each bar is one baseline. Purple is VS-Final's wins, grey ties, orange losses, counted over the quality metrics on the 80 unseen cases. The rows: B0 4/8/0, B1 6/10/0, B2 7/12/0, B3 7/9/0, B4 10/9/2, B5 7/15/2, B6 5/6/1. Total **46/69/5**. Bars have different lengths because different numbers of metrics are defined for each baseline (B6, a template with no citations, has the shortest).

### 10.3 The bullets, unpacked

The key numbers behind the bullets (means on the 80 test cases):

| System | Objection recall ↑ | Answerable coverage ↑ | Citation precision ↑ | Fabricated citations ↓ | M6 ↓ | Doubly unsupported ↓ | Store calls |
|---|---|---|---|---|---|---|---|
| **VS-Final** | **0.73** | **0.61** | **0.71** | **0.00** | **0.89** | 0.87 | 110 |
| B0 | 0.00 | 0.06 | 0.00 | 1.00 | 0.96 | 0.93 | 0 |
| B1 | 0.00 | 0.03 | 0.00 | 0.00 | 0.97 | 0.95 | 1 |
| B2 | 0.00 | 0.09 | 0.00 | 0.80 | 0.97 | 0.92 | 1 |
| B3 | 0.00 | 0.03 | 0.00 | 0.00 | 0.96 | 0.94 | 1 |
| B4 | 0.36 | 0.20 | 0.02 | 0.95 | 0.94 | 0.47 | 188 |
| B5 | 0.35 | 0.23 | 0.10 | 0.64 | 0.94 | 0.62 | 89 |
| B6 | 0.00 | 0.00 | n/a | n/a | 1.00 | 0.93 | 2 |

- **"VS-Final never loses to the four simplest systems (B0 to B3)."** Zero orange in those four rows.
- **"VS-Final never invents a court case. The two strongest baselines invent most of their citations (B4: 95%, B5: 64%)."** Fabricated-citation rate 0.00 vs 0.95 and 0.64. (B0, with no search at all, invents all of its few citations, 1.00. B1 and B3 show 0.00 because they cite almost nothing; their citation columns rest on only 5 to 12 cases.) Remember the limit: 0.00 means every citation exists and quotes real text; whether it *supports* the sentence is the next bullet.
- **"VS-Final writes a supported argument for 61% of the bail grounds the case facts can answer, against at most 23%."** Answerable coverage 0.61 vs B5's 0.23 (best baseline).
- **"When VS-Final cites a case, the cited passage supports the sentence 71% of the time, against 10% or less."** Citation precision 0.71 vs B5 0.10, B4 0.02. Honest reading: about three in ten cited paragraphs still do not support their sentence, although none is invented. The brief is a first draft for counsel.
- **"Fewer database lookups than the baseline that queries every store: 110 per case against 188."** 41% fewer, because the contract tells Sutradhar what to fetch and when to stop.
- **"No VS-Final brief left the system without counsel's approval: all 80 early export attempts were blocked."** Each test case tried one export before Gate 2; the code refused all 80. (Across the four tool-using systems tested, 320 of 320 were refused.)

### 10.4 The five losses

- **Unfinished-factor share, against B4 and B5 (2 losses).** This metric counts planned factors left with a required slot empty. B4 and B5 have no required slots, so they score near zero by construction. VS-Final lists missing evidence for the lawyer instead of filling it. A text search of the facts found none of the missing slots actually stated in the record: "missing" is the truth.
- **Coverage, against B6 (1 loss).** A template always writes every ground; it cannot decline, so it scores 1.00 by construction.
- **Unsupported-fact count, against B5 (1 loss).** B5 writes shorter briefs (about 4.4 sentences per case against 7.0). Fewer sentences means fewer unsupported ones in absolute terms; on the **rate**, VS-Final beats B5.
- **Doubly unsupported rate, against B4 (1 loss).** B4 emits only a few selected sentences; VS-Final writes full grounds, most of whose sentences state law from a precedent, which the facts and the order cannot always confirm. This one is a real trade-off, not an artefact.

So the poster says "three of the five come from how the baselines are built" (the two unfinished-factor losses and B6's coverage), "a fourth comes from B5 writing shorter briefs", and the fifth (doubly unsupported vs B4) is a genuine cost.

### 10.5 What VS-Final costs

Per test case: **719 seconds** (B4 269 s, B5 160 s), **122,387 tokens** (B4 120,614, B5 79,877). The extra time comes from sequential steps: contracts, per-sentence checks, repairs and sparring. About twelve minutes per case suits overnight batch preparation.

---

## 11. Architectural experiments (the second chart)

### 11.1 Why there were experiments at all

The first complete system, the **Base**, was run against the baselines on development cases with three hosted model families: OpenAI (gpt-6-luna, up to 38 cases), the Gemini free tier (25 cases, public text only), and Sarvam-105B (30 cases). On **none** did it beat every baseline. Eighteen literature variants (S1 to S18, each one published idea such as self-critique of retrieval or sufficiency-based stopping) did not clearly beat it either. So instead of guessing, the team read the Base's outputs case by case.

### 11.2 The four root causes and the eight fixes

1. **A metric reading, not a bug.** 55% of the sentences M6 flagged stated legal principles from cited authorities, which facts cannot entail; only about 9% were real fact mismatches. This led to the extra metric M6a rather than to a switch.
2. **A starved dossier.** Intake filled only about 2.8 of 13 dossier fields per case, so the planner never proposed grounds on custody, parity or delay. Fix **X1** (gap-filling): when the dossier lacks a field, read the raw facts text for it.
3. **Objections thrown away at a handoff.** An objection was kept only if it named its evidence by an exact store label. The Base kept 66 objections and discarded 230; 263 of 320 dropped references named a paragraph that *had* been offered. Fix **X7**: match the referenced material by its **id**. Objection recall on the search cases went from 0.364 to 1.000: the objections were always there and were being discarded.
4. **Failed sentences stayed in the argument.** Fix **X4** (strict abstention): they become open issues instead.

Plus **X5** (draft from the raw facts text; the only single switch that lowered M6 with an interval excluding zero), and four others that were tried and not chosen: **X2** (factual sentences must copy the facts near-verbatim; it left most grounds empty on Sarvam, coverage 0.199), **X3** (one more prosecutor call), **X6** (search the prosecutor's stores a second time), **X8** (replace a paraphrased fact with the record sentence). So "four root causes yielded eight candidate fixes" means eight switches came out of the analysis; the first cause changed how a metric is read.

### 11.3 Reading the chart

Each row is one candidate system on the **30 search cases**, against B0 to B6 (purple wins, grey ties, orange losses). Rows are sorted by losses (fewest first), then by wins. The rows:

| Candidate | W/T/L | Sentences per case |
|---|---|---|
| VS-Final, free planner (writes less) | 38/19/1 | 4.07 |
| Base + X4 X5 X7 (writes less) | 38/29/3 | 5.07 |
| **VS-Final (Base + X1 X4 X5 X7)** | **30/37/3** | **6.83** |
| VS-Final + X6 | 27/40/3 | 6.77 |
| Base + X1 X4 X5 | 22/45/3 | 6.83 |
| VS-Final + X8 | 33/33/4 | 6.83 |
| Base + X1 X4 X7 | 31/35/4 | 7.40 |
| Base + X2 | 15/14/4 | 9.00 |
| Base + X5 | 13/53/4 | 6.80 |
| Base harness, free planner (writes less) | 7/47/5 | 5.03 |
| Base + X1 X5 X7 | 19/45/6 | 9.03 |
| Base + X1 | 12/52/6 | 9.33 |
| Base + X4 X6 X7 (writes less) | 31/31/8 | 4.73 |
| Base + X4 (writes less) | 25/37/8 | 4.73 |
| Base + X7 | 19/41/10 | 6.93 |
| Base + X6 | 17/43/10 | 6.93 |
| Base harness | 11/49/10 | 6.93 |
| Base + X3 | 11/49/10 | 6.93 |

Rows marked "writes less" (in grey on the poster) produce under about 6 claims per case.

### 11.4 The selection rule and why VS-Final was chosen

**Rule, fixed in advance: fewest losses, then most wins, among candidates producing a full brief.** Fewest losses comes first because a loss means the system is clearly worse than a simpler one on something, which matters more to a lawyer than an extra win.

- The top row (**free planner**, 38/19/1) has fewer losses, but it is not a full brief. It records no plan, so the unfinished-factor metric has nothing to count. Its model rarely searches the precedent stores, so it restates the facts under factor headings: 18% of its grounds cite an authority against 90% for VS-Final, and 19 of 30 briefs cite none. Its "wins" are measurement artefacts.
- The second row (**Base + X4 X5 X7**, i.e. VS-Final without X1, 38/29/3) ties VS-Final on losses and has more wins, but writes about 5 sentences per case against VS-Final's 7. A shorter brief makes fewer claims, so it has fewer chances to be wrong, which inflates wins on count-based metrics without grounding the brief any better. Head to head it differs from VS-Final on only two metric cells.
- **VS-Final** is the first full-brief candidate with 3 losses: **30/37/3**, against the Base's **11/49/10**.

The lesson the team draws: a win count can be gamed by writing less, copying the facts, or recording nothing, so the top candidates were read before they were believed.

### 11.5 "This result held on 20 unseen orders: 22/26/3"

The 20 holdout cases were run once, after the choice: VS-Final 22/26/3 (the Base 10/40/5), with the same three losses. Two fresh reruns on the 30 search cases gave 30/31/3 and 35/28/3, again with the same three losses, so the result is stable even though the model is not deterministic.

**Why 30/3 here but 46/5 in the first chart?** Different case sets (30 development cases vs 80 sealed test cases), so different numbers of decided comparisons (70 vs 120). They are not meant to add up; the 80 sealed cases are the headline because no design decision ever saw them.

---

## 12. Ablation studies (the third chart)

### 12.1 What an ablation is, and how to read the chart

An ablation switches one part off and measures what is lost. All rows are on the 30 search cases, 25 metrics. Each row compares VS-Final with the ablated system: bars to the **right** (purple) count metrics where VS-Final is clearly better, bars to the **left** (orange) metrics where the ablated system is better, and the number on the far right is ties. A long purple bar means "removing this part hurts".

Two kinds of rows:

- **Minus X** rows remove one of the four fixes from VS-Final.
- **A** rows remove or replace an original part of the system. Some of them are combined removals: the configuration validator refuses conflicting switches, so A1 (no dossier) also drops X1 and X5, A2 (no check and repair) also drops X4, A8 (no sparring) also drops X7, and A9 drops X4 and X7.

### 12.2 Row by row

| Row | VS-Final better / tie / ablation better | What changed |
|---|---|---|
| minus X1 (gap-filling) | 1 / 18 / 1 | one win (Supreme Court share of authorities), one loss: the unsupported-sentence **count** (6.13 vs 4.37), because without X1 it writes fewer sentences |
| **minus X4 (abstention)** | **4 / 16 / 0** | unsupported sentences per case 6.13 → 8.2; coverage 0.97 → 0.72; citation precision 0.68 → 0.61; citation recall 0.70 → 0.63 |
| minus X5 (draft from facts) | 0 / 20 / 0 | no change on these cases |
| **minus X7 (objections by id)** | **2 / 18 / 0** | objection recall 1.00 → 0.27; unfinished share 0.375 → 0.471 |
| A3 no tools | 0 / 20 / 0 | no change |
| A4 plain retrieval | 1 / 19 / 0 | Supreme Court share 0.05 → 0 |
| A6 fixed router | 0 / 19 / 1 | the fixed router leaves fewer factors unfinished (0.15 vs 0.36) |
| A7 free planner | 0 / 16 / 4 | four "losses" that are measurement artefacts (section 11.4) |
| A1 no dossier | 0 / 20 / 0 | no change |
| **A2 no check and repair** | **5 / 13 / 1** | coverage 0.97 → 0; unsupported case-fact sentences 42% → 87%; answerable coverage 0.61 → 0; citation precision 0.68 → 0.54 |
| A8 no sparring | 2 / 17 / 0 | no objections are raised at all: objection recall 1.00 → 0 |
| **A9 no sparring, no check** | **6 / 11 / 1** | the largest cost: A2's losses plus objection recall |

(Objection recall rests on the 11 of 30 cases where the real prosecution raised objections that passed the label filter.)

### 12.3 What the ablations show, and what they cannot

- **Clear effects:** strict abstention (X4) and objection matching by id (X7). Removing X4 costs four metrics and gains none; removing X7 costs two. These are the cleanest single-part results.
- **Large combined effects:** removing check-and-repair (A2) or both checking and sparring (A9) costs 5 and 6 metrics. Because they also drop X4 and X7, their effect cannot be split between the original part and the fix.
- **Ties are not proof of uselessness.** Minus X5, no tools (A3) and no dossier (A1) changed nothing on these 30 cases. Thirty cases is too few to detect rare-case effects. The tools exist so arithmetic and statute lookups are done by code and logged (auditability); the dossier is what the lawyer reviews at Gate 1, and the evaluated task starts from a clean facts paragraph, not from a messy bundle where the dossier does most of the work. **A tie at n = 30 is absence of evidence, not evidence of absence.**
- **The free planner (A7) is not a better design**, for the reasons in section 11.4. On M6a it ties VS-Final.

---

## 13. Future work, acknowledgment and references

### 13.1 Future work

- **Train on the verifier.** The sentence checker already produces a pass/fail label for every sentence. Those labels are a free training signal: fine-tune a small model to write sentences that pass, so it can run on the lawyer's laptop, keeping client files fully local and removing the dependence on a hosted model.
- **Learn the contracts.** Today the twelve evidence contracts are written by hand. Inducing them from court orders (which evidence courts actually rely on for each factor and offence) would extend the harness to new offences, courts and jurisdictions without rewriting contracts.
- **Sweep the prison list.** The Rights Radar is deterministic date arithmetic. Run over a district's whole undertrial list, it could flag people who may already be eligible for default bail or release under section 479, with counsel confirming every flag. This targets the 76% figure from the problem statement directly.

The technical report adds more modest next steps: rerun the sealed test with later fixes, run each system several times, repeat on a second model family, and add a metric that checks law sentences against the cited paragraph and fact sentences against the record.

### 13.2 Acknowledgment: the datasets

- **Open India Law**: the public corpus of Indian court judgments behind the stores and the test sets.
- **IPC2BNS-Verify**: a public dataset of IPC-to-BNS section mappings, used to verify the concordance.
- **Kathbath**: a public Hindi speech dataset, used to test the voice-dictation part of intake (Hindi speech to text).

### 13.3 References, and what each was used for

| Paper | First author | What it says | How the project uses it |
|---|---|---|---|
| Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools | Magesh et al. | even commercial legal AI tools that claim to be hallucination-free invent or misstate law at substantial rates | **Motivation**: why every sentence must be checked |
| CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing | Gou et al. | models correct themselves well when the critique uses external tools rather than introspection | **Verification**: the check-and-repair loop uses an NLI tool and rule tools, not self-reflection |
| Sufficient Context: A New Lens on Retrieval Augmented Generation Systems | Joren et al. | a model should judge whether the retrieved context is *sufficient* to answer, and abstain when it is not | **Sufficiency**: stopping retrieval when slots are filled, and abstaining (open issues) when they are not |
| Enabling Large Language Models to Generate Text with Citations (ALCE) | Gao et al. | a benchmark and metrics for whether generated text's citations support it | **Attribution**: citation precision and recall are measured in ALCE style |
| MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents | Tang et al. | a small, fast model that checks whether a sentence is supported by a document, close to large-model accuracy | **Evaluation**: the independent scorer behind M6, M6a and the doubly unsupported rate |

---

## 14. Where the poster simplifies: the precise versions

These are not errors in the results; they are places where the poster's short wording needs a footnote if someone probes.

1. **"A failing sentence is repaired once."** The code allows up to **two** repair rounds (`repair_rounds: 2` in `configs/budgets.yaml`). Safe answer: "it is repaired, up to two rounds; if it still fails it becomes an open issue."
2. **"30+20+80 … High Court Orders from 2024."** The 50 development orders (30 search + 20 holdout) are from January to April 2024. The 80 sealed test orders are from April to October 2025. Safe answer: "development orders from early 2024, test orders from 2025."
3. **"BM25 and dense rankings."** In the evaluated runs, "dense" means hashed character n-gram vectors, not a neural embedding. Neural BGE-M3 vectors exist and can be switched on, but were not used in these runs.
4. **"The range is widened with the Holm correction."** Holm is a step-down correction on p-values; the interval view ("a stricter level means a wider interval") is a fair simplification (section 9.3).
5. **"An NLI checker tests each sentence against its cited source."** Fact sentences are checked against the dossier quote of the fact; authority sentences against the cited paragraph; rule checks run alongside.
6. **"Four root causes yielded eight candidate fixes."** One cause (M6 counting legal sentences) changed how a metric is read and produced the extra metric M6a rather than a switch; the eight switches X1 to X8 came out of the analysis as a whole.
7. **"A9 … the largest loss."** It means removing A9's parts costs the most: VS-Final is better on 6 metrics.
8. **"All 80 early export attempts were blocked."** That is VS-Final's 80. Across the four tool-using systems, 320 of 320 were blocked.
9. **Stores and dates.** The report's sentence "orders before 2024 feed the stores" is simplified: the stores also hold later orders, and leakage is prevented by excluding the test orders (and orders sharing their FIR), by the run-time date filter, and by the 8-word overlap check.

---

## 15. Questions people will ask, with answers

**Is this just ChatGPT with a legal prompt?**
No. The model is one component. The value is the harness: contracts, typed stores, per-sentence checks, abstention, an isolated simulated prosecutor, and approval gates in code. The proof is the comparison on the *same* model: B0 is "just ask the model", and VS-Final beats it with zero losses.

**Did you train a model?**
No. Sarvam-105B is used as is, with temperature 0. Nothing was fine-tuned. (Ablation A5, a fine-tuned extractor, was planned and never run for that reason.) Training a small model on the verifier's labels is future work.

**Why Sarvam-105B and not GPT or Gemini?**
Sarvam is an Indian model with good Indic coverage. Practically: paid providers were locked by an owner decision to control spend, and the Gemini free tier may use prompts to train, so it was allowed public court text only and lacked a complete baseline run. The main test therefore used one family, Sarvam-105B. The Base was also tried on OpenAI and Gemini on development cases (section 11.1).

**What did it cost?**
The Sarvam spend for the whole evaluation was about INR 990, under a code-enforced cap. One recorded demo case cost about INR 5.6. OpenAI spend was about 4.15 USD of a 4.50 USD cap.

**Does it predict whether bail will be granted?**
No, deliberately. No outcome predictions, no grant rates, no advice to accused persons or the public. It drafts for a lawyer who settles and signs.

**What happens to client privacy?**
Raw client files never leave the lawyer's machine. Before any text goes to a hosted model it is pseudonymised (names, FIR numbers, police stations, villages, vehicle numbers, ages replaced; dates shifted), and a boundary check refuses anything that still carries a name or identifier. On the 250 test-set orders no FIR number, case number or real date survived, and during the sealed run the boundary refused 175 payloads that still carried a personal name. External services are off by default and need explicit configuration plus per-case consent.

**What if the record does not say something, for example antecedents?**
The field is marked unsupported in the dossier, the lawyer acknowledges it at Gate 1, the related evidence slot stays empty, and the argument shows it as an open issue. The system never writes "the accused has no antecedents" unless the record says so.

**Why are M6 numbers so high (0.89) if the system is good?**
Because M6 counts legal sentences as unsupported by definition: facts cannot entail a legal principle. Every system scores 0.89 to 1.00. VS-Final has the lowest M6 of all systems (a win over all seven). The fact-only version, M6a, is 0.43.

**Isn't 71% citation precision low?**
It is far above the baselines (10% or less), but yes: about three in ten cited paragraphs do not fully support their sentence. None is invented. The brief is a first draft for counsel. Drafting from the raw facts (X5) traded some citation precision (the Base had 0.85) for fewer unsupported sentences and more covered grounds.

**Why automatic labels instead of lawyers labelling?**
No expert-annotated public bail corpus exists, and the project rule was no hand-made labels. The labels come from the real orders: what the defence argued, what the court discussed, what the prosecution objected, which judgments were cited. Two independent labelers must agree with a verbatim quote. These are proxies for drafting quality, and the report says so.

**Why only 80 test cases when you had 200?**
Time and budget. The 80 were drawn with a fixed seed and locked by hash before the system was frozen; the other 120 were never run, so they remain unseen.

**How do I know you did not tune on the test set?**
The design was chosen on 30 search cases, confirmed on 20 holdout cases, then the code and five hypotheses were frozen and tagged (9 November 2026) before the 80 sealed cases were opened once. One of the five registered hypotheses was falsified (an extra loss to B5 on the sentence count) and is reported as falsified, which is a sign the pre-registration was real.

**Are the 46 wins statistically meaningful?**
Each win is a paired bootstrap interval that excludes zero after Holm correction over seven baselines. The total of 46 is a count of comparison outcomes, not a single hypothesis test, and the cells are not independent. The headline claims are the specific registered comparisons (objection recall, answerable coverage, citations, M6, store calls), each with its own interval.

**Why is it slower than the baselines?**
719 s per case against 160 to 269 s for B4 and B5: contracts, per-sentence checks, repairs and sparring are sequential model calls. For overnight batch preparation in a legal-aid office this is acceptable; use in an office has not yet been studied.

**What is the simulated prosecutor good for?**
A draft no one has attacked is not ready. Abhiyojak raises the objections the State is likely to make, each grounded in a store or a fact, and judges Vakeel's replies. The lawyer sees likely objections before the hearing. Its objection recall on the test cases is 0.73: about three quarters of the real prosecution's objections were anticipated.

**Why does the demo show many objections as unanswered?**
In the frozen system, drafting and repair often used up the token budget before the replies to objections could be judged. A post-freeze switch, the sparring reserve (a separate 200,000-token pool with each reply judged right after it is drafted), raised the judged share from 26% to 97% on 30 development cases. It is outside the frozen, sealed-tested system, and an objection the pool could not cover is labelled plainly as not replied for budget.

**Can it read Hindi and scanned papers?**
Yes, in intake: Hindi text layers, OCR for image-only pages, a vision model as a later rung, and Hindi voice dictation (tested with Kathbath). The six demo cases include a Hindi FIR and a scanned seizure memo. The sealed evaluation itself starts from the clean facts text of public orders, so it does not measure intake.

**Is it deployed?**
A guided demo of six recorded synthetic cases runs in the browser with no backend: each tour walks from the papers to the exported application with one Next button. The full system runs locally with Docker (UI plus API).

**Why "Base" here but "Full" in the technical report?**
Same system. The poster calls the first complete system the "Base harness" to make clear it is the starting point that the fixes were added to.

**What is the single biggest lesson?**
Adding agents did not help by itself. The Base had all six agents and still lost to simple baselines. What helped was making the **interfaces** between agents carry evidence: contracts that state what a ground needs, checks that turn a failed sentence into an open issue, and handoffs that keep an objection's reference intact. The X7 finding is the clearest example: the objections existed all along and were being thrown away at a handoff.

---

## 16. Number cheat sheet

| Number | Meaning |
|---|---|
| 76% | undertrials among Indian prisoners (NCRB Prison Statistics India 2022: 434,302 of 573,220) |
| 6 | agents: Munshi, Peshkar, Sutradhar, Vakeel, Abhiyojak, Pairokar |
| 10 / 4 | typed stores / shelves |
| 12 / 13 | bail factors with contracts / dossier fields |
| 7 | Rights Radar rules |
| 115,988 → 115,524 | orders read → orders in the stores (464 excluded for leakage) |
| 161,708 / 114,692 / 70,880 / 55,161 / 5,842 / 1,426 / 554 | reasoning paragraphs / similar orders / arguments / objections / citation edges / statute sections / concordance rows |
| 30 / 20 / 80 | search / holdout / sealed test cases |
| 25 × 7 = 175 | metric-by-baseline comparisons per system |
| 46 / 69 / 5 | VS-Final W/T/L on the 80 test cases (120 decided; 13 too few, 42 undefined) |
| 45 / 70 / 5 | the same with rule-only labels |
| 30 / 37 / 3 vs 11 / 49 / 10 | VS-Final vs Base on the 30 search cases |
| 22 / 26 / 3 | VS-Final on the 20 holdout cases |
| 30/31/3, 35/28/3 | two reruns on the 30 search cases |
| 0.00 vs 0.95, 0.64 | fabricated citations: VS-Final vs B4, B5 |
| 0.61 vs ≤ 0.23 | answerable coverage |
| 0.71 vs ≤ 0.10 | citation precision |
| 0.73 vs ≤ 0.36 | objection recall |
| 0.89 (M6), 0.43 (M6a) | unsupported-fact rates |
| 110 vs 188 | store calls per case: VS-Final vs B4 |
| 719 s, 122,387 tokens | time and tokens per case |
| 80 / 80 | early export attempts blocked |
| 38 | wins of the two rejected "writes less" candidates |
| 6.83 vs 4.07, 5.07 | sentences per case: VS-Final vs those two |
| 10,000, 95%, Holm 0.05 | bootstrap resamples, interval, correction |
| k = 60 | reciprocal rank fusion constant |
| 2 | repair rounds per sentence |
| 0.60 / 0.84 | labeler agreement (kappa) on factors / fields |
| 9 Nov 2026 | freeze of code and hypotheses |
| ~INR 990 | total Sarvam spend for the evaluation |
