# Vakeel-Sahayak.ai

**A bail-preparation assistant for legal-aid lawyers (LMA Group Project 2026).**

Vakeel-Sahayak.ai helps a lawyer prepare a regular bail application in the Delhi High Court. It has two agents:

1. **Case-File Agent.** It reads the uploaded court orders, or facts typed into a chat, and builds a case dossier. Every field in the dossier comes with the source sentence it was taken from.
2. **Bail-Brief Agent.** It drafts a bail brief from the approved dossier. Every claim in the brief is checked against the dossier or against a retrieved judgment. IPC-era case law is carried over to BNS-era cases, and the brief warns when a provision has changed.

The project combines all five course capabilities: a QLoRA-fine-tuned extractor, retrieval over Open India Law, a plan, draft and check loop, two agents with approval steps for the lawyer, and deterministic tools. Every model is open-weight, and no part of the project needs manual annotation.

**Status:** proposal stage. Implementation starts after TA approval.

## Repository layout

```
.
├── README.md
└── docs/
    ├── proposal/                  Proposal for TA review
    │   ├── proposal.md            Markdown version (renders on GitHub, Mermaid diagram included)
    │   ├── proposal.tex           LaTeX source
    │   ├── proposal.pdf           Compiled proposal (8 pages plus references)
    │   ├── build.sh               Rebuilds the diagram (if changed) and the PDF
    │   └── figures/
    │       ├── architecture.mmd   Mermaid source of the architecture diagram
    │       └── architecture.pdf   Rendered diagram used by the LaTeX file
    ├── plan.md                    Working project plan: data, models, schemas, user flows, evaluation, compute
    ├── research/                  Background research from the ideation phase
    │   ├── datasets_sources.md    Datasets, benchmarks, tools and papers
    │   ├── pipeline_research.md   Research landscape and gaps
    │   └── ideas.md               Early ideation notes
    └── course/
        └── project_announcement.md   Course project brief
```

## Building the proposal PDF

```bash
./docs/proposal/build.sh
```

The script needs `pdflatex` (TeX Live). If the diagram source has changed, it also needs Node.js and Chrome or Chromium, because it re-renders the diagram with `@mermaid-js/mermaid-cli`.
