# Formal targets for the lif_core memory hardening: the SECDED (26,20)
# neuron-state codec, and both coded files in place inside the datapath
# that reads and writes them.
#
# Standalone:      make -C formal -f lif_mem.mk lif_mem_all
# As a fragment:   include lif_mem.mk   (from formal/Makefile), then add
#                  lif_mem_all to the `everything` goal and lif_mem_clean
#                  to `clean-all`. Every target name here is prefixed and
#                  phony, so the fragment cannot collide with the aer_fifo
#                  targets (all, prove, bmc, cover, prove_d4, clean), with
#                  npu_regbank.mk, ecc.mk, lif_ctrl.mk or scrub.mk, and
#                  the sby working directories are all named lif_mem_*.
#
# WIRED INTO formal/Makefile on 2026-08-26: that file includes this
# fragment, carries lif_mem_all in `everything` and lif_mem_clean in
# `clean-all`. These eight tasks are part of the project's formal gate
# and run with `make -C formal everything`, not an opt-in beside it.
#
# This job exists because the docs/16 fault-injection campaign ranked the
# three unprotected memory files as the entire residual silent-corruption
# risk of the pilot -- wmem 56.2% SDC over 256 flip-flops, vmem 91.7%
# over 128, rmem 100.0% over 32 -- and the hardening that answers that
# ranking is a pair of error-correcting codes. A code that miscorrects is
# worse than no code: it turns a wrong answer the design used to produce
# visibly into a wrong answer the design certifies as right. Both codes
# are small enough to prove outright, so both are proven outright, and
# the lif_core-level tasks then prove the datapath actually uses them --
# a correct codec wired to the wrong codeword is still a broken design,
# and no codec-level proof can see that.
#
# The split between the two property files, and the reason the read tasks
# assume an injected error rather than deriving one, are documented at
# the top of formal/lif_mem.sby and formal/lif_mem_props.v.

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

LIF_MEM_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

ifeq ($(.DEFAULT_GOAL),)
.DEFAULT_GOAL := lif_mem_all
endif

.PHONY: lif_mem_all lif_mem_codec lif_mem_codec_abc lif_mem_codec_cover \
        lif_mem_read lif_mem_read_3x2 lif_mem_read_cover lif_mem_inv \
        lif_mem_inv_cover lif_mem_clean

# The proof gate for this block: the (26,20) codec on two engine
# families, the read-path fault model at a clean and at an awkward
# geometry, the write-consistency invariant by k-induction, and three
# cover tasks (docs/09 section B.1 vacuity rule -- passing asserts with
# failing covers are red). The cover tasks are load-bearing here in a
# specific way: the read properties are implications on the weight of a
# symbolic error vector, so an assumption that made a weight
# unsatisfiable would leave every assertion about it trivially true.
lif_mem_all: lif_mem_codec lif_mem_codec_abc lif_mem_codec_cover \
             lif_mem_read lif_mem_read_3x2 lif_mem_read_cover \
             lif_mem_inv lif_mem_inv_cover

lif_mem_codec:
	cd $(LIF_MEM_DIR) && $(SBY) -f lif_mem.sby codec

lif_mem_codec_abc:
	cd $(LIF_MEM_DIR) && $(SBY) -f lif_mem.sby codec_abc

lif_mem_codec_cover:
	cd $(LIF_MEM_DIR) && $(SBY) -f lif_mem.sby codec_cover

lif_mem_read:
	cd $(LIF_MEM_DIR) && $(SBY) -f lif_mem.sby read

lif_mem_read_3x2:
	cd $(LIF_MEM_DIR) && $(SBY) -f lif_mem.sby read_3x2

lif_mem_read_cover:
	cd $(LIF_MEM_DIR) && $(SBY) -f lif_mem.sby read_cover

lif_mem_inv:
	cd $(LIF_MEM_DIR) && $(SBY) -f lif_mem.sby inv

lif_mem_inv_cover:
	cd $(LIF_MEM_DIR) && $(SBY) -f lif_mem.sby inv_cover

lif_mem_clean:
	rm -rf $(LIF_MEM_DIR)/lif_mem_codec $(LIF_MEM_DIR)/lif_mem_codec_abc \
	       $(LIF_MEM_DIR)/lif_mem_codec_cover $(LIF_MEM_DIR)/lif_mem_read \
	       $(LIF_MEM_DIR)/lif_mem_read_3x2 $(LIF_MEM_DIR)/lif_mem_read_cover \
	       $(LIF_MEM_DIR)/lif_mem_inv $(LIF_MEM_DIR)/lif_mem_inv_cover \
	       $(LIF_MEM_DIR)/lif_mem
