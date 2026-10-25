# Vakeel-Sahayak.ai

**A bail-preparation assistant for legal-aid lawyers (LMA Group Project 2026).**

Vakeel-Sahayak.ai helps a lawyer prepare a regular bail application in an Indian court from the case file. Six agents work together:

1. **Munshi** (intake) reads any kind of PDF (digital, scanned, photographed, Hindi, several documents in one file), files what it finds into typed stores and asks the lawyer only for what is missing.
2. **Peshkar** builds the source-checked dossier and the List of Dates, runs a rules-based Rights Radar (default bail, BNSS s.479, notice of appearance, grounds of arrest, and more), and spots what changed when a new order arrives.
3. **Sutradhar** decides, for each bail factor, which of ten stores to query and when it has enough evidence.
4. **Vakeel** drafts grounds that cite only facts on record and real judgments, checks every claim, and never drops one silently.
5. **Abhiyojak** attacks the draft the way the prosecution would, kept deliberately isolated from the drafter.
6. **Pairokar** ranks many files by legal urgency for a legal-aid office.

The lawyer approves the dossier and the final draft; nothing is exported without that approval, and this is enforced in code. The project combines all five course capabilities and is evaluated against simpler baselines (see `docs/evaluation-plan.md`).

**Status (2026-10-25):** the agents, stores, Rights Radar, evaluation infrastructure and a redesigned frontend are built and unit-tested on offline stand-in models. Not yet built: the LangGraph flow that connects the agents, the real API routes, DOCX export, the metrics and statistics code, and any real-model results. Start with `AGENTS.md`, then `split.md` (who does what) and `progress.md` (status of everything).

**Quick start:** `docker compose up`, then open http://localhost:3000 (the UI runs on sample data until the API routes exist). See `DOCKER.md`.

## Repository layout

```
.
├── README.md
├── pyproject.toml                 Package `vakeel_sahayak` (Python >= 3.10); extras: ocr, speech, models, train, eval, dev
├── Makefile                       Targets: setup, datasets, interim, stores, models, smoke, eval-*, test-*, docker-*
├── .env.example  .gitignore
├── configs/                       YAML: models, stores, budgets, thresholds, paths, tools, rights rules, splits
│   ├── finetune/                  QLoRA and teacher-pilot configs
│   └── eval/                      Run registry (shards, node-hours) and hypotheses
├── src/vakeel_sahayak/
│   ├── schemas/                   IngestionReport, CaseDossier, RightsReport, RetrievalPlan, BailBrief,
│   │                              SparringRecord, TriageCard, Event, store rows, enums
│   ├── record/                    Event log, case state (views), SQLite checkpointer
│   ├── orchestration/             LangGraph wiring, approval gates, budgets, ablation switches
│   ├── agents/                    munshi/ peshkar/ sutradhar/ vakeel/ abhiyojak/ pairokar/ (+ base, registry)
│   ├── tools/                     39 tools by domain: intake/, dossier, case/, law/, caselaw/, advocacy/, drafting/
│   ├── stores/                    Ten stores on four shelves, one module each, plus base, registry, chunking
│   ├── contracts/                 Evidence-contract loader and factors/*.yaml (12 factors)
│   ├── rights/                    Rights Radar engine and rules/ (7 rules)
│   ├── ingestion/                 Routing ladder, page signals, routes/, bundles, gaps, Hindi, voice
│   ├── truth_maintenance/         Dependencies, staleness, incremental redraft
│   ├── batch/                     Pairokar queue, retrieval cache, scheduler, urgency rule
│   ├── privacy/                   Pseudonymisation, leak check, injection guard, sensitive-matter decline
│   ├── models/                    Model clients: vLLM, local 4B, VLM, OCR, ASR, translation, NLI, embeddings
│   ├── export/                    DOCX application, List of Dates, hearing card, PDF
│   ├── api/                       FastAPI app and routers (cases, upload, chat, events, gates, export, desk, library)
│   ├── pipelines/                 Open India Law ingest, order splitter, factor tagger, gold G1-G7, store builders
│   ├── finetune/                  Teacher dossiers, span-check filter, noise augmentation, QLoRA
│   ├── testsets/                  Construction of T1-T9
│   ├── eval/                      baselines B0-B4, ablations A1-A10, ingestion P1-P6, features F1-F8, metrics, stats, runners
│   └── config.py
├── frontend/                      Next.js (App Router, TypeScript): app/ routes, components/{landing,agents,workspace,...},
│                                  lib/ (API client, SSE hook, types), styles/tokens.css ("Manuscript" palette)
├── scripts/                       Local helpers; scripts/ada/ holds interactive shard runners and the QLoRA sbatch
├── data/                          raw/ interim/ stores/ testsets/ cases/ (contents gitignored; see data/README.md)
└── docs/
    ├── plan.md                    Working project plan (v5)
    ├── architecture/skeleton.md   Plan-section to module map and conventions for coding agents
    ├── proposal/                  Proposal for TA review (md, tex, pdf, build.sh, figures/)
    ├── research/                  Background research from the ideation phase
    └── course/                    Course project brief
```

## Getting started (skeleton)

The repository is a skeleton: every module has typed signatures and docstrings, and every body raises `NotImplementedError`. Nothing runs end to end yet.

```bash
python3 -m venv .venv
.venv/bin/pip install pydantic pyyaml fastapi httpx python-multipart   # light deps only
.venv/bin/pip install -e . --no-deps                                   # or `pip install -e ".[dev]"` for everything
.venv/bin/python -c "import vakeel_sahayak"                            # every submodule imports cleanly
cd frontend && npm install                                             # optional; then `npm run dev`
```

Heavy ML dependencies (vLLM, torch, Docling, Surya) are in optional extras and are imported lazily. Read `docs/architecture/skeleton.md` before adding code.

## Building the proposal PDF

```bash
./docs/proposal/build.sh
```

The script needs `pdflatex` (TeX Live). If the diagram source has changed, it also needs Node.js and Chrome or Chromium, because it re-renders the diagram with `@mermaid-js/mermaid-cli`.
