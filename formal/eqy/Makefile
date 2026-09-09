# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
#
# Equivalence checking: does the mapped netlist compute what the RTL says?
#
#   make -C formal/eqy              three modules and both negative controls
#   make -C formal/eqy voter        one of them
#   make -C formal/eqy controls     only the controls
#
# WHY THIS DIRECTORY EXISTS
#
# Until 2026-09-09 this repository had no equivalence check of any kind.
# The argument ran: the RTL is proved by SymbiYosys, the netlist is
# censused by sw/tests, therefore the netlist implements the proved RTL.
# The middle link does not follow. A census counts flip-flops and walks
# cones; it never establishes that the netlist computes the RTL's
# function. A synthesis fault that preserved three banks of 55 flip-flops
# and MISCOMPUTED THE VOTER would pass every guard in this repository --
# and the voter is the one module a flip-flop census structurally cannot
# check, because it has no storage at all.
#
# So the three modules are chosen for that reason rather than for
# convenience: tmr_voter is what the census cannot see, and the two
# SECDED codecs are what every protected register in the design depends
# on being right.
#
# THE GATE SIDE IS EXTRACTED FROM THE SIGN-OFF RUN, not synthesised
# fresh. A fresh synthesis would show the recipe is equivalence-
# preserving today; extracting from the run shows it of the artefact
# `docs/34` freezes, which is the question worth asking.
#
# `bind *` IS NOT DECORATION. eqy partitions at module outputs and feeds
# each partition's cut points as INDEPENDENT free inputs. For secded_dec
# that manufactures an unreachable state -- a syndrome no code word
# produces -- and reports a counterexample on a correct netlist. Binding
# the cut points to the gold design's own nets removes the freedom
# without weakening the proof. It cost one false FAIL to learn, and the
# general statement is worth carrying: partitioned equivalence checking
# is sound for proofs and INCOMPLETE FOR REFUTATIONS.
#
# THE NEGATIVE CONTROLS ARE PART OF THE DEFAULT TARGET, because a
# checker that has never been seen to fail is not a checker. A control
# that passes is an error here, not a curiosity.

SHELL := /bin/bash
ROOT := $(abspath ../..)
RUN ?= $(ROOT)/hw/openlane/pilot_ihp/runs/signoff-6x2

include $(ROOT)/tools.mk

# tools.mk defines its own first target, so say which one is ours.
.DEFAULT_GOAL := all

# The PDK the run itself recorded, read from the run rather than assumed
# -- hw/tb/Makefile.gl does the same thing for the same reason.
EQY_PDK_ROOT ?= $(shell python3 -c "import json; \
	print(json.load(open('$(RUN)/resolved.json'))['PDK_ROOT'])" 2>/dev/null)
EQY_PDK ?= ihp-sg13g2
EQY_SCL ?= sg13g2_stdcell
LIB ?= $(EQY_PDK_ROOT)/$(EQY_PDK)/libs.ref/$(EQY_SCL)/lib/$(EQY_SCL)_typ_1p20V_25C.lib

# The hierarchical netlist, before the flow flattens it. A module body is
# only extractable while the hierarchy is still there.
HIER := $(RUN)/06-yosys-synthesis/tt_um_melihakbulut_nssoc.nl.v.hierarchy.nl.v

OUT := out
.PHONY: all voter enc dec controls clean tools
all: voter enc dec controls

tools:
	@test -x "$(EQY)" || { echo "eqy not found at '$(EQY)'"; exit 1; }
	@test -r "$(LIB)" || { echo "liberty not readable at '$(LIB)'"; exit 1; }
	@test -r "$(HIER)" || { echo "hierarchical netlist missing: $(HIER)"; \
		echo "(runs/ is gitignored build output; re-harden or point RUN at one)"; exit 1; }

voter: $(OUT)/tmr_voter.pass
enc:   $(OUT)/secded_enc.pass
dec:   $(OUT)/secded_dec.pass
controls: $(OUT)/voter_mutant.failed $(OUT)/secded_dec_mutant.failed

$(OUT):
	@mkdir -p $(OUT)

# A parameterised module is not in the netlist under its own name:
# tmr_voter is instantiated with WIDTH = 55 and appears as
# `$paramod\tmr_voter\WIDTH=s32'...110111`. Hard-coding that string
# would break the moment the width changes, so it is derived from the
# netlist and renamed back, which also keeps the two sides of the miter
# under one name.
$(OUT)/gate_%.v: tools | $(OUT)
	@echo "== extract $* from the sign-off netlist"
	@mod=$$(grep -o "module [^ (]*$*[^ (]*" $(HIER) | sed 's/^module //' \
		| sort -u | head -1); \
	 test -n "$$mod" || { echo "no module matching '$*' in $(HIER)"; exit 1; }; \
	 echo "   module: $$mod"; \
	 { echo "read_liberty -lib $(LIB)"; \
	   echo "read_verilog $(HIER)"; \
	   echo "hierarchy -top $$mod"; \
	   [ "$$mod" = "$*" ] || echo "rename $$mod $*"; \
	   echo "write_verilog $@"; } > $(OUT)/ex_$*.ys
	@$(YOSYS) -q -s $(OUT)/ex_$*.ys

define WRITE_EQY
@{ echo '[gold]'; \
   echo 'read_verilog $(2)'; \
   $(if $(3),echo '$(3)';) \
   echo 'prep -top $(1)'; \
   echo; echo '[gate]'; \
   echo 'read_liberty -ignore_miss_func $(LIB)'; \
   echo 'read_verilog $(CURDIR)/$(OUT)/gate_$(1).v'; \
   echo 'prep -top $(1)'; \
   echo; echo '[collect *]'; echo 'bind *'; \
   echo; echo '[strategy sat]'; echo 'use sat'; echo 'depth 5'; } > $@
endef

$(OUT)/tmr_voter.eqy: $(OUT)/gate_tmr_voter.v
	$(call WRITE_EQY,tmr_voter,$(ROOT)/hw/rtl/tmr_voter.v,chparam -set WIDTH 55 tmr_voter)
$(OUT)/secded_enc.eqy: $(OUT)/gate_secded_enc.v
	$(call WRITE_EQY,secded_enc,$(ROOT)/hw/rtl/secded_enc.v,)
$(OUT)/secded_dec.eqy: $(OUT)/gate_secded_dec.v
	$(call WRITE_EQY,secded_dec,$(ROOT)/hw/rtl/secded_dec.v,)

$(OUT)/mutant_tmr_voter.v: $(ROOT)/hw/rtl/tmr_voter.v $(ROOT)/formal/eqy/mutate.py | $(OUT)
	@python3 $(ROOT)/formal/eqy/mutate.py voter $@
$(OUT)/mutant_secded_dec.v: $(ROOT)/hw/rtl/secded_dec.v $(ROOT)/formal/eqy/mutate.py | $(OUT)
	@python3 $(ROOT)/formal/eqy/mutate.py dec $@

$(OUT)/voter_mutant.eqy: $(OUT)/gate_tmr_voter.v $(OUT)/mutant_tmr_voter.v
	$(call WRITE_EQY,tmr_voter,$(CURDIR)/$(OUT)/mutant_tmr_voter.v,chparam -set WIDTH 55 tmr_voter)
	@sed -i 's|gate_tmr_voter|gate_tmr_voter|' $@
$(OUT)/secded_dec_mutant.eqy: $(OUT)/gate_secded_dec.v $(OUT)/mutant_secded_dec.v
	$(call WRITE_EQY,secded_dec,$(CURDIR)/$(OUT)/mutant_secded_dec.v,)

# The mutant jobs name gate_<module>.v, which WRITE_EQY derives from the
# top module name; both controls reuse the honest gate side on purpose,
# because the point is that the RTL and the netlist disagree.
$(OUT)/voter_mutant.pass $(OUT)/secded_dec_mutant.pass:
	@echo "controls do not have a .pass target"; exit 1

$(OUT)/%.pass: $(OUT)/%.eqy
	@echo "== eqy $*"
	@rm -rf $(OUT)/wd_$*
	@cd $(OUT) && $(EQY) -f -d wd_$* $*.eqy > $*.log 2>&1 || true
	@grep -q 'DONE (PASS' $(OUT)/$*.log || { echo "FAILED: $*"; tail -20 $(OUT)/$*.log; exit 1; }
	@printf '  %s partition(s) proved\n' \
		"$$(grep -c 'Successfully proved equivalence of partition' $(OUT)/$*.log)"
	@touch $@

$(OUT)/%.failed: $(OUT)/%.eqy
	@echo "== eqy $* (negative control: must NOT pass)"
	@rm -rf $(OUT)/wd_$*
	@cd $(OUT) && $(EQY) -f -d wd_$* $*.eqy > $*.log 2>&1 || true
	@if grep -q 'DONE (PASS' $(OUT)/$*.log; then \
		echo "CONTROL PASSED: the check cannot fail, so it is not a check"; exit 1; fi
	@echo "  control fails as required"
	@touch $@

clean:
	rm -rf $(OUT)
