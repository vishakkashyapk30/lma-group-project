#!/usr/bin/env bash
# Build docs/report/main.pdf (pdflatex + bibtex; no latexmk needed).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex >build/pdflatex.out || { tail -40 build/pdflatex.out; exit 1; }
BIBINPUTS=. BSTINPUTS=. bibtex build/main >build/bibtex.out || { cat build/bibtex.out; exit 1; }
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex >build/pdflatex.out
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex >build/pdflatex.out
cp build/main.pdf main.pdf
echo "main.pdf: $(pdfinfo main.pdf 2>/dev/null | awk '/^Pages/{print $2}') pages"
