#!/usr/bin/env bash
# Build docs/report/midsubmission_v1.pdf (pdflatex + bibtex), the version without the OpenAI current-code block.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build_v1
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build_v1 midsubmission_v1.tex >build_v1/pdflatex.out || { tail -40 build_v1/pdflatex.out; exit 1; }
BIBINPUTS=. BSTINPUTS=. bibtex build_v1/midsubmission_v1 >build_v1/bibtex.out || { cat build_v1/bibtex.out; exit 1; }
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build_v1 midsubmission_v1.tex >build_v1/pdflatex.out
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build_v1 midsubmission_v1.tex >build_v1/pdflatex.out
cp build_v1/midsubmission_v1.pdf midsubmission_v1.pdf
echo "midsubmission_v1.pdf: $(pdfinfo midsubmission_v1.pdf | awk '/^Pages/{print $2}') pages"
