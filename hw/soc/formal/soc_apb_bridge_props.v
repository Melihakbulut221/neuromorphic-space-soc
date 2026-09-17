// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Formal properties for the system-bus to APB bridge (SymbiYosys
// harness, hw/soc/formal/soc_apb_bridge.sby).
//
// WHERE THESE PROPERTIES COME FROM, which matters more than what they
// say. This repository has twice locked in a bug by writing a checker
// that restated what the implementation did. Every property below is a
// clause of one of two specifications, both of which existed before the
// RTL:
//
//   * AMBA 3 APB. Every transfer is IDLE, then SETUP for exactly one
//     cycle with PSEL high and PENABLE low, then ACCESS with both high
//     until PREADY, with PADDR/PWRITE/PWDATA/PSTRB held stable from
//     SETUP to the end of ACCESS and PSLVERR meaningful only in the
//     PREADY cycle. A1-A5 are those clauses.
//   * The Ibex memory protocol, quoted in full in the header of
//     hw/soc/rtl/soc_bus.v from
//     ext/ibex/doc/03_reference/load_store_unit.rst: one grant per
//     request, exactly one rvalid per grant, response carries err. A6-A9
//     are those clauses from the slave side.
//
// DEVIATIONS, ENUMERATED HERE SO THE HEADER IS ENOUGH (2026-09-18).
// soc_apb_bridge gained an APB_TIMEOUT parameter, default 0. At 0 this
// file asserts everything below with no antecedent and the module is
// bit-identical to what it was; `prove` is that proof. At a non-zero
// value the bridge releases the FABRIC with a synthesised error after
// a bounded wait and holds the APB side, and exactly three clauses are
// deviated from, each guarded on `to_fired` at the point it is stated:
//
//   A5   PREADY no longer ends the transfer, because the bridge is
//        parked. Keeping A5 instead would mean dropping PSEL and
//        PENABLE, which is a master-side abort APB does not have and
//        A4 forbids. One of the two has to give and A4 is the one kept.
//   A9   a response can appear with no PREADY behind it. That IS the
//        parameter.
//   A10  that response is synthesised, so it is not what the
//        peripheral returned, because the peripheral returned nothing.
//
// A12, A12a and A12b are new and are the price of keeping the rest:
// PSEL and PENABLE stay asserted through a timeout, the timeout state
// belongs to ST_ACCESS, and at APB_TIMEOUT = 0 it does not exist.
// `prove_to` proves all of it at APB_TIMEOUT = 8.
//
// A10 and A11 are data-integrity properties -- what came back is what
// the peripheral returned, at the address that was asked for -- and are
// stated with ghost registers that capture the request and the response
// independently of the bridge's own storage.
//
// WHAT IS NOT PROVEN HERE:
//
//   * Liveness. Nothing here says a transfer ever completes. If the
//     peripheral never asserts PREADY the bridge waits forever and every
//     property below still holds. That is correct -- an APB slave is
//     required to assert PREADY eventually and this bridge cannot make
//     it -- but it means "the SoC cannot hang" is not a claim this file
//     supports. The cover tasks show that completion is REACHABLE, which
//     is weaker.
//   * Anything about which peripheral is selected. PSEL decode is in
//     soc_top.v, deliberately (see the bridge header), and is checked by
//     the cocotb suite against the generated map, not here.
//   * Byte strobes reaching a peripheral that honours them. Neither
//     peripheral in this SoC implements sub-word writes; PSTRB is
//     carried and its stability is proved, and nothing more is claimed.
//   * The 20-bit address truncation. A11 proves paddr_o carries
//     addr_i[19:0]; that the upper bits are safe to discard is a
//     property of the memory map (the bridge window is 1 MiB), checked
//     in sw/tests/test_memmap.py, not here.

reg f_past_valid;
initial f_past_valid = 1'b0;
always @(posedge clk_i) f_past_valid <= 1'b1;

initial assume (!rst_ni);

// ---------------------------------------------------------------------
// Environment: what a legal master and a legal peripheral do
// ---------------------------------------------------------------------
//
// Ibex protocol rule 1: req stays high until gnt, and the payload does
// not change while the request is pending. Without this the bridge would
// be asked to be correct against a master that is not.
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
// Ghost state
// ---------------------------------------------------------------------
//
// Deliberately independent of the bridge's own registers: these capture
// the request from the master port and the response from the peripheral
// port, so a property comparing them cannot be satisfied by the bridge
// merely being self-consistent.
reg [19:0] f_req_addr;
reg        f_req_write;
reg [31:0] f_req_wdata;
reg [3:0]  f_req_strb;
reg        f_outstanding;      // one at most; A7 proves that

reg [31:0] f_resp_rdata;
reg        f_resp_err;
reg        f_resp_captured;

// How many cycles the current transfer has spent in ACCESS, so a
// wait-state cover obligation can name a depth instead of chaining
// $past. Saturating, because the covers only ever ask about small values.
reg [2:0] f_access_cycles;
always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)                       f_access_cycles <= 3'd0;
    else if (!(psel_o && penable_o))   f_access_cycles <= 3'd0;
    else if (f_access_cycles != 3'd7)  f_access_cycles <= f_access_cycles + 3'd1;
end

always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        f_outstanding   <= 1'b0;
        f_req_addr      <= 20'h0;
        f_req_write     <= 1'b0;
        f_req_wdata     <= 32'h0;
        f_req_strb      <= 4'h0;
        f_resp_captured <= 1'b0;
        f_resp_rdata    <= 32'h0;
        f_resp_err      <= 1'b0;
    end else begin
        if (req_i && gnt_o) begin
            f_outstanding   <= 1'b1;
            f_req_addr      <= addr_i[19:0];
            f_req_write     <= we_i;
            f_req_wdata     <= wdata_i;
            f_req_strb      <= be_i;
            f_resp_captured <= 1'b0;
        end else if (rvalid_o) begin
            f_outstanding <= 1'b0;
        end
        if (psel_o && penable_o && pready_i) begin
            f_resp_rdata    <= prdata_i;
            f_resp_err      <= pslverr_i;
            f_resp_captured <= 1'b1;
        end
    end
end

// ---------------------------------------------------------------------
// I1: strengthening invariant, needed for induction and for nothing else
// ---------------------------------------------------------------------
//
// The ghost counter and the bridge's state machine have to agree, or
// k-induction starts from a state where the bridge is idle and the ghost
// believes a transfer is in flight -- which is unreachable but not
// excluded, and A7 fails there. This is the one property in this file
// that names the design's own state, and it is a bookkeeping invariant
// rather than a specification clause: it says the ghost tracks the
// design, not that the design is right.
//
// A transfer is outstanding exactly while the state machine is not idle,
// plus the single extra cycle in which the response is being delivered
// and the state machine has already returned to idle.
always @(posedge clk_i) if (rst_ni) begin
    // `&& !to_fired` is the deviation, not a weakening. After a
    // timeout the state machine deliberately does NOT return to idle:
    // it holds ST_ACCESS so PSEL and PENABLE stay asserted and APB is
    // never abandoned mid-transfer. The TRANSFER, though, is over --
    // the fabric got its response -- so the bookkeeping counter is
    // zero while the state is not idle, which is a combination that
    // cannot occur at APB_TIMEOUT = 0 and is the defining one above
    // it. Deleting the term instead would make this invariant say
    // nothing about the ordinary path.
    assert (f_outstanding == (((state != ST_IDLE) && !to_fired) || rvalid_o));
end

// ---------------------------------------------------------------------
// A1-A5: the APB transfer sequence
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    // A1. PENABLE only inside a selected transfer.
    assert (!penable_o || psel_o);

    // A2. SETUP lasts exactly one cycle and is always followed by ACCESS.
    if ($past(psel_o) && !$past(penable_o))
        assert (psel_o && penable_o);

    // A3. The payload is stable from SETUP to the end of ACCESS. Stated
    //     as "whenever the previous cycle was part of this transfer and
    //     the transfer has not ended, nothing moved".
    if ($past(psel_o) && !($past(psel_o) && $past(penable_o) && $past(pready_i))) begin
        assert (paddr_o  == $past(paddr_o));
        assert (pwrite_o == $past(pwrite_o));
        assert (pwdata_o == $past(pwdata_o));
        assert (pstrb_o  == $past(pstrb_o));
    end

    // A4. A wait state holds ACCESS: PSEL and PENABLE stay high.
    if ($past(psel_o) && $past(penable_o) && !$past(pready_i))
        assert (psel_o && penable_o);

    // A5. PREADY ends the transfer: PENABLE must drop.
    //
    // THE THIRD AND LAST DEVIATION, and the one that settles what the
    // parameter really costs. A timeout cannot be made protocol-clean:
    // dropping PSEL and PENABLE is a master-side abort, which APB does
    // not have and A4 forbids; HOLDING them means a late PREADY no
    // longer ends the transfer, which is this clause. There is no
    // third option, and the choice made is to keep A4 -- never abandon
    // a transfer mid-flight -- and to pay for it here.
    //
    // So at APB_TIMEOUT != 0 the parameter costs exactly three AMBA
    // clauses, A5, A9 and A10, each antecedent-guarded on `to_fired`
    // and each stated where it is deviated from rather than in a
    // footnote. At APB_TIMEOUT = 0, the shipping netlist, it costs
    // none of them: every property here holds with no antecedent, and
    // `prove` proves exactly that.
    if ($past(psel_o) && $past(penable_o) && $past(pready_i)
        && (APB_TIMEOUT == 0 || !to_fired))
        assert (!penable_o);
end

// ---------------------------------------------------------------------
// A6-A9: the slave side of the Ibex memory protocol
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    // A6. No response without a request. This is the property that a
    //     bridge which answered its own idle state would violate.
    assert (!rvalid_o || f_outstanding);

    // A7. At most one transaction is accepted at a time, which is what
    //     the bridge promises the fabric (soc_bus.v rule S4 permits a
    //     slave to accept fewer than the fabric would allow). Stated as:
    //     no grant while one is still outstanding, unless that one is
    //     being answered in this very cycle.
    assert (!(gnt_o && f_outstanding && !rvalid_o));

    // A8. A grant requires a request.
    assert (!gnt_o || req_i);

    // A9. The response is delivered exactly one cycle after the
    //     peripheral completed the transfer, and never otherwise. The
    //     "never otherwise" half is what makes this stronger than A6.
    //
    // THE DEVIATION, and it is stated here rather than discovered by a
    // reader of a counterexample. At APB_TIMEOUT != 0 the bridge
    // releases the fabric with an error after a bounded wait, so a
    // response CAN appear with no PREADY behind it: that is the whole
    // point of the parameter, and A9's "never otherwise" is exactly
    // what it deviates from. The deviation is confined to the cycle
    // that fires it -- `to_fired` rises with the response and is
    // sticky -- so the property holds unchanged everywhere else, and
    // at the shipping APB_TIMEOUT = 0 it holds with no antecedent at
    // all, which is the parameter point the shipped netlist is.
    // `to_fired` and not `$past(to_fired)`: the flag rises WITH the
    // response, in the same cycle, so the past value is still zero
    // in the one cycle the deviation happens.
    if (APB_TIMEOUT == 0 || !to_fired)
        assert (rvalid_o == ($past(psel_o) && $past(penable_o)
                             && $past(pready_i)));
end

// ---------------------------------------------------------------------
// A10-A11: data integrity
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    // A10. What the peripheral returned in its PREADY cycle is what the
    //      master gets, unmodified, together with its error flag.
    //
    // Same deviation, same reason: a timeout response is SYNTHESISED
    // and by definition is not what the peripheral returned, because
    // the peripheral returned nothing. What the parameter buys is that
    // the core sees an error it can report instead of a stall only the
    // watchdog ends, and the price is this property's scope. At
    // APB_TIMEOUT = 0 there is no price.
    if (rvalid_o && (APB_TIMEOUT == 0 || !to_fired)) begin
        assert (f_resp_captured);
        assert (rdata_o == f_resp_rdata);
        assert (err_o   == f_resp_err);
    end

    // A12a. AT APB_TIMEOUT = 0 THE TIMEOUT STATE DOES NOT EXIST, and
    //       k-induction has to be told so. The arm is behind
    //       `APB_TIMEOUT != 0`, so at the shipping default these two
    //       registers are constant zero and every state with either of
    //       them set is unreachable -- but induction starts wherever
    //       the invariant allows, and without this it starts inside
    //       the dead arm and the proof returns UNKNOWN. Asserting them
    //       makes them part of the inductive invariant, which is the
    //       standard shape and is why it is written down rather than
    //       discovered again.
    if (APB_TIMEOUT == 0) begin
        assert (!to_fired);
        assert (to_cnt == {TO_W{1'b0}});
    end

    // A12b. THE TIMEOUT STATE BELONGS TO ST_ACCESS, at every parameter
    //       point. The counter only advances in ST_ACCESS and is
    //       cleared on the way out; the flag is only ever set there and
    //       nothing leaves ST_ACCESS after it is. Every one of those is
    //       true of the circuit and none of them is true of an
    //       arbitrary starting state, which is what k-induction picks,
    //       so the proof does not close without them being said. This
    //       is the whole of the strengthening the parameter cost.
    if (state != ST_ACCESS) begin
        assert (!to_fired);
        assert (to_cnt == {TO_W{1'b0}});
    end
    assert (to_cnt <= TO_LIMIT);

    // A12, new with the deviation. The timeout must not become a way
    // to violate APB: whatever else it does, PSEL and PENABLE stay
    // asserted, which is A4's clause and the reason the fabric side is
    // released while the APB side is not.
    if (to_fired) begin
        // The state binding comes FIRST and is what makes the rest
        // inductive. Without it k-induction starts in a state where
        // to_fired is set and the machine is idle -- which the circuit
        // cannot reach, because to_fired is only ever set inside
        // ST_ACCESS and nothing leaves ST_ACCESS afterwards -- and the
        // proof fails on a counterexample that is not a behaviour.
        assert (state == ST_ACCESS);
        assert (psel_o && penable_o);
    end

    // A11. The peripheral is addressed with the low 20 bits of the
    //      address the master asked for, and is told the right direction
    //      and the right data.
    if (psel_o) begin
        assert (paddr_o  == f_req_addr);
        assert (pwrite_o == f_req_write);
        assert (pwdata_o == f_req_wdata);
        assert (pstrb_o  == f_req_strb);
    end
end

// ---------------------------------------------------------------------
// Cover: every proven behaviour must be reachable
//
// docs/09-formal-verification-plan.md B.1 vacuity rule: an assert set
// with unreachable behaviour proves nothing. Each of these is a distinct
// shape the assertions above are supposed to be constraining.
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && rst_ni) begin
    cover (rvalid_o && !err_o);                       // a clean transfer
    cover (rvalid_o && err_o);                        // an error transfer
    cover (rvalid_o && f_req_write);                  // a write completed
    cover (rvalid_o && !f_req_write);                 // a read completed
    // Zero wait states: PREADY high in the first ACCESS cycle.
    cover (psel_o && penable_o && pready_i && !$past(penable_o));
    // Three wait states, counted rather than expressed with a multi-cycle
    // $past so that the obligation is readable and the depth is explicit.
    cover (psel_o && penable_o && pready_i && f_access_cycles == 3'd3);
    // Back to back: a new grant in the cycle a response is delivered.
    cover (rvalid_o && gnt_o);
end
