# SymbiYosys jobs for the SoC fabric blocks.
#
#   cd hw/soc/formal && make            every task of every job
#   cd hw/soc/formal && make bus        soc_bus: bmc, prove, cover
#   cd hw/soc/formal && make apb        soc_apb_bridge: bmc, prove, cover
#   cd hw/soc/formal && make clint      soc_clint: bmc, prove, cover
#   cd hw/soc/formal && make busstat    soc_busstat: bmc, prove,
#                                       prove_w16, cover
#   cd hw/soc/formal && make gpio       soc_gpio: bmc, prove, prove_w16,
#                                       cover
#   cd hw/soc/formal && make qspi       soc_qspi: bmc, prove, prove_full,
#                                       cover
#   cd hw/soc/formal && make scrub      soc_scrub: bmc, prove, prove_w16,
#                                       cover (docs/67)
#   cd hw/soc/formal && make bytesecded the (16,8) byte shortening the
#                                       memory codec stores: bmc, prove,
#                                       prove_abc, cover (docs/67)
#   cd hw/soc/formal && make memecc     soc_mem_ecc over a four-row
#                                       array: bmc, prove, cover (docs/67)
#   cd hw/soc/formal && make wdog       soc_wdog: bmc, prove, prove_w0,
#                                       cover
#   cd hw/soc/formal && make npuser     the NPU serial transport: bmc,
#                                       prove, cover, prove_h3
#   cd hw/soc/formal && make regfile    the shortened SECDED code the
#                                       substituted register file uses:
#                                       bmc, prove, prove_abc, cover
#   cd hw/soc/formal && make wdogtmr    the watchdog's protected word:
#                                       the parameter guard, then eight
#                                       tasks over three soc_tmr_bank
#                                       replicas under one tmr_voter
#   cd hw/soc/formal && make clkwake   docs/77's clock-gate enable
#                                       transformation: bmc, prove,
#                                       cover, and the same three with
#                                       A2 dropped -- the fault case
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
.PHONY: all bus apb clint wdog wdogtmr wdog_tmr_params regfile busstat npuser gpio qspi scrub boot boot_tmr_params bytesecded memecc clkwake clean
.DEFAULT_GOAL := all
all: bus apb clint wdog wdogtmr regfile busstat npuser gpio qspi scrub boot bytesecded memecc clkwake

include $(REPO)/tools.mk

TASKS := bmc prove cover

bus:
	@for t in $(TASKS); do \
	  echo "== soc_bus $$t"; \
	  $(SBY) -f soc_bus.sby $$t || exit 1; \
	done

npuser:
	@for t in $(TASKS) prove_h3; do \
	  echo "== soc_npu_ser $$t"; \
	  $(SBY) -f soc_npu_ser.sby $$t || exit 1; \
	done

apb:
	@for t in $(TASKS); do \
	  echo "== soc_apb_bridge $$t"; \
	  $(SBY) -f soc_apb_bridge.sby $$t || exit 1; \
	done

clint:
	@for t in $(TASKS); do \
	  echo "== soc_clint $$t"; \
	  $(SBY) -f soc_clint.sby $$t || exit 1; \
	done

# The fault counters docs/44 adds, and the two widths they are proved
# at: CNT_W = 4 so that saturation is reachable inside a bounded model,
# and CNT_W = 16 because that is what soc_top.v instantiates.
BUSSTAT_TASKS := bmc prove prove_w16 cover

busstat:
	@for t in $(BUSSTAT_TASKS); do \
	  echo "== soc_busstat $$t"; \
	  $(SBY) -f soc_busstat.sby $$t || exit 1; \
	done

# The GPIO port docs/65 adds, at the two widths it is proved at: NBITS
# = 4 so that every cover is reachable in a bounded model, and NBITS =
# 16 because that is what soc_top.v instantiates.
GPIO_TASKS := bmc prove prove_w16 cover

gpio:
	@for t in $(GPIO_TASKS); do \
	  echo "== soc_gpio $$t"; \
	  $(SBY) -f soc_gpio.sby $$t || exit 1; \
	done

# The QSPI controller docs/66 adds, at the two widths it is proved at:
# LEN_W = 3 and DIV_W = 2 so that a whole frame, a pause and a resume
# are reachable in a bounded model, and LEN_W = 16, DIV_W = 4 because
# that is what soc_top.v instantiates.
QSPI_TASKS := bmc prove prove_full cover

qspi:
	@for t in $(QSPI_TASKS); do \
	  echo "== soc_qspi $$t"; \
	  $(SBY) -f soc_qspi.sby $$t || exit 1; \
	done

# The memory codec's counters docs/67 adds, at the two widths
# soc_busstat is proved at and for the same reason.
SCRUB_TASKS := bmc prove prove_w16 cover

scrub:
	@for t in $(SCRUB_TASKS); do \
	  echo "== soc_scrub $$t"; \
	  $(SBY) -f soc_scrub.sby $$t || exit 1; \
	done

# The boot flow's register block docs/68 adds, at the two counter widths
# soc_busstat is proved at and for the same reason, plus docs/69's
# HARDEN = 0 task -- which is not a duplicate: B1 rewrote the block's
# next state as one combinational function shared by both
# configurations, and proving the policy in both is what makes the
# like-for-like area baseline an established fact.
BOOT_TASKS := bmc prove prove_full prove_h0 cover

# soc_boot.v instantiates the SAME composition soc_wdog_tmr.sby proves
# -- three soc_tmr_bank replicas under hw/rtl/tmr_voter.v, POL_A/B/C,
# MIX off on A and on for B and C -- and at the shipped parameters its
# banked word is 22 bits, which is one of the four widths that job runs
# at. So the masking theorem is already proved for this block, and what
# has to be guarded is that the block still instantiates what was
# proved. Same shape as wdog_tmr_params, one file across, and it runs
# FIRST in the boot target.
BOOT_RTL := ../rtl/soc_boot.v

boot_tmr_params:
	@fail=0; \
	for pat in \
	  "localparam \[63:0\] POL_A = 64'h0000000000000000;" \
	  "localparam \[63:0\] POL_B = 64'h5555555555555555;" \
	  "localparam \[63:0\] POL_C = 64'hAAAAAAAAAAAAAAAA;" \
	  ".POL(POL_A), .MIX(0))" \
	  ".POL(POL_B), .MIX(1))" \
	  ".POL(POL_C), .MIX(1))" ; do \
	  grep -qF "$$(printf '%s' "$$pat" | sed 's/\\//g')" $(BOOT_RTL) || { \
	    echo "soc_boot.v no longer instantiates the composition" \
	         "soc_wdog_tmr.sby proves: $$pat"; fail=1; }; \
	done; \
	test $$fail -eq 0 || exit 1; \
	echo "== soc_boot parameter guard: the masks and the MIX" \
	     "assignments still match what soc_wdog_tmr.sby proves"

boot: boot_tmr_params
	@for t in $(BOOT_TASKS); do \
	  echo "== soc_boot $$t"; \
	  $(SBY) -f soc_boot.sby $$t || exit 1; \
	done

# The BYTE shortening of the (72,64) codec, four of which make one RAM
# row (docs/67): the same four tasks regfile_secded runs for the word
# shortening.
BYTE_TASKS := bmc prove prove_abc cover

bytesecded:
	@for t in $(BYTE_TASKS); do \
	  echo "== byte_secded $$t"; \
	  $(SBY) -f byte_secded.sby $$t || exit 1; \
	done

# The codec and the scrubber over a four-row array, docs/67: the stored
# rows are codewords in every reachable state, the codec is invisible in
# a fault-free machine, and the protocol is soc_mem's.
MEMECC_TASKS := bmc prove cover

memecc:
	@for t in $(MEMECC_TASKS); do \
	  echo "== soc_mem_ecc $$t"; \
	  $(SBY) -f soc_mem_ecc.sby $$t || exit 1; \
	done

WDOG_TASKS := bmc prove prove_w0 cover

wdog:
	@for t in $(WDOG_TASKS); do \
	  echo "== soc_wdog $$t"; \
	  $(SBY) -f soc_wdog.sby $$t || exit 1; \
	done

# The shortening of the (72,64) codec to the 40 bits
# hw/soc/rtl/ibex_regfile_secded.v actually stores.  formal/secded.sby
# proves the codec at its own width and is not touched by this work;
# what is new is that tying the upper 32 data bits to zero leaves a code
# that still corrects one error and detects two, which is an argument
# about which columns of H survive and which nothing checked.
REGFILE_TASKS := bmc prove prove_abc cover

regfile:
	@for t in $(REGFILE_TASKS); do \
	  echo "== regfile_secded $$t"; \
	  $(SBY) -f regfile_secded.sby $$t || exit 1; \
	done

# soc_wdog_tmr.sby rebuilds the composition soc_wdog.v's g_prot_tmr
# block builds, because a fault model needs free inputs at the voter and
# soc_wdog has no port for them. Three things are therefore copied: the
# three POL masks and which replicas carry MIX. This target reads them
# back out of the RTL and fails if any has moved, so the copy cannot
# drift silently. It is the same guard formal/tmr_voter_cfg.mk applies
# to the pilot's configuration domain, and it runs FIRST.
#
# The WIDTH is deliberately not guarded: soc_wdog computes PROT_W from
# its own field layout and the proof runs at four widths instead.
WDOG_RTL := ../rtl/soc_wdog.v

wdog_tmr_params:
	@fail=0; \
	for pat in \
	  "localparam \[63:0\] POL_A = 64'h0000000000000000;" \
	  "localparam \[63:0\] POL_B = 64'h5555555555555555;" \
	  "localparam \[63:0\] POL_C = 64'hAAAAAAAAAAAAAAAA;" \
	  ".POL(POL_A), .MIX(0))" \
	  ".POL(POL_B), .MIX(1))" \
	  ".POL(POL_C), .MIX(1))" ; do \
	  grep -qF "$$(printf '%s' "$$pat" | sed 's/\\//g')" $(WDOG_RTL) || { \
	    echo "soc_wdog_tmr.sby copies a parameter that has MOVED in" \
	         "$(WDOG_RTL): $$pat"; fail=1; }; \
	done; \
	test $$fail -eq 0 || exit 1; \
	echo "== soc_wdog_tmr parameter guard: the masks and the MIX" \
	     "assignments still match hw/soc/rtl/soc_wdog.v"

WDOG_TMR_TASKS := prove prove_w4 prove_w5 prove_w21 prove_w23 prove_rst1 prove_abc \
                  bmc cover

wdogtmr: wdog_tmr_params
	@for t in $(WDOG_TMR_TASKS); do \
	  echo "== soc_wdog_tmr $$t"; \
	  $(SBY) -f soc_wdog_tmr.sby $$t || exit 1; \
	done

# docs/77. Six tasks and not three: `sound` keeps A2 -- `slow` is a
# function of the block's state -- and proves T1 and T2; `upset` DROPS it
# and proves T2 alone, which is the fault case, a frozen fault line
# rising inside a block whose clock is stopped. A job whose two halves
# disagree about an assumption is the point of it, and the file says so.
CLKWAKE_TASKS := bmc prove cover bmc_upset prove_upset cover_upset

clkwake:
	@for t in $(CLKWAKE_TASKS); do \
	  echo "== clkgate_wake $$t"; \
	  $(SBY) -f clkgate_wake.sby $$t || exit 1; \
	done

clean:
	rm -rf $(addprefix clkgate_wake_,$(CLKWAKE_TASKS)) clkgate_wake \
	       $(addprefix soc_wdog_tmr_,$(WDOG_TMR_TASKS)) soc_wdog_tmr \
	       soc_bus soc_bus_bmc soc_bus_prove soc_bus_cover \
	       soc_apb_bridge soc_apb_bridge_bmc soc_apb_bridge_prove \
	       soc_apb_bridge_cover \
	       soc_clint soc_clint_bmc soc_clint_prove soc_clint_cover \
	       $(addprefix soc_wdog_,$(WDOG_TASKS)) soc_wdog \
	       $(addprefix regfile_secded_,$(REGFILE_TASKS)) regfile_secded \
	       $(addprefix soc_gpio_,$(GPIO_TASKS)) soc_gpio \
	       $(addprefix soc_qspi_,$(QSPI_TASKS)) soc_qspi \
	       $(addprefix soc_scrub_,$(SCRUB_TASKS)) soc_scrub \
	       $(addprefix soc_boot_,$(BOOT_TASKS)) soc_boot \
	       $(addprefix byte_secded_,$(BYTE_TASKS)) byte_secded \
	       $(addprefix soc_mem_ecc_,$(MEMECC_TASKS)) soc_mem_ecc
