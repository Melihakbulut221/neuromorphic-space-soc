# Formal verification targets (SymbiYosys + smtbmc/yices).
#
# Rootless tool discovery, house convention: prefer sby on PATH, then the
# known oss-cad-suite checkouts (sby brings its own yosys and solvers).
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

HERE := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

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
include $(HERE)/scrub.mk

# The full formal gate across every block.
everything: all regbank_all ecc lif_all scrub_all

clean-all: clean regbank_clean ecc_clean lif_clean scrub_clean
