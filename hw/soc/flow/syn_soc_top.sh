#!/usr/bin/env bash
# Synthesise soc_top -- the WHOLE SoC, core included -- onto ihp-sg13g2.
#
#   syn_soc_top.sh [clock_period_ns] [out_dir]
#
# docs/41 section 10 item 7 and docs/43 section 11 both recorded that
# `soc_top.v` had never been synthesised as one design, and docs/44
# section 10's last line repeated it. Every area and timing number under
# hw/soc/ before this script was per-block: flow/syn_ibex.sh measures
# `ibex_top` standalone and flow/syn_soc.sh measures one peripheral at a
# time, with soc_top.v excluded from its source list on purpose. This
# script is the missing one.
#
# THE RECIPE IS THE SAME RECIPE. Same liberty, same typical corner, same
# abc.constr (sg13g2_buf_4 driving, 5 fF load), same `-D` delay target,
# same deferred flatten, same `stat -liberty`. That is the whole point:
# a whole-design number measured a different way could not be compared
# with the per-block numbers it is supposed to compose from.
#
# ---------------------------------------------------------------------
# THE MEMORIES, WHICH ARE THE ONE THING THAT CANNOT BE SYNTHESISED
#
# hw/soc/rtl/soc_mem.v says of itself, in its first paragraph, that it is
# "a BEHAVIOURAL MODEL of a memory, not a memory": it infers a register
# array. soc_top.v instantiates it twice, at sizes the generated map
# fixes -- 64 KiB of RAM and 8 KiB of boot ROM, which is 16,384 and 2,048
# 32-bit words. Elaborated as one design those two arrays are 589,824
# flip-flops, against 2,328 in the whole of Ibex. Synthesising them would
# not be slow-but-honest; it would be a measurement of a simulation
# model. flow/syn_soc.sh already excludes soc_mem.v from its source list
# for exactly this reason and says so.
#
# So the memory boundary is cut, and SOC_MEM says how:
#
#   stub       (default) The two instances are replaced by a MACRO
#              STAND-IN generated into the output directory. It keeps
#              soc_mem's ports and its protocol timing -- gnt_o = req_i
#              combinationally, rvalid_o and err_o registered -- and
#              replaces the array with one row plus input capture
#              registers, so that every path from the fabric into a
#              memory still ENDS at a flip-flop and every path out of one
#              still STARTS at a flip-flop. That is the first-order
#              timing model of an SRAM macro and it is what makes the
#              netlist readable by OpenSTA with no macro liberty.
#
#              IT IS NOT FUNCTIONAL. rdata_o is not the memory's
#              contents. This netlist is for area and timing and must
#              never be simulated or compared against one that is.
#
#   blackbox   The two instances are left as unresolved blackboxes. The
#              area report is then the SoC's standard-cell logic and
#              nothing else, with no stand-in contaminating it. This is
#              the cleanest AREA number and it cannot be timed: OpenSTA
#              has no liberty for the macro.
#
#   array      The real soc_mem.v, all 589,824 registers. Provided so the
#              claim above is falsifiable rather than asserted. It is run
#              only with SOC_ELAB_ONLY=1, which cuts the script after
#              `hierarchy -check`: that is docs/45 section 5's
#              elaboration measurement, and it is the only thing this
#              mode is used for. No area or timing number in docs/45
#              comes from it.
#
#   sram       THE REAL MEMORIES, added by docs/47. hw/soc/rtl/
#              soc_mem_sram.v declares a module called `soc_mem` built
#              on six RM_IHPSG13 SRAM macros -- four
#              RM_IHPSG13_1P_2048x64_c2_bm_bist for the 64 KiB RAM and
#              two RM_IHPSG13_1P_1024x32_c2_bm_bist for the 8 KiB boot
#              ROM. The macros are read as blackbox DECLARATIONS out of
#              hw/soc/pnr/, so `stat -liberty` reports the SoC's
#              standard-cell logic and the macro area is added from the
#              LEF separately; docs/47 section 4 does that addition in
#              public rather than folding it into one number.
#
#              UNLIKE `stub`, THIS ONE CAN BE TIMED PROPERLY. The PDK
#              ships Liberty for these macros at all three corners, so
#              flow/sta_soc_top.sh reads them when SOC_MEM=sram and the
#              read arc it charges -- 9.2941 ns at slow_1p08V_125C on
#              the 2048x64 part -- is the quantity docs/45 section 8
#              named as the thing the stub could not bound.
#
#              It is the netlist hw/soc/pnr/ hardens, and it MUST NOT BE
#              SIMULATED: the macros are blackboxes here and the ROM has
#              no contents.
#
# In `stub` mode the stand-in is held as a hierarchy boundary across
# synthesis so `stat -liberty` reports its area separately and the SoC's
# logic area can be had by subtraction, in the same run that produced the
# netlist STA reads. The boundary is released before the final flatten,
# by flow/syn_soc.sh's own argument about deferred flatten.
# ---------------------------------------------------------------------
#
# IBEX_REGFILE and IBEX_FAULT_PORT default to the design AS SHIPPED --
# `secded` and `1` -- and not to flow/syn_ibex.sh's `upstream` / `0`.
# The difference is deliberate and is flow/ibex_sources.sh's rule: the
# SoC flows build the design as it would ship, the standalone
# measurement flows reproduce a published number unless asked otherwise.
# soc_top.v connects rf_ecc_err_o unconditionally, so IBEX_FAULT_PORT=0
# here fails at elaboration with the port's name in the message.
#
# IBEX_RF_SYNPRE=1 hoists the register file's syndrome tree past the read
# multiplexer -- hw/soc/rtl/ibex_regfile_secded.v's SYNPRE, one parity
# tree per register. It DEFAULTS TO 0 and nothing sets it; the same rule
# flow/syn_ibex.sh states for the same parameter applies here, and
# sw/tests/test_soc_regfile_guards.py enforces it. docs/44 section 5.5
# priced it on the register file alone and docs/49 measures it through
# place-and-route, which is the only reason this knob exists on the
# whole-SoC flow at all.
#
# SOC_MEM_RDREG=1 is soc_top.v's MEM_RDREG, docs/50's knob: one register
# stage on the RAM's and the boot ROM's read return, which in
# SOC_MEM=sram means one flip-flop bank between the SRAM macros' A_DOUT
# multiplexer and everything downstream of it. IT DEFAULTS TO 0 and at 0
# nothing is emitted, so the script takes the path it took before the
# knob existed; the control is that the netlist is then byte-identical to
# the one docs/47 hardened, and docs/50 section 2 measures that it is.
#
# THE CHPARAM IS ON soc_top AND NOT ON soc_mem, deliberately. In
# SOC_MEM=stub and SOC_MEM=blackbox the module called `soc_mem` is a
# generated stand-in, and a chparam on a module that does not declare the
# parameter is an error rather than a no-op. Going through soc_top's own
# parameter means the four `soc_mem` implementations -- the behavioural
# model, the SRAM build, the stand-in and the blackbox -- all have to
# declare RDREG, which is a compile-time check that they agree on the
# boundary. sw/tests/test_soc_synthesis_guards.py checks the port lists;
# this checks the parameter.

set -euo pipefail

PERIOD_NS=${1:-20}
SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${2:-$SOC_DIR/out/soc-top}
RTL=$SOC_DIR/rtl
# hw/rtl/tmr_voter.v, secded_enc.v and secded_dec.v are READ from the
# pilot's directory and never modified.
PILOT_RTL=$(cd "$SOC_DIR/../rtl" && pwd)

SOC_MEM=${SOC_MEM:-stub}
case "$SOC_MEM" in
  stub|blackbox|array|sram) ;;
  *) echo "SOC_MEM must be stub, blackbox, array or sram, got '$SOC_MEM'" >&2
     exit 2 ;;
esac

IBEX_REGFILE=${IBEX_REGFILE:-secded}
IBEX_FAULT_PORT=${IBEX_FAULT_PORT:-1}
export IBEX_REGFILE IBEX_FAULT_PORT

# The hoisted syndrome, off by default. `chparam` on a module that does
# not declare the parameter is an error and not a no-op, so it is only
# emitted for this project's register file -- upstream's file has no
# SYNPRE. At 0 NOTHING is emitted, so the script takes the same path it
# took before this knob existed, and the control in docs/49 section 3 is
# that the netlist is byte-identical to the one docs/47 hardened.
IBEX_RF_SYNPRE=${IBEX_RF_SYNPRE:-0}
RF_CHPARAM="# IBEX_REGFILE=$IBEX_REGFILE: no register file chparam"
if [ "$IBEX_REGFILE" = "secded" ] && [ "$IBEX_RF_SYNPRE" != 0 ]; then
  RF_CHPARAM="chparam -set SYNPRE $IBEX_RF_SYNPRE ibex_register_file_ff"
fi

# docs/50's knob, on soc_top's own parameter. See the header.
SOC_MEM_RDREG=${SOC_MEM_RDREG:-0}
TOP_CHPARAM="# SOC_MEM_RDREG=0: no soc_top chparam"
if [ "$SOC_MEM_RDREG" != 0 ]; then
  TOP_CHPARAM="chparam -set MEM_RDREG $SOC_MEM_RDREG soc_top"
fi
# shellcheck source=hw/soc/flow/ibex_sources.sh
. "$SOC_DIR/flow/ibex_sources.sh"

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${YOSYS:?}" "${SG13G2_TYP:?}"

for f in "$RTL/soc_memmap.vh" "$RTL/soc_pnp_rom.vh" "$RTL/soc_apb_pnp_rom.vh"; do
  [ -f "$f" ] || {
    echo "missing $f: run 'python regmap/generate_memmap.py' first" >&2
    exit 1; }
done

rm -rf "$OUT"; mkdir -p "$OUT"

IBEX_SRCS=$(ibex_sources "$SOC_DIR" | tr '\n' ' ')

SOC_SRCS="$RTL/soc_bus.v $RTL/soc_apb_bridge.v $RTL/soc_uart.v \
$RTL/soc_gpio.v $RTL/soc_qspi.v $RTL/soc_pnp.v $RTL/soc_apb_pnp.v $RTL/soc_clint.v \
$RTL/soc_gptimer.v \
$RTL/soc_wdog.v $RTL/soc_busstat.v $RTL/soc_tmr_bank.v \
$PILOT_RTL/tmr_voter.v"

# ---- THE ACCELERATOR, WHICH WAS MISSING ------------------------------
#
# docs/51 put `u_npu` inside soc_top.v and this list was not updated, so
# from that commit until docs/61 this script did not elaborate at all:
#
#   ERROR: Module `\soc_npu' referenced in module `\soc_top' in cell
#          `\u_npu' is not part of the design.
#
# docs/57 section 3.2 found it and docs/59 section 7 found it again from
# the DEF. Everything docs/45, 47, 48, 49, 50 and 53 measure is a
# `soc_top` that this script could still build when they were written and
# that no longer exists: 27,565 cells against 41,543, 3,085 flip-flops
# against 5,237.
#
# THERE IS NO KNOB HERE AND THERE CANNOT BE ONE. soc_top.v instantiates
# u_npu unconditionally, so "without the NPU" is not a configuration of
# this design -- it is a different design, and the only artefact of it is
# the netlist already on disk at hw/soc/out/s47-sram/soc_top.netlist.v.
# A SOC_NPU=0 mode would not reproduce that netlist; it would fail to
# elaborate, exactly as this script did before this block was added.
#
# soc_npu.v instantiates hw/rtl/pilot_top.v -- the FROZEN pilot, docs/34
# -- rather than copying it, so pilot_top.v, lif_core.v, aer_fifo.v and
# scrub.v are READ out of hw/rtl/ and never modified, exactly as
# flow/sim_soc.sh reads them. The include path is needed for both
# directions: soc_npu.v includes rtl/soc_npu_regs.vh and pilot_top.v
# includes hw/rtl/npu_regs.vh.
#
# secded_enc.v and secded_dec.v have TWO consumers -- the register-file
# codec at IBEX_REGFILE=secded and lif_core's weight-word ECC -- and a
# module declared twice is an error. ibex_sources() supplies them in the
# secded configuration, so this list supplies them only in the other one.
# The rule and its wording are flow/sim_soc.sh's; there is one SECDED
# codec in this repository and both consumers read it from hw/rtl/.
NPU_SRCS="$RTL/soc_npu.v $RTL/soc_npu_ser.v \
$PILOT_RTL/pilot_top.v $PILOT_RTL/lif_core.v $PILOT_RTL/aer_fifo.v \
$PILOT_RTL/scrub.v"
if [ "$IBEX_REGFILE" != secded ]; then
  NPU_SRCS="$NPU_SRCS $PILOT_RTL/secded_enc.v $PILOT_RTL/secded_dec.v"
fi

# ---- the memory boundary --------------------------------------------
MEM_READ=""
MEM_ANCHOR="# SOC_MEM=$SOC_MEM: no memory hierarchy anchor"
MEM_RELEASE=""
PNR=$SOC_DIR/pnr
case "$SOC_MEM" in
  array)
    MEM_READ="read_verilog -I$RTL -defer $RTL/soc_mem.v"
    ;;
  sram)
    # The macro DECLARATIONS first, with -lib, so `soc_mem` resolves
    # against them and synthesis leaves the six instances alone. Nothing
    # downstream of a blackbox output is deleted and nothing driving a
    # blackbox input is either, so the fabric logic around the memories
    # and the bank multiplexers inside soc_mem_sram.v are all measured.
    MEM_READ="read_verilog -lib $PNR/RM_IHPSG13_1P_2048x64_c2_bm_bist_bb.v
read_verilog -lib $PNR/RM_IHPSG13_1P_1024x32_c2_bm_bist_bb.v
read_verilog -I$RTL -defer $RTL/soc_mem_sram.v"
    ;;
  blackbox)
    # A port declaration and nothing else. read_verilog -lib makes it a
    # blackbox, so hierarchy resolves the instances and synthesis leaves
    # them alone. Nothing downstream of a blackbox output is deleted,
    # and nothing driving a blackbox input is either, so the fabric
    # logic around the memories is measured in full.
    cat > "$OUT/soc_mem_bb.v" <<'EOF'
// BLACKBOX DECLARATION, generated by hw/soc/flow/syn_soc_top.sh.
// Not part of the design. Read with `read_verilog -lib`.
module soc_mem #(
    parameter integer WORDS     = 4096,
    parameter         RO        = 1'b0,
    parameter         INIT_FILE = "",
    parameter integer INIT_WORD = 0,
    parameter         RDREG     = 1'b0
) (
    input  wire        clk_i, rst_ni,
    input  wire        req_i,
    input  wire [31:0] addr_i,
    input  wire        we_i,
    input  wire [3:0]  be_i,
    input  wire [31:0] wdata_i,
    output wire        gnt_o,
    output wire        rvalid_o,
    output wire [31:0] rdata_o,
    output wire        err_o
);
endmodule
EOF
    MEM_READ="read_verilog -lib $OUT/soc_mem_bb.v"
    ;;
  stub)
    # MACRO STAND-IN. See the header. Ports and protocol timing are
    # soc_mem's; the array is not.
    cat > "$OUT/soc_mem_macro.v" <<'EOF'
// SRAM MACRO STAND-IN, generated by hw/soc/flow/syn_soc_top.sh.
//
// NOT PART OF THE DESIGN and NOT FUNCTIONAL. It exists so that soc_top
// can be synthesised and timed as one design without synthesising
// 589,824 registers of behavioural memory model.
//
// What it reproduces of hw/soc/rtl/soc_mem.v, and it is exactly the part
// that a timing report can see across the boundary:
//
//   * the ports, in name, width and direction
//   * gnt_o = req_i, combinational -- soc_bus.v rule S1 depends on it,
//     and it is the one real combinational path through this boundary
//   * rvalid_o and err_o registered from req_i / we_i, one cycle
//   * every remaining input CAPTURED in a flip-flop, so a path from the
//     fabric into a memory ends at a setup check the way it would end at
//     an SRAM macro's address register
//   * rdata_o driven from a flip-flop, so a path out of a memory starts
//     at a clock-to-Q the way it would start at a macro's output
//
// What it does NOT reproduce: the storage, the address decode, the read
// multiplexer, and a macro's clock-to-Q and setup, which are much larger
// than a standard-cell flip-flop's. Every number measured through this
// boundary inherits those four limits.
`timescale 1ns / 1ps
module soc_mem #(
    parameter integer WORDS     = 4096,
    parameter         RO        = 1'b0,
    parameter         INIT_FILE = "",
    parameter integer INIT_WORD = 0,
    // docs/50's response register. Reproduced here for the same reason
    // every other timing property of soc_mem is: at RDREG = 1 a path out
    // of a memory starts one flip-flop LATER, and a stand-in that did
    // not follow would time the wrong boundary.
    parameter         RDREG     = 1'b0
) (
    input  wire        clk_i,
    input  wire        rst_ni,
    input  wire        req_i,
    input  wire [31:0] addr_i,
    input  wire        we_i,
    input  wire [3:0]  be_i,
    input  wire [31:0] wdata_i,
    output wire        gnt_o,
    output wire        rvalid_o,
    output wire [31:0] rdata_o,
    output wire        err_o
);
  reg [31:0] row;
  reg [29:0] a_q;
  reg [3:0]  be_q;
  reg        we_q;
  reg [31:0] rd0;
  reg        rv0, er0;

  assign gnt_o = req_i;

  wire write_attempt = req_i && we_i;
  wire do_write      = write_attempt && !RO;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rv0      <= 1'b0;
      rd0      <= 32'h0;
      er0      <= 1'b0;
      row      <= 32'h0;
      a_q      <= 30'h0;
      be_q     <= 4'h0;
      we_q     <= 1'b0;
    end else begin
      rv0      <= req_i;
      er0      <= write_attempt && RO;
      a_q      <= addr_i[31:2];
      be_q     <= be_i;
      we_q     <= we_i;
      if (do_write) begin
        if (be_i[0]) row[7:0]   <= wdata_i[7:0];
        if (be_i[1]) row[15:8]  <= wdata_i[15:8];
        if (be_i[2]) row[23:16] <= wdata_i[23:16];
        if (be_i[3]) row[31:24] <= wdata_i[31:24];
      end
      // A function of the captured inputs, so none of the capture
      // registers is dead and opt_clean cannot delete the endpoints
      // this stand-in exists to provide.
      rd0 <= row ^ {a_q[29:28] ^ {2{we_q}}, a_q[27:0], be_q[3:2], be_q[1:0]};
    end
  end

  generate
  if (!RDREG) begin : g_rd1
    assign rvalid_o = rv0;
    assign rdata_o  = rd0;
    assign err_o    = er0;
  end
  if (RDREG) begin : g_rd2
    reg [31:0] rd1;
    reg        rv1, er1;
    always @(posedge clk_i or negedge rst_ni)
      if (!rst_ni) begin
        rv1 <= 1'b0; rd1 <= 32'h0; er1 <= 1'b0;
      end else begin
        rv1 <= rv0; er1 <= er0;
        if (rv0) rd1 <= rd0;
      end
    assign rvalid_o = rv1;
    assign rdata_o  = rd1;
    assign err_o    = er1;
  end
  endgenerate
endmodule
EOF
    MEM_READ="read_verilog -defer $OUT/soc_mem_macro.v"
    MEM_ANCHOR="setattr -mod -set keep_hierarchy 1 *soc_mem*"
    MEM_RELEASE="setattr -mod -set keep_hierarchy 0 *soc_mem*"
    ;;
esac

# ---- SOC_KEEP_HIER, a DIAGNOSTIC and not the measurement -------------
#
# With SOC_KEEP_HIER=1 the direct children of soc_top -- the core, the
# fabric, the bridge and the peripherals -- are held as hierarchy
# boundaries. `flatten` skips a module carrying keep_hierarchy, so each
# child is still flattened INTERNALLY and only the top-level boundaries
# survive. Two things become measurable that the flattened build cannot
# show: `stat -liberty` reports each block's area inside the integrated
# design, and OpenSTA's path reports carry hierarchical instance names,
# so a critical path can be attributed to a block rather than inferred
# from whichever nets happened to keep a public name.
#
# IT IS A DIFFERENT NETLIST AND ITS SLACK IS NOT THE HEADLINE. A kept
# boundary blocks constant propagation across it, and soc_top.v drives
# `cheriot_enable_i` with a constant -- docs/44 section 5.1's whole
# subject. In this mode that constant stops at the port and the CHERIoT
# logic comes back, so the design it times is not the design the flatten
# builds. Both are run and docs/45 quotes both, labelled.
KEEP_HIER_SET="# SOC_KEEP_HIER=0: soc_top is flattened whole"
KEEP_HIER_FLATTEN="attrmap -modattr -remove keep_hierarchy
flatten"
KEEP_HIER_TOTAL="# SOC_KEEP_HIER=0: area.rpt is already the whole design"
SPLIT_PORTS=""
AREA_SUMMARY=area.rpt
if [ "${SOC_KEEP_HIER:-0}" = 1 ]; then
  KEEP_HIER_SET="setattr -mod -set keep_hierarchy 1 *ibex_top* *soc_bus* \
*soc_apb_bridge* *soc_uart* *soc_pnp* *soc_apb_pnp* *soc_clint* \
*soc_gptimer* *soc_mem*"
  KEEP_HIER_FLATTEN="# SOC_KEEP_HIER=1: the block boundaries are kept"
  # `stat -liberty` on a hierarchical design reports each module's LOCAL
  # area and rounds the roll-up to two significant figures, so the whole
  # design's total is taken from a flattened COPY. Flattening after
  # technology mapping moves no cell, so this total is exact for the
  # netlist above and is not a second synthesis.
  KEEP_HIER_TOTAL="design -push-copy
attrmap -modattr -remove keep_hierarchy
flatten
opt_clean -purge
tee -o $OUT/area_total.rpt stat -liberty $SG13G2_TYP
design -pop"
  # Ports as well as nets, so a bus that crosses a kept boundary is
  # split consistently on both sides of it.
  SPLIT_PORTS="-ports"
  AREA_SUMMARY=area_total.rpt
fi

# SOC_ELAB_ONLY=1 stops after `hierarchy -check`, which is the question
# docs/45 section 5 asks on its own: does the whole design RESOLVE? It is
# the only way to run SOC_MEM=array to a conclusion in a sensible time,
# because what follows would then be a synthesis of 589,824 registers of
# behavioural memory model.
cat > "$OUT/abc.constr" <<EOF
set_driving_cell sg13g2_buf_4
set_load 0.005
EOF

cat > "$OUT/soc_top_syn.ys" <<EOF
read_liberty -lib $SG13G2_TYP

read_verilog -defer $RTL/prim_clock_gating.v
read_verilog -defer $IBEX_SRCS
read_verilog -I$RTL -defer $SOC_SRCS
read_verilog -I$RTL -I$PILOT_RTL -defer $NPU_SRCS
$MEM_READ
read_verilog -I$RTL -defer $RTL/soc_top.v

$RF_CHPARAM
$TOP_CHPARAM

hierarchy -check -top soc_top

# Upstream's redundancy anchors, unconditionally, exactly as
# syn/ibex_syn.ys.in applies them. At SecureIbex = 0 these modules are
# absent and the setattr is a no-op.
setattr -mod -set keep_hierarchy 1 *prim_generic_and2*
setattr -mod -set keep_hierarchy 1 *prim_generic_buf*
setattr -mod -set keep_hierarchy 1 *prim_generic_clock_mux2*
setattr -mod -set keep_hierarchy 1 *prim_generic_flop*
# hw/soc/rtl/soc_tmr_bank.v carries keep_hierarchy as one of its two
# anti-merge defences and it must survive to abc, or the watchdog's
# triplicated state is voted away by the optimiser -- docs/41.
$MEM_ANCHOR
$KEEP_HIER_SET

synth -flatten -top soc_top
opt -purge

write_verilog $OUT/soc_top.pre_map.v

dfflibmap -liberty $SG13G2_TYP
opt
abc -liberty $SG13G2_TYP -constr $OUT/abc.constr -D $PERIOD_NS

# Per-module area BEFORE the deferred flatten, so the memory stand-in's
# contribution is separable in the same run that produced the netlist.
tee -o $OUT/area_hier.rpt stat -liberty $SG13G2_TYP

setattr -mod -set keep_hierarchy 0 *prim_generic_and2*
setattr -mod -set keep_hierarchy 0 *prim_generic_buf*
setattr -mod -set keep_hierarchy 0 *prim_generic_clock_mux2*
setattr -mod -set keep_hierarchy 0 *prim_generic_flop*
$MEM_RELEASE
$KEEP_HIER_FLATTEN
setundef -zero
opt_clean -purge

write_verilog -noattr $OUT/soc_top.netlist.v

splitnets $SPLIT_PORTS
clean
write_verilog -noattr -noexpr -nohex -nodec $OUT/soc_top.sta.v

check
tee -o $OUT/area.rpt stat -liberty $SG13G2_TYP
tee -o $OUT/hierarchy.rpt stat
$KEEP_HIER_TOTAL
EOF

# SOC_ELAB_ONLY=1 truncates the script after `hierarchy -check`, which
# is the question docs/45 section 5 asks on its own: does the whole
# design RESOLVE? It is the only way to run SOC_MEM=array to a
# conclusion in a sensible time, because what follows would then be a
# synthesis of 589,824 registers of behavioural memory model. yosys has
# no `exit`, so the script is cut rather than branched.
if [ "${SOC_ELAB_ONLY:-0}" = 1 ]; then
  sed -e '/^hierarchy -check/q' "$OUT/soc_top_syn.ys" > "$OUT/soc_top_elab.ys"
  echo "stat" >> "$OUT/soc_top_elab.ys"
  "$YOSYS" -l "$OUT/syn.log" -s "$OUT/soc_top_elab.ys" > /dev/null
  echo "elaboration only (SOC_ELAB_ONLY=1), mem=$SOC_MEM"
  grep -E "End of script|Warnings:" "$OUT/syn.log" || true
  echo "  log: $OUT/syn.log"
  exit 0
fi

"$YOSYS" -l "$OUT/syn.log" -s "$OUT/soc_top_syn.ys" > /dev/null

awk -v top=soc_top -v ge=7.2576 '
  $NF == "cells"                      { cells = $1 }
  $NF ~ /^sg13g2_(s?df|dl[hl])/       { ff += $1 }
  /Chip area for module/              { gsub(/[^0-9.]/, "", $NF); area = $NF + 0 }
  END {
    printf "%-22s cells=%-6d flops=%-6d area_um2=%.4f  kGE=%.3f\n",
           top, cells, ff, area, area / ge / 1000.0
  }
' "$OUT/$AREA_SUMMARY"

echo "  mem=$SOC_MEM  regfile=$IBEX_REGFILE  fault_port=$IBEX_FAULT_PORT  synpre=$IBEX_RF_SYNPRE"
echo "  mem_rdreg=$SOC_MEM_RDREG  abc -D $PERIOD_NS"
echo "  report: $OUT/$AREA_SUMMARY  per-module: $OUT/area_hier.rpt"
echo "  netlist: $OUT/soc_top.netlist.v  sta: $OUT/soc_top.sta.v  log: $OUT/syn.log"
