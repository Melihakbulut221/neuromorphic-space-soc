# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

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

# The RM_IHPSG13 SRAM macros, added by docs/47 for SOC_MEM=sram. Note the
# CORNER-NAME MISMATCH, which is the PDK's and not ours: the standard
# cells ship fast_1p32V_m40C and the SRAM macros ship fast_1p32V_m55C,
# so the macro file attached to the `fast` corner here is characterised
# 15 C colder than the cells around it. docs/12 section 6.4a found this
# and hw/openlane/sram_pilot/config.json makes the same cross-corner map;
# it is stated at every place it is done rather than in one of them.
SG13G2_SRAM_DIR ?= $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_sram
SRAM_RAM_MACRO  ?= RM_IHPSG13_1P_2048x64_c2_bm_bist
SRAM_ROM_MACRO  ?= RM_IHPSG13_1P_1024x32_c2_bm_bist
SRAM_TYP  ?= $(SG13G2_SRAM_DIR)/lib/$(SRAM_RAM_MACRO)_typ_1p20V_25C.lib $(SG13G2_SRAM_DIR)/lib/$(SRAM_ROM_MACRO)_typ_1p20V_25C.lib
SRAM_SLOW ?= $(SG13G2_SRAM_DIR)/lib/$(SRAM_RAM_MACRO)_slow_1p08V_125C.lib $(SG13G2_SRAM_DIR)/lib/$(SRAM_ROM_MACRO)_slow_1p08V_125C.lib
SRAM_FAST ?= $(SG13G2_SRAM_DIR)/lib/$(SRAM_RAM_MACRO)_fast_1p32V_m55C.lib $(SG13G2_SRAM_DIR)/lib/$(SRAM_ROM_MACRO)_fast_1p32V_m55C.lib

# --- Ibex upstream ----------------------------------------------------
IBEX_URL    ?= https://github.com/lowRISC/ibex.git
IBEX_COMMIT ?= 34b0705760ef3dfa00e99637432473d2be8f22f3
IBEX_DIR    ?= $(SOC_DIR)/ext/ibex

# --- riscv-formal -----------------------------------------------------
# The formal RISC-V ISA description and its check generator, planned in
# docs/09 part B track 1 and brought up in docs/63. Same rule as Ibex:
# fetched by commit into a gitignored ext/ directory, never vendored,
# and `git -C $(RVFORMAL_DIR) status` stays clean -- the harness that
# binds it to this core lives in hw/soc/rvformal/, OUTSIDE the checkout,
# for the reason hw/soc/flow/rvformal.sh's header gives.
#
# Pinned by COMMIT and not by tag, because riscv-formal publishes no
# releases. There is therefore no release archive to sha256, and that is
# a real difference from sv2v and the RISC-V GCC above rather than an
# omission: a git commit id is a content hash of the tree, so `checkout
# <sha>` is verified by git itself, but there is no second, independent
# digest of a downloaded artefact the way there is for those two.
RVFORMAL_URL    ?= https://github.com/YosysHQ/riscv-formal.git
RVFORMAL_COMMIT ?= c992aa61fdfe0846c5ed90324c596202a1c69b76
RVFORMAL_DIR    ?= $(SOC_DIR)/ext/riscv-formal

# --- interface IP candidates, docs/65 -----------------------------------
# The four third-party cores docs/03 section 2.2 selected for the
# spacecraft interfaces, fetched by commit into gitignored ext/
# directories by the Ibex rule: never vendored, never edited, pinned
# here by the commit id that is itself a content hash of the tree. None
# of them publishes releases, so there is no archive to sha256 -- the
# same difference from sv2v and the RISC-V GCC that riscv-formal's entry
# above records.
#
# What each one is, what licence it carries, and what docs/65 found when
# it was put through this flow:
#
#   opentitan            lowRISC OpenTitan, Apache-2.0. Only hw/ip/spi_host
#                        and its dependency closure are checked out, by
#                        sparse checkout, because the repository is
#                        ~220 MB packed. spi_host is the QSPI candidate;
#                        hw/soc/flow/sv2v_spi_host.sh converts it.
#   spacewire_reloaded   LGPL-2.1-or-later (LGPL-2.1.txt, and an SPDX tag
#                        in every source file). The SpaceWire candidate:
#                        a Verilog-2001 translation of SpaceWire Light
#                        with AXI4-Lite and AXI4-Stream wrappers.
#   can                  the Mohor SJA1000-style CAN 2.0B core, LGPL-2.1-
#                        or-later per the header of every file, with the
#                        Bosch protocol-licence notice docs/03 records.
#   verilog-i2c          alexforencich/verilog-i2c, MIT (COPYING).
#
# Licence compatibility with docs/14's recommendation (CERN-OHL-W-2.0 for
# RTL): Apache-2.0 and MIT are inbound-compatible; the two LGPL cores are
# the case docs/14 section 5.2 argues is a bad fit for silicon and
# recommends keeping out of the funded scope. Fetching them here for
# ASSESSMENT does not put them in the design: nothing under hw/soc/rtl
# instantiates any of them.
OPENTITAN_URL    ?= https://github.com/lowRISC/opentitan.git
OPENTITAN_COMMIT ?= 1e1dace7680251f88ab11adedd8766222f333962
OPENTITAN_DIR    ?= $(SOC_DIR)/ext/opentitan
# The sparse-checkout set: spi_host, the prim/tlul/racl primitives its
# closure reaches, the two top-level packages, and spi_device for the
# passthrough types spi_host's port list names.
OPENTITAN_SPARSE ?= hw/ip/spi_host hw/ip/prim hw/ip/prim_generic \
                    hw/ip/tlul hw/ip/spi_device/rtl \
                    hw/top_earlgrey/rtl hw/dv/sv/dv_utils LICENSE

SPW_URL     ?= https://github.com/lcapossio/spacewire_reloaded.git
SPW_COMMIT  ?= 450d2254bb980dc08825a575e205acbbefbc8a69
SPW_DIR     ?= $(SOC_DIR)/ext/spacewire_reloaded

CAN_URL     ?= https://github.com/freecores/can.git
CAN_COMMIT  ?= 470f0e7ab174dfef01a05f5d5ad01f28f6f4dc17
CAN_DIR     ?= $(SOC_DIR)/ext/can

I2C_URL     ?= https://github.com/alexforencich/verilog-i2c.git
I2C_COMMIT  ?= a65be4045e898a52e791c6ee71f8f79a7cd2e129
I2C_DIR     ?= $(SOC_DIR)/ext/verilog-i2c

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
	@echo "riscv-formal = $(RVFORMAL_DIR) @ $(RVFORMAL_COMMIT)"
	@if [ -d "$(RVFORMAL_DIR)/.git" ]; then \
	   echo "riscv-formal HEAD = $$(git -C $(RVFORMAL_DIR) rev-parse HEAD)"; \
	   if [ -n "$$(git -C $(RVFORMAL_DIR) status --porcelain)" ]; then \
	     echo "ERROR: $(RVFORMAL_DIR) is NOT clean. It is a fetched"; \
	     echo "       checkout, not a place to edit -- the harness is in"; \
	     echo "       hw/soc/rvformal/."; exit 1; fi; \
	 else echo "riscv-formal not fetched. Run 'make fetch-riscv-formal'."; fi
	@for pair in "opentitan:$(OPENTITAN_DIR):$(OPENTITAN_COMMIT)" \
	             "spacewire_reloaded:$(SPW_DIR):$(SPW_COMMIT)" \
	             "can:$(CAN_DIR):$(CAN_COMMIT)" \
	             "verilog-i2c:$(I2C_DIR):$(I2C_COMMIT)"; do \
	   n=$${pair%%:*}; rest=$${pair#*:}; d=$${rest%%:*}; c=$${rest#*:}; \
	   if [ -d "$$d/.git" ]; then \
	     echo "$$n HEAD = $$(git -C $$d rev-parse HEAD) (pinned $$c)"; \
	     if [ -n "$$(git -C $$d status --porcelain)" ]; then \
	       echo "ERROR: $$d is NOT clean. It is a fetched checkout, not a"; \
	       echo "       place to edit."; exit 1; fi; \
	   else echo "$$n not fetched. Run 'make fetch-$$n'."; fi; \
	 done

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
	@echo 'SG13G2_SRAM_DIR="$(SG13G2_SRAM_DIR)"'
	@echo 'SRAM_RAM_MACRO="$(SRAM_RAM_MACRO)"'
	@echo 'SRAM_ROM_MACRO="$(SRAM_ROM_MACRO)"'
	@echo 'SRAM_TYP="$(SRAM_TYP)"'
	@echo 'SRAM_SLOW="$(SRAM_SLOW)"'
	@echo 'SRAM_FAST="$(SRAM_FAST)"'
	@echo 'IBEX_DIR="$(IBEX_DIR)"'
	@echo 'IBEX_COMMIT="$(IBEX_COMMIT)"'
	@echo 'RVFORMAL_DIR="$(RVFORMAL_DIR)"'
	@echo 'RVFORMAL_COMMIT="$(RVFORMAL_COMMIT)"'
	@echo 'OPENTITAN_DIR="$(OPENTITAN_DIR)"'
	@echo 'OPENTITAN_COMMIT="$(OPENTITAN_COMMIT)"'
	@echo 'SPW_DIR="$(SPW_DIR)"'
	@echo 'CAN_DIR="$(CAN_DIR)"'
	@echo 'I2C_DIR="$(I2C_DIR)"'
	@echo 'SBY="$(SBY)"'

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

.PHONY: fetch-riscv-formal
fetch-riscv-formal:
	@mkdir -p $(SOC_DIR)/ext
	@if [ ! -d "$(RVFORMAL_DIR)/.git" ]; then \
	   git clone --quiet $(RVFORMAL_URL) $(RVFORMAL_DIR); fi
	git -C $(RVFORMAL_DIR) fetch --quiet origin
	git -C $(RVFORMAL_DIR) checkout --quiet $(RVFORMAL_COMMIT)
	@echo "riscv-formal @ $$(git -C $(RVFORMAL_DIR) rev-parse HEAD)"
	@test -f "$(RVFORMAL_DIR)/insns/isa_rv32imc.txt" || { \
	   echo "ERROR: the pinned commit has no insns/isa_rv32imc.txt."; exit 1; }
	@test -z "$$(git -C $(RVFORMAL_DIR) status --porcelain)" || { \
	   echo "ERROR: checkout is dirty after fetch."; exit 1; }

# --- the interface IP candidates, docs/65 -------------------------------
# OpenTitan is fetched WITHOUT a checkout and then sparse-checked-out to
# the set above: the whole repository is ~220 MB packed and the closure
# spi_host needs is about 100 MB of it. `--filter=blob:none` fetches the
# commit graph and only the blobs the sparse set names.
.PHONY: fetch-opentitan
fetch-opentitan:
	@mkdir -p $(SOC_DIR)/ext
	@if [ ! -d "$(OPENTITAN_DIR)/.git" ]; then \
	   git clone --quiet --filter=blob:none --no-checkout \
	     $(OPENTITAN_URL) $(OPENTITAN_DIR); \
	   git -C $(OPENTITAN_DIR) sparse-checkout init --cone; fi
	git -C $(OPENTITAN_DIR) sparse-checkout set $(OPENTITAN_SPARSE)
	git -C $(OPENTITAN_DIR) fetch --quiet origin
	git -C $(OPENTITAN_DIR) checkout --quiet $(OPENTITAN_COMMIT)
	@echo "opentitan @ $$(git -C $(OPENTITAN_DIR) rev-parse HEAD)"
	@test -f "$(OPENTITAN_DIR)/hw/ip/spi_host/rtl/spi_host.sv" || { \
	   echo "ERROR: the sparse checkout has no hw/ip/spi_host/rtl/spi_host.sv."; exit 1; }

define fetch_small_ip
	@mkdir -p $(SOC_DIR)/ext
	@if [ ! -d "$(2)/.git" ]; then git clone --quiet $(1) $(2); fi
	git -C $(2) fetch --quiet origin
	git -C $(2) checkout --quiet $(3)
	@echo "$(notdir $(2)) @ $$(git -C $(2) rev-parse HEAD)"
	@test -z "$$(git -C $(2) status --porcelain)" || { \
	   echo "ERROR: checkout is dirty after fetch."; exit 1; }
endef

.PHONY: fetch-spacewire_reloaded fetch-can fetch-verilog-i2c
fetch-spacewire_reloaded:
	$(call fetch_small_ip,$(SPW_URL),$(SPW_DIR),$(SPW_COMMIT))
fetch-can:
	$(call fetch_small_ip,$(CAN_URL),$(CAN_DIR),$(CAN_COMMIT))
fetch-verilog-i2c:
	$(call fetch_small_ip,$(I2C_URL),$(I2C_DIR),$(I2C_COMMIT))
