# Formal targets for the NPU register bank (docs/09 section B.1 target #6).
#
# Standalone:      make -f formal/npu_regbank.mk regbank_all
# Or, once the integrator wires it in, `include npu_regbank.mk` from
# formal/Makefile: every target and variable here is prefixed, the sby
# discovery is skipped when the including makefile already set SBY, and the
# default goal is only claimed when nothing else has claimed it.

# Rootless tool discovery, same house convention as formal/Makefile:
# prefer sby on PATH, then the known oss-cad-suite checkouts.
ifeq ($(origin SBY),undefined)
# Standalone invocation (`make -f <this>.mk ...`) used to rediscover sby
# with a PATH probe and a glob over several oss-cad-suite checkouts. On
# this machine that silently selected a sibling project's toolchain --
# the exact incident tools.mk was written to end, still reachable
# through a documented command. The pin is the single source now; see
# tools.mk, and `make -f tools.mk toolcheck` for what it resolves to.
include $(dir $(lastword $(MAKEFILE_LIST)))../tools.mk
endif

REGBANK_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

ifeq ($(.DEFAULT_GOAL),)
.DEFAULT_GOAL := regbank_all
endif

.PHONY: regbank_all regbank_prove regbank_prove_cnt2 regbank_prove_n256 \
        regbank_bmc regbank_cover regbank_clean

# The proof gate: k-induction at silicon parameters, the same properties at
# 2-bit counters and on a core smaller than the regmap default, the bounded
# backstop, and the reachability covers.
regbank_all: regbank_prove regbank_prove_cnt2 regbank_prove_n256 \
             regbank_bmc regbank_cover

regbank_prove:
	cd $(REGBANK_DIR) && $(SBY) -f npu_regbank.sby prove

regbank_prove_cnt2:
	cd $(REGBANK_DIR) && $(SBY) -f npu_regbank.sby prove_cnt2

# A 256-neuron build: the case that pins the CFG_NEUR / CFG_AXON reset
# values to the N_NEURONS / N_AXONS parameters rather than to the
# regmap.yaml 512 literal (RTL header C8).
regbank_prove_n256:
	cd $(REGBANK_DIR) && $(SBY) -f npu_regbank.sby prove_n256

regbank_bmc:
	cd $(REGBANK_DIR) && $(SBY) -f npu_regbank.sby bmc

regbank_cover:
	cd $(REGBANK_DIR) && $(SBY) -f npu_regbank.sby cover

regbank_clean:
	rm -rf $(REGBANK_DIR)/npu_regbank_prove \
	       $(REGBANK_DIR)/npu_regbank_prove_cnt2 \
	       $(REGBANK_DIR)/npu_regbank_prove_n256 \
	       $(REGBANK_DIR)/npu_regbank_bmc \
	       $(REGBANK_DIR)/npu_regbank_cover \
	       $(REGBANK_DIR)/npu_regbank
