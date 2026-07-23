#!/usr/bin/env bash
# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
#
# Render the standalone TikZ figures to SVG and PDF.
#
# Both formats are committed because Read the Docs has no LaTeX installation
# for TikZ. Pages reference figures as "name.*" so Sphinx picks the SVG for the
# HTML builder and the PDF for the LaTeX builder, which keeps the PDF output
# working without an SVG converter dependency.
#
# Run this only when a .tex source changes, and commit the result.
#
# Requires: pdflatex and dvisvgm, both from a TeX Live install.

set -euo pipefail

cd "$(dirname "$0")"
out="../"

command -v pdflatex >/dev/null || { echo "pdflatex not found"; exit 1; }
command -v dvisvgm  >/dev/null || { echo "dvisvgm not found";  exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

status=0
for tex in tikz_*.tex; do
    stem="${tex%.tex}"
    echo "rendering ${stem}"

    # DVI first, for dvisvgm. It needs a dvi with the PostScript specials.
    if ! pdflatex -output-format=dvi -interaction=nonstopmode -halt-on-error \
            -output-directory="$work" "$tex" >"$work/${stem}.dvi.log" 2>&1; then
        echo "  FAILED (dvi), see $work/${stem}.dvi.log" >&2
        tail -20 "$work/${stem}.dvi.log" >&2
        status=1
        continue
    fi
    dvisvgm --font-format=woff --exact --no-fonts \
            --output="${out}${stem}.svg" "$work/${stem}.dvi" >/dev/null 2>&1
    echo "  -> ${out}${stem}.svg"

    # PDF for the LaTeX builder.
    if ! pdflatex -interaction=nonstopmode -halt-on-error \
            -output-directory="$work" "$tex" >"$work/${stem}.pdf.log" 2>&1; then
        echo "  FAILED (pdf), see $work/${stem}.pdf.log" >&2
        tail -20 "$work/${stem}.pdf.log" >&2
        status=1
        continue
    fi
    cp "$work/${stem}.pdf" "${out}${stem}.pdf"
    echo "  -> ${out}${stem}.pdf"
done

exit $status
