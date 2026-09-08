// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Formal properties for the core-local interruptor (SymbiYosys harness,
// hw/soc/formal/soc_clint.sby).
//
// WHERE THESE PROPERTIES COME FROM. Two specifications, both older than
// this project:
//
//   * the RISC-V privileged specification's machine timer. mtime is a
//     counter; mtimecmp is a comparand; the machine timer interrupt is a
//     LEVEL asserted exactly while mtime >= mtimecmp, unsigned, over the
//     full 64 bits; the machine software interrupt is the low bit of
//     msip and nothing else. C1-C4 are those clauses.
//   * the fabric slave contract S1-S4 quoted in the header of
//     hw/soc/rtl/soc_bus.v: a grant requires a request, exactly one
//     rvalid per grant, and the response carries rdata and err in that
//     cycle. P1-P3 are those clauses from the slave side.
//
// THE ARCHITECTURAL STATE IS RECONSTRUCTED FROM THE PORTS. f_mtime and
// f_mtimecmp below are built only from what a bus master did and from
// the passage of time; they never read mtime or mtimecmp. So C1 is a
// statement about what software asked for, not about what the design
// stored, and a block whose comparison was 32 bits wide, whose byte
// lanes were wrong, or whose tick was doubled would fail it.
//
// TICK_DIV IS FIXED AT 1 FOR THE PROOF. That is how soc_top.v
// instantiates it. A divided time base is a parameter this file does not
// reach: with TICK_DIV > 1 the ghost would have to model the prescaler,
// which would make it a copy of the design rather than a reconstruction
// of the architecture.
//
// H6 ADDS TWO CLAUSES, E1 AND E2, and they are the ones that say the
// protection is transparent and self-scrubbing.
//
//   E1. The stored word is always a codeword: mtime_chk_q is the
//       encoding of mtime_q. That is the SELF-SCRUB stated as an
//       invariant -- the block returns to a clean codeword on the next
//       edge and stays there -- and it is also what makes the induction
//       close, because without it k-induction starts from a state whose
//       check bits are arbitrary and every clause below fails there for
//       a reason that says nothing about the design.
//   E2. In the absence of a fault the correction is the identity:
//       mtime == mtime_q. `mtime` is what C1, C3 and the ghost read, so
//       E2 is why the whole property set below is BYTE FOR BYTE what it
//       was before H6 and why H6 is invisible to the architecture.
//
// WHAT IS NOT PROVEN HERE:
//
//   * Liveness. Nothing says a deadline is ever met or a response ever
//     arrives.
//   * The 64-bit write hazard, in either direction. It is a property of
//     a SEQUENCE of two bus transactions, not of any one cycle, and it
//     is demonstrated by measurement in
//     hw/soc/tb/cocotb/test_soc_clint.py.
//   * Which addresses reach this block. That is the fabric's decode,
//     proved in soc_bus_props.v against the generated map.
//   * Anything at TICK_DIV other than 1, and anything about a second
//     hart, which does not exist.
//   * Reset behaviour beyond the initial state.
//   * THAT THE CODE CORRECTS ANYTHING. Nothing here injects a fault,
//     because a formal harness that deposits into a register is proving
//     a property of the harness. E1 and E2 are statements about the
//     fault-free machine; the correction is measured in
//     hw/soc/tb/cocotb/test_soc_clint_fi.py and the codec itself is
//     proved once, for every consumer, in formal/secded.sby.
//   * Anything at HARDEN = 0. The proof runs the configuration that
//     ships. E1 and E2 are guarded so that the file still elaborates
//     unhardened, and nothing runs it there.

reg f_past_valid;
initial f_past_valid = 1'b0;
always @(posedge clk_i) f_past_valid <= 1'b1;

initial assume (!rst_ni);

// ---------------------------------------------------------------------
// Environment: a legal master (Ibex protocol rule 1)
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    if ($past(req_i) && !$past(gnt_o)) begin
        assume (req_i);
        assume (addr_i  == $past(addr_i));
        assume (we_i    == $past(we_i));
        assume (be_i    == $past(be_i));
        assume (wdata_i == $past(wdata_i));
    end
end

// ---------------------------------------------------------------------
// Ghost architectural state, from the ports only
// ---------------------------------------------------------------------
wire f_wr  = req_i && gnt_o && we_i;
wire f_hit_msip     = (addr_i[15:0] == REG_MSIP);
wire f_hit_cmpl     = (addr_i[15:0] == REG_MTIMECMPL);
wire f_hit_cmph     = (addr_i[15:0] == REG_MTIMECMPH);
wire f_hit_timel    = (addr_i[15:0] == REG_MTIMEL);
wire f_hit_timeh    = (addr_i[15:0] == REG_MTIMEH);
wire f_hit_any = f_hit_msip | f_hit_cmpl | f_hit_cmph | f_hit_timel | f_hit_timeh;

function [31:0] f_merge;
    input [31:0] old;
    input [3:0]  be;
    input [31:0] wd;
    begin
        f_merge = {be[3] ? wd[31:24] : old[31:24],
                   be[2] ? wd[23:16] : old[23:16],
                   be[1] ? wd[15:8]  : old[15:8],
                   be[0] ? wd[7:0]   : old[7:0]};
    end
endfunction

reg [63:0] f_mtime;
reg [63:0] f_mtimecmp;
reg        f_msip;

always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        f_mtime    <= 64'd0;
        f_mtimecmp <= 64'd0;
        f_msip     <= 1'b0;
    end else begin
        // Time passes, and a store to one half replaces that half.
        f_mtime[31:0]  <= (f_wr && f_hit_timel)
                        ? f_merge(f_mtime[31:0], be_i, wdata_i)
                        : (f_mtime + 64'd1) & 64'hFFFFFFFF;
        f_mtime[63:32] <= (f_wr && f_hit_timeh)
                        ? f_merge(f_mtime[63:32], be_i, wdata_i)
                        : ((f_mtime + 64'd1) >> 32);
        if (f_wr && f_hit_cmpl)
            f_mtimecmp[31:0]  <= f_merge(f_mtimecmp[31:0], be_i, wdata_i);
        if (f_wr && f_hit_cmph)
            f_mtimecmp[63:32] <= f_merge(f_mtimecmp[63:32], be_i, wdata_i);
        if (f_wr && f_hit_msip && be_i[0])
            f_msip <= wdata_i[0];
    end
end

// The offset and the direction of the request that is currently
// outstanding, captured at the grant so that the response can be checked
// against what was actually asked for.
reg        f_out;
reg [15:0] f_out_off;
reg        f_out_hit;
always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        f_out     <= 1'b0;
        f_out_off <= 16'h0;
        f_out_hit <= 1'b0;
    end else begin
        f_out <= req_i && gnt_o;
        if (req_i && gnt_o) begin
            f_out_off <= addr_i[15:0];
            f_out_hit <= f_hit_any;
        end
    end
end

// ---------------------------------------------------------------------
// I1: strengthening invariant, for induction and for nothing else
// ---------------------------------------------------------------------
//
// The ghost architectural state and the design's registers have to
// agree, or k-induction starts from a state where they do not and every
// property below fails there for reasons that say nothing about the
// design. It is also a real check in its own right: a design that
// dropped a byte lane, or ticked twice, diverges here.
always @(posedge clk_i) if (rst_ni) begin
    assert (f_mtime    == mtime);
    assert (f_mtimecmp == mtimecmp);
    assert (f_msip     == msip);
    assert (f_out      == rvalid_o);
end

// ---------------------------------------------------------------------
// E1-E2: the H6 codeword (docs/58)
// ---------------------------------------------------------------------
//
// f_chk is the encoding recomputed HERE, from the eight rows of the H
// matrix written out again rather than read from the instance. That is
// deliberate and it is the same rule secded_enc.v's own header applies
// to secded_dec.v: a check that read the encoder's output would be
// comparing the design against itself. If these constants and the RTL's
// diverge, E1 fails.
`ifdef SOC_CLINT_HARDENED
localparam [63:0] F_H_ROW0 = 64'h1F04225844B12CB7;
localparam [63:0] F_H_ROW1 = 64'h2F0844A88952555B;
localparam [63:0] F_H_ROW2 = 64'h4F10893112649A6D;
localparam [63:0] F_H_ROW3 = 64'h8F2111C22388E38E;
localparam [63:0] F_H_ROW4 = 64'hF1421E043C0F03F0;
localparam [63:0] F_H_ROW5 = 64'hF283E007C00FFC00;
localparam [63:0] F_H_ROW6 = 64'hF4FC0007FFF00000;
localparam [63:0] F_H_ROW7 = 64'hF8FFFFF800000000;

wire [7:0] f_chk = {^(mtime_q & F_H_ROW7), ^(mtime_q & F_H_ROW6),
                    ^(mtime_q & F_H_ROW5), ^(mtime_q & F_H_ROW4),
                    ^(mtime_q & F_H_ROW3), ^(mtime_q & F_H_ROW2),
                    ^(mtime_q & F_H_ROW1), ^(mtime_q & F_H_ROW0)};

always @(posedge clk_i) if (rst_ni) begin
    // E1. The stored word is a codeword, always. This is the self-scrub:
    //     whatever an upset does, the very next edge writes the encoding
    //     of the value that goes in, so the invariant is restored in one
    //     cycle and holds in every reachable state.
    assert (mtime_chk_q == f_chk);

    // E2. With E1 holding, the syndrome is zero, so the decoder is the
    //     identity and the codec is invisible to everything above it.
    assert (mtime == mtime_q);

    // E2b. And nothing is reported in a fault-free machine.
    assert (!mt_ecc_o);
end
`endif

// ---------------------------------------------------------------------
// C1-C2: the two interrupt outputs are functions of the architecture
// ---------------------------------------------------------------------
always @(posedge clk_i) if (rst_ni) begin
    // C1. The machine timer interrupt is a level, asserted exactly while
    //     the 64-bit unsigned comparison holds. Not a pulse, not
    //     latched, and not a comparison of the low halves.
    assert (irq_timer_o == (f_mtime >= f_mtimecmp));

    // C2. The machine software interrupt is the low bit of msip and
    //     nothing else in that word reaches it.
    assert (irq_software_o == f_msip);
end

// ---------------------------------------------------------------------
// C3-C4: reads return the architectural state
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    if (rvalid_o && !err_o) begin
        case (f_out_off)
            REG_MSIP:      assert (rdata_o == {31'h0, $past(f_msip)});
            REG_MTIMECMPL: assert (rdata_o == $past(f_mtimecmp[31:0]));
            REG_MTIMECMPH: assert (rdata_o == $past(f_mtimecmp[63:32]));
            REG_MTIMEL:    assert (rdata_o == $past(f_mtime[31:0]));
            REG_MTIMEH:    assert (rdata_o == $past(f_mtime[63:32]));
            default:       assert (1'b0);   // an unimplemented offset
                                            // must have set err_o
        endcase
    end
end

// ---------------------------------------------------------------------
// P1-P3: the slave side of the fabric contract, and the error rule
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    // P1. A grant requires a request.
    assert (!gnt_o || req_i);

    // P2. Exactly one rvalid per granted request, one cycle later, and
    //     never otherwise. The "never otherwise" half is what a block
    //     that answered its own idle state would violate.
    assert (rvalid_o == $past(req_i && gnt_o));

    // P3. err_o on a response is exactly "the offset that was asked for
    //     is not one this block implements". Both directions: an
    //     implemented offset never errors and an unimplemented one
    //     always does, which is the choice soc_clint.v's header argues
    //     against reading zero.
    if (rvalid_o) assert (err_o == !f_out_hit);
end

// ---------------------------------------------------------------------
// Cover: docs/09 B.1 vacuity rule -- every proven behaviour reachable
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && rst_ni) begin
    cover (irq_timer_o && f_mtimecmp != 64'd0);   // a real deadline met
    cover (!irq_timer_o);                         // and not met
    cover (irq_software_o);
    cover (rvalid_o && err_o);                    // an unimplemented offset
    cover (rvalid_o && !err_o && f_out_off == REG_MTIMEL);
    cover (rvalid_o && gnt_o);                    // back to back
    cover (f_mtimecmp[63:32] != 32'd0);           // the high half is used
end
