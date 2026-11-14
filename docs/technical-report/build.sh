#!/usr/bin/env bash
# Build docs/technical-report/technical_report.pdf (pdflatex + bibtex; no latexmk needed).
# Each pdflatex pass runs under a 2 GB memory limit when systemd-run is available.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
if command -v systemd-run >/dev/null 2>&1 && systemd-run --user --scope -q -p MemoryMax=2G -- true 2>/dev/null; then
  LIMIT=(systemd-run --user --scope -q -p MemoryMax=2G --)
else
  LIMIT=()
fi
tex() { "${LIMIT[@]}" pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build technical_report.tex >build/pdflatex.out || { tail -40 build/pdflatex.out; exit 1; }; }
tex
BIBINPUTS=. BSTINPUTS=. bibtex build/technical_report >build/bibtex.out || { cat build/bibtex.out; exit 1; }
tex
tex
tex
cp build/technical_report.pdf technical_report.pdf
grep -E "Overfull|undefined|multiply" build/technical_report.log || true
echo "technical_report.pdf: $(pdfinfo technical_report.pdf 2>/dev/null | awk '/^Pages/{print $2}') pages"
