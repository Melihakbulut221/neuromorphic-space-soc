SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# TB=<block> selects the suite; aer_fifo is the default and is the one
# elaborated in this file.
TB ?= aer_fifo

# Every other block owns a standalone driver hw/tb/Makefile.<block> (the
# convention docs/11 section 2 fixes: new blocks add a fragment instead of
# editing this file). TB=<block> forwards there rather than duplicating the
# fragment's SIM_BUILD, results file and parameter handling here, so
# `make TB=secded` and `cd hw/tb && make -f Makefile.secded` are the same
# run and cannot drift apart.
TB_FRAGMENTS := regbank lif secded tmr pilot
TB_BLOCKS := aer_fifo $(TB_FRAGMENTS)

# An unrecognised TB= used to fall through every branch and start the
# simulator with no sources and no test module, which deleted results.xml
# and then failed with an unrelated cocotb traceback. Reject it here
# instead, at parse time, before anything is removed.
ifeq ($(filter $(TB),$(TB_BLOCKS)),)
$(error unknown TB=$(TB); expected one of: $(TB_BLOCKS))
endif

ifneq ($(filter $(TB),$(TB_FRAGMENTS)),)

TB_FRAGMENT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/Makefile.$(TB))

# Forward whatever was asked for. With no goal named, the fragment's own
# default goal decides (all widths, both elaborations, and so on); command
# line variables such as SECDED_DUT=enc or TMR_WIDTH=32 are passed down by
# make itself. The fragment repeats the venv discovery below, so no PATH
# work is needed on this side.
ifeq ($(MAKECMDGOALS),)
.DEFAULT_GOAL := tb_dispatch
.PHONY: tb_dispatch
tb_dispatch:
	@$(MAKE) -f $(TB_FRAGMENT) --no-print-directory
else
.PHONY: $(MAKECMDGOALS)
$(MAKECMDGOALS):
	@$(MAKE) -f $(TB_FRAGMENT) --no-print-directory $@
endif

else

# Rootless tool discovery: iverilog comes from PATH (~/.local/bin class
# install or an oss-cad-suite checkout); cocotb lives in the project venv
# hw/.venv. If cocotb-config is not already on PATH, re-invoke make with
# the venv prepended -- make < 4.4 does not pass exported PATH to
# $(shell ...), which the cocotb makefiles rely on.
VENV_BIN := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../.venv/bin)

ifeq ($(shell command -v cocotb-config 2>/dev/null),)

GOALS := $(if $(MAKECMDGOALS),$(MAKECMDGOALS),sim)
.PHONY: $(GOALS)
$(GOALS):
	@PATH="$(VENV_BIN):$$PATH" $(MAKE) --no-print-directory $@

else

RTL = $(PWD)/../rtl

# TB is aer_fifo here: any other value was either dispatched to its
# fragment or rejected above.
VERILOG_SOURCES = $(RTL)/aer_fifo.v
TOPLEVEL = aer_fifo
MODULE = test_aer_fifo
COMPILE_ARGS += -I$(RTL)
COMPILE_ARGS += $(EXTRA_COMPILE_ARGS)

include $(shell cocotb-config --makefiles)/Makefile.sim

endif

endif
