# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
#
#   make -C paper            build the PDF
#   make -C paper check      re-derive every number the paper prints
#   make -C paper clean
#
# ~~THE PDF IS NOT BUILT IN THIS REPOSITORY'S DEVELOPMENT ENVIRONMENT.
# There is no TeX installation on the machine this paper was written on;
# `pdflatex`, `xelatex`, `lualatex`, `latexmk` and `tectonic` are all
# absent.~~
#
# CORRECTED 2026-09-14: tectonic 0.17.0 is installed, into an isolated
# conda prefix rather than the system, so no root was needed and nothing
# outside that prefix moved. `make` now builds the PDF here: 31 pages,
# zero undefined citations, seven overfull/underfull boxes. The sentence
# above was true when it was written and had become a reason not to try.
#
# The rest of the original note still holds and is why this target is
# written the way it is: the source is written to compile on arXiv,
# which runs its own TeX Live, and CI builds it on every push so that
# "it compiles" is a checked claim rather than an assumed one.
#
# Corrected 2026-09-12: this named .github/workflows/paper.yml, which
# was deleted in 74fdddf when three workflows were replaced by the
# single .github/workflows/checks.yml. That file calls
# scripts/ci_local.sh, whose `paper` job installs texlive and runs the
# build; commit cf2ece6 records it green. A pointer at a deleted file is
# worse than no pointer, because it reads as a checked claim and there
# is nothing behind it -- and nothing in the suite could catch it, since
# test_doc_links.py only follows references inside documents.
#
# That is stated here rather than discovered by whoever runs this first.
#
# `make arxiv` builds the tarball arXiv actually wants: the .tex and the
# .bbl, no .bib. It refuses to write one without a .bbl.

# tectonic resolves its own packages and runs the passes itself, so it
# is preferred when present; the pdflatex path is kept because arXiv and
# CI have TeX Live and not tectonic. --keep-intermediates is NOT
# optional: the arxiv target ships main.bbl, and without it tectonic
# deletes the one file that target exists to carry.
TECTONIC ?= $(shell command -v tectonic 2>/dev/null || \
              ls $(HOME)/.local/opt/tectonic-env/bin/tectonic 2>/dev/null)
LATEX ?= pdflatex
BIBTEX ?= bibtex
DOC := main

.PHONY: all check clean
all: $(DOC).pdf

$(DOC).pdf: $(DOC).tex refs.bib
ifneq ($(TECTONIC),)
	$(TECTONIC) -X compile $(DOC).tex --outdir . --keep-logs \
	  --keep-intermediates
	@grep -qE 'Citation .* undefined' $(DOC).log \
	  && { echo "undefined citations -- see $(DOC).log"; exit 1; } || true
	@test -s $(DOC).bbl || { echo "no $(DOC).bbl -- the arxiv target \
	  needs it and tectonic was asked to keep it"; exit 1; }
else
	@command -v $(LATEX) >/dev/null || { \
	  echo "no $(LATEX) and no tectonic on this machine."; \
	  echo "The source is arXiv-ready and CI builds it; see the header."; \
	  exit 1; }
	$(LATEX) -interaction=nonstopmode $(DOC)
	$(BIBTEX) $(DOC)
	$(LATEX) -interaction=nonstopmode $(DOC)
	$(LATEX) -interaction=nonstopmode $(DOC)
	@grep -qE 'Citation .* undefined' $(DOC).log \
	  && { echo "undefined citations -- see $(DOC).log"; exit 1; } || true
endif

check:
	python3 check_claims.py

# main.bbl IS NOT BUILD OUTPUT for this deliverable. arXiv compiles the
# tarball it is given and does not run BibTeX, so the .bbl must travel
# with the source or every citation renders as [?] -- a warning, not an
# error, so an unchecked build is green on an empty bibliography.
.PHONY: arxiv
arxiv: $(DOC).pdf
	@test -s $(DOC).bbl || { echo "no $(DOC).bbl to ship"; exit 1; }
	tar czf arxiv.tar.gz $(DOC).tex $(DOC).bbl
	@echo "arxiv.tar.gz written -- .tex and .bbl, no .bib"

clean:
	rm -f $(DOC).pdf $(DOC).aux $(DOC).log $(DOC).out \
	      $(DOC).blg $(DOC).toc arxiv.tar.gz
