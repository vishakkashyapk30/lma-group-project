# Status report (ACL format) — draft

LMA group project status report, written with the official ACL style files. Draft state: the system, evaluation design, limitations and plan are written; the results section is a template; `\todo{...}` markers (red, bold in the PDF) mark every number or fact still needed.

## Files

| Path | What |
|---|---|
| `main.tex` | Preamble (`acl.sty`, `[preprint]` option), `\todo` macro, `\resulttable` macro, title, section includes |
| `sections/*.tex` | abstract, introduction, related, system (with the TikZ architecture figure), evaluation, results (template), limitations, threats, status, ethics, appendix |
| `references.bib` | only papers from the verification table of `docs/literature-to-code-map.md` or cited with a checked venue in `docs/plan.md` v6 and `docs/literature-review-and-usage.md` (see the header comment of the file) |
| `acl.sty`, `acl_natbib.bst`, `acl_latex.tex` | official files from github.com/acl-org/acl-style-files (downloaded with curl; `acl_latex.tex` is the template, kept for reference) |
| `build.sh`, `Makefile` | `pdflatex` + `bibtex` (no `latexmk` on this machine); `make` or `./build.sh` writes `main.pdf` |

## Build

```bash
cd docs/report && ./build.sh      # needs pdflatex and bibtex (TeX Live); output main.pdf
```
Draft mode: `\drafttrue` in `main.tex` shows `\todo` text in red; set `\draftfalse` for a clean copy (then no sentence may depend on a todo). Use `\usepackage[review]{acl}` for an anonymous version, `[final]` for camera-ready.

## Where results tables come from

Nothing in the text is a typed result. The results section and the appendix include LaTeX fragments written by the scoring pipeline (`src/vakeel_sahayak/eval/scoring/render.py`):

```bash
.venv/bin/python -m vakeel_sahayak.eval.scoring score --runs data/eval/dev_runs --slice dev --gold-source both --out data/eval/dev_scores
.venv/bin/python -m vakeel_sahayak.eval.scoring report --scores data/eval/dev_scores --out docs/results/dev-sweep
```
Files read from `docs/results/dev-sweep/tables/` (by `\resulttable{stem}{n|w}`; `w` forces a two-column `table*` at `\scriptsize`): `table1_main`, `table_paired`, `table_holm`, `table_sweep_metrics`, `table9_cost`, `table_label_coverage`, `table_label_sensitivity`, `table_label_kappa`, `table_citations`, `table_abstention`, `table_rights`, `table_sweep_robustness`. A missing file shows a placeholder box, so the document compiles with or without them. Check the `--out` argument of `report` so the files land in `tables/` under that folder. Generated tables add pages: `table1_main` goes in the body, the rest are in the appendix. When the tables exist, re-check the page count and any overfull table.

## Status (2026-10-27)

- Written: all sections; architecture figure (TikZ, v6 design, redrawn; the proposal's figure is the older two-agent v4); appendix with reproducibility, the arms table and the metric table.
- Builds with pdflatex: yes (10 pages in total). Numbered sections run to about 7 pages, not 6; to reach 6, move the arms table or the Related Work detail to the appendix, or cut the Limitations bullets.
- Not written: any result number (by design), the `\todo` items listed in the hand-off message, a camera-ready check of the bibliography (author lists are as in the project docs: "and others" where the docs give only a first author; Doyle 1979 was checked on secondary sources only; Wachsmuth et al. and Cemri et al. have surnames only in the docs).
- Not in this folder: results (owner decision: no new paid runs for now; the dev reruns at tag `dev-sweep-v1` are on disk but unscored).

Rules followed: past tense for what is built, no outcome claims, no AI attribution, authors are the four teammates.
