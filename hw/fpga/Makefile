# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# ECP5 / ULX3S fit-and-timing check for tt_um_melihakbulut_nssoc.
#
# This is a portability and timing probe, not a product flow. It answers
# one question: does the RTL that goes to the ASIC also synthesize, place,
# route and pack on an open-source FPGA toolchain, and at what Fmax. See
# README.md for what that does and does not prove.
#
# Usage
#   make                    synth + pnr + bitstream for the default part
#   make DEVICE=45k         same for a 45F
#   make FREQ=50            require 50 MHz instead of the default 25
#   make fit                pnr on 85F, 45F and 12F, print a summary table
#   make report             print resources and Fmax from the last run
#   make clean              remove build/
#
# Rootless tool discovery
#   Same shape as hw/tb/Makefile: look on PATH first, and if the tool is
#   not there, re-invoke make once with a discovered toolchain directory
#   prepended. Nothing is installed and nothing outside build/ is written.
#   Override with OSS_CAD_BIN=/path/to/oss-cad-suite/bin if the glob below
#   does not find your checkout.

# Both tool recipes pipe into tee so the log is kept and still streams.
# Without pipefail the recipe would take tee's exit status, and a nextpnr
# timing failure would be reported as success -- nextpnr writes the
# textcfg before it runs the final timing check, so the `test -f` guard
# below does not catch it either. DELETE_ON_ERROR then removes the
# half-valid output so the next make actually re-runs.
SHELL      := /bin/bash
.SHELLFLAGS := -o pipefail -c
.DELETE_ON_ERROR:

MKFILE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RTL        := $(MKFILE_DIR)/../rtl
BUILD      := $(MKFILE_DIR)/build

# First oss-cad-suite bin directory found under $HOME/Downloads or $HOME.
# Wildcard, not a hardcoded version, so a toolchain update does not need an
# edit here.
OSS_CAD_BIN ?= $(firstword $(wildcard \
	$(HOME)/Downloads/oss-cad-suite*/oss-cad-suite/bin \
	$(HOME)/oss-cad-suite/bin \
	$(HOME)/.local/oss-cad-suite/bin))

# All three tools have to come from the same place. Checking only yosys is
# not enough: a distribution yosys can sit on PATH with no nextpnr-ecp5
# next to it, and the run then dies halfway through with the ASIC-side
# yosys having already produced a netlist.
TOOLS_ON_PATH := $(and \
	$(shell command -v yosys 2>/dev/null), \
	$(shell command -v nextpnr-ecp5 2>/dev/null), \
	$(shell command -v ecppack 2>/dev/null))

ifeq ($(TOOLS_ON_PATH),)

ifeq ($(OSS_CAD_BIN),)
$(error yosys, nextpnr-ecp5 and ecppack are not all on PATH and no oss-cad-suite was found; set OSS_CAD_BIN=/path/to/oss-cad-suite/bin)
endif

GOALS := $(if $(MAKECMDGOALS),$(MAKECMDGOALS),all)
.PHONY: $(GOALS)
$(GOALS):
	@PATH="$(OSS_CAD_BIN):$$PATH" $(MAKE) -f $(lastword $(MAKEFILE_LIST)) --no-print-directory $@

else

# ------------------------------------------------------------------ part
# ULX3S ships LFE5U-85F-6BG381C; 45F and 12F variants exist in the same
# package and the same LPF fits all three. Speed grade 6 is what is on the
# board, so it is the default here. -8 parts exist but not on this board.
DEVICE  ?= 85k
PACKAGE ?= CABGA381
SPEED   ?= 6

# Clock target in MHz. 25 is the conservative ROADMAP point and the ULX3S
# oscillator frequency; 50 is the ROADMAP system-clock target. The LPF
# carries no FREQUENCY line on purpose so this can be swept without an
# edit.
FREQ ?= 25
SEED ?= 0

# nextpnr returns non-zero when the frequency target is missed. That is
# the useful default for `make`. Set ALLOW_FAIL=1 to route anyway and read
# the achieved number off a failing run.
ALLOW_FAIL ?= 0
ifeq ($(ALLOW_FAIL),1)
PNR_FAIL_ARG := --timing-allow-fail
endif

TOP := tt_um_melihakbulut_nssoc

# Exactly the file set the ASIC top pulls in. npu_regs.vh is reached
# through -I $(RTL); scrub.v and npu_regbank.v are not on this list
# because pilot_top.v does not instantiate them.
SOURCES := \
	$(RTL)/tt_um_melihakbulut_nssoc.v \
	$(RTL)/pilot_top.v \
	$(RTL)/lif_core.v \
	$(RTL)/aer_fifo.v \
	$(RTL)/tmr_voter.v \
	$(RTL)/secded_enc.v \
	$(RTL)/secded_dec.v

INC := $(RTL)/npu_regs.vh

# Every knob that changes the routed result is in the file name, so
# `make FREQ=50` after `make FREQ=25` actually re-runs instead of finding
# an up-to-date target from the previous constraint.
STEM    := $(DEVICE)_speed$(SPEED)_$(FREQ)MHz_seed$(SEED)

JSON    := $(BUILD)/$(TOP).json
CONFIG  := $(BUILD)/$(TOP)_$(STEM).config
BIT     := $(BUILD)/$(TOP)_$(STEM).bit
SYNLOG  := $(BUILD)/yosys_$(TOP).log
PNRLOG  := $(BUILD)/nextpnr_$(STEM).log

.PHONY: all synth pnr bit fit report clean
all: bit

$(BUILD):
	@mkdir -p $(BUILD)

# --------------------------------------------------------------- synth
# read_verilog is deliberately left in its default Verilog-2005 mode. The
# sources need no -sv: adding it changes nothing in the result (checked,
# identical cell counts), so leaving it off keeps the flag honest about
# what the RTL actually is. FORMAL is left undefined so the
# formal/*_props.v includes stay out.
synth: $(JSON)
$(JSON): $(SOURCES) $(INC) | $(BUILD)
	yosys -p "read_verilog -I $(RTL) $(SOURCES); \
	          synth_ecp5 -top $(TOP) -json $(JSON)" 2>&1 | tee $(SYNLOG)
	@test -f $(JSON)

# ----------------------------------------------------------------- pnr
pnr: $(CONFIG)
$(CONFIG): $(JSON) $(MKFILE_DIR)/ulx3s.lpf
	nextpnr-ecp5 \
	  --$(DEVICE) --package $(PACKAGE) --speed $(SPEED) \
	  --seed $(SEED) --freq $(FREQ) $(PNR_FAIL_ARG) \
	  --json $(JSON) \
	  --lpf $(MKFILE_DIR)/ulx3s.lpf \
	  --textcfg $(CONFIG) 2>&1 | tee $(PNRLOG)
	@test -f $(CONFIG)

# ----------------------------------------------------------- bitstream
# Packing is not needed for a fit check, but it is the last step that can
# still fail, so running it makes the "the flow completes" claim complete.
bit: $(BIT)
$(BIT): $(CONFIG)
	ecppack --compress $(CONFIG) $(BIT)

# ----------------------------------------------------------------- fit
# Route the same netlist on all three ULX3S device options and print the
# achieved Fmax for each. ALLOW_FAIL=1 so a missed target still reports.
fit: $(JSON)
	@for d in 85k 45k 12k; do \
	  $(MAKE) -f $(lastword $(MAKEFILE_LIST)) --no-print-directory \
	    DEVICE=$$d FREQ=$(FREQ) ALLOW_FAIL=1 pnr >/dev/null 2>&1; \
	  printf '%-5s %s\n' "$$d" \
	    "$$(grep -h 'Max frequency' $(BUILD)/nextpnr_$${d}_speed$(SPEED)_$(FREQ)MHz_seed$(SEED).log | tail -1 | sed 's/^Info: //;s/^Warning: //')"; \
	done

# -------------------------------------------------------------- report
report:
	@echo "--- yosys cell counts (post synth_ecp5) ---"
	@awk '/^=== $(TOP) ===$$/{buf=""; grab=1; next} \
	      /^=== design hierarchy ===$$/{grab=0} \
	      grab{buf=buf $$0 "\n"} END{printf "%s", buf}' $(SYNLOG) \
	  | grep -E 'CCU2C|LUT4|PFUMX|L6MUX21|TRELLIS_FF|DP16KD|MULT18X18|cells' || true
	@echo "--- nextpnr device utilisation ---"
	@grep -hE 'TRELLIS_IO:|DCCA:|DP16KD:|MULT18X18D:|TRELLIS_FF:|TRELLIS_COMB:' \
	  $(PNRLOG) | sed 's/^Info: //' || true
	@echo "--- timing ---"
	@grep -h 'Max frequency' $(PNRLOG) | tail -1 | sed 's/^Info: //;s/^Warning: //' || true

clean:
	rm -rf $(BUILD)

endif
