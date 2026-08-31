# Formal targets for the pilot's configuration TMR domain: three
# pilot_cfg_bank replicas under one tmr_voter, the composition
# hw/rtl/pilot_top.v builds around its u_cfg_vote instance.
#
# Standalone:      make -C formal -f tmr_voter_cfg.mk tmr_cfg_all
# As a fragment:   include tmr_voter_cfg.mk   (from formal/Makefile), then add
#                  tmr_cfg_all to the `everything` goal and tmr_cfg_clean
#                  to `clean-all`. Every target name here is prefixed and
#                  phony, so the fragment cannot collide with the
#                  aer_fifo targets (all, prove, bmc, cover, prove_d4,
#                  resync, resync_cover, clean), with npu_regbank.mk,
#                  ecc.mk, lif_ctrl.mk, lif_mem.mk or scrub.mk, and the
#                  sby working directories are all named tmr_voter_cfg_*.
#
# A note on that name, because it was chosen rather than inherited. The
# job is the TMR voter in the one protected block the pilot has, so
# tmr_voter_cfg is what it is; it also means the sby working directories
# land under the `formal/tmr_voter*/` rule the repository's .gitignore
# already carries, so a new block adds no untracked output and this
# track does not have to edit a file it does not own. Both reasons are
# stated here so the next person does not have to guess which one it was.
#
# WHAT THIS FRAGMENT CLOSES, against docs/09-formal-verification-plan.md:
#
#   target #6, "TMR'd CSRs vote correctly (reuse #4)" ... closed here
#   target #4a, "the masking theorem ... is reported per protected
#       block" .................................. its one instance is here
#
# and what it does NOT close, so that "tmr_cfg_all PASSes" cannot be read as
# more than it is:
#
#   target #4b, replica resynchronization. This domain has none. The
#       banks hold their own state and are restored by a host rewrite,
#       which is what hw/rtl/pilot_top.v says. The one resync path in the
#       design is the queue pointer domain of hw/rtl/aer_fifo.v, and
#       formal/aer_fifo.sby's `resync` task is its proof.
#   the anti-merge argument. POL and MIX exist so that yosys opt_merge
#       cannot collapse the three banks into one, and that is a property
#       of the MAPPED NETLIST, not of the RTL semantics. A mutant that
#       gives replica C MIX = 0 keeps every property in this job true and
#       destroys the defence; sw/tests/test_synthesis_guards.py counts
#       flip-flops in both flows and is what catches that one. The two
#       kinds of evidence do not substitute for each other and neither is
#       dropped.
#   the register decode that drives cfg_wr_en / cfg_wr_d, the T_* field
#       packing, and the CFG_RST_VAL assembly. Those are target #6 proper
#       (formal/npu_regbank.sby) and the elaboration guards.
#
# Mutation evidence for this gate (docs/09 B.1 vacuity rule, extended),
# all measured on the pinned toolchain [fact, 2026-08-31]. Five mutants,
# each reintroducing a defect this job exists to catch:
#
#   C1  cfg_dec's layer-2 rotation off by one ((i+1) % LO -> i % LO)
#   C2  the MIX bank applies POL inside the encode rather than outside
#       (cfg_enc(nxt ^ POL) instead of cfg_enc(nxt) ^ POL)
#   C3  tmr_voter loses the (in_b & in_c) majority term
#   C4  the polarity banks lose their per-bit write enable, so a partial
#       write overwrites the bits it was not meant to touch
#   C5  cfg_dec is wrong for exactly one stored word (an extra ^ (&c)),
#       a value-dependent divergence no directed test reaches
#
# Each of the five fails prove, prove_w8, bmc and prove_abc. None fails
# cover, which is the expected result and worth stating: the cover task
# checks that the proven behaviours are reachable, not that they are
# right, and a gate that reported otherwise would be measuring something
# else. C5 is the one that makes the case for a proof over a test: it is
# reachable only for a single 55-bit configuration word, so no directed
# stimulus finds it, while every assertion-carrying task here does.
#
# Tool discovery, house convention. Skipped when the including makefile
# has already resolved SBY.
# This fragment's own directory, captured BEFORE the tools.mk include
# below: an `include` permanently appends the included file to
# MAKEFILE_LIST, so computing the directory after it yields the
# repository root instead. See the same note in the other five fragments.
TMR_CFG_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

ifeq ($(origin SBY),undefined)
# Standalone invocation (`make -f <this>.mk ...`) resolves the toolchain
# through the same pin as the aggregate gate; see tools.mk for the
# incident that rule exists to end, and `make -f tools.mk toolcheck` for
# what it resolves to.
include $(TMR_CFG_DIR)/../tools.mk
endif

TMR_CFG_RTL := $(TMR_CFG_DIR)/../hw/rtl/pilot_top.v

ifeq ($(.DEFAULT_GOAL),)
.DEFAULT_GOAL := tmr_cfg_all
endif

.PHONY: tmr_cfg_all tmr_cfg_params tmr_cfg_prove tmr_cfg_prove_rst1 \
        tmr_cfg_prove_rstx tmr_cfg_prove_abc tmr_cfg_prove_w8 \
        tmr_cfg_bmc tmr_cfg_cover tmr_cfg_clean

# The proof gate for this block: the property set by k-induction at the
# silicon parameters, at two further reset images, at a narrow width, and
# on a second engine family; the bounded backstop; and the covers
# (docs/09 section B.1 vacuity rule -- passing asserts with failing
# covers are red). tmr_cfg_params runs first and is not decoration: this
# job rebuilds pilot_top's composition out of the same two RTL modules
# because that file has no `ifdef FORMAL hook and the pilot is frozen, so
# the width, the three polarity masks and which replica carries MIX = 1
# are COPIED. The guard reads them back out of the RTL and fails if any
# has moved, which is the only thing standing between this proof and a
# proof about a composition the chip no longer builds.
tmr_cfg_all: tmr_cfg_params tmr_cfg_prove tmr_cfg_prove_rst1 \
             tmr_cfg_prove_rstx tmr_cfg_prove_abc tmr_cfg_prove_w8 \
             tmr_cfg_bmc tmr_cfg_cover

tmr_cfg_params:
	@f='$(TMR_CFG_RTL)'; rc=0; \
	check() { \
	  grep -qF "$$2" "$$f" || { \
	    echo "tmr_cfg_params: $$1 not found in hw/rtl/pilot_top.v"; \
	    echo "                expected: $$2"; rc=1; }; }; \
	check "TMR_W"     "localparam integer TMR_W    = 55;"; \
	check "CFG_POL_A" "localparam [63:0] CFG_POL_A = 64'h0000000000000000;"; \
	check "CFG_POL_B" "localparam [63:0] CFG_POL_B = 64'h007FFFFFFFFFFFFF;"; \
	check "CFG_POL_C" "localparam [63:0] CFG_POL_C = 64'h002AAAAAAAAAAAAA;"; \
	check "MIX on C"  ".POL(CFG_POL_C),"; \
	check "MIX value" "                     .MIX(1))"; \
	check "bank A"    "#(.W(TMR_W), .RST_VAL(CFG_RST_VAL), .POL(CFG_POL_A))"; \
	check "bank B"    "#(.W(TMR_W), .RST_VAL(CFG_RST_VAL), .POL(CFG_POL_B))"; \
	if [ $$rc -ne 0 ]; then \
	  echo "tmr_cfg_params: the configuration TMR domain in the RTL no longer"; \
	  echo "                matches the parameters formal/tmr_voter_cfg_props.v is"; \
	  echo "                proven at. Update the harness and re-run, or the"; \
	  echo "                proof is about a composition the chip does not build."; \
	  exit 1; \
	fi; \
	echo "tmr_cfg_params: pilot_top.v parameters match the harness"

tmr_cfg_prove:
	cd $(TMR_CFG_DIR) && $(SBY) -f tmr_voter_cfg.sby prove

tmr_cfg_prove_rst1:
	cd $(TMR_CFG_DIR) && $(SBY) -f tmr_voter_cfg.sby prove_rst1

tmr_cfg_prove_rstx:
	cd $(TMR_CFG_DIR) && $(SBY) -f tmr_voter_cfg.sby prove_rstx

tmr_cfg_prove_abc:
	cd $(TMR_CFG_DIR) && $(SBY) -f tmr_voter_cfg.sby prove_abc

tmr_cfg_prove_w8:
	cd $(TMR_CFG_DIR) && $(SBY) -f tmr_voter_cfg.sby prove_w8

tmr_cfg_bmc:
	cd $(TMR_CFG_DIR) && $(SBY) -f tmr_voter_cfg.sby bmc

tmr_cfg_cover:
	cd $(TMR_CFG_DIR) && $(SBY) -f tmr_voter_cfg.sby cover

tmr_cfg_clean:
	rm -rf $(TMR_CFG_DIR)/tmr_voter_cfg_prove \
	       $(TMR_CFG_DIR)/tmr_voter_cfg_prove_rst1 \
	       $(TMR_CFG_DIR)/tmr_voter_cfg_prove_rstx \
	       $(TMR_CFG_DIR)/tmr_voter_cfg_prove_abc \
	       $(TMR_CFG_DIR)/tmr_voter_cfg_prove_w8 \
	       $(TMR_CFG_DIR)/tmr_voter_cfg_bmc \
	       $(TMR_CFG_DIR)/tmr_voter_cfg_cover \
	       $(TMR_CFG_DIR)/tmr_voter_cfg
