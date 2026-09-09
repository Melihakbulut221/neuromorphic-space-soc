# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
#
#   make -C paper            build the PDF
#   make -C paper check      re-derive every number the paper prints
#   make -C paper clean
#
# THE PDF IS NOT BUILT IN THIS REPOSITORY'S DEVELOPMENT ENVIRONMENT.
# There is no TeX installation on the machine this paper was written on;
# `pdflatex`, `xelatex`, `lualatex`, `latexmk` and `tectonic` are all
# absent. The source is written to compile on arXiv, which runs its own
# TeX Live, and .github/workflows/paper.yml builds it on every push so
# that "it compiles" is a checked claim rather than an assumed one.
#
# That is stated here rather than discovered by whoever runs this first.

LATEX ?= pdflatex
BIBTEX ?= bibtex
DOC := main

.PHONY: all check clean
all: $(DOC).pdf

$(DOC).pdf: $(DOC).tex refs.bib
	@command -v $(LATEX) >/dev/null || { \
	  echo "no $(LATEX) on this machine."; \
	  echo "The source is arXiv-ready and CI builds it; see the header."; \
	  exit 1; }
	$(LATEX) -interaction=nonstopmode $(DOC)
	-$(BIBTEX) $(DOC)
	$(LATEX) -interaction=nonstopmode $(DOC)
	$(LATEX) -interaction=nonstopmode $(DOC)

check:
	python3 check_claims.py

clean:
	rm -f $(DOC).pdf $(DOC).aux $(DOC).log $(DOC).out $(DOC).bbl \
	      $(DOC).blg $(DOC).toc
