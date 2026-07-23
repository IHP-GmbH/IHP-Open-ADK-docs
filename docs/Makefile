# Copyright 2026 IHP Open ADK Authors
# SPDX-License-Identifier: Apache-2.0
#
# Minimal makefile for Sphinx documentation.

SPHINXOPTS    ?= -j auto -W --keep-going
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build
PYTHON        ?= python3

.PHONY: docs setup preprocess build linkcheck latexpdf clean display help

# Default: full local build chain.
docs: clean setup preprocess build display

setup:
	$(PYTHON) -m pip install -r requirements.txt

# Regenerate every table and CLI transcript from the pinned sources under src/.
# Mirrors the pre_build jobs in ../.readthedocs.yaml; keep the two in sync.
preprocess:
	$(PYTHON) scripts/gen_rule_tables.py
	$(PYTHON) scripts/gen_adapter_table.py
	$(PYTHON) scripts/gen_version_matrix.py
	$(PYTHON) scripts/gen_cli_usage.py

build:
	$(SPHINXBUILD) -b html $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/html

linkcheck:
	$(SPHINXBUILD) -b linkcheck $(SOURCEDIR) $(BUILDDIR)/linkcheck

latexpdf:
	$(SPHINXBUILD) -b latex $(SOURCEDIR) $(BUILDDIR)/latex
	$(MAKE) -C $(BUILDDIR)/latex all-pdf

clean:
	rm -rf $(BUILDDIR)

display:
	xdg-open $(BUILDDIR)/html/index.html >/dev/null 2>&1 || true

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)
