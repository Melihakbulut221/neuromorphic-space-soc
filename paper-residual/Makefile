# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
#
#   make -C paper-residual         build the PDF
#   make -C paper-residual arxiv   the .tex + .bbl tarball arXiv wants
#   make -C paper-residual clean
#
# tectonic resolves its own packages and runs the passes itself, so it is
# preferred when present; the pdflatex path is kept because arXiv and CI
# have TeX Live and not tectonic. --keep-intermediates is not optional:
# the arxiv target ships main.bbl, and without it tectonic deletes the
# one file that target exists to carry.
TECTONIC ?= $(shell command -v tectonic 2>/dev/null || \
              ls $(HOME)/.local/opt/tectonic-env/bin/tectonic 2>/dev/null)
LATEX ?= pdflatex
BIBTEX ?= bibtex
DOC := main

.PHONY: all arxiv clean
all: $(DOC).pdf

$(DOC).pdf: $(DOC).tex refs.bib
ifneq ($(TECTONIC),)
	$(TECTONIC) -X compile $(DOC).tex --outdir . --keep-logs \
	  --keep-intermediates
else
	@command -v $(LATEX) >/dev/null || { \
	  echo "no $(LATEX) and no tectonic on this machine."; exit 1; }
	$(LATEX) -interaction=nonstopmode $(DOC)
	$(BIBTEX) $(DOC)
	$(LATEX) -interaction=nonstopmode $(DOC)
	$(LATEX) -interaction=nonstopmode $(DOC)
endif
	@grep -qE 'Citation .* undefined|Reference .* undefined' $(DOC).log \
	  && { echo "undefined citations or references -- see $(DOC).log"; \
	       exit 1; } || true

# main.bbl IS NOT BUILD OUTPUT for this deliverable. arXiv compiles the
# tarball it is given and does not run BibTeX, so the .bbl must travel
# with the source or every citation renders as [?].
arxiv: $(DOC).pdf
	@test -s $(DOC).bbl || { echo "no $(DOC).bbl to ship"; exit 1; }
	tar czf arxiv.tar.gz $(DOC).tex $(DOC).bbl
	@echo "arxiv.tar.gz written -- .tex and .bbl, no .bib"

clean:
	rm -f $(DOC).pdf $(DOC).aux $(DOC).bbl $(DOC).blg $(DOC).log \
	      $(DOC).out arxiv.tar.gz
