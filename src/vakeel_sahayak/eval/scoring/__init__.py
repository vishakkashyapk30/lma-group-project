"""Scoring of driver run directories against the T1 gold (docs/evaluation-plan.md sections 4, 5, 6; handoff docs/handoff/eval-scoring.md).

Load a run directory, join with the gold of the chosen source, compute the per-case metrics of the headline table, the paired statistics and the Holm
decisions of the registered primary families, the gold-source sensitivity sweep, and write the tables (Markdown, LaTeX, CSV) and figures.
CLI: `python -m vakeel_sahayak.eval.scoring score|report ...`.
"""
