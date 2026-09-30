# LMA Group Project 2026: Verified Bail Preparation for Legal-Aid Defense Counsel

This is the planning stage of an end-to-end agentic system for Indian criminal law. It has two parts:

- A **Court-Records Agent** turns a case file into a verified dossier.
- A **Defense-Preparation Agent** uses that dossier to write a grounded bail brief whose citations have been checked.

The system combines RAG, tool calling, multi-step reasoning, a QLoRA-fine-tuned small model, and human-in-the-loop review.

| File | Contents |
|---|---|
| [plan.md](plan.md) | Full project plan: users, research questions, architecture, tools, fine-tuning, evaluation sets, metrics, ablations, compute, timeline, risks |
| [datasets_sources.md](datasets_sources.md) | Datasets, benchmarks, tools/APIs, baseline papers and metric sources, arranged by category |
| [pipeline_research.md](pipeline_research.md) | Research landscape, gaps, candidate research ideas, failure modes |
| [ideas.md](ideas.md) | Early ideation notes |
| [project_announcement.md](project_announcement.md) | Course project brief |

**Status:** proposal stage. Implementation starts after TA approval.
