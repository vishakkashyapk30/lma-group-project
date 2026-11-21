#!/usr/bin/env bash
# Renders docs/assets/architecture.png from architecture.tex, which holds Figure 1 of
# docs/technical-report/technical_report.tex unchanged. Needs pdflatex (TeX Live) and pdftoppm (poppler).
set -euo pipefail
cd "$(dirname "$0")"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
# Optional: bash build.sh compact  -> architecture_compact.{pdf,png} (poster figure, 600 dpi)
if [ "${1:-}" = "compact" ]; then
  pdflatex -interaction=nonstopmode -halt-on-error -output-directory "$tmp" architecture_compact.tex >/dev/null
  cp "$tmp/architecture_compact.pdf" architecture_compact.pdf
  pdftoppm -png -r 600 -singlefile architecture_compact.pdf architecture_compact
  echo "wrote $(pwd)/architecture_compact.pdf and .png"
  exit 0
fi
pdflatex -interaction=nonstopmode -halt-on-error -output-directory "$tmp" architecture.tex >/dev/null
pdftoppm -png -r 200 -singlefile "$tmp/architecture.pdf" architecture
echo "wrote $(pwd)/architecture.png"

