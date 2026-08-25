# Formal targets for the lif_core control path: command arbitration, the
# input and output handshakes, scan integrity and the spec section 11.4
# SAFE state.
#
# Standalone:      make -C formal -f lif_ctrl.mk lif_all
# As a fragment:   include lif_ctrl.mk   (from formal/Makefile), then add
#                  lif_all to the `everything` goal and lif_clean to
#                  `clean-all`. Every target name here is prefixed and
#                  phony, so the fragment cannot collide with the
#                  aer_fifo targets (all, prove, bmc, cover, prove_d4,
#                  clean), with npu_regbank.mk or with ecc.mk, and the sby
#                  working directories are all named lif_ctrl_*.
#
# This job exists because the LIF datapath's golden-model lockstep does
# not constrain the control interface at all: five independent mutants of
# ev_ready, tick_ready, the state_clr priority and the held-spike
# interaction survived the entire lockstep suite. See the header of
# formal/lif_ctrl_props.v.

# Tool discovery, house convention (prefer sby on PATH, then the known
# rootless oss-cad-suite checkouts). Skipped when the including makefile
# has already resolved SBY.
ifeq ($(origin SBY),undefined)
SBY := $(shell command -v sby 2>/dev/null)
ifeq ($(SBY),)
SBY := $(firstword $(wildcard \
	$(HOME)/oss-cad-suite/bin/sby \
	$(HOME)/Documents/gt2n-soc/tools/oss-cad-suite/bin/sby \
	$(HOME)/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite/bin/sby))
endif
ifeq ($(SBY),)
$(error sby not found: install oss-cad-suite or put sby on PATH)
endif
endif

LIF_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

ifeq ($(.DEFAULT_GOAL),)
.DEFAULT_GOAL := lif_all
endif

.PHONY: lif_all lif_prove lif_prove_3x2 lif_prove_8x2 lif_bmc \
        lif_bmc_live lif_bmc_safe lif_cover lif_cover_safe lif_clean

# The proof gate for this block: the property set by k-induction at three
# geometries, the bounded backstop, the bounded-liveness watchdog, the
# SAFE-state response from an injected illegal encoding, and both cover
# tasks (docs/09 section B.1 vacuity rule -- passing asserts with failing
# covers are red). lif_bmc_safe is load-bearing, not decoration: the
# SAFE-state recovery is vacuous in lif_prove, for the reason recorded in
# the H8 note of lif_ctrl_props.v.
lif_all: lif_prove lif_prove_3x2 lif_prove_8x2 lif_bmc lif_bmc_live \
         lif_bmc_safe lif_cover lif_cover_safe

lif_prove:
	cd $(LIF_DIR) && $(SBY) -f lif_ctrl.sby prove

lif_prove_3x2:
	cd $(LIF_DIR) && $(SBY) -f lif_ctrl.sby prove_3x2

lif_prove_8x2:
	cd $(LIF_DIR) && $(SBY) -f lif_ctrl.sby prove_8x2

lif_bmc:
	cd $(LIF_DIR) && $(SBY) -f lif_ctrl.sby bmc

lif_bmc_live:
	cd $(LIF_DIR) && $(SBY) -f lif_ctrl.sby bmc_live

lif_bmc_safe:
	cd $(LIF_DIR) && $(SBY) -f lif_ctrl.sby bmc_safe

lif_cover:
	cd $(LIF_DIR) && $(SBY) -f lif_ctrl.sby cover

lif_cover_safe:
	cd $(LIF_DIR) && $(SBY) -f lif_ctrl.sby cover_safe

lif_clean:
	rm -rf $(LIF_DIR)/lif_ctrl_prove $(LIF_DIR)/lif_ctrl_prove_3x2 \
	       $(LIF_DIR)/lif_ctrl_prove_8x2 $(LIF_DIR)/lif_ctrl_bmc \
	       $(LIF_DIR)/lif_ctrl_bmc_live $(LIF_DIR)/lif_ctrl_bmc_safe \
	       $(LIF_DIR)/lif_ctrl_cover \
	       $(LIF_DIR)/lif_ctrl_cover_safe $(LIF_DIR)/lif_ctrl
