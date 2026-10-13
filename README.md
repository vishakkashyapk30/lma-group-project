# Vakeel-Sahayak.ai

**A bail-preparation assistant for legal-aid lawyers (LMA Group Project 2026).**

Vakeel-Sahayak.ai helps a lawyer prepare a regular bail application in an Indian court. It has two agents:

1. **Case-File Agent.** It reads the uploaded court orders, or facts typed into a chat, and builds a case dossier. Every field in the dossier comes with the source sentence it was taken from.
2. **Bail-Brief Agent.** It drafts a bail brief from the approved dossier. Every claim in the brief is checked against the dossier or against a retrieved judgment. IPC-era case law is carried over to BNS-era cases, and the brief warns when a provision has changed.

The project combines all five course capabilities: a QLoRA-fine-tuned extractor, retrieval over Open India Law, a plan, draft and check loop, two agents with approval steps for the lawyer, and deterministic tools. Every model is open-weight, and no part of the project needs manual annotation.

**Status:** proposal stage. Implementation starts after TA approval.

## Repository layout

```
.
├── README.md
├── pyproject.toml                 Package `vakeel_sahayak` (Python >= 3.10); extras: ocr, speech, models, train, eval, dev
├── Makefile                       Stub targets: setup, stores, testsets, eval-*, api, frontend, lint, test
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
