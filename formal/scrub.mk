# Formal targets for the weight-SRAM ECC scrub controller: window
# containment, writeback discipline, walk integrity, port handshake,
# deadlock freedom and any-state SEU recovery.
#
# Standalone:      make -C formal -f scrub.mk scrub_all
# As a fragment:   include scrub.mk   (from formal/Makefile), then add
#                  scrub_all to the `everything` goal and scrub_clean to
#                  `clean-all`. Every target name here is prefixed and
#                  phony, so the fragment cannot collide with the aer_fifo
#                  targets (all, prove, bmc, cover, prove_d4, clean), with
#                  npu_regbank.mk, ecc.mk or lif_ctrl.mk, and the sby
#                  working directories are all named scrub_*.
#
# NOT YET WIRED INTO formal/Makefile. That file is owned by the
# integrator and this track does not edit it; the change it needs is
# three lines and is spelled out above. Until it lands,
# `make -C formal everything` does NOT run these nine tasks and the
# docs/09 status column says so.
#
# This job exists because the scrub controller is the one block in the
# fault-tolerance set that is a MASTER on a memory port the rest of the
# chip depends on. Everything else in that set (the codec, the voter) can
# only fail by producing a wrong answer; this one can fail by writing to
# the wrong place, by rewriting a word the ECC could not correct, by
# skipping a word so upsets accumulate there unseen, or by driving the
# port at all after an upset in its own state register. Those four are
# SC1/SC6, SC4, SC11 and SC15 in formal/scrub_props.v.
#
# Mutation evidence for this gate (docs/09 B.1 vacuity rule, extended):
# seventeen mutants, each reintroducing one of those defects, were run
# against the whole task set. Every one is killed by at least one task.
# Three of them -- a default arm that recovers to S_IDLE, a S_SAFE that
# does not latch ERR_CFG, and a S_SAFE that keeps driving mem_req -- pass
# bmc and bmc_live (and the first two pass prove as well; the third only
# degrades prove to UNKNOWN), and are killed ONLY by the two any-state
# tasks scrub_bmc_any and scrub_prove_any. Those tasks are load-bearing,
# not decoration; see the methodology note at the top of
# formal/scrub_props.v.

# Tool discovery, house convention (prefer sby on PATH, then the known
# rootless oss-cad-suite checkouts). Skipped when the including makefile
# has already resolved SBY.
ifeq ($(origin SBY),undefined)
# Standalone invocation (`make -f <this>.mk ...`) used to rediscover sby
# with a PATH probe and a glob over several oss-cad-suite checkouts. On
# this machine that silently selected a sibling project's toolchain --
# the exact incident tools.mk was written to end, still reachable
# through a documented command. The pin is the single source now; see
# tools.mk, and `make -f tools.mk toolcheck` for what it resolves to.
include $(dir $(lastword $(MAKEFILE_LIST)))../tools.mk
endif

SCRUB_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

ifeq ($(.DEFAULT_GOAL),)
.DEFAULT_GOAL := scrub_all
endif

.PHONY: scrub_all scrub_prove scrub_prove_small scrub_prove_pdr scrub_bmc \
        scrub_bmc_any scrub_prove_any scrub_bmc_live scrub_cover \
        scrub_cover_any scrub_clean

# The proof gate for this block: the property set by k-induction at the
# silicon parameters and at the degenerate geometry, the same set on a
# second engine family, the bounded backstop, the any-state recovery pair,
# the bounded-response liveness task and both cover tasks (docs/09 section
# B.1 vacuity rule -- passing asserts with failing covers are red).
scrub_all: scrub_prove scrub_prove_small scrub_prove_pdr scrub_bmc \
           scrub_bmc_any scrub_prove_any scrub_bmc_live scrub_cover \
           scrub_cover_any

scrub_prove:
	cd $(SCRUB_DIR) && $(SBY) -f scrub.sby prove

scrub_prove_small:
	cd $(SCRUB_DIR) && $(SBY) -f scrub.sby prove_small

scrub_prove_pdr:
	cd $(SCRUB_DIR) && $(SBY) -f scrub.sby prove_pdr

scrub_bmc:
	cd $(SCRUB_DIR) && $(SBY) -f scrub.sby bmc

scrub_bmc_any:
	cd $(SCRUB_DIR) && $(SBY) -f scrub.sby bmc_any

scrub_prove_any:
	cd $(SCRUB_DIR) && $(SBY) -f scrub.sby prove_any

scrub_bmc_live:
	cd $(SCRUB_DIR) && $(SBY) -f scrub.sby bmc_live

scrub_cover:
	cd $(SCRUB_DIR) && $(SBY) -f scrub.sby cover

scrub_cover_any:
	cd $(SCRUB_DIR) && $(SBY) -f scrub.sby cover_any

scrub_clean:
	rm -rf $(SCRUB_DIR)/scrub_prove $(SCRUB_DIR)/scrub_prove_small \
	       $(SCRUB_DIR)/scrub_prove_pdr $(SCRUB_DIR)/scrub_bmc \
	       $(SCRUB_DIR)/scrub_bmc_any $(SCRUB_DIR)/scrub_prove_any \
	       $(SCRUB_DIR)/scrub_bmc_live \
	       $(SCRUB_DIR)/scrub_cover $(SCRUB_DIR)/scrub_cover_any \
	       $(SCRUB_DIR)/scrub
