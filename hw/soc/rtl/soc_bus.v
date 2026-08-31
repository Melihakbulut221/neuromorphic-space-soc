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
    //   0 RAM, 1 ROM, 2 APB, 3 PNP. Index 4 is the internal error slave
    //   and has no port.
    output wire [3:0]  s_req_o,
    output wire [31:0] s_addr_o,
    output wire        s_we_o,
    output wire [3:0]  s_be_o,
    output wire [31:0] s_wdata_o,
    input  wire [3:0]  s_gnt_i,
    input  wire [3:0]  s_rvalid_i,
    input  wire [31:0] s_rdata_0_i,
    input  wire [31:0] s_rdata_1_i,
    input  wire [31:0] s_rdata_2_i,
    input  wire [31:0] s_rdata_3_i,
    input  wire [3:0]  s_err_i
);

`include "soc_memmap.vh"

  // Five targets: four ports plus the error slave. NS is not a parameter
  // because the decode below names the regions individually; adding a
  // region means editing both, and hw/soc/tb/cocotb/test_soc_bus.py
  // checks the decode against the generated map rather than against this
  // file, so the two cannot silently disagree.
  localparam integer NS      = 5;
  localparam integer ERRSLV  = 4;
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

  // rst_ni gates both. Without it the request and grant paths, which are
  // purely combinational, stay live while the design is held in reset:
  // a master driving req during reset would have a transaction ACCEPTED
  // by a slave, while the response queues and counters are held at zero.
  // The slave's response would then arrive after reset release and pop a
  // queue that never recorded the request, underflowing the accounting.
  // Ibex holds its request ports low in reset so this cannot happen in
  // this SoC, but "cannot happen because of the master we happen to have"
  // is not a property of this file. It was found by the cocotb suite
  // driving requests during reset, which is why that test exists.
  wire can_issue_i = rst_ni && mi_req_i &&
                     ((cnt_i == 2'd0) ||
                      ((lock_i == tgt_i) && (cnt_i < MAX_OUT[1:0])));
  wire can_issue_d = rst_ni && md_req_i &&
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
  wire target_ready = (tgt == ERRSLV[2:0]) ? 1'b1 : s_gnt_i[tgt[1:0]];
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
  assign push[4] = accepted && (tgt == ERRSLV[2:0]);

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
  assign slv_rdata[4] = 32'h0;      // error slave returns no data

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
                    | ({32{resp_to_d[4]}} & slv_rdata[4]);
  assign mi_rdata_o = ({32{resp_to_i[0]}} & slv_rdata[0])
                    | ({32{resp_to_i[1]}} & slv_rdata[1])
                    | ({32{resp_to_i[2]}} & slv_rdata[2])
                    | ({32{resp_to_i[3]}} & slv_rdata[3])
                    | ({32{resp_to_i[4]}} & slv_rdata[4]);

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

`ifdef FORMAL
`include "soc_bus_props.v"
`endif

endmodule
