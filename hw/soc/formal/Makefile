# SymbiYosys jobs for the SoC fabric blocks.
#
#   cd hw/soc/formal && make            every task of every job
#   cd hw/soc/formal && make bus        soc_bus: bmc, prove, cover
#   cd hw/soc/formal && make apb        soc_apb_bridge: bmc, prove, cover
#   cd hw/soc/formal && make clean
#
# sby is resolved through the repository's tools.mk, not off PATH. That
# file exists because a formal gate once resolved `sby` through a glob and
# silently ran a sibling project's toolchain; its rule is one checkout,
# named explicitly, overridable, verified. hw/soc/tools.soc.mk includes it
# and adds the SoC-specific tools, and `make -f hw/soc/tools.soc.mk
# soc-toolcheck` prints what would actually be used.
#
# These jobs are deliberately NOT added to the pilot's formal/ directory.
# docs/34-pilot-freeze.md pins the pilot for the TTIHP26b shuttle and
# nothing under formal/ is touched by this work.

REPO := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../../..)

# Stated before the include, and stated again with .DEFAULT_GOAL, because
# tools.mk carries its own first target: a bare `make` here would
# otherwise run the repository tool check and report success without
# having run a single proof.
.PHONY: all bus apb clean
.DEFAULT_GOAL := all
all: bus apb

include $(REPO)/tools.mk

TASKS := bmc prove cover

bus:
	@for t in $(TASKS); do \
	  echo "== soc_bus $$t"; \
	  $(SBY) -f soc_bus.sby $$t || exit 1; \
	done

apb:
	@for t in $(TASKS); do \
	  echo "== soc_apb_bridge $$t"; \
	  $(SBY) -f soc_apb_bridge.sby $$t || exit 1; \
	done

clean:
	rm -rf soc_bus soc_bus_bmc soc_bus_prove soc_bus_cover \
	       soc_apb_bridge soc_apb_bridge_bmc soc_apb_bridge_prove \
	       soc_apb_bridge_cover
