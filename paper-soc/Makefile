# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
#
#   make -C paper-soc         build the PDF
#   make -C paper-soc arxiv   the .tex + .bbl + figures tarball arXiv wants
#   make -C paper-soc clean
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
FIGS := figures/floorplan_macros.pdf figures/layout_regions.pdf \
        figures/layout_panels.pdf

.PHONY: all arxiv clean
all: $(DOC).pdf

$(DOC).pdf: $(DOC).tex refs.bib $(FIGS)
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
# with the source or every citation renders as [?]. Unlike paper-design,
# this paper has figures, and they must travel with it too: a tarball of
# .tex and .bbl alone would not compile here.
arxiv: $(DOC).pdf
	@test -s $(DOC).bbl || { echo "no $(DOC).bbl to ship"; exit 1; }
	tar czf arxiv.tar.gz $(DOC).tex $(DOC).bbl $(FIGS)
	@echo "arxiv.tar.gz written -- .tex, .bbl and the three figures"

clean:
	rm -f $(DOC).pdf $(DOC).aux $(DOC).bbl $(DOC).blg $(DOC).log \
	      $(DOC).out arxiv.tar.gz
