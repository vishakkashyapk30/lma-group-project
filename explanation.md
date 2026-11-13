# Vakeel-Sahayak.ai: the project in brief

## The problem
Legal-aid lawyers in India prepare bail applications from messy case files: scanned or photographed orders, Hindi and English, several documents merged into one PDF. Missing a single fact can cost a client their liberty: a custody date that opens default bail, or a co-accused who got bail. Vakeel-Sahayak.ai turns such a file into a source-checked bail application that the lawyer approves.

It is built as an **agent harness**, not a single model call. Six agents work over ten typed stores, and every claim in the draft points back to a page or a judgment.

## How a case flows through the system
1. **Upload.** Counsel adds the case file: PDF, photo or DOCX.
2. **Munshi (intake)** reads every page by text layer, OCR or vision. It splits the bundle into documents (FIR, remand order, court order, custody certificate) and files the text into the case's private store. It asks only about what is missing, for example "Has the charge sheet been filed?"
3. **Peshkar (dossier)** builds the dossier, with each field quoting its source page, and the List of Dates. It also runs the **Rights Radar**: seven rules checked in code, not by a model (default bail, BNSS s.479 undertrial limit, notice of appearance, grounds of arrest, production within 24 hours, Antil category, statutory bars). The rule texts are verified against the official bare acts by script.
4. **Gate 1.** Counsel reviews the dossier and approves it, acknowledging anything the papers do not support.
5. **Sutradhar (orchestrator)** reads a short evidence contract for each of 12 bail factors. It decides which stores to search, in what order, and when it has enough.
6. **Vakeel (drafter)** writes the grounds. Each sentence is marked as a case fact `[F:...]` or a legal authority `[A:...]`. A checker tests every sentence against its source; failing sentences are repaired or withheld and listed for counsel. Nothing is dropped silently.
7. **Abhiyojak (prosecution)** attacks the draft the way the State would, isolated from the drafter. Vakeel answers each objection, and a hearing-prep card is built.
8. **Gate 2.** Counsel approves the final draft, and only then can it be exported: the application, List of Dates, objections sheet and hearing card, as DOCX or PDF. The export is bound to the exact text counsel approved.
9. **Pairokar (batch desk)** ranks many files by legal urgency for a legal-aid office.

## Data and stores
- **Shared stores** are built from public data: about 116,000 court orders from Open India Law, the statutes, and the IPC→BNS and CrPC→BNSS concordance. They are organised on three shelves:
  - **law:** statutes, concordance;
  - **case law:** court reasoning, citation graph with authority and good-law status, similar orders;
  - **advocacy:** arguments and objections from past orders, never cited as authority.
- **Per-case stores** hold the client's documents, timeline and dossier. They live only on the lawyer's machine.
- **Retrieval** is hybrid. Metadata filters come first, then BM25 and dense-vector rankings fused by reciprocal rank fusion, with a leakage guard so a case never sees orders dated after its own.
- **The event log** records every agent step, tool call and approval. This makes each case replayable and auditable.

## Rules the system enforces in code
- **Only counsel approves.** No agent can approve a gate, and export is impossible before Gate 2.
- **Privacy.** Client files never leave the machine. Anything sent to a hosted model is pseudonymised first, and free-tier models get public data only.
- **No prediction.** The system gives no outcome predictions, no grant rates and no advice to the public.
- **No manual annotation.** Gold labels come from court text, with a rule labeler and a separate model labeler that must agree and quote a verbatim span.

## Finding the architecture, and how it was evaluated
- **Baselines.** The full system was compared against seven simpler ones:
  - B0: a single model call;
  - B1: one store, one drafting call;
  - B2: whole-order embeddings;
  - B3: naive chunking;
  - B4: query every store;
  - B5: a learned store router;
  - B6: an expert rule list.
- **Statistics.** A win counts only when a paired bootstrap interval excludes zero, with a Holm correction across the baselines.
- **Search.** A search over opt-in switches ran on 30 development orders on Sarvam-105B. It chose **c1457**: the full system plus four switches.
  - Fill dossier gaps from the raw facts.
  - Strict abstention: withhold what the record does not support.
  - Draft from the facts text.
  - Match objections to evidence by ID.
- **Holdout.** It was confirmed on 20 held-out orders. The hypotheses were pre-registered and the freeze tags created before the blind run.
- **Blind result.** On 80 sealed orders, opened once, c1457 scored **46 wins, 69 ties and 5 losses** against B0–B6. The original full system scored 29, 76 and 15.
  - Four of the five registered hypotheses held: better objection recall and coverage than the original full system, better citation precision with no fabricated citations, fewer unsupported facts, and fewer store calls than querying every store.
  - The fifth failed on one comparison: B5 writes fewer sentences, so it has fewer unsupported ones in absolute count, while c1457 still wins on the rate.
- **Ablations.** Twelve ablations of c1457 were scored; none produced a better brief.

## Honest limitations
- c1457 is slower and uses more tokens than the cheapest baselines: about 9 minutes and 120,000 tokens per case, against B5's 77,000 tokens.
- A few losses are structural and are reported, not hidden. For example, a rule list (B6) covers every factor by construction.
- The Rights rules are checked against the statute texts in the store. The Companies Act text comes from a 2016 copy of the Ministry's text, so later amendments to it are not covered.
- In the offline demo, stand-in models replace the hosted LLM. The flow, gates, checks and exports are real, but the draft wording is simpler than with Sarvam-105B.

## Running the demo
- **Backend:** `.venv/bin/python -m uvicorn vakeel_sahayak.api.asgi:app --port 8000`
- **Frontend:** `cd frontend && NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_BASE=http://localhost:8000 npx next dev -p 3000`
- **Demo cases:** `.venv/bin/python scripts/load_demo_cases.py` loads 100 cases built from public court orders, in six input formats (born-digital, scanned, degraded scan, phone photo, Hindi, legacy-font Hindi).
- **Then:** open http://localhost:3000/cases, pick a case, and walk it through review facts → check rights → Gate 1 → draft → sparring → Gate 2 → export.
