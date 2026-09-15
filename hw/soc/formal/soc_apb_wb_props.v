// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Formal properties for the APB completer to Wishbone B3 classic
// initiator bridge (SymbiYosys harness, hw/soc/formal/soc_apb_wb.sby).
//
// WHERE THESE PROPERTIES COME FROM, which matters more than what they
// say, for the reason soc_apb_bridge_props.v gives: this repository has
// twice locked in a bug by writing a checker that restated what the
// implementation did. Every property below is a clause of one of two
// specifications, both of which existed before the RTL:
//
//   * Wishbone B3, revision B.3. Section 3.1.3 (handshaking protocol):
//     a cycle is terminated by exactly one of ACK, ERR or RTY, and the
//     initiator responds to the termination by ending the strobe.
//     Section 3.1.4 (use of STB_O): STB is asserted only within a cycle,
//     which CYC frames, and ADR, DAT_O, SEL and WE are qualified by STB.
//     Sections 3.2.1 and 3.2.2 (single read, single write): the
//     initiator presents address, data, select and direction with the
//     strobe and holds them until the target terminates. Section 3.5
//     (data organisation): SEL_O() names the lanes carrying valid data.
//     W1-W8 are those clauses, from the initiator's side.
//   * AMBA 3 APB. A completer holds PREADY low to insert wait states and
//     raises it to end ACCESS; PSLVERR is meaningful only in the PREADY
//     cycle; PRDATA is meaningful only in the PREADY cycle of a read.
//     P1-P3 are those clauses, from the completer's side. E1-E5 are the
//     requester's clauses, ASSUMED: the bridge is proved against a
//     requester that obeys the protocol, which soc_apb_bridge.sby proves
//     the fabric's requester does.
//
// D1 and D2 are the lane adapter's data-integrity properties -- the
// target is addressed with the word offset and the lane PSTRB named,
// receives the byte the requester sent on that lane, and the byte the
// requester gets back is the byte the target returned, on that lane,
// with the other lanes zero -- and are stated with ghost registers that
// capture the request and the response from the ports, independently
// of the bridge's own storage. The lane rule (lowest set strobe bit,
// lane 0 for no strobe) is restated here in f_lane_of rather than
// borrowed from the module's function, for the same reason.
//
// WHY THE LANE IS THE STROBE'S AND NOT THE ADDRESS'S is a fact about
// the fabric these properties do not encode but the covers exercise:
// Ibex word-aligns every data address and puts the byte offset in the
// byte enable, for loads as for stores (ibex_load_store_unit.sv, "output
// data address must be word aligned"), and soc_apb_bridge_props.v A11
// proves that enable reaches PSTRB unchanged. The first draft of these
// properties named the lane by PADDR[1:0] and the proof passed against
// a request the fabric never issues. The lane covers below are stated
// with PADDR[1:0] == 2'b00 and a one-hot PSTRB, which is the request it
// does issue, so that the shape that was wrong is the shape that is
// covered.
//
// WHAT IS NOT PROVEN HERE:
//
//   * Liveness. Nothing here says a cycle ever terminates. A target
//     that never asserts ACK, ERR or RTY holds the bridge in its strobe
//     state and PREADY low forever, and every property below still
//     holds. The bridge cannot make a target answer, so a bounded
//     liveness claim would be a property of the target, not of this
//     module; the cover task shows completion is REACHABLE, which is
//     weaker, and says so.
//   * That the target obeys Wishbone. Nothing about ack_i, err_i, rty_i
//     or dat_i is assumed: the target may assert two terminations at
//     once, or a termination while the bus is idle, and the properties
//     must hold regardless. That is deliberate. The two cores this
//     bridge is for have no ERR or RTY pin, so a proof that leaned on
//     their good behaviour would be leaning on a tie-off. Both
//     misbehaviours have a cover below, so that "must hold regardless"
//     is a claim about states the solver reached and not about states
//     the assumptions happened to exclude.
//   * Which slot selects this bridge, and the truncation of adr_o to
//     the core's address width. Both are the instantiation's, in
//     soc_top.v, and are checked by the cocotb suite against the
//     generated map, not here.
//   * That PSTRB at this port is what Ibex drove. That is A11's claim
//     about soc_apb_bridge, proved there, and the composition is by
//     the same argument as E1-E5.
//   * The meaning of PRDATA on a write. APB defines it for reads only,
//     and D2 is stated for reads only.

reg f_past_valid;
initial f_past_valid = 1'b0;
always @(posedge clk_i) f_past_valid <= 1'b1;

initial assume (!rst_ni);

// A termination, as seen on the ports. Stated here rather than borrowed
// from the module so that a property cannot inherit a mistake in the
// module's own decode.
wire f_wb_term = ack_i | err_i | rty_i;

// ---------------------------------------------------------------------
// Environment: what a legal APB requester does
// ---------------------------------------------------------------------
//
// These are the five clauses of the APB transfer sequence, restated as
// assumptions on the requester's outputs. They are the same clauses
// soc_apb_bridge_props.v A1-A5 PROVE of the fabric's requester (E1 is
// A1, E2 is A2, E3 is A4, E4 is A3, E5 is A5), so the composition is
// sound: what is assumed here is proved there.
always @(posedge clk_i) if (rst_ni) begin
    // E1. PENABLE only inside a selected transfer.
    assume (!penable_i || psel_i);
end

always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    // E2. SETUP lasts exactly one cycle and is always followed by ACCESS.
    if ($past(psel_i) && !$past(penable_i))
        assume (psel_i && penable_i);

    // E3. A wait state holds ACCESS: PSEL and PENABLE stay high until
    //     this bridge raises PREADY.
    if ($past(psel_i) && $past(penable_i) && !$past(pready_o))
        assume (psel_i && penable_i);

    // E4. The payload is stable from SETUP to the end of ACCESS. PSTRB
    //     is part of the payload, and A3 proves it stable with the rest.
    if ($past(psel_i) && !($past(psel_i) && $past(penable_i) && $past(pready_o))) begin
        assume (paddr_i  == $past(paddr_i));
        assume (pwrite_i == $past(pwrite_i));
        assume (pwdata_i == $past(pwdata_i));
        assume (pstrb_i  == $past(pstrb_i));
    end

    // E5. PREADY ends the transfer: the next cycle is IDLE or a new
    //     SETUP, never a continued ACCESS.
    if ($past(psel_i) && $past(penable_i) && $past(pready_o))
        assume (!penable_i);
end

// ---------------------------------------------------------------------
// Ghost state
// ---------------------------------------------------------------------
//
// Deliberately independent of the bridge's own registers: these capture
// the request from the APB port and the response from the Wishbone
// port, so a property comparing them cannot be satisfied by the bridge
// merely being self-consistent.
//
// An APB transfer, seen from the port, begins in the first cycle PSEL is
// high with no transfer in progress (SETUP, for a requester that obeys
// E2) and ends in the cycle PREADY is high.
reg             f_apb_active;
reg [ADR_W-1:0] f_req_addr;
reg             f_req_write;
reg [31:0]      f_req_wdata;
reg [3:0]       f_req_strb;

// Whether this transfer began with PENABLE already high -- ACCESS with
// no SETUP, which APB forbids and E1-E5 do not exclude -- so that the
// path the module's header says serves that mistake has a witness.
reg             f_req_nosetup;

// Terminations the bridge has accepted -- strobe high and one of ACK,
// ERR, RTY high -- during the current APB transfer. Two bits so that a
// second one is representable and can therefore be forbidden.
reg [1:0]       f_terms;

reg [7:0]       f_resp_data;
reg             f_resp_err;
reg             f_resp_rty;

// How many cycles the strobe has been high, so a wait-state cover
// obligation can name a depth instead of chaining $past. Saturating,
// because the covers only ever ask about small values.
reg [2:0]       f_stb_cycles;
always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)                     f_stb_cycles <= 3'd0;
    else if (!stb_o)                 f_stb_cycles <= 3'd0;
    else if (f_stb_cycles != 3'd7)   f_stb_cycles <= f_stb_cycles + 3'd1;
end

always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        f_apb_active <= 1'b0;
        f_req_addr   <= {ADR_W{1'b0}};
        f_req_write  <= 1'b0;
        f_req_wdata  <= 32'h0;
        f_req_strb   <= 4'h0;
        f_req_nosetup <= 1'b0;
        f_terms      <= 2'd0;
        f_resp_data  <= 8'h0;
        f_resp_err   <= 1'b0;
        f_resp_rty   <= 1'b0;
    end else begin
        if (psel_i && !f_apb_active) begin
            f_apb_active <= 1'b1;
            f_req_addr   <= paddr_i;
            f_req_write  <= pwrite_i;
            f_req_wdata  <= pwdata_i;
            f_req_strb   <= pstrb_i;
            f_req_nosetup <= penable_i;
            f_terms      <= 2'd0;
        end else if (psel_i && penable_i && pready_o) begin
            f_apb_active <= 1'b0;
        end
        if (stb_o && f_wb_term) begin
            f_resp_data <= dat_i;
            f_resp_err  <= err_i | rty_i;
            f_resp_rty  <= rty_i;
            if (f_terms != 2'd3) f_terms <= f_terms + 2'd1;
        end
    end
end

// The lane a strobe names: its lowest set bit, lane 0 when none is set.
// This is the adapter's contract, written down once, here, and NOT the
// module's own lane_of -- a property that called the design's function
// would prove the design agrees with itself.
function [1:0] f_lane_of;
    input [3:0] strb;
    begin
        casez (strb)
            4'b???1: f_lane_of = 2'd0;
            4'b??10: f_lane_of = 2'd1;
            4'b?100: f_lane_of = 2'd2;
            4'b1000: f_lane_of = 2'd3;
            default: f_lane_of = 2'd0;
        endcase
    end
endfunction

wire [1:0] f_lane = f_lane_of(f_req_strb);

// The byte of the captured request on the lane the captured strobe
// names, and the address the target must see: the captured word offset
// with that lane in its low two bits.
reg [7:0] f_req_byte;
always @(*) begin
    case (f_lane)
        2'd0: f_req_byte = f_req_wdata[7:0];
        2'd1: f_req_byte = f_req_wdata[15:8];
        2'd2: f_req_byte = f_req_wdata[23:16];
        2'd3: f_req_byte = f_req_wdata[31:24];
    endcase
end
wire [ADR_W-1:0] f_req_wbaddr = {f_req_addr[ADR_W-1:2], f_lane};

// ---------------------------------------------------------------------
// I1: strengthening invariant, needed for induction and for nothing else
// ---------------------------------------------------------------------
//
// The ghost and the bridge's state machine have to agree, or
// k-induction starts from a state where the bridge is idle and the ghost
// believes a transfer is in flight, which is unreachable but not
// excluded. This is the one place in this file that names the design's
// own state; it says the ghost tracks the design, not that the design
// is right.
//
// A transfer is active exactly while the state machine is not idle,
// and this transfer's termination has been counted exactly when the
// response is being delivered.
always @(posedge clk_i) if (rst_ni) begin
    assert (f_apb_active == (state != ST_IDLE));
    if (state == ST_CYCLE) assert (f_terms == 2'd0);
    if (state == ST_RESP)  assert (f_terms == 2'd1);
end

// ---------------------------------------------------------------------
// W1-W8: the Wishbone B3 classic cycle, from the initiator's side
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    // W1. STB only inside a cycle: CYC frames it (B3 3.1.4).
    assert (!stb_o || cyc_o);

    // W2. And this bridge issues single cycles only, so CYC is never held
    //     across an idle strobe -- the "cyc framing" docs/65 section 9.4
    //     names as the proof surface. A block cycle would be legal B3
    //     and would break both cores' ack generation.
    assert (!cyc_o || stb_o);

    // W3. No Wishbone cycle without an APB transfer in ACCESS. This is
    //     the property a bridge that answered its own idle state, or
    //     that strobed the target during SETUP, would violate.
    assert (!cyc_o || (psel_i && penable_i));

    // W4. Once the strobe is up it stays up, with ADR, WE, DAT and SEL
    //     unchanged, until the target terminates (B3 3.2.1, 3.2.2).
    if ($past(stb_o) && !$past(f_wb_term)) begin
        assert (stb_o && cyc_o);
        assert (adr_o == $past(adr_o));
        assert (we_o  == $past(we_o));
        assert (dat_o == $past(dat_o));
        assert (sel_o == $past(sel_o));
    end

    // W5. Termination ends the cycle: STB and CYC drop in the next cycle
    //     (B3 3.1.3), which is what lets a target that pulses ack, or
    //     toggles it while stb is held, see exactly one strobe.
    if ($past(stb_o) && $past(f_wb_term))
        assert (!stb_o && !cyc_o);

    // W6. SEL is qualified by STB (B3 3.1.4) and, with one lane, is
    //     that lane: high with the strobe and only with the strobe.
    assert (sel_o == stb_o);

    // W7. Exactly one termination per APB transfer: never a strobe after
    //     this transfer's cycle has terminated, and never a second
    //     termination counted.
    assert (!(stb_o && f_terms != 2'd0));
    assert (f_terms != 2'd2 && f_terms != 2'd3);
    if (pready_o) assert (f_terms == 2'd1);

    // W8. The idle bus is low: outside a selected transfer nothing is
    //     driven toward the target.
    if (!psel_i)
        assert (!cyc_o && !stb_o && !sel_o);
end

// ---------------------------------------------------------------------
// P1-P3: the completer side of AMBA 3 APB
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    // P1. PREADY is raised exactly one cycle after the target terminated
    //     the cycle this bridge launched, and never otherwise. The
    //     "never otherwise" half is what makes a termination seen while
    //     the strobe is low -- which nothing forbids the target from
    //     asserting -- harmless: it does not become a PREADY.
    assert (pready_o == ($past(stb_o) && $past(f_wb_term)));

    // P2. PREADY only while a transfer is in ACCESS.
    assert (!pready_o || (psel_i && penable_i));

    // P3. PSLVERR only with PREADY.
    assert (!pslverr_o || pready_o);
end

// ---------------------------------------------------------------------
// D1-D2: the lane adapter's data integrity
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    // D1. While the strobe is up, the target is addressed with the word
    //     offset the requester asked for and the lane its strobe named
    //     in the low two bits, is told the right direction, and sees
    //     the byte from that lane. Stated through the PREADY cycle as
    //     well: B3 does not ask for that, but the lane of PRDATA is
    //     decoded from adr_o in that cycle, and this is where D2's lane
    //     is anchored to the request. The first induction attempt
    //     failed without it, from a state where a separate lane
    //     register disagreed with the address; the register is gone and
    //     the anchor is here.
    if (stb_o || pready_o) begin
        assert (adr_o == f_req_wbaddr);
        assert (we_o  == f_req_write);
        assert (dat_o == f_req_byte);
    end

    // D2. In the PREADY cycle the error flag is the target's ERR or RTY
    //     from the termination, and on a read the byte the target
    //     returned at termination sits on the lane the strobe named
    //     with the other three lanes zero.
    if (pready_o) begin
        assert (pslverr_o == f_resp_err);
        if (!f_req_write) begin
            case (f_lane)
                2'd0: assert (prdata_o == {24'h0, f_resp_data});
                2'd1: assert (prdata_o == {16'h0, f_resp_data, 8'h0});
                2'd2: assert (prdata_o == {8'h0, f_resp_data, 16'h0});
                2'd3: assert (prdata_o == {f_resp_data, 24'h0});
            endcase
        end
    end
end

// ---------------------------------------------------------------------
// Cover: every proven behaviour must be reachable
//
// docs/09-formal-verification-plan.md B.1 vacuity rule: an assert set
// with unreachable behaviour proves nothing. Each of these is a distinct
// shape the assertions above are supposed to be constraining. The lane
// covers are stated as Ibex issues the request -- PADDR[1:0] zero, the
// byte offset in a one-hot PSTRB -- because that is the shape the first
// draft got wrong and a cover on the address's low bits would not have
// noticed.
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && rst_ni) begin
    cover (pready_o && !pslverr_o && !f_req_write);           // a read completes
    cover (pready_o && !pslverr_o &&  f_req_write);           // a write completes
    cover (pready_o &&  pslverr_o && !f_resp_rty);            // ERR terminates
    cover (pready_o &&  pslverr_o &&  f_resp_rty);            // RTY terminates
    // Zero wait states: the target terminates in the first strobe cycle.
    cover (stb_o && f_wb_term && f_stb_cycles == 3'd0);
    // Three wait states, counted rather than expressed with a multi-cycle
    // $past so that the obligation is readable and the depth is explicit.
    cover (stb_o && f_wb_term && f_stb_cycles == 3'd3);
    // Back to back: a new SETUP in the cycle after PREADY.
    cover (psel_i && !penable_i && $past(pready_o));
    // lbu at byte offset 3, as Ibex issues it: aligned address, strobe
    // 4'b1000. The target is addressed at offset 3 and the byte comes
    // back in bits 31:24 with nothing below.
    cover (pready_o && !f_req_write && f_req_addr[1:0] == 2'b00 &&
           f_req_strb == 4'b1000 && adr_o[1:0] == 2'd3 &&
           f_resp_data == 8'hA5);
    // sb at byte offset 1, as Ibex issues it: aligned address, strobe
    // 4'b0010, byte on bits 15:8. The target is addressed at offset 1
    // and receives that byte.
    cover (stb_o && f_wb_term && we_o && f_req_addr[1:0] == 2'b00 &&
           f_req_strb == 4'b0010 && adr_o[1:0] == 2'd1 && dat_o == 8'h5A);
    // A half-word strobe reaches its lowest byte: 4'b1100 is lane 2.
    cover (stb_o && f_wb_term && f_req_strb == 4'b1100 && adr_o[1:0] == 2'd2);
    // A word strobe reaches lane 0.
    cover (stb_o && f_wb_term && f_req_strb == 4'b1111 && adr_o[1:0] == 2'd0);
    // No strobe at all on a read is lane 0.
    cover (pready_o && !f_req_write && f_req_strb == 4'b0000 &&
           adr_o[1:0] == 2'd0);
    // The two target misbehaviours the header says are tolerated, as
    // witnesses rather than as claims. A termination in the SETUP cycle,
    // before the strobe is up: the bridge launches its cycle anyway and
    // does not hand the stray ACK back as a PREADY.
    cover ($past(psel_i && !stb_o && f_wb_term) && stb_o && !pready_o);
    // ACK and ERR asserted together: one termination, reported as an
    // error, and the transfer completes.
    cover (pready_o && pslverr_o && $past(ack_i && err_i));
    // ACCESS with no SETUP, which APB forbids and the module's header
    // says is served from ACCESS rather than hung on: it completes.
    cover (pready_o && f_req_nosetup);
end
