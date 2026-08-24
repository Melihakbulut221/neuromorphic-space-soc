SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# TB=aer_fifo (default); future blocks add branches here.
TB ?= aer_fifo

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

ifeq ($(TB),aer_fifo)
VERILOG_SOURCES = $(RTL)/aer_fifo.v
TOPLEVEL = aer_fifo
MODULE = test_aer_fifo
COMPILE_ARGS += -I$(RTL)
COMPILE_ARGS += $(EXTRA_COMPILE_ARGS)
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

endif
