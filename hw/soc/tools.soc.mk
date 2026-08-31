# Toolchain resolution for the SoC (management subsystem) work.
#
# This extends the repository-wide `tools.mk`. The rule there -- one
# checkout, named explicitly, overridable, and verified -- applies here
# unchanged, and everything the pinned oss-cad-suite carries is taken
# from it.
#
# Three tools the SoC flow needs are NOT in the pinned oss-cad-suite, so
# they are pinned here by the same rule rather than resolved off PATH:
#
#   sv2v    SystemVerilog-to-Verilog-2005 converter. Not shipped by
#           oss-cad-suite (checked: `ls $(OSS_CAD_SUITE)/bin` at
#           2026-08-31 has no sv2v). Pinned to the upstream release
#           binary, by tag AND by sha256 of the release archive:
#             https://github.com/zachjs/sv2v/releases/tag/v0.0.13
#             sv2v-Linux.zip
#             sha256 552799a1d76cd177b9b4cc63a3e77823a3d2a6eb4ec006569
#                    288abeff28e1ff8
#           Unpacked under hw/soc/tools/sv2v-Linux/. Rootless, static.
#
#   riscv-none-elf-gcc
#           Bare-metal RV32 toolchain, for the program the simulation
#           runs. Not in oss-cad-suite. Pinned to the xPack release, by
#           tag AND by the sha256 the release publishes alongside it --
#           which was checked against the downloaded file rather than
#           merely copied from the page:
#             https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack
#               /releases/tag/v15.2.0-1
#             xpack-riscv-none-elf-gcc-15.2.0-1-linux-x64.tar.gz
#             sha256 aaaa8060c914851a3e5ee1ba82cc3d6f80972f90638a05c6e
#                    823a37557a33758
#           Unpacked under hw/soc/tools/rvgcc/. Rootless.
#
#   sta     OpenSTA. Not in oss-cad-suite either. Taken from the same
#           LibreLane tool tree the pilot's sign-off runs used, so the
#           CPU numbers and the pilot numbers come from one STA build:
#             $(LL_BIN)/sta
#           `docs/12` section on tool identity records that tree.
#
# Run `make -f tools.soc.mk toolcheck` to see what would actually be
# used, including versions.

# Resolve this file's own location, immediately and simply-expanded,
# BEFORE the include below appends to MAKEFILE_LIST. A deferred
# expansion here silently resolves against the caller's working
# directory instead of the makefile's, which pointed every tool path at
# $HOME the first time this file was run from the repository root.
SOC_MK    := $(abspath $(lastword $(MAKEFILE_LIST)))
SOC_DIR   := $(patsubst %/,%,$(dir $(SOC_MK)))
REPO_ROOT ?= $(abspath $(SOC_DIR)/../..)

include $(REPO_ROOT)/tools.mk

# --- sv2v -------------------------------------------------------------
SV2V_VERSION     ?= v0.0.13
SV2V_ZIP_SHA256  ?= 552799a1d76cd177b9b4cc63a3e77823a3d2a6eb4ec006569288abeff28e1ff8
SV2V_URL         ?= https://github.com/zachjs/sv2v/releases/download/$(SV2V_VERSION)/sv2v-Linux.zip
SV2V             ?= $(SOC_DIR)/tools/sv2v-Linux/sv2v

# --- riscv-none-elf-gcc -----------------------------------------------
RVGCC_VERSION    ?= v15.2.0-1
RVGCC_TGZ_SHA256 ?= aaaa8060c914851a3e5ee1ba82cc3d6f80972f90638a05c6e823a37557a33758
RVGCC_URL        ?= https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/$(RVGCC_VERSION)/xpack-riscv-none-elf-gcc-15.2.0-1-linux-x64.tar.gz
RVGCC_DIR        ?= $(SOC_DIR)/tools/rvgcc
RVGCC            ?= $(RVGCC_DIR)/bin/riscv-none-elf-gcc

# --- OpenSTA ----------------------------------------------------------
LL_BIN ?= $(HOME)/.local/opt/llbin
STA    ?= $(LL_BIN)/sta

# --- PDK --------------------------------------------------------------
# The LibreLane-pinned IHP-Open-PDK commit, as recorded in docs/12.
PDK_VERSION ?= c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c
PDK_ROOT    ?= $(HOME)/.ciel/ciel/ihp-sg13g2/versions/$(PDK_VERSION)
SG13G2_LIB_DIR ?= $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib
SG13G2_TYP  ?= $(SG13G2_LIB_DIR)/sg13g2_stdcell_typ_1p20V_25C.lib
SG13G2_SLOW ?= $(SG13G2_LIB_DIR)/sg13g2_stdcell_slow_1p08V_125C.lib
SG13G2_FAST ?= $(SG13G2_LIB_DIR)/sg13g2_stdcell_fast_1p32V_m40C.lib
SG13G2_VLOG ?= $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_stdcell.v

# --- Ibex upstream ----------------------------------------------------
IBEX_URL    ?= https://github.com/lowRISC/ibex.git
IBEX_COMMIT ?= 34b0705760ef3dfa00e99637432473d2be8f22f3
IBEX_DIR    ?= $(SOC_DIR)/ext/ibex

.PHONY: soc-toolcheck
soc-toolcheck: toolcheck
	@echo "---- SoC-specific tools ----"
	@echo "sv2v      = $(SV2V)"
	@test -x "$(SV2V)" || { echo "ERROR: sv2v not unpacked. Run 'make fetch-sv2v'."; exit 1; }
	@echo "sv2v version = $$($(SV2V) --version) (pinned $(SV2V_VERSION))"
	@echo "rvgcc     = $(RVGCC)"
	@test -x "$(RVGCC)" || { echo "ERROR: riscv gcc not unpacked. Run 'make fetch-rvgcc'."; exit 1; }
	@echo "rvgcc version = $$($(RVGCC) -dumpversion) (pinned $(RVGCC_VERSION))"
	@echo "sta       = $(STA)"
	@test -x "$(STA)" || { echo "ERROR: OpenSTA not found at $(STA)."; exit 1; }
	@echo "sta version  = $$($(STA) -version 2>/dev/null)"
	@echo "PDK_ROOT  = $(PDK_ROOT)"
	@test -f "$(SG13G2_TYP)" || { echo "ERROR: sg13g2 liberty not found."; exit 1; }
	@echo "ibex      = $(IBEX_DIR) @ $(IBEX_COMMIT)"
	@if [ -d "$(IBEX_DIR)/.git" ]; then \
	   echo "ibex HEAD = $$(git -C $(IBEX_DIR) rev-parse HEAD)"; \
	 else echo "ibex not fetched. Run 'make fetch-ibex'."; fi

# Single source of truth for the shell scripts under flow/: they eval
# this instead of re-deriving paths, so the Makefile and the scripts can
# never disagree about which tool ran.
.PHONY: printvars
printvars:
	@echo 'YOSYS="$(YOSYS)"'
	@echo 'IVERILOG="$(IVERILOG)"'
	@echo 'VVP="$(VVP)"'
	@echo 'SV2V="$(SV2V)"'
	@echo 'STA="$(STA)"'
	@echo 'RVGCC="$(RVGCC)"'
	@echo 'PDK_ROOT="$(PDK_ROOT)"'
	@echo 'SG13G2_TYP="$(SG13G2_TYP)"'
	@echo 'SG13G2_SLOW="$(SG13G2_SLOW)"'
	@echo 'SG13G2_FAST="$(SG13G2_FAST)"'
	@echo 'SG13G2_VLOG="$(SG13G2_VLOG)"'
	@echo 'IBEX_DIR="$(IBEX_DIR)"'
	@echo 'IBEX_COMMIT="$(IBEX_COMMIT)"'

.PHONY: fetch-sv2v
fetch-sv2v:
	@mkdir -p $(SOC_DIR)/tools
	curl -sSL -o $(SOC_DIR)/tools/sv2v-Linux.zip "$(SV2V_URL)"
	@echo "$(SV2V_ZIP_SHA256)  $(SOC_DIR)/tools/sv2v-Linux.zip" | sha256sum -c -
	cd $(SOC_DIR)/tools && unzip -o -q sv2v-Linux.zip && rm -f sv2v-Linux.zip
	@$(SV2V) --version

.PHONY: fetch-rvgcc
fetch-rvgcc:
	@mkdir -p $(SOC_DIR)/tools
	curl -sSL -o $(SOC_DIR)/tools/rvgcc.tar.gz "$(RVGCC_URL)"
	@echo "$(RVGCC_TGZ_SHA256)  $(SOC_DIR)/tools/rvgcc.tar.gz" | sha256sum -c -
	@mkdir -p $(RVGCC_DIR)
	tar -xzf $(SOC_DIR)/tools/rvgcc.tar.gz -C $(RVGCC_DIR) --strip-components=1
	@rm -f $(SOC_DIR)/tools/rvgcc.tar.gz
	@$(RVGCC) --version | head -1

.PHONY: fetch-ibex
fetch-ibex:
	@mkdir -p $(SOC_DIR)/ext
	@if [ ! -d "$(IBEX_DIR)/.git" ]; then \
	   git clone --quiet $(IBEX_URL) $(IBEX_DIR); fi
	git -C $(IBEX_DIR) fetch --quiet origin
	git -C $(IBEX_DIR) checkout --quiet $(IBEX_COMMIT)
	@echo "ibex @ $$(git -C $(IBEX_DIR) rev-parse HEAD)"
