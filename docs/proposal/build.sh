#!/usr/bin/env bash
# Build proposal.pdf from proposal.tex.
# Re-renders the Mermaid diagram first if figures/architecture.mmd is newer than its PDF.
# Needs: pdflatex (TeX Live), and for the diagram, Node.js plus Chrome/Chromium.
# Usage: ./build.sh
set -euo pipefail
cd "$(dirname "$0")"

if [[ figures/architecture.mmd -nt figures/architecture.pdf ]]; then
  export PUPPETEER_EXECUTABLE_PATH="${PUPPETEER_EXECUTABLE_PATH:-$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)}"
  npx -y -p @mermaid-js/mermaid-cli mmdc -i figures/architecture.mmd -o figures/architecture.pdf
fi

mkdir -p build
for _ in 1 2 3; do
  pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build proposal.tex > build/pdflatex.out
done
cp build/proposal.pdf proposal.pdf
echo "proposal.pdf: $(pdfinfo proposal.pdf | awk '/^Pages/{print $2}') pages"
