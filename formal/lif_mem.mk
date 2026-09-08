# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

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
# This fragment's own directory, captured BEFORE the tools.mk include
# below. `$(lastword $(MAKEFILE_LIST))` names the file make is currently
# reading, and an `include` permanently appends the included file to that
# list -- so computing the directory after the include yielded the
# REPOSITORY ROOT, and every standalone `make -C formal -f <block>.mk`
# then ran `cd <repo root> && sby -f <block>.sby`, which fails with
# "No such file or directory". That regression arrived with the toolchain
# pin and is fixed here rather than worked around at the call site; the
# fragment behaved correctly when included from formal/Makefile, because
# there SBY is already set and the include is skipped.
LIF_MEM_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

ifeq ($(origin SBY),undefined)
# Standalone invocation (`make -f <this>.mk ...`) used to rediscover sby
# with a PATH probe and a glob over several oss-cad-suite checkouts. On
# this machine that silently selected a sibling project's toolchain --
# the exact incident tools.mk was written to end, still reachable
# through a documented command. The pin is the single source now; see
# tools.mk, and `make -f tools.mk toolcheck` for what it resolves to.
include $(LIF_MEM_DIR)/../tools.mk
endif


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
