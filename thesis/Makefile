# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
#
#   make -C thesis         build the PDF
#   make -C thesis arxiv   the .tex + .bbl tarball arXiv wants
#   make -C thesis clean
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
# TWO GATES ON THE RENDERED PAGE. Neither of these can be seen by
# reading the source, and both have shipped in this project: an
# instruction line that leaked into a table body made a row 890 pt
# wider than the page, and a figure printed every macro's name on top
# of its own dimensions for two revisions. The log answers the first;
# only the PDF answers the second.
	@grep -q 'Overfull' $(DOC).log && { \
	  echo "overfull box -- something is wider than the page:"; \
	  grep -n 'Overfull' $(DOC).log; exit 1; } || true
	@command -v pdftotext >/dev/null || { \
	  echo "pdftotext (poppler-utils) is needed to check the page for"; \
	  echo "text printed over other text; install it or build elsewhere."; \
	  exit 1; }
	@python3 ../scripts/pdf_overlap_check.py $(DOC).pdf --quiet
# A GROUP SEPARATOR INSIDE A DECIMAL PART. siunitx applies
# group-separator to the DECIMAL side as well as the integer side
# unless group-digits=integer says otherwise, so a number with four
# decimal places prints as 7.575,8. Two published revisions of the
# thesis printed the design's worst setup slack and its hold margin
# that way, 44 numbers in all. This is checked in the source rather
# than in the rendered text because the rendered form -- a comma
# between digits -- is indistinguishable from a prose list of three
# decimals, and the source form is exact. Comments are stripped
# first: the preamble's own note names the key, and a grep that
# saw it there passed a file that did not set it.
	@sh -c 'if sed "s/%.*//" $(DOC).tex | grep -q "group-separator" && \
	          ! sed "s/%.*//" $(DOC).tex | grep -q "group-digits=integer"; \
	        then \
	          echo "siunitx will group the DECIMAL part of every number"; \
	          echo "with four or more places: set group-digits=integer"; \
	          echo "in $(DOC).tex, beside group-separator."; exit 1; fi'

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
