// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// soc_tmr_bank: one physical replica of a TMR domain in the SoC.
//
// =====================================================================
// WHERE THIS COMES FROM, AND WHAT IS DIFFERENT
// =====================================================================
//
// This module is derived from `pilot_cfg_bank` in hw/rtl/pilot_top.v --
// the same POL + MIX storage transform, the same two unit-triangular
// XOR layers, the same reasoning. It is a separate module in hw/soc/rtl
// rather than a reuse of that one for two reasons, both mechanical:
//
//   * `pilot_cfg_bank` is declared inside hw/rtl/pilot_top.v, a file
//     that also declares the whole NPU pilot and includes npu_regs.vh.
//     Reading it into the SoC's synthesis and simulation flows to get
//     one bank module would drag the pilot's elaboration in with it.
//   * docs/34-pilot-freeze.md pins every file in hw/rtl by git blob hash
//     for the TTIHP26b shuttle, so that file cannot be split.
//
// hw/rtl/tmr_voter.v is a different case and is NOT copied: it is a
// standalone 61-line file with no includes, so hw/soc reads it in place.
// Nothing in hw/rtl is modified by this work.
//
// Three deliberate differences from `pilot_cfg_bank`:
//
//   1. NO PER-BIT WRITE ENABLE. The whole word is written on every clock
//      edge. This is not a simplification for its own sake; it is the
//      answer to the problem docs/40 section 7.2 found in this domain.
//      Everything in soc_wdog.v lives in the POWER-ON reset domain, so
//      there is no reset that ever cleans up after an upset -- the
//      watchdog's own reset does not reach it, and a power cycle is the
//      end of the mission's uptime. A bank that HOLDS its value repairs
//      a corrupted replica only when the value is next written, and a
//      register such as `rst_seen` or the bootstrap latch is written
//      once and then never again. So a held bank in this domain
//      accumulates corruption: the first upset is masked, the second in
//      a different replica on the same bit is not, and nothing in
//      between rewrites the first. Writing unconditionally makes the
//      voter a continuous scrubber: the corrected word goes back into
//      all three replicas on the very next edge, so the domain is
//      exposed to a coincident second upset for one clock cycle rather
//      than for the mission.
//
//      That is also why this bank is cheaper than pilot_cfg_bank per
//      bit: with no partial write there is no read-modify-write, so the
//      MIX replica needs no decode-substitute-encode mux, only the
//      encode on the way in and the decode on the way out.
//
//   2. MIX IS AVAILABLE ON MORE THAN ONE REPLICA, and soc_wdog.v uses it
//      on two. pilot_cfg_bank pays for the mixing once because
//      polarity alone already separates A from B where merging happens.
//      That is true, and docs/33-rail-transform.md then measured what it
//      costs: to separate B from A on EVERY bit, POL_B has to be all
//      ones, which makes B's reset image all ones, which is a flip-flop
//      dfflibmap has to build by inversion, and abc folds the inversion
//      against the bank's own correction. The polarity is erased at
//      technology mapping. It does not matter there, because dfflibmap
//      runs after the last pass that can merge anything -- but it means
//      the artifact carries one defence where the RTL states two.
//
//      Giving B the mixing too removes the need for POL_B to be all
//      ones: B and C are separated from A by the weight of their stored
//      functions and from each other by POL_B = ~POL_C, so both POL
//      masks can be mixed patterns and neither reset image is uniform.
//      Whether that survives technology mapping is a measurement, not an
//      argument, and it is made in docs/41 section 6 rather than
//      asserted here.
//
//   3. AN ELABORATION GUARD ON W >= 4, which pilot_top.v carries at the
//      instantiation and this module does not have. It is here because
//      the whole point of this bank in the SoC is that one-bit and
//      two-bit flags are BUNDLED into it -- see below -- and a future
//      edit that narrowed the bundle would silently disarm MIX.
//
// =====================================================================
// THE REPLICATION BOUND, AND WHY THE BUNDLE IS THE ANSWER
// =====================================================================
//
// hw/rtl/pilot_top.v section 8.2 proves that three replicas cannot be
// held apart over ONE bit: there are exactly two storage functions, x
// and ~x, so a third replica is bit-for-bit identical to one of the
// other two and opt_merge hashes it away.
// docs/30-dispatcher-protection.md section 3.3 re-derives the general
// statement: over W bits the affine transforms give 2 * (2^W - 1)
// coordinate functions -- 2 at W = 1, 6 at W = 2, 14 at W = 3 -- and
// three replicas need six distinct ones, so THREE BITS is the first
// width at which a third replica has functions left to take.
//
// The state this bank protects in soc_wdog.v is mostly one-bit flags:
// the bootstrap latch, the stage-1 pending flag, the reset record. None
// of them can be tripled on its own. They are therefore concatenated
// into a single word of PW bits and this bank replicates the WORD, which
// is the move hw/rtl/pilot_top.v's header already names ("state bundled
// into one W >= 4 bank so that MIX applies") and which docs/30 could not
// make for `dstate` because that state is two bits and has nowhere else
// to go. Here the bits are all in one module and all in one reset
// domain, so the bundle is free.
//
// =====================================================================
// WHAT THIS MODULE DOES NOT DO
// =====================================================================
//
//   * It does not vote. It is one replica. The voter is
//     hw/rtl/tmr_voter.v and the instantiating block owns it.
//   * It does not report. A replica cannot know it is the odd one out.
//   * It does not resynchronise itself. Resync here is the
//     unconditional write from the voted word, and that belongs to the
//     instantiating block because only it knows what the next value is.
//   * It claims nothing about the MAPPED netlist. What POL and MIX buy
//     is that no two replicas present the same stored function to the
//     structural hashing in `opt_merge`, which runs before technology
//     mapping. Whether the mapped cells are still distinguishable is a
//     separate question, docs/33 is the record of getting that
//     distinction wrong once, and the evidence that the defence held is
//     the FLIP-FLOP COUNT in sw/tests/test_soc_synthesis_guards.py.

`timescale 1ns / 1ps
`default_nettype none

// keep_hierarchy is the first of the two anti-merge defences and the
// weaker one: `flatten` skips a module carrying it and `opt_merge` does
// not merge instances of user-defined modules unless invoked with
// -share_all. It is flow-portable across the yosys ASIC recipe and
// synth_ecp5 and NOT portable to a front end that does not read yosys
// attributes -- which is the whole reason the POL/MIX storage transform
// below exists and is measured with this attribute deleted from the
// text of the file.
(* keep_hierarchy *)
module soc_tmr_bank #(
    parameter integer W       = 8,      // <= 64, and >= 4 (see the guard)
    parameter [63:0]  RST_VAL = 64'd0,  // reset image, true polarity
    parameter [63:0]  POL     = 64'd0,  // per-bit storage polarity
    parameter integer MIX     = 0       // 0 = polarity only, 1 = + XOR mix
) (
    input  wire         clk_i,
    input  wire         rst_ni,   // the instantiating block's reset
    input  wire [W-1:0] d_i,      // next value, true polarity, every clock
    output wire [W-1:0] q_o       // stored value, true polarity
);

    // Split point of the two XOR layers. Below four bits a half is one
    // bit wide, the layer-2 rotation `(i+1) % LO` degenerates to the
    // identity, and a stored bit can fall back to weight 1 -- which is
    // exactly the collision MIX exists to make impossible. This is the
    // guard pilot_top.v carries at its instantiation; here it is in the
    // module, because in this design the bundle width is what a future
    // edit is most likely to change.
    generate
        if (W < 4) begin : g_too_narrow
            ERROR_soc_tmr_bank_W_below_4_disarms_the_MIX_transform guard ();
        end
        if (W > 64) begin : g_too_wide
            ERROR_soc_tmr_bank_W_exceeds_the_64_bit_RST_VAL_and_POL guard ();
        end
    endgenerate

    localparam integer LO = W / 2;
    localparam integer HI = W - LO;

    // enc: true value -> stored image. Layer 1 makes every low bit
    // `v[i] ^ v[LO+i]` (weight 2). Layer 2 makes every high bit
    // `v[LO+i] ^ enc_lo[(i+1) % LO]` (weight 3; the rotation by one is
    // what stops the layer-2 term cancelling the bit's own value). No
    // output row has weight 1, which is the whole property: nothing of
    // weight >= 2 can equal x_i or ~x_i for any i, so a MIX replica is
    // PROVABLY non-collidable with a polarity replica rather than
    // measured to be.
    function [W-1:0] mix_enc(input [W-1:0] v);
        reg [W-1:0] t;
        integer i;
        begin
            t = v;
            for (i = 0; i < LO; i = i + 1)
                t[i] = v[i] ^ v[LO + i];
            for (i = 0; i < HI; i = i + 1)
                t[LO + i] = v[LO + i] ^ t[(i + 1) % LO];
            mix_enc = t;
        end
    endfunction

    // dec: stored image -> true value. The same two layers in reverse.
    // Layer 2 never touched the low half, so c[(i+1) % LO] below is
    // still the layer-1 output that enc used. The map is a product of
    // two unit-triangular matrices over GF(2), so it is invertible by
    // construction and this is its inverse, not an approximation of one.
    function [W-1:0] mix_dec(input [W-1:0] c);
        reg [W-1:0] t;
        integer i;
        begin
            t = c;
            for (i = 0; i < HI; i = i + 1)
                t[LO + i] = c[LO + i] ^ c[(i + 1) % LO];
            for (i = 0; i < LO; i = i + 1)
                t[i] = c[i] ^ t[LO + i];
            mix_dec = t;
        end
    endfunction

    // keep is the weakest of the three layers and is here only to stop
    // opt_clean removing the wire name; hw/rtl/pilot_top.v measured that
    // on its own it does NOT stop the merge. It is never the evidence.
    (* keep *) reg [W-1:0] bits;

    generate
    if (MIX == 0) begin : g_polarity
        always @(posedge clk_i or negedge rst_ni) begin
            if (!rst_ni) bits <= RST_VAL[W-1:0] ^ POL[W-1:0];
            else         bits <= d_i ^ POL[W-1:0];
        end
        assign q_o = bits ^ POL[W-1:0];
    end else begin : g_mixed
        always @(posedge clk_i or negedge rst_ni) begin
            if (!rst_ni) bits <= mix_enc(RST_VAL[W-1:0]) ^ POL[W-1:0];
            else         bits <= mix_enc(d_i) ^ POL[W-1:0];
        end
        assign q_o = mix_dec(bits ^ POL[W-1:0]);
    end
    endgenerate

endmodule

`default_nettype wire
