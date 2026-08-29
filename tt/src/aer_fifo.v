// AER event FIFO: parameterized synchronous FIFO carrying address-event
// (AER) words between the event interfaces and the NPU pipeline
// (docs/10-npu-mvp-spec.md section 7: EVQ_IN / EVQ_OUT, 16-bit local
// event word, 64-deep by default).
//
// Contract:
//   - Registered output: an accepted read presents its data on rd_data on
//     the next clock edge, flagged by rd_valid for one cycle.
//   - Overflow-safe: a write while full is dropped (never corrupts stored
//     events or pointers) and counted in a sticky saturating drop counter,
//     surfaced at the register block as CNT_EVQ_OVF / STATUS.OVF_SEEN.
//     This is the software injection port (EVQ_IN) semantics; a link-side
//     producer gets lossless backpressure by gating wr_en with !full.
//     A write coincident with a read while full is still dropped: full is
//     evaluated before the read frees a slot (conservative, formally proven).
//   - A read while empty is refused; rd_data holds its last value.
//   - drop_clr maps to FAULT_CLR; a drop coincident with the clear
//     restarts the counter at 1 so the event is not lost (house convention).
//   - level is exact occupancy (0..DEPTH), full == (level == DEPTH),
//     empty == (level == 0); level feeds EVQ_STAT.
//   - The two pointers are triple-redundant and voted (section "pointer
//     TMR" below). ptr_mismatch reports a corrected replica disagreement
//     for one cycle; it is a level output, and the instantiating block
//     qualifies and counts it.
//
// The registered output is a decision, not an accident, and it is the
// one thing here that a consumer has to design around. hw/rtl/npu_regbank.v
// convention C9 requires its EVQ_OUT source to be SHOW-AHEAD
// (first-word-fall-through): valid means "a word is presented now", the
// data is that word, and both hold until the pop advances the queue.
// This module does not meet that contract and deliberately still does
// not, because the alternative is worse: a show-ahead read port needs a
// combinational read of mem[], which turns the storage into an
// asynchronous-read register file. No synchronous SRAM macro can
// implement one, so at NPU scale (docs/10 section 7.2 sizes EVQ at 64
// entries per node, and the mesh has one per node) the queue could never
// be retargeted from flip-flops to a macro. It would also invalidate the
// four proofs in formal/aer_fifo.sby, which assert the registered
// timing directly (P5: rd_valid == $past(rd_ok), and rd_data holds
// otherwise).
//
// The gap is closed on the consumer side by a one-entry show-ahead
// adapter, which costs one flop-width plus a valid bit and no bandwidth
// that any register-mapped host can notice. hw/rtl/pilot_top.v section 8
// carries the reference implementation (oh_valid / oh_data / oh_pop) and
// the full comparison of the three options that were considered.
//
// DEPTH must be a power of two, >= 2 (enforced by an elaboration guard).
// Plain Verilog-2005, Icarus-clean; the formal properties
// (formal/aer_fifo_props.v) are textually included under `ifdef FORMAL
// and are invisible to simulation and synthesis.
`default_nettype none

module aer_fifo #(
    parameter WIDTH  = 16,             // AER event word width (docs/10 section 7.1)
    parameter DEPTH  = 64,             // entries, power of two >= 2 (EVQ_*_DEPTH)
    parameter DROP_W = 16,             // sticky drop counter width
    parameter AW     = $clog2(DEPTH)   // derived pointer width, do not override
) (
    input  wire              clk,
    input  wire              rst_n,
    // write side (AER producer)
    input  wire              wr_en,
    input  wire [WIDTH-1:0]  wr_data,
    output wire              full,
    // read side (event pipeline)
    input  wire              rd_en,
    output reg  [WIDTH-1:0]  rd_data,
    output reg               rd_valid,
    output wire              empty,
    // occupancy and overflow observability
    output wire [AW:0]       level,
    input  wire              drop_clr,
    output reg  [DROP_W-1:0] drop_cnt,
    // pointer TMR observability: one or both pointer voters disagreed
    // this cycle, so an upset was corrected. Combinational level, one
    // flag for both pointers; the instantiating block edge-detects and
    // counts it (hw/rtl/pilot_top.v feeds CNT_TMR and STATUS/TMR_SEEN).
    output wire              ptr_mismatch
);

    // Elaboration guard: a DEPTH outside the contract (power of two, >= 2)
    // takes the generate branch and references a module that deliberately
    // does not exist, so elaboration fails with the module name as the
    // message in every tool (Icarus, Yosys). Plain-2005 construct; DEPTH=1
    // would otherwise degenerate the [AW-1:0] index part-selects to [-1:0].
    generate
        if (DEPTH < 2 || (DEPTH & (DEPTH - 1)) != 0) begin : g_bad_depth
            ERROR_aer_fifo_DEPTH_must_be_a_power_of_two_ge_2 guard ();
        end
    endgenerate

    localparam [DROP_W-1:0] DROP_MAX = {DROP_W{1'b1}};

    // =================================================================
    // Pointer TMR
    // =================================================================
    // These two pointers were the highest-rate silent corruptor measured
    // anywhere in the pilot. The fault-injection campaign put 24
    // single-bit upsets into the four pointers of the two queue
    // instances and 22 ended in silent data corruption -- 21 of them in
    // the drained event stream itself, with nothing flagged: whole
    // bursts re-emitted, events duplicated, events lost, events
    // fabricated, and an unwritten slot presented as a spike. An
    // event interface has no sequence number and no length field --
    // docs/10 section 7.1 freezes the word at TYPE plus a 10-bit ID --
    // so a consumer cannot tell any of those from a real spike train.
    // Twelve flip-flops, one percent of the register count, carried 46
    // percent of the design's residual silent corruption (docs/16
    // section 5.2). That is the best protection-per-flip-flop in the
    // design, and this is the protection.
    //
    // Shape: three replicas per pointer, a bitwise majority vote, and
    // the VOTED value fed back as the next state of all three replicas.
    // Everything downstream -- level, full, empty, the mem[] index --
    // reads the voted pointer and nothing else, so a single corrupted
    // replica is masked at every output. Voted feedback also repairs the
    // corrupted replica on the next edge, so the module does not
    // accumulate upsets between events; the cost is that a replica is
    // rewritten every cycle rather than only on an increment, which is
    // switching power spent to close the accumulation window.
    //
    // The voter is written inline rather than instantiated from
    // hw/rtl/tmr_voter.v, and the expressions are that module's, verbatim.
    // The reason is file lists: this module is elaborated standalone by
    // hw/tb/Makefile (VERILOG_SOURCES is aer_fifo.v alone) and by the
    // four jobs of formal/aer_fifo.sby, so a second source file here
    // would have to be added to every one of them and aer_fifo would
    // stop being a self-contained leaf. tmr_voter is proven exhaustively
    // in formal/tmr_voter.sby; the same two expressions are re-proven
    // here in context by P7/P8 of formal/aer_fifo_props.v.
    //
    // ------------------------------------------------------------------
    // The trap, and the construction that answers it
    // ------------------------------------------------------------------
    // Three replicas written from the same next-state expression are
    // provably equivalent, so yosys `opt_dff` normalises them into
    // identical flip-flops and `opt_merge` hashes them into one bank.
    // The design then ships one physical pointer read three times behind
    // a voter that agrees with itself. That is not hypothetical: it is
    // what happened to the configuration TMR in hw/rtl/pilot_top.v, it
    // survived review, and it was caught only by counting flip-flop
    // cells in the hardened netlist. With voted feedback the hazard is
    // acute rather than incidental -- all three replicas are loaded from
    // one shared net, which is exactly the signature opt_merge hashes on.
    //
    // The answer is the pattern pilot_cfg_bank proved out, applied to a
    // pointer:
    //
    //   keep_hierarchy   `flatten` skips the bank module and `opt_merge`
    //                    does not merge instances of user-defined modules
    //                    unless invoked with -share_all, so the three
    //                    banks are two independent steps from collapse.
    //                    Honoured by both flows this repository runs
    //                    (LibreLane/yosys and synth_ecp5); portable to no
    //                    front end that ignores yosys attributes, which
    //                    is why the second defence exists.
    //   POL + MIX        a per-replica storage TRANSFORM, plain
    //                    Verilog-2005, depending on no attribute. Each
    //                    bank stores a different FUNCTION of the pointer,
    //                    so no two banks have a flip-flop with the same
    //                    (D, reset) signature and structural hashing has
    //                    nothing to match even with the hierarchy gone.
    //                    Replica A stores the pointer true, replica B its
    //                    exact complement, replica C an XOR mixing in
    //                    which every stored bit is a function of two or
    //                    three pointer bits. See aer_ptr_bank for why the
    //                    third replica needs the mixing and cannot be had
    //                    from a polarity or a rotation.
    //
    // Neither is trusted. sw/tests/test_synthesis_guards.py counts the
    // flip-flops of all twelve banks in the mapped netlist of both flows,
    // and again with keep_hierarchy stripped before synthesis, and is
    // mutation-checked against a scratch copy with this construction
    // reverted. That test, not either mechanism, is what keeps this true.
    //
    // ------------------------------------------------------------------
    // Two consequences outside this file, both measured, neither fixed
    // here because neither file is this change's to edit
    // ------------------------------------------------------------------
    //   hw/tb/test_fi_campaign.py names its pointer targets
    //   `u_evq_in.wr_ptr` and the three siblings. Those names still
    //   exist and are now the VOTED wires rather than storage, so the
    //   campaign keeps running and keeps reporting -- measured
    //   2026-08-29 on this RTL, evq_ptr 23 SDC and 1 HANG out of 24,
    //   which is its pre-TMR result to within one outcome [fact]. That
    //   number is true and it is about the voter's output node, which
    //   nothing claims to protect and which is not a flip-flop. It is
    //   not a statement about the replicas. The targets have to move to
    //   `{u_evq_in,u_evq_out}.u_{w,r}ptr_{a,b,c}.bits`, which is what
    //   hw/tb/test_aer_fifo.py injects into, before the campaign says
    //   anything about this hardening either way.
    //
    //   hw/openlane/aer_fifo/config.json hardens this module standalone
    //   and does not set SYNTH_HIERARCHY_MODE, so it takes LibreLane's
    //   default "flatten", which flattens before mapping and leaves the
    //   three derived `$paramod...aer_ptr_bank` types in the netlist for
    //   Checker.YosysUnmappedCells to abort on. Measured with the
    //   config's own SYNTH_PARAMETERS (WIDTH 16, DEPTH 64) on sg13g2:
    //   six $paramod instances survive [fact]. It needs the same
    //   "deferred_flatten" key the other three configs already carry --
    //   hw/rtl/pilot_top.v header section 9 records why that key exists.
    //   Same run, for the tile budget: 3146 -> 3354 cells and
    //   81,684.86 -> 84,452.34 um2 for the queue alone at DEPTH = 64,
    //   where the pointers are 7 bits and the TMR costs 28 flip-flops
    //   rather than the pilot's 24 [fact].
    localparam integer PW = AW + 1;   // pointer width, wrap bit included

    // Per-replica polarity. Carried as 64 bits so the bank's port
    // declaration does not depend on PW; the bank uses POL[PW-1:0] and
    // guards PW <= 64. Polarity separates A from B and can do no more
    // than that -- a storage bit has two polarities and there are three
    // replicas -- so C is held apart by MIX = 1, not by PTR_POL_C, which
    // survives for the storage-direction decorrelation argument in the
    // bank header.
    localparam [63:0] PTR_POL_A = 64'h0000000000000000;  // true
    localparam [63:0] PTR_POL_B = 64'hFFFFFFFFFFFFFFFF;  // complement
    localparam [63:0] PTR_POL_C = 64'h5555555555555555;  // even bits

    wire [PW-1:0] wr_ptr_a, wr_ptr_b, wr_ptr_c;
    wire [PW-1:0] rd_ptr_a, rd_ptr_b, rd_ptr_c;

`ifdef FORMAL
    // Formal-only fault injection, one free vector per replica, XORed
    // into the replica's value on the way to the voter. This is the same
    // shape hw/rtl/pilot_top.v uses for the configuration TMR (inj_a /
    // inj_b / inj_c) and it models an upset in the replica exactly:
    // because every replica's next state is loaded from the VOTED value,
    // corrupting a replica's output and corrupting its stored bits have
    // identical consequences everywhere.
    //
    // The vectors are free every cycle, so the proof covers a persistent
    // stuck replica as well as a single-cycle strike; the only
    // restriction is the one TMR actually claims, at most one faulty
    // replica per pointer, assumed in formal/aer_fifo_props.v. All four
    // jobs of formal/aer_fifo.sby run with this enabled, so P1..P6 are
    // proven UNDER a single-replica pointer fault rather than beside it.
    (* anyseq *) reg [PW-1:0] f_inj_wa, f_inj_wb, f_inj_wc;
    (* anyseq *) reg [PW-1:0] f_inj_ra, f_inj_rb, f_inj_rc;
`else
    wire [PW-1:0] f_inj_wa = {PW{1'b0}};
    wire [PW-1:0] f_inj_wb = {PW{1'b0}};
    wire [PW-1:0] f_inj_wc = {PW{1'b0}};
    wire [PW-1:0] f_inj_ra = {PW{1'b0}};
    wire [PW-1:0] f_inj_rb = {PW{1'b0}};
    wire [PW-1:0] f_inj_rc = {PW{1'b0}};
`endif

    // Voter inputs.
    wire [PW-1:0] wv_a = wr_ptr_a ^ f_inj_wa;
    wire [PW-1:0] wv_b = wr_ptr_b ^ f_inj_wb;
    wire [PW-1:0] wv_c = wr_ptr_c ^ f_inj_wc;
    wire [PW-1:0] rv_a = rd_ptr_a ^ f_inj_ra;
    wire [PW-1:0] rv_b = rd_ptr_b ^ f_inj_rb;
    wire [PW-1:0] rv_c = rd_ptr_c ^ f_inj_rc;

    // Bitwise majority (tmr_voter.v: at least two of three) and the
    // not-all-equal flag ((a^b)|(a^c) is zero exactly when b == a and
    // c == a, which also covers b != c).
    wire [PW-1:0] wr_ptr = (wv_a & wv_b) | (wv_a & wv_c) | (wv_b & wv_c);
    wire [PW-1:0] rd_ptr = (rv_a & rv_b) | (rv_a & rv_c) | (rv_b & rv_c);
    wire wr_ptr_mm = |((wv_a ^ wv_b) | (wv_a ^ wv_c));
    wire rd_ptr_mm = |((rv_a ^ rv_b) | (rv_a ^ rv_c));

    assign ptr_mismatch = wr_ptr_mm || rd_ptr_mm;

    // Pointers carry one extra wrap bit; occupancy is their difference.
    reg [WIDTH-1:0] mem [0:DEPTH-1];

    assign level = wr_ptr - rd_ptr;
    assign full  = (level == DEPTH[AW:0]);
    assign empty = (wr_ptr == rd_ptr);

    wire wr_ok   = wr_en && !full;   // accepted write
    wire rd_ok   = rd_en && !empty;  // accepted read
    wire wr_drop = wr_en && full;    // dropped write

    // Next pointer state, computed once from the VOTED value and loaded
    // into all three replicas. Loading unconditionally rather than under
    // an increment enable is what makes the domain self-correcting: a
    // replica corrupted at any time is rewritten from the vote on the
    // next edge.
    wire [PW-1:0] wr_ptr_nxt = wr_ptr + {{AW{1'b0}}, wr_ok};
    wire [PW-1:0] rd_ptr_nxt = rd_ptr + {{AW{1'b0}}, rd_ok};

    aer_ptr_bank #(.W(PW), .POL(PTR_POL_A))
        u_wptr_a (.clk(clk), .rst_n(rst_n), .d(wr_ptr_nxt), .q(wr_ptr_a));
    aer_ptr_bank #(.W(PW), .POL(PTR_POL_B))
        u_wptr_b (.clk(clk), .rst_n(rst_n), .d(wr_ptr_nxt), .q(wr_ptr_b));
    aer_ptr_bank #(.W(PW), .POL(PTR_POL_C), .MIX(1))
        u_wptr_c (.clk(clk), .rst_n(rst_n), .d(wr_ptr_nxt), .q(wr_ptr_c));

    aer_ptr_bank #(.W(PW), .POL(PTR_POL_A))
        u_rptr_a (.clk(clk), .rst_n(rst_n), .d(rd_ptr_nxt), .q(rd_ptr_a));
    aer_ptr_bank #(.W(PW), .POL(PTR_POL_B))
        u_rptr_b (.clk(clk), .rst_n(rst_n), .d(rd_ptr_nxt), .q(rd_ptr_b));
    aer_ptr_bank #(.W(PW), .POL(PTR_POL_C), .MIX(1))
        u_rptr_c (.clk(clk), .rst_n(rst_n), .d(rd_ptr_nxt), .q(rd_ptr_c));

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_data  <= {WIDTH{1'b0}};
            rd_valid <= 1'b0;
            drop_cnt <= {DROP_W{1'b0}};
        end else begin
            if (wr_ok)
                mem[wr_ptr[AW-1:0]] <= wr_data;
            if (rd_ok)
                rd_data <= mem[rd_ptr[AW-1:0]];
            rd_valid <= rd_ok;
            if (drop_clr)
                drop_cnt <= wr_drop ? {{(DROP_W - 1){1'b0}}, 1'b1}
                                    : {DROP_W{1'b0}};
            else if (wr_drop && drop_cnt != DROP_MAX)
                drop_cnt <= drop_cnt + 1'b1;
        end
    end

`ifdef FORMAL
`include "aer_fifo_props.v"
`endif

endmodule

// =====================================================================
// aer_ptr_bank: one physical replica of one AER queue pointer
// =====================================================================
//
// One instance per replica, six per queue instance. The reason this is a
// module at all, rather than three reg vectors in aer_fifo, is the
// header section above: three flip-flop banks loaded from the same net
// are one bank after yosys opt_dff + opt_merge, and the voter above them
// then votes three copies of the same corrupted value.
//
// Where this module lives, and why it is not pilot_cfg_bank
// ---------------------------------------------------------
// hw/rtl/pilot_top.v already carries a bank module of this shape and the
// two are close relatives; a single shared module was the first design
// considered and was rejected on two grounds, both mechanical.
//
//   - It would have to be its own file. pilot_cfg_bank currently sits at
//     the bottom of pilot_top.v, and aer_fifo cannot include a module
//     from a file it is not compiled with. Moving it to hw/rtl/*.v means
//     editing the file list of hw/tb/Makefile, hw/tb/Makefile.pilot,
//     hw/fpga/Makefile, hw/openlane/*/config.json, scripts/
//     gen_tt_submission.py RTL_SOURCES and every .sby that elaborates
//     pilot_top -- and, critically, adding a second source file to
//     hw/tb/Makefile and formal/aer_fifo.sby, which is exactly the
//     property this leaf is required to keep: aer_fifo elaborates alone,
//     from one file, in a cocotb suite and in four formal jobs.
//   - The two banks do not want the same interface. pilot_cfg_bank takes
//     a per-bit write enable and holds otherwise, because a
//     configuration word is written field by field from a register bus.
//     A voted pointer is loaded whole, every cycle, from one expression.
//     Sharing would mean a wr_en port tied to all ones at six of the
//     nine instances and a MIX path that re-encodes a word it never
//     partially writes.
//
// So the pattern is shared and the code is not, and the two modules are
// checked by the same test for the same property. The duplication is one
// encode and one decode function; the alternative was a cross-cutting
// edit to seven file lists to save it.
//
// The two defences, neither trusted alone
// ---------------------------------------
//   keep_hierarchy   `flatten` skips this module, and `opt_merge` does
//                    not merge instances of user-defined modules unless
//                    it is invoked with -share_all. Flow-portable across
//                    the LibreLane/yosys ASIC flow and synth_ecp5, both
//                    of which use the same `flatten` pass; NOT portable
//                    to a front end that does not read yosys attributes,
//                    which is why the storage transform below exists.
//   POL + MIX        the per-replica storage TRANSFORM. Plain
//                    Verilog-2005; depends on no attribute.
//
// The transform, and why it is what it is. What opt_merge hashes is the
// stored FUNCTION -- concretely, the net driving D and the reset value --
// so the question is how many distinct functions of the loaded pointer
// the three banks present:
//
//   POL alone gives two. A storage bit has exactly two polarities, x_i
//   and ~x_i, so with three replicas one of them always collides
//   bit-for-bit with another. This is measured, not argued: the
//   configuration domain sat exactly on that bound until MIX was added
//   to it (hw/rtl/pilot_top.v header section 9).
//
//   A per-replica bit ROTATION does not help, which is worth stating
//   because it looks like it should. Structural hashing is indifferent
//   to bit position: rotating relabels which physical flip-flop holds
//   which value bit but leaves the SET of stored functions identical, so
//   the rotated bank hashes into the unrotated one flop for flop.
//
//   MIX = 1 gives a third function by making every stored bit an XOR of
//   TWO OR THREE distinct pointer bits. Nothing of that form can equal
//   x_i or ~x_i for any i, so replica C is provably non-collidable
//   against A and B rather than measured to be. The map is two
//   unit-triangular XOR layers over GF(2): layer 1 makes every bit the
//   XOR of itself and its upper neighbour, and layer 2 folds the layer-1
//   bit 0 into the top bit, which is the bit layer 1 leaves at weight
//   one. Invertible by construction (a product of two unit-triangular
//   matrices) and its inverse is the same two layers run backwards. One
//   XOR per bit forward; the reverse is an XOR chain of length W-1,
//   which is this defence's timing cost and the reason MIX is paid for
//   on one replica of three rather than two.
//
// The honest limit, stated where it applies. Every row of the MIX map
// has weight >= 2 only for W >= 3. At W = 2 -- an EVQ_*_DEPTH of 2,
// which hw/tb/Makefile.pilot exercises as the q2x2 build -- no 2x2
// invertible GF(2) matrix has both rows of weight 2, so one of replica
// C's two bits necessarily reduces to a single pointer bit and can be
// hashed into replica A or B once keep_hierarchy is gone. That is a
// property of the width, not of this map: at W = 2 the attribute-free
// layer holds five of six flip-flops per pointer and no encoding can do
// better. The pilot's own build is DEPTH = 4 (W = 3) and the default is
// DEPTH = 64 (W = 7), both fully covered.
//
// The map is invertible by construction, and the construction is
// checked rather than asserted: hw/tb/test_aer_fifo.py is run at DEPTH
// 2, 4, 8 and 64, which is W = 2, 3, 4 and 7, and every one of its
// fifteen tests reads the queue through q. A non-invertible map would
// not survive the first fill and drain.
//
// A single upset in replica C decodes to two or three wrong bits at q.
// That is free against a single fault: they are all in ONE replica, and
// a bitwise majority masks every bit on which one replica disagrees,
// however many. What it costs is a double fault: two upsets in different
// replicas are uncorrectable only if they land on the same bit of the
// voted word, and widening replica C's error from one bit to two or
// three raises that coincidence for a (C, A) or (C, B) pair by about the
// same factor [estimate on the factor; the widening itself is fact]. It
// buys the third replica existing at all, which is a first-order effect
// traded against a second-order one.
//
// `keep` on `bits` is a third, weakest layer: measured on the
// configuration domain it does NOT stop the merge on its own -- it
// preserves the wire name while the storage still disappears -- so it is
// here only to stop opt_clean, never as evidence that the bank survived.
// The evidence is the flip-flop count in
// sw/tests/test_synthesis_guards.py.
//
// The stored image is `enc(d) ^ POL` and the port presents
// `dec(bits ^ POL)`, so every user of q sees the true pointer and only
// the physical cells differ. A debugger reading u_wptr_b.bits sees the
// complement of the write pointer and u_wptr_c.bits sees its mixed
// image, both by design; hw/tb/test_aer_fifo.py drives the replicas
// through this port rather than by writing bits directly, except in the
// injection tests, which deliberately corrupt the raw image.
(* keep_hierarchy *)
module aer_ptr_bank #(
    parameter integer W   = 3,        // pointer width, 2..64
    parameter [63:0]  POL = 64'd0,    // per-replica storage polarity
    parameter integer MIX = 0         // 0 = polarity only, 1 = + XOR mix
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [W-1:0] d,    // next pointer value, true polarity
    output wire [W-1:0] q     // stored pointer value, true polarity
);
    // Elaboration guards, aer_fifo house style. W < 2 degenerates the
    // two-layer map into the identity (and the part-selects with it);
    // W > 64 would silently truncate POL, which is carried as 64 bits so
    // that the port list does not depend on W.
    generate
        if (W < 2) begin : g_bank_too_narrow
            ERROR_aer_ptr_bank_W_must_be_ge_2 guard ();
        end
        if (W > 64) begin : g_bank_too_wide
            ERROR_aer_ptr_bank_W_exceeds_the_64_bit_POL_parameter guard ();
        end
    endgenerate

    // enc: true value -> stored image. Layer 1 makes every bit below the
    // top `v[i] ^ v[i+1]` (weight 2) and leaves the top bit at weight 1;
    // layer 2 folds the layer-1 bit 0 into that top bit, taking it to
    // `v[W-1] ^ v[0] ^ v[1]` (weight 3). No output row then has weight 1
    // for W >= 3, which is the whole property.
    function [W-1:0] ptr_enc(input [W-1:0] v);
        reg [W-1:0] t;
        integer i;
        begin
            t = v;
            for (i = 0; i < W - 1; i = i + 1)
                t[i] = v[i] ^ v[i + 1];
            t[W-1] = v[W-1] ^ t[0];
            ptr_enc = t;
        end
    endfunction

    // dec: stored image -> true value. The same two layers in reverse.
    // Layer 2 never touched bit 0, so c[0] below is still the layer-1
    // output that enc used.
    function [W-1:0] ptr_dec(input [W-1:0] c);
        reg [W-1:0] t;
        integer i;
        begin
            t = c;
            t[W-1] = c[W-1] ^ c[0];
            for (i = W - 2; i >= 0; i = i - 1)
                t[i] = c[i] ^ t[i + 1];
            ptr_dec = t;
        end
    endfunction

    (* keep *) reg [W-1:0] bits;

    generate
    if (MIX == 0) begin : g_polarity
        // Polarity-only replica: W flip-flops and, for POL != 0, one
        // inverter per bit on each side, which is what makes replica B's
        // D net a different net from replica A's.
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) bits <= {W{1'b0}} ^ POL[W-1:0];
            else        bits <= d ^ POL[W-1:0];
        end
        assign q = bits ^ POL[W-1:0];
    end else begin : g_mixed
        // Mixed replica. The pointer is loaded whole every cycle, so
        // unlike pilot_cfg_bank there is no read-modify-write here: the
        // encode is one XOR layer on the way in and the decode is the
        // reverse chain on the way out.
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) bits <= ptr_enc({W{1'b0}}) ^ POL[W-1:0];
            else        bits <= ptr_enc(d) ^ POL[W-1:0];
        end
        assign q = ptr_dec(bits ^ POL[W-1:0]);
    end
    endgenerate
endmodule

`default_nettype wire
