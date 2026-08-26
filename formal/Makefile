# Formal verification targets (SymbiYosys + smtbmc/yices).
#
# Tool resolution lives in one place for the whole repository. The glob
# that used to sit here silently selected a sibling project's toolchain;
# see tools.mk for the incident and the rule that replaced it.
HERE := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
include $(HERE)/../tools.mk

ifeq ($(SBY),)
$(error sby not found: set OSS_CAD_SUITE to an oss-cad-suite checkout, or put sby on PATH)
endif

.PHONY: all everything prove bmc cover prove_d4 clean clean-all

# The aer_fifo proof gate: full k-induction at default parameters, plus
# the fast parameterization check and the reachability covers. `all` is
# kept aer_fifo-only so existing invocations keep their meaning; use
# `everything` for the whole formal suite.
all: prove prove_d4 bmc cover

prove bmc cover prove_d4:
	cd $(HERE) && $(SBY) -f aer_fifo.sby $@

clean:
	rm -rf $(HERE)/aer_fifo_prove $(HERE)/aer_fifo_prove_d4 \
	       $(HERE)/aer_fifo_bmc $(HERE)/aer_fifo_cover \
	       $(HERE)/aer_fifo

# Per-block fragments. Each defines prefixed targets and skips its own
# tool discovery because SBY is already resolved above.
include $(HERE)/npu_regbank.mk
include $(HERE)/ecc.mk
include $(HERE)/lif_ctrl.mk
include $(HERE)/lif_mem.mk
include $(HERE)/scrub.mk

# The full formal gate across every block.
everything: all regbank_all ecc lif_all lif_mem_all scrub_all

clean-all: clean regbank_clean ecc_clean lif_clean lif_mem_clean \
           scrub_clean
