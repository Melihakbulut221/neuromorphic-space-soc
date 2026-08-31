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
