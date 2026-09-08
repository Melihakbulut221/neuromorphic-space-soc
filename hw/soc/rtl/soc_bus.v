// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// System fabric: two Ibex-native masters onto four slave ports plus an
// internal error slave.
//
// The interconnect decision this file implements, and the AHB option it
// declines, are docs/39-soc-bus-and-memory-map.md sections 3 and 4.
// Short version: the fabric protocol is Ibex's own req/gnt/rvalid, which
// is the protocol both masters already speak, so nothing is translated
// on the critical path. AMBA APB appears at the peripheral boundary
// (soc_apb_bridge.v) because that is where a standard protocol buys
// something. There is no AHB anywhere in this SoC and none is claimed.
//
// =====================================================================
// THE PROTOCOL, which is a specification and not a description of this
// file
// =====================================================================
//
// Taken verbatim from Ibex's load/store unit reference,
// ext/ibex/doc/03_reference/load_store_unit.rst, section "Protocol",
// because that document is the normative statement of what the two
// masters do and this fabric has to be correct against it rather than
// against itself:
//
//   1. The master drives a valid address and asserts req. For a store it
//      also drives we, be and wdata. The slave answers with gnt as soon
//      as it is ready. That may be the same cycle or any number of
//      cycles later.
//   2. After a grant the address, wdata, we and be MAY CHANGE in the next
//      cycle. The slave is assumed to have captured them.
//   3. The slave answers with rvalid high for EXACTLY ONE CYCLE per
//      granted request, carrying rdata and err in that same cycle. It may
//      be one or more cycles after the grant.
//   4. When multiple granted requests are outstanding, responses are
//      returned IN ORDER, one rvalid each.
//
// Rule 3 applies to writes as well as reads: every granted request gets
// exactly one rvalid, and for a write the rdata is meaningless.
//
// =====================================================================
// WHAT THIS FABRIC REQUIRES OF A SLAVE
// =====================================================================
//
// S1. Rules 1-4 above, from the slave side.
// S2. The address, we, be and wdata buses are BROADCAST to every slave
//     and are valid only in the cycle where that slave's own req and gnt
//     are both high. A slave must capture what it needs in that cycle.
// S3. In-order responses even when the two masters are interleaved. A
//     slave sees one request stream; the fabric restores the per-master
//     ordering from it, and can only do that if the slave does not
//     reorder.
// S4. At most MAX_OUT requests per master may be outstanding at a slave,
//     so at most 2*MAX_OUT in total. The fabric enforces this by
//     withholding grants; a slave does not have to.
//
// =====================================================================
// THE ONE RESTRICTION THIS FABRIC IMPOSES ON A MASTER, AND WHY
// =====================================================================
//
// A master may have several requests outstanding, but they must all be
// to the SAME slave. A request to a different slave is not granted until
// the master's outstanding count reaches zero.
//
// The reason is protocol rule 4. Slaves have different latencies -- the
// RAM answers in one cycle, the peripheral bridge in four or more. If a
// master could issue to the bridge and then to the RAM, the RAM's answer
// would arrive first and the master would see its responses out of
// order, which rule 4 forbids and which Ibex's prefetch buffer and LSU
// both rely on.
//
// The alternatives were: a reorder buffer (real area, and it has to
// store a full response), or one outstanding request per master (which
// halves instruction fetch bandwidth, because a fetch could then only be
// issued after the previous one returned). This restriction costs
// nothing in the case that actually happens -- linear instruction fetch
// out of one memory -- and costs one dead cycle when a master switches
// target, which for the data port is most accesses and for the
// instruction port is a branch across a region boundary.
//
// MAX_OUT is 2 because that is what Ibex issues: NUM_REQS = 2 in
// ext/ibex/rtl/ibex_prefetch_buffer.sv, and the load/store unit issues a
// second request before the first response during a split misaligned
// access (ext/ibex/rtl/ibex_load_store_unit.sv, WAIT_RVALID_MIS).
//
// =====================================================================
// ARBITRATION
// =====================================================================
//
// Round-robin between the two masters: the one that did not win last
// wins a tie. Fixed priority to the data port would have been simpler
// and is what most small systems do, but round-robin makes the
// no-starvation property provable in two cycles rather than argued from
// "the pipeline cannot issue loads without instructions", which is a
// statement about the core and not about this file.
//
// =====================================================================
// THE CLOCK-GATE ENABLE, AND WHY IT IS AN OUTPUT AND NOT A GATE
// =====================================================================
//
// `clk_en_o` is a combinational statement about this cycle: it is high
// whenever any register in this module CAN change value at the edge
// that ends the cycle. It is not a power-management policy and it does
// not read `core_sleep_o` or any other block's state; it is a property
// of this file's own next-state functions, and its whole content is:
//
//   G1. `issue_en` moves only while it is 0.
//   G2. `last_was_d` moves only on `accepted`, and `accepted` implies
//       `any_win`, which implies one of the two masters is requesting.
//   G3. `err_rvalid` is set only by `accepted` and is cleared only when
//       it is already 1.
//   G4. `q_owner` and `q_fill` move only on a push or a pop. A push
//       implies `accepted`; a pop is `slv_rvalid`, which is
//       `{err_rvalid, s_rvalid_i}`.
//   G5. `cnt_i`, `cnt_d`, `lock_i` and `lock_d` move only on a grant or
//       an rvalid. A grant implies a request; an rvalid to a master
//       implies a `slv_rvalid`.
//
// THE GATE ITSELF IS IN soc_top.v, not here, and that placement is the
// whole reason the fabric's proofs did not have to be re-argued. Every
// property in hw/soc/formal/soc_bus_props.v samples `posedge clk_i`. If
// this module gated its own clock, F1 to F9 would be properties of a
// design whose clock the property set could not see, and the fairness
// bound F9 in particular -- which counts CYCLES -- would be counting
// something else. Instead this module is proved AS WRITTEN, on an
// ungated clock, and one added property F10 states G1 to G5 as a
// theorem: in every cycle where `clk_en_o` is low, no register in this
// module changes value. F10 is what licenses soc_top.v to replace
// `clk_i` with `ICG(clk_i, clk_en_o)`, because a design whose state does
// not change is a design whose state does not change whether or not it
// is clocked. F1 to F9 are therefore not weakened, not re-stated and
// not re-proved against a gated slave: they are transported unchanged.
//
// AND NOTHING ABOUT THIS ENABLE IS VISIBLE TO A SLAVE. `s_req_o`,
// `s_addr_o` and the grant outputs are combinational, so the fabric
// answers a master in the cycle it asks whether or not the previous
// cycle was clocked.
//
// THE ONE OBLIGATION THIS CREATES IS A STATIC-TIMING ONE, AND IT IS A
// FULL CYCLE AND NOT A HALF ONE. `sg13g2_lgcp_1` is
// `clock_gating_integrated_cell : "latch_posedge"`: the latch is
// transparent while CLK is low and CLOSES on the rising edge, so the
// value that decides an edge is the enable's settled value during the
// cycle that edge ends, and OpenSTA's clock gating check requires it
// stable at that rising edge. It is an ordinary setup path that happens
// to end at a clock gate, derived from the cell's Liberty with no
// constraint written by hand, and docs/76 section 9.5 measures what it
// costs on the placed design: this enable's check MET by +0.7197 ns at
// the slow corner before detailed routing and misses by -0.7495 ns
// after it, on a design that fails setup at that corner on 3,055
// endpoints without it.

`timescale 1ns / 1ps

module soc_bus (
    input  wire        clk_i,
    input  wire        rst_ni,

    // ---- master 0: Ibex instruction port. Read-only. ----
    input  wire        mi_req_i,
    input  wire [31:0] mi_addr_i,
    output wire        mi_gnt_o,
    output wire        mi_rvalid_o,
    output wire [31:0] mi_rdata_o,
    output wire        mi_err_o,

    // ---- master 1: Ibex data port ----
    input  wire        md_req_i,
    input  wire [31:0] md_addr_i,
    input  wire        md_we_i,
    input  wire [3:0]  md_be_i,
    input  wire [31:0] md_wdata_i,
    output wire        md_gnt_o,
    output wire        md_rvalid_o,
    output wire [31:0] md_rdata_o,
    output wire        md_err_o,

    // ---- slave ports. Address and write data are broadcast (S2). ----
    // Index order is fixed and is the order the decode below assigns:
    //   0 RAM, 1 ROM, 2 APB, 3 PNP, 4 CLINT, 5 NPU. Index 6 is the
    //   internal error slave and has no port.
    output wire [5:0]  s_req_o,
    output wire [31:0] s_addr_o,
    output wire        s_we_o,
    output wire [3:0]  s_be_o,
    output wire [31:0] s_wdata_o,
    input  wire [5:0]  s_gnt_i,
    input  wire [5:0]  s_rvalid_i,
    input  wire [31:0] s_rdata_0_i,
    input  wire [31:0] s_rdata_1_i,
    input  wire [31:0] s_rdata_2_i,
    input  wire [31:0] s_rdata_3_i,
    input  wire [31:0] s_rdata_4_i,
    input  wire [31:0] s_rdata_5_i,
    input  wire [5:0]  s_err_i,

    // ---- clock-gate enable. See the header, and F10. ----
    output wire        clk_en_o
);

`include "soc_memmap.vh"

  // Six targets: five ports plus the error slave. NS is not a parameter
  // because the decode below names the regions individually; adding a
  // region means editing both, and hw/soc/tb/cocotb/test_soc_bus.py
  // checks the decode against the generated map rather than against this
  // file, so the two cannot silently disagree.
  //
  // Port 4 (CLINT) is the one added by
  // docs/40-interrupts-timers-watchdog.md. It is a system-bus slave and
  // not a peripheral behind the APB bridge, because the frozen map puts
  // it at 0xE0000000 as a region in its own right -- and because mtime
  // is read on every scheduler tick, so paying the bridge's three-cycle
  // minimum for it would be the wrong trade for the one register in this
  // SoC that software polls in a loop.
  //
  // Port 5 (NPU) is the one added by docs/51-npu-integration.md. It is a
  // system-bus slave and not a peripheral behind the APB bridge,
  // because the frozen map gives the NPU a 256 MiB REGION at
  // 0x10000000 rather than a 4 KiB peripheral slot -- and a 4 KiB slot
  // could not hold sixteen per-node register windows in the first
  // place. It is also, by a wide margin, the SLOWEST slave here: about
  // 172 cycles, against the peripheral bridge's three. soc_npu.v's
  // header records what that costs and where.
  localparam integer NS      = 7;
  localparam integer ERRSLV  = 6;
  localparam integer MAX_OUT = 2;

  // -------------------------------------------------------------------
  // Address decode, once per master.
  //
  // Decoding both masters before arbitration rather than decoding the
  // winner afterwards costs a second comparator set and buys the
  // same-slave check below, which has to know each master's target
  // whether or not that master is winning this cycle.
  // -------------------------------------------------------------------
  function [2:0] decode;
    input [31:0] a;
    begin
      if      ((a & SOC_MASK_RAM) == SOC_BASE_RAM) decode = 3'd0;
      else if ((a & SOC_MASK_ROM) == SOC_BASE_ROM) decode = 3'd1;
      else if ((a & SOC_MASK_APB) == SOC_BASE_APB) decode = 3'd2;
      else if ((a & SOC_MASK_PNP) == SOC_BASE_PNP) decode = 3'd3;
      else if ((a & SOC_MASK_CLINT) == SOC_BASE_CLINT)
                                                   decode = 3'd4;
      else if ((a & SOC_MASK_NPU) == SOC_BASE_NPU) decode = 3'd5;
      else                                         decode = ERRSLV[2:0];
    end
  endfunction

  wire [2:0] tgt_i = decode(mi_addr_i);
  wire [2:0] tgt_d = decode(md_addr_i);

  // -------------------------------------------------------------------
  // Per-master outstanding accounting
  // -------------------------------------------------------------------
  reg  [1:0] cnt_i, cnt_d;      // 0..MAX_OUT
  reg  [2:0] lock_i, lock_d;    // slave the outstanding requests went to

  // The request path has to be dead while the design is held in reset.
  // Without a gate the request and grant paths, which are purely
  // combinational, stay live: a master driving req during reset would
  // have a transaction ACCEPTED by a slave, while the response queues
  // and counters are held at zero. The slave's response would then
  // arrive after reset release and pop a queue that never recorded the
  // request, underflowing the accounting. Ibex holds its request ports
  // low in reset so this cannot happen in this SoC, but "cannot happen
  // because of the master we happen to have" is not a property of this
  // file. It was found by the cocotb suite driving requests during
  // reset, which is why that test exists.
  //
  // THE GATE IS A LOCAL FLIP-FLOP AND NOT rst_ni ITSELF, and the reason
  // is measured rather than stylistic. Until docs/47 this read
  // `rst_ni && ...`, and docs/45 section 7.2 found what that costs at
  // the top level: it puts the SoC's LARGEST net -- rst_sys_n, 2,766
  // flip-flop reset pins in the whole-design netlist -- into a purely
  // COMBINATIONAL datapath. These two gates were its only two data
  // sinks, and they were enough to make the worst SYNCHRONOUS setup
  // path (-60.6191 ns at the slow corner) worse than the worst
  // asynchronous recovery path (-53.3681). Building the reset tree is
  // place-and-route's obligation; putting a data path through it is
  // this file's decision, and it is reversed here.
  //
  // `issue_en` is cleared asynchronously by rst_ni exactly as every
  // other register in this file is, and set on the first clock edge
  // after release. Its fanout is two. The behaviour is strictly more
  // conservative than gating with rst_ni directly: the fabric stays
  // closed for one ADDITIONAL cycle after reset deassertion, during
  // which the counters and queues this gate exists to protect are
  // already released. The cost is one flip-flop and one cycle of
  // latency on the first transaction after a reset, once, at boot.
  // docs/47 section 5.
  reg issue_en;
  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni) issue_en <= 1'b0;
    else         issue_en <= 1'b1;

  wire can_issue_i = issue_en && mi_req_i &&
                     ((cnt_i == 2'd0) ||
                      ((lock_i == tgt_i) && (cnt_i < MAX_OUT[1:0])));
  wire can_issue_d = issue_en && md_req_i &&
                     ((cnt_d == 2'd0) ||
                      ((lock_d == tgt_d) && (cnt_d < MAX_OUT[1:0])));

  // -------------------------------------------------------------------
  // Round-robin arbitration
  // -------------------------------------------------------------------
  reg  last_was_d;
  wire d_wins = can_issue_d && (!can_issue_i || !last_was_d);
  wire i_wins = can_issue_i && !d_wins;

  wire [2:0]  tgt      = d_wins ? tgt_d : tgt_i;
  wire        any_win  = d_wins || i_wins;

  // The error slave is inside this module and is always ready. A real
  // slave port answers with its own gnt.
  wire target_ready = (tgt == ERRSLV[2:0]) ? 1'b1 : s_gnt_i[tgt];
  wire accepted     = any_win && target_ready;

  assign mi_gnt_o = i_wins && target_ready;
  assign md_gnt_o = d_wins && target_ready;

  // Broadcast request payload (S2).
  assign s_addr_o  = d_wins ? md_addr_i  : mi_addr_i;
  assign s_we_o    = d_wins ? md_we_i    : 1'b0;
  assign s_be_o    = d_wins ? md_be_i    : 4'hF;
  assign s_wdata_o = d_wins ? md_wdata_i : 32'h0;

  assign s_req_o[0] = any_win && (tgt == 3'd0);
  assign s_req_o[1] = any_win && (tgt == 3'd1);
  assign s_req_o[2] = any_win && (tgt == 3'd2);
  assign s_req_o[3] = any_win && (tgt == 3'd3);
  assign s_req_o[4] = any_win && (tgt == 3'd4);
  assign s_req_o[5] = any_win && (tgt == 3'd5);

  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni)      last_was_d <= 1'b0;
    else if (accepted) last_was_d <= d_wins;

  // -------------------------------------------------------------------
  // The error slave: fixed one-cycle latency, always ready, err high.
  //
  // One flop, so it can accept a request every cycle and still return
  // exactly one rvalid per grant, in order (S1, S3). An unmapped access
  // therefore reaches the core as data_err_i, which Ibex turns into a
  // load or store access fault rather than a silent read of zero.
  // -------------------------------------------------------------------
  reg err_rvalid;
  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni) err_rvalid <= 1'b0;
    else         err_rvalid <= accepted && (tgt == ERRSLV[2:0]);

  wire [NS-1:0] slv_rvalid = {err_rvalid, s_rvalid_i};
  wire [NS-1:0] slv_err    = {1'b1,       s_err_i};

  // -------------------------------------------------------------------
  // Per-slave response ownership queues
  //
  // One bit per outstanding request: which master it belongs to. Depth
  // is 2*MAX_OUT because both masters may hold MAX_OUT at the same
  // slave. Because slaves answer in order (S3), the head of the queue
  // names the owner of the response arriving now.
  //
  // The queue is a shift register rather than a pointer FIFO: at depth 4
  // and width 1 the pointers would cost more than the storage.
  //
  // q_fill IS TWO BITS AND THAT IS DELIBERATE. The queue holds up to
  // QD = 4 entries, so a fill LEVEL would need three bits. This is not a
  // fill level, it is the write index, and the write index only ever
  // takes the values 0..3: a push at fill 4 is impossible, because fill 4
  // means both masters hold MAX_OUT at this slave, and then neither
  // can_issue. Modulo-4 is therefore exact for every value the index is
  // ever read at, and it decrements back through 4 -> 3 correctly because
  // 0 - 1 = 3.
  //
  // Written as three bits first, which measured 8,814.015 um2 against
  // 8,551.116 um2 for two -- and both reported the SAME 42 flip-flops,
  // because the third bit influences nothing outside itself and the
  // synthesiser removed it while keeping 41 cells of its arithmetic.
  // Two bits is what the design means, so two bits is what it says. The
  // property that makes it safe -- the queue never exceeds QD entries --
  // is not visible in a modulo counter, so it is proved separately with
  // a ghost counter in hw/soc/formal/soc_bus_props.v rather than left to
  // this comment.
  // -------------------------------------------------------------------
  localparam integer QD = 2 * MAX_OUT;

  reg  [QD-1:0] q_owner [0:NS-1];   // 1 = data port, 0 = instruction port
  reg  [1:0]    q_fill  [0:NS-1];   // write index, modulo QD

  wire [NS-1:0] push;
  assign push[0] = accepted && (tgt == 3'd0);
  assign push[1] = accepted && (tgt == 3'd1);
  assign push[2] = accepted && (tgt == 3'd2);
  assign push[3] = accepted && (tgt == 3'd3);
  assign push[4] = accepted && (tgt == 3'd4);
  assign push[5] = accepted && (tgt == 3'd5);
  assign push[6] = accepted && (tgt == ERRSLV[2:0]);

  integer s;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      for (s = 0; s < NS; s = s + 1) begin
        q_owner[s] <= {QD{1'b0}};
        q_fill[s]  <= 2'd0;
      end
    end else begin
      for (s = 0; s < NS; s = s + 1) begin
        case ({push[s], slv_rvalid[s]})
          2'b10: begin   // push only
            q_owner[s][q_fill[s]] <= d_wins;
            q_fill[s] <= q_fill[s] + 2'd1;
          end
          2'b01: begin   // pop only
            q_owner[s] <= {1'b0, q_owner[s][QD-1:1]};
            q_fill[s]  <= q_fill[s] - 2'd1;
          end
          2'b11: begin   // both: shift down, new entry at the new tail.
            // The bit-select assignment comes second on purpose: in
            // Verilog the later nonblocking assignment wins for the bits
            // it covers, so the queue shifts and the new entry lands at
            // the index the shift vacated, in one statement pair.
            q_owner[s] <= {1'b0, q_owner[s][QD-1:1]};
            q_owner[s][q_fill[s] - 2'd1] <= d_wins;
          end
          default: ;
        endcase
      end
    end
  end

  // -------------------------------------------------------------------
  // Response steering
  //
  // The same-slave restriction is what makes this a simple OR: a given
  // master's outstanding requests are all at one slave, so at most one
  // slave can be returning a response for it in any cycle. Without that
  // restriction two slaves could answer the same master in one cycle and
  // one of the two answers would be lost.
  // -------------------------------------------------------------------
  wire [NS-1:0] resp_to_d, resp_to_i;
  wire [31:0]   slv_rdata [0:NS-1];

  assign slv_rdata[0] = s_rdata_0_i;
  assign slv_rdata[1] = s_rdata_1_i;
  assign slv_rdata[2] = s_rdata_2_i;
  assign slv_rdata[3] = s_rdata_3_i;
  assign slv_rdata[4] = s_rdata_4_i;
  assign slv_rdata[5] = s_rdata_5_i;
  assign slv_rdata[6] = 32'h0;      // error slave returns no data

  genvar g;
  generate
    for (g = 0; g < NS; g = g + 1) begin : g_resp
      assign resp_to_d[g] = slv_rvalid[g] &&  q_owner[g][0];
      assign resp_to_i[g] = slv_rvalid[g] && !q_owner[g][0];
    end
  endgenerate

  assign md_rvalid_o = |resp_to_d;
  assign mi_rvalid_o = |resp_to_i;

  assign md_rdata_o = ({32{resp_to_d[0]}} & slv_rdata[0])
                    | ({32{resp_to_d[1]}} & slv_rdata[1])
                    | ({32{resp_to_d[2]}} & slv_rdata[2])
                    | ({32{resp_to_d[3]}} & slv_rdata[3])
                    | ({32{resp_to_d[4]}} & slv_rdata[4])
                    | ({32{resp_to_d[5]}} & slv_rdata[5])
                    | ({32{resp_to_d[6]}} & slv_rdata[6]);
  assign mi_rdata_o = ({32{resp_to_i[0]}} & slv_rdata[0])
                    | ({32{resp_to_i[1]}} & slv_rdata[1])
                    | ({32{resp_to_i[2]}} & slv_rdata[2])
                    | ({32{resp_to_i[3]}} & slv_rdata[3])
                    | ({32{resp_to_i[4]}} & slv_rdata[4])
                    | ({32{resp_to_i[5]}} & slv_rdata[5])
                    | ({32{resp_to_i[6]}} & slv_rdata[6]);

  assign md_err_o = |(resp_to_d & slv_err);
  assign mi_err_o = |(resp_to_i & slv_err);

  // -------------------------------------------------------------------
  // Outstanding counters and slave locks
  // -------------------------------------------------------------------
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      cnt_i  <= 2'd0;
      cnt_d  <= 2'd0;
      lock_i <= 3'd0;
      lock_d <= 3'd0;
    end else begin
      case ({mi_gnt_o, mi_rvalid_o})
        2'b10:   cnt_i <= cnt_i + 2'd1;
        2'b01:   cnt_i <= cnt_i - 2'd1;
        default: ;
      endcase
      case ({md_gnt_o, md_rvalid_o})
        2'b10:   cnt_d <= cnt_d + 2'd1;
        2'b01:   cnt_d <= cnt_d - 2'd1;
        default: ;
      endcase
      if (mi_gnt_o) lock_i <= tgt_i;
      if (md_gnt_o) lock_d <= tgt_d;
    end
  end

  // -------------------------------------------------------------------
  // The clock-gate enable, which is the header's G1 to G5 written out
  //
  // Read it as one disjunction of five reasons this module might have
  // work to do at the end of this cycle:
  //
  //   !issue_en          G1: the boot cycle, once, ever.
  //   mi_req_i           G2, and the grant half of G5: a request is the
  //   md_req_i           precondition of every grant, and a grant is the
  //                      precondition of `accepted` and of every push.
  //   |s_rvalid_i        G4 and the response half of G5: a pop.
  //   err_rvalid         G3, and the error slave's own pop.
  //
  // `err_rvalid` is this module's own register and `issue_en` is too, so
  // the enable is a function of the ports plus two bits of state that
  // are themselves frozen while it is low -- which is the reason it
  // cannot get stuck: nothing inside can raise it, and nothing inside
  // needs to.
  //
  // NOT INCLUDED, deliberately: `cnt_i`, `cnt_d` and `q_fill`. A master
  // with an outstanding request is waiting for a slave, and waiting
  // costs this module nothing until the response arrives. Adding an
  // "outstanding" term would hold the clock on for the 172 cycles of an
  // NPU register access and buy nothing -- F10 is what says so, because
  // the enable it proves complete does not contain one.
  assign clk_en_o = !issue_en || mi_req_i || md_req_i
                 || (|s_rvalid_i) || err_rvalid;

`ifdef FORMAL
`include "soc_bus_props.v"
`endif

endmodule
