# Formal targets for the fault-tolerance primitives: the SECDED (72, 64)
# weight-SRAM codec and the TMR voter.
#
# Usage, standalone:      make -C formal -f ecc.mk ecc
# Usage, as a fragment:   include ecc.mk   (from formal/Makefile)
#
# Every target name is prefixed and phony, so the fragment cannot collide
# with the aer_fifo targets (all, prove, bmc, cover, prove_d4, clean) or
# with the sby working directories of the same name.
#
# What this fragment does and does not close, against
# docs/09-formal-verification-plan.md:
#
#   target #2, SECDED codec .............. closed by ecc_secded
#   target #4, "TMR voters + resync path"  PARTLY closed by ecc_tmr
#
# Target #4 has three clauses. The two voter clauses - output is always
# majority(a,b,c), and no single corrupted replica can change the output -
# are proven exhaustively here at WIDTH 1, 8 and 32, with the default width
# additionally re-proven on a second engine family (tmr_bmc_abc).
# The third clause, "after fault removal, replicas re-converge within N
# cycles (L as bounded safety)", is proven NOWHERE and is not scheduled by
# this fragment. It has no subject yet: hw/rtl/tmr_voter.v contains no
# resynchronization path by design (restoring a faulty replica belongs to
# the protected block) and hw/rtl/pilot_top.v, the only current user of the
# voter, states that "no replica resynchronization is implemented".
# Closing it needs RTL first, then a bounded-response property under
# induction - a new formal/<block>.mk and property file, not a task added
# to this one. Until then, "ecc PASSes" means the voter theorem holds, not
# that target #4 is complete.

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

ECC_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

.PHONY: ecc ecc_secded ecc_tmr ecc_clean \
        secded_bmc secded_bmc_abc secded_cover \
        tmr_bmc tmr_bmc_abc tmr_bmc_w1 tmr_bmc_w32 tmr_prove \
        tmr_cover tmr_cover_w1 tmr_cover_w32

# The proof gate for this block: both property sets on two independent
# engine families at their default parameters, the voter re-proven at
# WIDTH 1 and 32, and the non-vacuity covers at every width. 11 sby tasks.
ecc: ecc_secded ecc_tmr

# SECDED. Both modules are combinational, so BMC at depth 1 is exhaustive
# over the whole symbolic input space (docs/09 target #2) - a full proof,
# not a bounded one. bmc and bmc_abc are the same property set on an SMT
# bit-blaster and on the AIGER/SAT path: two separate tasks, because sby
# races the engines listed inside one task and reports the first to answer.
ecc_secded: secded_bmc secded_bmc_abc secded_cover

secded_bmc:
	cd $(ECC_DIR) && $(SBY) -f secded.sby bmc

secded_bmc_abc:
	cd $(ECC_DIR) && $(SBY) -f secded.sby bmc_abc

secded_cover:
	cd $(ECC_DIR) && $(SBY) -f secded.sby cover

# TMR voter (the voter clauses of docs/09 target #4; the resync clause is
# out of scope, see the header). Exhaustive at each elaborated width; the
# k-induction flow is included here because the voter proof is instant.
# Each width also gets its own cover task: the cover set is
# width-conditional, so covering only at the default WIDTH = 8 would leave
# the WIDTH = 1 and WIDTH = 32 property sets with no reachability check at
# all, and would never exercise the generate arm the condition guards.
ecc_tmr: tmr_bmc tmr_bmc_abc tmr_bmc_w1 tmr_bmc_w32 tmr_prove \
         tmr_cover tmr_cover_w1 tmr_cover_w32

tmr_bmc:
	cd $(ECC_DIR) && $(SBY) -f tmr_voter.sby bmc

tmr_bmc_abc:
	cd $(ECC_DIR) && $(SBY) -f tmr_voter.sby bmc_abc

tmr_bmc_w1:
	cd $(ECC_DIR) && $(SBY) -f tmr_voter.sby bmc_w1

tmr_bmc_w32:
	cd $(ECC_DIR) && $(SBY) -f tmr_voter.sby bmc_w32

tmr_prove:
	cd $(ECC_DIR) && $(SBY) -f tmr_voter.sby prove

tmr_cover:
	cd $(ECC_DIR) && $(SBY) -f tmr_voter.sby cover

tmr_cover_w1:
	cd $(ECC_DIR) && $(SBY) -f tmr_voter.sby cover_w1

tmr_cover_w32:
	cd $(ECC_DIR) && $(SBY) -f tmr_voter.sby cover_w32

ecc_clean:
	rm -rf $(ECC_DIR)/secded_bmc $(ECC_DIR)/secded_bmc_abc \
	       $(ECC_DIR)/secded_cover $(ECC_DIR)/secded \
	       $(ECC_DIR)/tmr_voter_bmc $(ECC_DIR)/tmr_voter_bmc_abc \
	       $(ECC_DIR)/tmr_voter_bmc_w1 $(ECC_DIR)/tmr_voter_bmc_w32 \
	       $(ECC_DIR)/tmr_voter_prove $(ECC_DIR)/tmr_voter_cover \
	       $(ECC_DIR)/tmr_voter_cover_w1 $(ECC_DIR)/tmr_voter_cover_w32 \
	       $(ECC_DIR)/tmr_voter
