#!/usr/bin/env bash
# Renders docs/assets/architecture.png from architecture.tex, which holds Figure 1 of
# docs/technical-report/technical_report.tex unchanged. Needs pdflatex (TeX Live) and pdftoppm (poppler).
set -euo pipefail
cd "$(dirname "$0")"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
pdflatex -interaction=nonstopmode -halt-on-error -output-directory "$tmp" architecture.tex >/dev/null
pdftoppm -png -r 200 -singlefile "$tmp/architecture.pdf" architecture
echo "wrote $(pwd)/architecture.png"
