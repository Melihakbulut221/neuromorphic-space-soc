// soc_npu: the CPU-side NPU interface, and the frozen pilot behind it.
//
// docs/39-soc-bus-and-memory-map.md section 9 item 4 is the gap this
// closes: "No NPU connection. The 256 MiB window is frozen and reaches
// the error slave." docs/51-npu-integration.md is the design argument;
// this header states the contract the argument produced.
//
// =====================================================================
// 1. TWO INTERFACES, BECAUSE THERE ARE TWO PROBLEMS
// =====================================================================
//
// Configuration and event flow are not the same problem and this module
// does not pretend they are. They have different rates, different
// latency tolerances, different transports on the die, and they land in
// different places in the frozen memory map -- which is not a
// coincidence, because regmap/memmap.yaml's author separated them
// before either existed.
//
//   THE NODE REGISTER WINDOW, on the system bus at SOC_BASE_NPU.
//   A memory-mapped view of one docs/10 section 10 register block per
//   mesh node, at NODE_ID * 0x1000, which is the per-node base address
//   docs/10 section 8 item 5 FREEZES. Low rate, latency tolerant,
//   ordinary loads and stores. Its transport is soc_npu_ser.v and a
//   register access costs about 172 clock cycles.
//
//   THE EVENT PORT, on the peripheral bus in the NPUCFG slot.
//   A pair of 16-bit AER event queues (docs/10 section 7.1 event words)
//   with a hardware engine between them and the die. This is the
//   datapath. An injection costs a write to one register and a
//   collection costs a read from another, both at APB rate, and the
//   engine does the transport work in the background.
//
// The split is why NPUCFG spends the interrupt and the node window does
// not: an interrupt is a datapath signal. docs/40 froze NPUCFG at APB
// slot 0x019 with source number 24 on fast local line 12 and this block
// occupies exactly that. It spends NOTHING that was spare -- lines 13
// and 14 are still unassigned -- and one line is enough for any number
// of nodes because the cause register, not the wire, says what happened.
//
// =====================================================================
// 2. THE TRANSPORT, AND WHY IT IS THE SERIAL ONE
// =====================================================================
//
// hw/rtl/pilot_top.v is INSTANTIATED HERE, unmodified, out of the
// directory docs/34-pilot-freeze.md pins by git blob hash. Not copied,
// not adapted, not given a parallel register port. Its register bank is
// reached the way the TTIHP26b die will be reached: four serial pins.
//
// The full argument is docs/51 section 3. The short form is that the
// die that comes back in 2027 has a serial port and nothing else, so a
// parallel port would make the SoC's model of the NPU unvalidatable
// against the only real hardware this project will ever have -- and the
// cost of avoiding that is 172 cycles on a register access that
// software performs a few dozen times per pass.
//
// hw/soc/flow/sim_soc.sh already reads hw/rtl/tmr_voter.v the same way,
// and the rule is the one every hardening document here has followed:
// hw/rtl/ is READ and never written.
//
// =====================================================================
// 3. THE DIE'S PARALLEL AER PORT IS USED, AND IT IS NOT SYMMETRIC
// =====================================================================
//
// pilot_top.v section 1's pin contract gives the event path its own
// pins, and this module uses them on the input side and cannot use them
// on the output side. That asymmetry is in the pin contract, not in
// this file:
//
//   INPUT.  AER_IN_ADDR[3:0] with AER_IN_TICK and a rising-edge
//   AER_IN_STB carries a SPIKE or a TICK, one per strobe, at four clock
//   cycles each. This module drives them, gated on AER_IN_RDY.
//
//   AND IT CANNOT CARRY A SYNC. The pin word's TYPE field is built
//   from AER_IN_TICK alone, so it is 00 or 01 and never 10. SYNC -- the
//   frame barrier that docs/10 section 7.1 makes the determinism and
//   multi-pass handshake primitive -- has no pin, and this module
//   injects it by writing the die's EVQ_IN register over the serial
//   transport instead. That is 172 cycles once per frame, not per
//   event.
//
//   OUTPUT.  AER_OUT_VLD says an event is presented and AER_OUT_ID[3:0]
//   is, in pilot_top.v's own words, "the low four bits of its ID
//   field". THERE IS NO TYPE ON THE OUTPUT PINS. A SYNC echo and a
//   spike from neuron 0 are the same four bits, and the barrier that
//   tells the sequencer a frame is complete is exactly what would be
//   lost by reading them.
//
//   So AER_OUT_VLD is used as a NOTIFICATION and the word is read from
//   the die's EVQ_OUT register, which pilot_top.v section 1 says "is
//   always available over the serial EVQ_OUT register". AER_OUT_ACK is
//   tied low and is never used: the serial read is itself the pop, and
//   two pop paths into one show-ahead register would be two ways to
//   lose the same event.
//
// The cost is stated rather than hidden: an output event costs a serial
// frame and an input SPIKE costs four cycles, so this port is ~43x
// faster inbound than outbound. That is the pin budget of a Tiny
// Tapeout tile showing through, and docs/51 section 8 measures it.
//
// =====================================================================
// 4. QUEUES
// =====================================================================
//
// Both queues are hw/rtl/aer_fifo.v, the proved queue the die itself
// uses, instantiated from the frozen directory for the same reason
// pilot_top is: a second event queue in this repository would be a
// second set of pointer, parity and drop semantics to get right. Its
// drop counter, its entry parity and its pointer voting come along.
//
// The capture queue needs a SHOW-AHEAD read, because the register view
// of EVQ_OUT is "read one word, see VALID and EVENT in the same
// access". aer_fifo is a registered-output queue, so the gap is closed
// by the one-entry adapter of pilot_top.v section 8 -- convention C9,
// whose reference implementation is that file's oh_valid/oh_data/oh_pop
// and whose alternatives that section already rejected.
//
// The injection queue needs no adapter, because the engine never has to
// peek: it POPS the head, holds it, and then decides which transport it
// takes. What it does need is a BOUNDED WAIT, because aer_fifo may
// legitimately answer a read with nothing -- an entry whose stored
// parity fails is DISCARDED and rd_valid is held low. A fetch that
// never returns would hang the engine, so it expires, counts, and
// reports. hw/rtl/pilot_top.v does the same thing at its own dispatcher
// for the same reason (docs/16 section 5.1).
//
// =====================================================================
// 5. WHAT IS NOT HERE
// =====================================================================
//
// No descriptor rings. docs/08 section 3.1 sketches "per-node SRAM
// apertures + descriptor rings" for this window and this block builds
// the apertures and not the rings, because a ring is a BUS MASTER and
// this fabric has two master ports, hardcoded, with a two-master
// round-robin arbiter whose fairness property is written for two.
// docs/51 section 9 prices it and states the event rate above which it
// pays for itself.
//
// No hardening of anything this file adds. The queues carry aer_fifo's
// protection because they are aer_fifo; the engine's state, the
// registers and the serial shift path have none, which is the same
// position docs/39 section 9 item 3 records for the whole SoC.
//
// No second node. N_NODES is a parameter, the window decodes all
// sixteen NODE_ID values docs/10 section 8 item 2 allows, and fifteen
// of them are a bus error.

`timescale 1ns / 1ps

module soc_npu #(
    // Mesh nodes instantiated. The window decodes 16 (docs/10 section 8
    // item 2's 4-bit NODE_ID); nodes at or above this index fault.
    parameter integer N_NODES   = 1,
    // The pilot's geometry, as elaborated for the TTIHP26b shuttle.
    parameter integer N_NEURONS = 8,
    parameter integer N_AXONS   = 8,
    // Serial transport half period, in clk cycles. soc_npu_ser.v's
    // header is why 2 is both legal and exact.
    parameter integer SER_HALF  = 2,
    // SoC-side event queue depths. Powers of two >= 2 (aer_fifo).
    parameter integer INJ_DEPTH = 8,
    parameter integer CAP_DEPTH = 8,
    // Bounded wait on an injection-queue fetch, in clk cycles.
    parameter integer FETCH_MAX = 8
) (
    input  wire        clk_i,
    input  wire        rst_ni,

    // ---- system bus slave: the node register window ----
    input  wire        req_i,
    input  wire [31:0] addr_i,
    input  wire        we_i,
    input  wire [3:0]  be_i,
    input  wire [31:0] wdata_i,
    output wire        gnt_o,
    output reg         rvalid_o,
    output reg  [31:0] rdata_o,
    output reg         err_o,

    // ---- APB slave: the NPUCFG slot, the event port ----
    input  wire        psel_i,
    input  wire        penable_i,
    input  wire [11:0] paddr_i,
    input  wire        pwrite_i,
    input  wire [31:0] pwdata_i,
    output reg  [31:0] prdata_o,
    output wire        pready_o,
    output wire        pslverr_o,

    // ---- interrupt, fast local line SOC_IRQLINE_NPUCFG ----
    output wire        irq_o,

    // ---- observation of the die's pins, for a testbench or a scope ----
    output wire        obs_ser_sck_o,
    output wire        obs_ser_cs_n_o,
    output wire        obs_ser_mosi_o,
    output wire        obs_ser_miso_o,
    output wire        obs_aer_in_stb_o,
    output wire        obs_aer_out_vld_o
);

  // The die's own register offsets, from the single source. No literal
  // offset of regmap/regmap.yaml appears anywhere in this file.
`include "soc_npu_regs.vh"

  // Sized forms of the parameters, so nothing below part-selects an
  // integer parameter.
  localparam [4:0] NNODES_5 = N_NODES[4:0];
  localparam [7:0] NNODES_8 = N_NODES[7:0];
  localparam [7:0] SERHALF_8 = SER_HALF[7:0];
  localparam [7:0] INJDEP_8 = INJ_DEPTH[7:0];
  localparam [7:0] CAPDEP_8 = CAP_DEPTH[7:0];
  localparam [3:0] FETCHMAX_4 = FETCH_MAX[3:0];

  generate
    if (N_NODES < 1 || N_NODES > 16) begin : g_bad_nodes
      ERROR_soc_npu_N_NODES_must_be_between_1_and_16 g ();
    end
    if (FETCH_MAX < 1 || FETCH_MAX > 15) begin : g_bad_fetch
      ERROR_soc_npu_FETCH_MAX_must_be_between_1_and_15 g ();
    end
  endgenerate

  // -------------------------------------------------------------------
  // NPUCFG register offsets.
  //
  // This block's own register map, written here, exactly as soc_uart's
  // and soc_gptimer's are: regmap/memmap.yaml describes where a block
  // lives and has never described what is inside one. The NODE window's
  // map is different -- it IS regmap/regmap.yaml -- and this module
  // does not restate a single offset of it.
  // -------------------------------------------------------------------
  localparam [11:0] R_ID       = 12'h000;
  localparam [11:0] R_VERSION  = 12'h004;
  localparam [11:0] R_CTRL     = 12'h008;
  localparam [11:0] R_STATUS   = 12'h00C;
  localparam [11:0] R_IRQCAUSE = 12'h010;
  localparam [11:0] R_IRQMASK  = 12'h014;
  localparam [11:0] R_EVQ_IN   = 12'h018;
  localparam [11:0] R_EVQ_OUT  = 12'h01C;
  localparam [11:0] R_EVQ_STAT = 12'h020;
  localparam [11:0] R_GEOM     = 12'h024;
  localparam [11:0] R_CNT      = 12'h028;
  localparam [11:0] R_CNT_DROP = 12'h02C;

  // "NPUC": the fabric controller, next to the node's own "NPU1"
  // (regmap/regmap.yaml ID). Same convention, one letter apart, so a
  // reader that lands on either knows which one it is.
  localparam [31:0] ID_WORD  = 32'h4E505543;
  localparam [31:0] VER_WORD = 32'h00000001;

  // CTRL bits
  localparam integer B_IN_EN  = 0;
  localparam integer B_OUT_EN = 1;
  localparam integer B_FLUSH  = 2;   // self-clearing
  localparam integer B_SCRUB  = 3;   // self-clearing, pulses SCRUB_STB

  // IRQ_CAUSE bits. b0..b4 are LEVELS whose source clears them; b5 and
  // b6 are STICKY and write-1-to-clear. That split is not untidiness:
  // a full queue that refused a write is an EVENT with no state behind
  // it, and docs/50 section 5.1 is the record of what happens when a
  // counter or a flag is given semantics its source cannot support.
  localparam integer C_EVT      = 0; // level: the capture queue is not empty
  localparam integer C_ERR      = 1; // level: the die's ERR pin
  localparam integer C_SEC      = 2; // level: the die's SEC pin
  localparam integer C_DED      = 3; // level: the die's DED pin
  localparam integer C_TMR      = 4; // level: the die's TMR pin
  localparam integer C_INJ_OVF  = 5; // sticky: an EVQ_IN write was refused
  localparam integer C_FETCH_ER = 6; // sticky: an injection fetch expired
  localparam integer NCAUSE     = 7;

  // -------------------------------------------------------------------
  // The serial transport, and its arbiter
  //
  // TWO CLIENTS, FIXED PRIORITY TO THE CPU. A node-window access is a
  // load or a store that has STALLED the pipeline; the event engine's
  // work can always wait, and waiting loses nothing -- a full EVQ_OUT
  // stalls the die's update pipeline rather than dropping spikes
  // (docs/10 section 7.2), and a full injection queue refuses the write
  // at the register and counts it.
  //
  // The cost is stated: software that hammers the node window starves
  // the event engine for as long as it does so.
  // -------------------------------------------------------------------
  wire        ser_busy;
  wire        ser_done;
  wire [31:0] ser_rdata;

  // Node-window FSM state, declared here because the transport arbiter
  // below reads it. Its behaviour is in the node-window section.
  //
  // ISSUE AND WAIT ARE SEPARATE STATES, for the reason the event
  // engine's states carry at length: soc_npu_ser.v drops `busy_o` and
  // raises `done_o` at the same edge, so a state that both starts a
  // frame and watches for its completion starts a SECOND frame on the
  // way out. On the window that second frame is a repeat of the same
  // access with the same captured payload, and -- because it is still
  // owned by the window -- its completion is then mistaken for the
  // response to the NEXT access. Measured: a read immediately after a
  // write to the same register returned zero, which is what a write
  // frame's MISO carries. It only appeared when the two accesses were
  // close together, because anything slow in between let the spurious
  // frame drain first.
  localparam [1:0] W_IDLE  = 2'd0;
  localparam [1:0] W_ISSUE = 2'd1;
  localparam [1:0] W_WAIT  = 2'd2;
  localparam [1:0] W_RESP  = 2'd3;
  reg [1:0]   win_state;

  reg         win_start;
  reg         win_we;
  reg  [6:0]  win_addr;
  reg  [31:0] win_wdata;

  reg         ev_start;
  reg         ev_we;
  reg  [6:0]  ev_addr;
  reg  [31:0] ev_wdata;

  // The CPU wins, and `win_wants` rather than `win_start` is what the
  // engine has to defer to. Both clients see the same registered
  // ser_busy, so gating the engine on win_start alone would let both
  // raise a start in the SAME cycle -- the multiplexer below would
  // serve the window, the engine would believe its frame had begun,
  // and the ownership flag would never report it done. The engine
  // therefore stands off for as long as the window FSM is waiting for
  // the transport at all, which is also what "fixed priority to the
  // CPU" is supposed to mean.
  wire        win_wants = (win_state == W_ISSUE)
                       || (win_state == W_WAIT);
  wire        ser_start = win_start || ev_start;
  wire        ser_we    = win_start ? win_we    : ev_we;
  wire [6:0]  ser_addr  = win_start ? win_addr  : ev_addr;
  wire [31:0] ser_wdata = win_start ? win_wdata : ev_wdata;

  // Which client owns the frame in flight, captured at the start.
  reg         ser_owner_win;
  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni)          ser_owner_win <= 1'b0;
    else if (ser_start)   ser_owner_win <= win_start;

  wire ser_done_win = ser_done &&  ser_owner_win;
  wire ser_done_ev  = ser_done && !ser_owner_win;

  wire ser_sck, ser_cs_n, ser_mosi, ser_miso;

  soc_npu_ser #(.HALF (SER_HALF)) u_ser (
      .clk_i      (clk_i),
      .rst_ni     (rst_ni),
      .start_i    (ser_start),
      .we_i       (ser_we),
      .addr_i     (ser_addr),
      .wdata_i    (ser_wdata),
      .busy_o     (ser_busy),
      .done_o     (ser_done),
      .rdata_o    (ser_rdata),
      .ser_sck_o  (ser_sck),
      .ser_cs_n_o (ser_cs_n),
      .ser_mosi_o (ser_mosi),
      .ser_miso_i (ser_miso)
  );

  // -------------------------------------------------------------------
  // The node register window: a system-bus slave
  //
  // GRANT DISCIPLINE. This slave accepts ONE request at a time and
  // withholds gnt otherwise, which is soc_bus.v's rule S4 and is
  // exactly what soc_apb_bridge.v already does. The difference is the
  // duration -- three cycles there, about 172 here -- and the
  // consequence is worth writing down because this is the first slave
  // in the SoC slow enough to make it visible:
  //
  //   soc_bus.v's round-robin arbiter picks a winner BEFORE it looks at
  //   the target's grant, and its no-starvation property F9 has "every
  //   slave ready" in its antecedent for that reason (docs/39 section 8
  //   defect 3). So while a master is being refused HERE, the other
  //   master is not granted either.
  //
  // In this SoC that costs nothing measurable, and the reason is a
  // property of the CORE rather than of this file: Ibex is a two-stage
  // machine with no cache, so a load stalls the pipeline until its data
  // returns and no second request to this window is ever issued while
  // the first is in flight. docs/51 section 8 measures it rather than
  // asserting it. "Cannot happen because of the master we happen to
  // have" is not a property of a slave -- docs/39 section 8 defect 4 --
  // so it is measured and reported, not relied on.
  //
  // ADDRESS DECODE, in the order a reader should check it:
  //   addr[27:16] != 0   -> error. Only the low 64 KiB of the 256 MiB
  //                         window is node register space; the rest,
  //                         including the descriptor-ring area, is
  //                         reserved and faults.
  //   node >= N_NODES    -> error.
  //   addr[11:9] != 0    -> error. The die's frame carries a 7-bit word
  //                         index (pilot_top.v P2), so offsets 0x000 to
  //                         0x1FC are the whole reachable map.
  //   a write with be != 4'hF or a misaligned address -> error. The
  //                         serial frame is 32 bits wide and has no
  //                         byte enable; a partial write cannot be
  //                         performed and must not be silently widened.
  // -------------------------------------------------------------------
  wire [3:0] win_node   = addr_i[15:12];
  wire       win_in_reg = (addr_i[27:16] == 12'd0)
                       && ({1'b0, win_node} < NNODES_5)
                       && (addr_i[11:9] == 3'd0);
  wire       win_align  = (addr_i[1:0] == 2'd0);
  wire       win_bad    = !win_in_reg || !win_align
                       || (we_i && (be_i != 4'hF));

  assign gnt_o = req_i && (win_state == W_IDLE);

  reg win_err_q;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      win_state <= W_IDLE;
      win_start <= 1'b0;
      win_we    <= 1'b0;
      win_addr  <= 7'd0;
      win_wdata <= 32'd0;
      win_err_q <= 1'b0;
      rvalid_o  <= 1'b0;
      rdata_o   <= 32'd0;
      err_o     <= 1'b0;
    end else begin
      win_start <= 1'b0;
      rvalid_o  <= 1'b0;
      case (win_state)
        W_IDLE: begin
          if (req_i) begin
            // Captured in the grant cycle, the only cycle the fabric
            // guarantees the broadcast payload (soc_bus.v S2).
            win_err_q <= win_bad;
            win_we    <= we_i;
            win_addr  <= addr_i[8:2];
            win_wdata <= wdata_i;
            if (win_bad) begin
              win_state <= W_RESP;
            end else begin
              win_state <= W_ISSUE;
            end
          end
        end

        W_ISSUE: begin
          // The CPU has priority, so the only thing that can be in
          // front of this is an event-engine frame that had already
          // started.
          if (!ser_busy && !ser_start) begin
            win_start <= 1'b1;
            win_state <= W_WAIT;
          end
        end

        W_WAIT: begin
          if (ser_done_win) begin
            rdata_o   <= ser_rdata;
            win_state <= W_RESP;
          end
        end

        W_RESP: begin
          rvalid_o  <= 1'b1;
          err_o     <= win_err_q;
          if (win_err_q) rdata_o <= 32'd0;
          win_state <= W_IDLE;
        end

        default: win_state <= W_IDLE;
      endcase
    end
  end

  // -------------------------------------------------------------------
  // Control and status registers, driven from the APB face
  // -------------------------------------------------------------------
  reg        ctrl_in_en, ctrl_out_en;
  reg        flush_pulse, scrub_pulse;
  reg [NCAUSE-1:0] irq_mask;
  reg        sticky_inj_ovf, sticky_fetch_er;

  wire apb_wr = psel_i && penable_i &&  pwrite_i;
  wire apb_rd = psel_i && penable_i && !pwrite_i;

  // -------------------------------------------------------------------
  // SoC-side event queues
  //
  // blk_rst_n carries CTRL.FLUSH into the queues, which is the
  // SoC-side analogue of the die's CTRL.SOFT_RST: the queues and the
  // engine go back to empty, the registers do not. The sticky cause
  // bits are NOT in this domain -- a recovery that erased the record of
  // what it recovered from is the defect docs/16 section 5.1 named and
  // pilot_top.v section 5 corrects.
  // -------------------------------------------------------------------
  wire blk_rst_n = rst_ni && !flush_pulse;

  wire        inj_full, inj_empty, inj_rd_valid;
  wire [15:0] inj_rd_data;
  wire [$clog2(INJ_DEPTH):0] inj_level;
  wire [7:0]  inj_drop;
  wire        inj_ptr_mm, inj_par_err;
  reg         inj_rd_en;

  wire        inj_wr_en = apb_wr && (paddr_i == R_EVQ_IN);

  aer_fifo #(.WIDTH (16), .DEPTH (INJ_DEPTH), .DROP_W (8)) u_inj (
      .clk (clk_i), .rst_n (blk_rst_n),
      .wr_en (inj_wr_en), .wr_data (pwdata_i[15:0]), .full (inj_full),
      .rd_en (inj_rd_en), .rd_data (inj_rd_data),
      .rd_valid (inj_rd_valid), .empty (inj_empty), .level (inj_level),
      .drop_clr (1'b0), .drop_cnt (inj_drop),
      .ptr_mismatch (inj_ptr_mm), .rv_mismatch (),
      .par_err (inj_par_err)
  );

  wire        cap_full, cap_empty, cap_rd_valid;
  wire [15:0] cap_rd_data;
  wire [$clog2(CAP_DEPTH):0] cap_level;
  wire        cap_ptr_mm, cap_par_err;
  reg         cap_wr_en;
  reg  [15:0] cap_wr_data;
  reg         cap_rd_en;

  aer_fifo #(.WIDTH (16), .DEPTH (CAP_DEPTH), .DROP_W (8)) u_cap (
      .clk (clk_i), .rst_n (blk_rst_n),
      .wr_en (cap_wr_en), .wr_data (cap_wr_data), .full (cap_full),
      .rd_en (cap_rd_en), .rd_data (cap_rd_data),
      .rd_valid (cap_rd_valid), .empty (cap_empty), .level (cap_level),
      .drop_clr (1'b0), .drop_cnt (),
      .ptr_mismatch (cap_ptr_mm), .rv_mismatch (),
      .par_err (cap_par_err)
  );

  // The one-entry show-ahead adapter (pilot_top.v section 8, convention
  // C9): the register view of EVQ_OUT is a single-access pop, and
  // aer_fifo presents its data one cycle after an accepted read.
  reg         oh_valid;
  reg  [15:0] oh_data;
  reg         oh_req;      // a read is in flight

  wire        oh_pop = apb_rd && (paddr_i == R_EVQ_OUT) && oh_valid;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      oh_valid  <= 1'b0;
      oh_data   <= 16'd0;
      oh_req    <= 1'b0;
      cap_rd_en <= 1'b0;
    end else if (!blk_rst_n) begin
      oh_valid  <= 1'b0;
      oh_req    <= 1'b0;
      cap_rd_en <= 1'b0;
    end else begin
      cap_rd_en <= 1'b0;
      if (cap_rd_valid) begin
        oh_data  <= cap_rd_data;
        oh_valid <= 1'b1;
        oh_req   <= 1'b0;
      end else if (oh_pop) begin
        oh_valid <= 1'b0;
      end
      // Refill when the holding register is free and nothing is in
      // flight. A read whose entry fails its parity check returns no
      // rd_valid; oh_req simply stays set until the next entry arrives,
      // and the queue's own level tells software the difference.
      if (!oh_valid && !oh_req && !cap_rd_valid && !cap_empty
          && !cap_rd_en && !oh_pop) begin
        cap_rd_en <= 1'b1;
        oh_req    <= 1'b1;
      end
    end
  end

  // -------------------------------------------------------------------
  // The frozen pilot
  // -------------------------------------------------------------------
  wire        node_aer_in_rdy, node_aer_out_vld, node_busy;
  wire        node_err, node_sec, node_ded, node_tmr;
  wire [3:0]  node_aer_out_id;

  reg         aer_in_stb, aer_in_tick;
  reg  [3:0]  aer_in_addr;

  pilot_top #(
      .N_NEURONS     (N_NEURONS),
      .N_AXONS       (N_AXONS),
      .EVQ_IN_DEPTH  (4),
      .EVQ_OUT_DEPTH (4),
      .CNT_W         (8)
  ) u_node0 (
      .clk         (clk_i),
      .rst_n       (rst_ni),
      .ser_sck     (ser_sck),
      .ser_cs_n    (ser_cs_n),
      .ser_mosi    (ser_mosi),
      .ser_miso    (ser_miso),
      .aer_in_stb  (aer_in_stb),
      .aer_in_tick (aer_in_tick),
      .aer_in_addr (aer_in_addr),
      .aer_in_rdy  (node_aer_in_rdy),
      .aer_out_vld (node_aer_out_vld),
      .aer_out_id  (node_aer_out_id),
      // Tied low, deliberately. The serial EVQ_OUT read IS the pop, and
      // a second pop path into the die's one-entry show-ahead register
      // would be a second way to lose an event. Section 3.
      .aer_out_ack (1'b0),
      .scrub_stb   (scrub_pulse),
      .busy        (node_busy),
      .err         (node_err),
      .sec_seen    (node_sec),
      .ded_seen    (node_ded),
      .tmr_seen    (node_tmr)
  );

  // The die's four-bit output nibble is deliberately unread: section 3
  // is why the word comes from the register and not from these pins.
  // The queues' pointer-voter and parity observability is likewise
  // brought out of aer_fifo and not yet given a register -- the SoC has
  // no fault-counter block of its own and inventing one here would put
  // NPU-only telemetry outside BUSSTAT, which docs/41 owns.
  wire _unused_node = &{1'b0, node_aer_out_id, inj_ptr_mm, cap_ptr_mm,
                        cap_par_err, inj_par_err, 1'b0};

  // -------------------------------------------------------------------
  // The event engine
  //
  // One FSM, one serial client. DRAIN OUTRANKS INJECT: a full EVQ_OUT
  // on the die stalls its update pipeline (docs/10 section 7.2 -- spikes
  // are never dropped, the pipeline waits), so injecting into a stalled
  // core achieves nothing, while draining unblocks it.
  //
  // The event word's TYPE field (docs/10 section 7.1 bits [15:14])
  // chooses the inbound transport: 00 SPIKE and 01 TICK take the pins,
  // 10 SYNC and 11 take the serial EVQ_IN register. 11 is reserved and
  // the die drops and does not count it; this module does not filter it
  // out, because filtering here would make a host unable to observe the
  // die's own documented behaviour for a reserved code.
  // -------------------------------------------------------------------
  //
  // ISSUE AND WAIT ARE SEPARATE STATES, and that is not tidiness. A
  // single state that both raised `start` and watched for `done` fires
  // BOTH in the cycle the frame completes -- soc_npu_ser.v drops
  // `busy_o` and raises `done_o` at the same edge -- so the engine
  // launches a second, unwanted frame on its way out. That second frame
  // is a read of EVQ_OUT, which POPS, and the result reaches an engine
  // that has moved on. Measured: it duplicated one barrier echo in a
  // twelve-event stream and left a spurious pop in flight behind it.
  localparam [3:0] E_IDLE    = 4'd0;
  localparam [3:0] E_FETCH   = 4'd1;
  localparam [3:0] E_DECIDE  = 4'd2;
  localparam [3:0] E_PIN_A   = 4'd3;
  localparam [3:0] E_PIN_S   = 4'd4;
  localparam [3:0] E_PIN_G   = 4'd5;
  localparam [3:0] E_SER_RQ  = 4'd6;
  localparam [3:0] E_SER_W   = 4'd7;
  localparam [3:0] E_DRN_RQ  = 4'd8;
  localparam [3:0] E_DRN_W   = 4'd9;

  reg [3:0]  ev_state;
  reg [15:0] ev_word;
  reg [3:0]  ev_wait;
  reg [15:0] cnt_in, cnt_out;

  wire drain_want = ctrl_out_en && node_aer_out_vld && !cap_full;
  wire inject_want = ctrl_in_en && !inj_empty;

  // The die's own register offsets, from the generated header. No
  // literal offset of regmap/regmap.yaml appears in this file.
  localparam [6:0] SA_EVQ_IN  = ADDR_EVQ_IN[8:2];
  localparam [6:0] SA_EVQ_OUT = ADDR_EVQ_OUT[8:2];


  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      ev_state    <= E_IDLE;
      ev_word     <= 16'd0;
      ev_wait     <= 4'd0;
      ev_start    <= 1'b0;
      ev_we       <= 1'b0;
      ev_addr     <= 7'd0;
      ev_wdata    <= 32'd0;
      inj_rd_en   <= 1'b0;
      aer_in_stb  <= 1'b0;
      aer_in_tick <= 1'b0;
      aer_in_addr <= 4'd0;
      cap_wr_en   <= 1'b0;
      cap_wr_data <= 16'd0;
      cnt_in      <= 16'd0;
      cnt_out     <= 16'd0;
    end else begin
      ev_start  <= 1'b0;
      inj_rd_en <= 1'b0;
      cap_wr_en <= 1'b0;

      if (!blk_rst_n) begin
        ev_state   <= E_IDLE;
        aer_in_stb <= 1'b0;
      end else begin
      case (ev_state)
        E_IDLE: begin
          aer_in_stb <= 1'b0;
          if (drain_want) begin
            ev_state <= E_DRN_RQ;
          end else if (inject_want) begin
            inj_rd_en <= 1'b1;
            ev_wait   <= 4'd0;
            ev_state  <= E_FETCH;
          end
        end

        // Bounded wait. aer_fifo discards an entry whose stored parity
        // fails and holds rd_valid low; without this the engine would
        // stop for ever on a single upset.
        E_FETCH: begin
          if (inj_rd_valid) begin
            ev_word  <= inj_rd_data;
            ev_state <= E_DECIDE;
          end else if (ev_wait == FETCHMAX_4) begin
            ev_state <= E_IDLE;
          end else begin
            ev_wait <= ev_wait + 4'd1;
          end
        end

        E_DECIDE: begin
          if (ev_word[15:14] == 2'b10 || ev_word[15:14] == 2'b11) begin
            ev_state <= E_SER_RQ;
          end else if (node_aer_in_rdy) begin
            aer_in_tick <= ev_word[14];
            aer_in_addr <= ev_word[3:0];
            ev_state    <= E_PIN_A;
          end
          // else: hold here until the die's input queue has room.
          // AER_IN_RDY is !full on the die; a strobe into a full queue
          // would be counted as a software-port drop, which is the one
          // thing this engine must never make the die report.
        end

        // The die two-flop synchronizes AER_IN_ADDR and AER_IN_TICK
        // alongside AER_IN_STB, so the address driven in the same cycle
        // as the strobe is the address the strobe carries. It is driven
        // one cycle EARLIER anyway, because a value that is stable
        // before and after the edge is one fewer thing to reason about.
        E_PIN_A: begin
          aer_in_stb <= 1'b1;
          ev_state   <= E_PIN_S;
        end

        E_PIN_S: begin
          aer_in_stb <= 1'b0;
          ev_wait    <= 4'd0;
          ev_state   <= E_PIN_G;
        end

        // The strobe must return low and be SEEN low before the next
        // rising edge, which is two synchronizer stages away.
        E_PIN_G: begin
          if (ev_wait == 4'd2) begin
            if (cnt_in != 16'hFFFF) cnt_in <= cnt_in + 16'd1;
            ev_state <= E_IDLE;
          end else begin
            ev_wait <= ev_wait + 4'd1;
          end
        end

        E_SER_RQ: begin
          if (!ser_busy && !win_wants && !win_start && !ev_start) begin
            ev_start <= 1'b1;
            ev_we    <= 1'b1;
            ev_addr  <= SA_EVQ_IN;
            ev_wdata <= {16'd0, ev_word};
            ev_state <= E_SER_W;
          end
        end

        E_SER_W: begin
          if (ser_done_ev) begin
            if (cnt_in != 16'hFFFF) cnt_in <= cnt_in + 16'd1;
            ev_state <= E_IDLE;
          end
        end

        E_DRN_RQ: begin
          if (!ser_busy && !win_wants && !win_start && !ev_start) begin
            ev_start <= 1'b1;
            ev_we    <= 1'b0;
            ev_addr  <= SA_EVQ_OUT;
            ev_wdata <= 32'd0;
            ev_state <= E_DRN_W;
          end
        end

        E_DRN_W: begin
          if (ser_done_ev) begin
            // regmap/regmap.yaml: EVQ_OUT is "b31 VALID, [15:0] event
            // word". A read with VALID clear popped nothing and is
            // discarded here -- it can happen if the die's holding
            // register emptied between AER_OUT_VLD rising and the frame
            // completing, which nothing in this SoC can cause but which
            // the register's own contract permits.
            if (ser_rdata[31]) begin
              cap_wr_en   <= 1'b1;
              cap_wr_data <= ser_rdata[15:0];
              if (cnt_out != 16'hFFFF) cnt_out <= cnt_out + 16'd1;
            end
            ev_state <= E_IDLE;
          end
        end

        default: ev_state <= E_IDLE;
      endcase
      end
    end
  end

  // -------------------------------------------------------------------
  // APB register file
  // -------------------------------------------------------------------
  wire [NCAUSE-1:0] cause;
  assign cause[C_EVT]      = !cap_empty || oh_valid;
  assign cause[C_ERR]      = node_err;
  assign cause[C_SEC]      = node_sec;
  assign cause[C_DED]      = node_ded;
  assign cause[C_TMR]      = node_tmr;
  assign cause[C_INJ_OVF]  = sticky_inj_ovf;
  assign cause[C_FETCH_ER] = sticky_fetch_er;

  assign irq_o = |(cause & irq_mask);

  wire fetch_expire = (ev_state == E_FETCH) && !inj_rd_valid
                   && (ev_wait == FETCHMAX_4);

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      ctrl_in_en      <= 1'b0;
      ctrl_out_en     <= 1'b0;
      flush_pulse     <= 1'b0;
      scrub_pulse     <= 1'b0;
      irq_mask        <= {NCAUSE{1'b0}};
      sticky_inj_ovf  <= 1'b0;
      sticky_fetch_er <= 1'b0;
    end else begin
      flush_pulse <= 1'b0;
      scrub_pulse <= 1'b0;

      if (inj_wr_en && inj_full) sticky_inj_ovf  <= 1'b1;
      if (fetch_expire)          sticky_fetch_er <= 1'b1;

      if (apb_wr) begin
        case (paddr_i)
          R_CTRL: begin
            ctrl_in_en  <= pwdata_i[B_IN_EN];
            ctrl_out_en <= pwdata_i[B_OUT_EN];
            flush_pulse <= pwdata_i[B_FLUSH];
            scrub_pulse <= pwdata_i[B_SCRUB];
          end
          R_IRQMASK: irq_mask <= pwdata_i[NCAUSE-1:0];
          R_IRQCAUSE: begin
            // Only the two sticky bits are clearable. A write to a
            // level bit is accepted and does nothing, because the way
            // to clear a level is to fix what is raising it.
            if (pwdata_i[C_INJ_OVF])  sticky_inj_ovf  <= 1'b0;
            if (pwdata_i[C_FETCH_ER]) sticky_fetch_er <= 1'b0;
          end
          default: ;
        endcase
      end
    end
  end

  // Every offset this block does not implement completes with PSLVERR,
  // the same rule soc_clint.v applies inside its window and soc_top.v
  // applies to an unoccupied slot: a reserved address is a bus error at
  // the core, never a read of zero that looks like a working register.
  reg  hit;
  always @(*) begin
    hit      = 1'b1;
    prdata_o = 32'h0;
    case (paddr_i)
      R_ID:       prdata_o = ID_WORD;
      R_VERSION:  prdata_o = VER_WORD;
      R_CTRL:     prdata_o = {30'd0, ctrl_out_en, ctrl_in_en};
      R_STATUS:   prdata_o = {20'd0,
                              node_tmr, node_ded, node_sec, node_err,
                              node_busy, node_aer_out_vld,
                              node_aer_in_rdy,
                              cap_full, cap_empty && !oh_valid,
                              inj_full, inj_empty,
                              ser_busy};
      R_IRQCAUSE: prdata_o = {{(32-NCAUSE){1'b0}}, cause};
      R_IRQMASK:  prdata_o = {{(32-NCAUSE){1'b0}}, irq_mask};
      R_EVQ_IN:   prdata_o = 32'h0;   // write-only, reads zero
      R_EVQ_OUT:  prdata_o = {oh_valid, 15'd0, oh_data};
      R_EVQ_STAT: prdata_o = {16'd0,
                              4'd0, cap_level[3:0] + {3'd0, oh_valid},
                              4'd0, inj_level[3:0]};
      R_GEOM:     prdata_o = {CAPDEP_8, INJDEP_8, SERHALF_8, NNODES_8};
      R_CNT:      prdata_o = {cnt_out, cnt_in};
      R_CNT_DROP: prdata_o = {24'd0, inj_drop};
      default:    hit = 1'b0;
    endcase
  end

  assign pready_o  = 1'b1;
  assign pslverr_o = psel_i && !hit;

  assign obs_ser_sck_o     = ser_sck;
  assign obs_ser_cs_n_o    = ser_cs_n;
  assign obs_ser_mosi_o    = ser_mosi;
  assign obs_ser_miso_o    = ser_miso;
  assign obs_aer_in_stb_o  = aer_in_stb;
  assign obs_aer_out_vld_o = node_aer_out_vld;

  wire _unused_apb = &{1'b0, paddr_i[1:0], pwdata_i[31:16], 1'b0};

endmodule
