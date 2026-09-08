# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# Toolchain resolution, shared by every makefile in this repository.
#
# Why this file exists. The formal gate used to resolve `sby` through a
# glob over several oss-cad-suite checkouts, taking whichever the
# wildcard listed first. On the development machine that silently
# selected a *different project's* toolchain, so a run of the 37-task
# formal gate was executed by tools nothing in this repository pinned.
# Three yosys builds were reachable at once: 0.67+146 in a Downloads
# checkout, 0.67+94 in a sibling project's tools directory, and a third
# in ~/.local/bin that a bare `yosys` resolves to. The results were not
# wrong, but they were not reproducible either, and a report that cannot
# name the tool that produced it is evidence of nothing.
#
# The rule here: one checkout, named explicitly, overridable, and
# verified. Set OSS_CAD_SUITE to point somewhere else; run
# `make -f tools.mk toolcheck` to see what would actually be used.

# The pinned checkout. Override on the command line or in the
# environment to use a different one:
#   make OSS_CAD_SUITE=$HOME/oss-cad-suite ...
OSS_CAD_SUITE ?= $(HOME)/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite

# The version this repository's recorded results were produced with.
# `toolcheck` compares against it and warns on a mismatch rather than
# failing, so a newer toolchain is usable but never silent.
OSS_CAD_SUITE_YOSYS_PIN ?= 0.67+146

TOOL_BIN := $(OSS_CAD_SUITE)/bin

SBY       := $(TOOL_BIN)/sby
YOSYS     := $(TOOL_BIN)/yosys
IVERILOG  := $(TOOL_BIN)/iverilog
VVP       := $(TOOL_BIN)/vvp
VERILATOR := $(TOOL_BIN)/verilator

# Fall back to PATH only for tools the pinned checkout does not carry,
# and only when they are genuinely absent, so a missing checkout is an
# error with a name rather than a mysterious command-not-found later.
ifeq ($(wildcard $(SBY)),)
SBY := $(shell command -v sby 2>/dev/null)
endif
ifeq ($(wildcard $(YOSYS)),)
YOSYS := $(shell command -v yosys 2>/dev/null)
endif
ifeq ($(wildcard $(IVERILOG)),)
IVERILOG := $(shell command -v iverilog 2>/dev/null)
endif

.PHONY: toolcheck
toolcheck:
	@echo "OSS_CAD_SUITE = $(OSS_CAD_SUITE)"
	@test -d "$(OSS_CAD_SUITE)" || { \
	  echo "ERROR: pinned checkout not found. Set OSS_CAD_SUITE to a real path."; \
	  exit 1; }
	@echo "sby       = $(SBY)"
	@echo "yosys     = $(YOSYS)"
	@echo "iverilog  = $(IVERILOG)"
	@v=$$("$(YOSYS)" -V 2>/dev/null | sed -n 's/^Yosys \([^ ]*\).*/\1/p'); \
	 echo "yosys version = $$v (pinned $(OSS_CAD_SUITE_YOSYS_PIN))"; \
	 if [ "$$v" != "$(OSS_CAD_SUITE_YOSYS_PIN)" ]; then \
	   echo "WARNING: yosys differs from the version the recorded results were produced with."; \
	   echo "         Re-derive any number you are about to quote, or set OSS_CAD_SUITE to the pinned checkout."; \
	 fi
