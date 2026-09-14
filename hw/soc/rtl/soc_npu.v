// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

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
// No second node. N_NODES is a parameter, the window decodes all
// sixteen NODE_ID values docs/10 section 8 item 2 allows, and fifteen
// of them are a bus error.
//
// =====================================================================
// 6. WHAT IS HARDENED, AND WHAT THE MEASUREMENT SAID TO LEAVE ALONE
// =====================================================================
//
// Until docs/55 this header said "No hardening of anything this file
// adds", and docs/39 section 9 item 3 recorded the same for the whole
// SoC. docs/52 then measured the block -- 700 injections, seven strata,
// each run twice -- and RANKED WHAT TO PROTECT BY CONSEQUENCE rather
// than by size. Three things came out of it and they are built here.
// Every one of them names the number it rests on, because a hardening
// with no measurement behind it is the mistake docs/38 section 10 item 4
// names and this file is the second block in the SoC to avoid it.
//
//   H1. A BOUND ON THE FABRIC RESPONSE.  [7 of 7 dead machines,
//       docs/52 section 7.1; 5 in the transport's phase state, 2 in
//       `win_state`]
//       This block's ONLY lethal failure is a lost fabric response: a
//       frame that never ends, so busy_o never falls, so the window
//       never leaves W_WAIT, so rvalid never returns, and Ibex stalls
//       for ever. soc_npu_ser.v now bounds the frame; the window now
//       bounds its own wait, and both turn a dead machine into a LOAD
//       ACCESS FAULT the program can handle. The watchdog caught all
//       seven and its answer was a system reset; this is the cheaper
//       answer the campaign says is worth building.
//
//   H2. THE QUEUES' PROTECTION HAS SOMEWHERE TO REPORT.  [79 absorbed
//       upsets, 0 visible to any operator channel, docs/52 section 10]
//       `ptr_mismatch`, `par_err` and `rv_mismatch` used to leave the
//       two aer_fifo instances and go nowhere. They now do two things:
//       they raise a sticky bit in this block's own cause register, and
//       they leave the block as fault lines into BUSSTAT, where docs/44
//       already built saturating counters and stickies for exactly this
//       class of event. docs/51 section 14 item 1 declined this on the
//       grounds that a fault-counter block invented HERE would put
//       NPU-only telemetry outside BUSSTAT -- which is an argument about
//       WHERE THE COUNTERS LIVE and not about whether the events are
//       visible, and the counters live in BUSSTAT.
//
//   H3. THE CONTROL AND CAUSE BANK IS TRIPLED.  [16 false fault reports
//       in 100 draws, docs/52 sections 6.3 and 11.2]
//       The highest per-bit consequence anywhere in that campaign, and
//       note its SHAPE: it is not a missed fault, it is a FABRICATED
//       one. A fault-reporting channel that invents events is worse than
//       one that is merely lossy, because it will be believed, and every
//       recovery policy docs/09's S2 supervisor might implement reads
//       this register. docs/41 section 3.1's criterion -- persistent
//       times silent -- selects exactly these bits: software writes them
//       once, this block never rewrites them, and nothing votes, scrubs
//       or reports them.
//
// H4 AND H5 ARE docs/56'S, AND THE TWO OF THEM REST ON ONE MEASUREMENT
// THAT COULD NOT BE MADE BEFORE IT. docs/52 and docs/55 drew the event
// engine as ONE stratum of 140 bits contributing 1.71 of the
// connection's 4.17 points, and docs/55 section 14 item 1 made splitting
// it the PRECONDITION of hardening it, on the ground that an
// undifferentiated stratum is hardened by protecting its largest
// structure. Split into five and drawn 100 times each, the engine's
// silent corruption is not spread over it at all:
//
//     ev_data   64 bits, 45.7 % of the engine   0 of 100
//     ev_cnt    32 bits, 22.9 %                 0 of 100
//     ev_seq    19 bits                        13 of 100
//     ev_oh     19 bits                         6 of 100
//     ev_pin     6 bits                        18 of 100
//
// -- and per SITE, 96 % of the engine's whole rate is in NINE BITS:
// `aer_in_stb` (18 of 18 draws), `ev_state` (7 of 20), `oh_req` (3 of
// 4), `cap_wr_en` (5 of 8), `oh_valid` (2 of 4) and `inj_rd_en` (1 of
// 4). THE RATE IS IN THE STROBES AND NOT IN THE DATA. docs/56 section 3.
//
//   H4. THE SHOW-AHEAD ADAPTER'S READ IS BOUNDED.  [`oh_req`: 3 silent
//       wrong inferences in 4 draws, and a wedge no campaign reached]
//       The reason is a defect this file's own header describes and
//       applies to the OTHER queue -- a read of an aer_fifo may
//       legitimately return nothing, so it needs a bound -- and the
//       adapter had none. `oh_req` was cleared by `cap_rd_valid` alone
//       and the refill stood off on `!oh_req`, so ONE discarded capture
//       entry, or one upset that set that flag, stopped the block
//       delivering events FOR EVER while `cause[C_EVT]` went on saying
//       one was waiting. Measured both ways in: docs/56 section 5.1.
//
//   H5. THE AER STROBE IS GATED BY THE STATE THAT IMPLIES IT.
//       [`aer_in_stb`: 18 silent wrong inferences in 18 draws]
//       The highest per-bit rate in any campaign this block has had, on
//       ONE flip-flop, and the whole of `ev_pin`'s contribution. An
//       upset in it strobed a phantom SPIKE or TICK into the frozen die
//       with whatever the address and type pins held, and the die
//       accepted it. `aer_in_stb == (ev_state == E_PIN_S)` was already
//       an invariant of the FSM, so the redundancy was in the netlist
//       and was not being used; the pin is now the AND of the two and a
//       disagreement raises IRQ_CAUSE.AER_MM. IT COSTS NO FLIP-FLOP.
//       Section 9.
//
// AND TWO THINGS THE MEASUREMENT SAID TO LEAVE ALONE, which is the part
// of the ranking that keeps being counter-intuitive. `evq_data` -- the
// two queues' stored words and their entry parity -- is 41.2 % of the
// connection's flip-flops and 53.5 % of its area (docs/51 section 11),
// and it produced ZERO silent wrong inferences in 100 draws. The reason
// is occupancy: the queues hold a couple of live entries out of eight,
// so most of those 304 bits are storage nothing will read. A hardening
// wave that started with the biggest structure would have spent its
// whole budget there and bought nothing. NOTHING IN THIS FILE PROTECTS
// THE QUEUE STORAGE and docs/55 section 6 is why.
//
// docs/56 found the same shape one level down and it is now a rule
// rather than a coincidence: `ev_data`, the event word in flight, is 64
// of the engine's 140 bits -- the largest sub-stratum by a factor of
// three -- and came back 0 of 100, as did `ev_cnt`'s 32. NOTHING IN
// THIS FILE PROTECTS THE EVENT WORD EITHER.
//
// =====================================================================
// 7. THE REPLICATION BOUND, AND WHY THE BANK IS ONE WORD
// =====================================================================
//
// hw/rtl/pilot_top.v section 8.2 proves three replicas cannot be held
// apart over ONE bit -- there are exactly two storage functions, x and
// ~x -- and docs/30 section 3.3 generalises it: three bits is the first
// width at which a third replica has a function left to take. Almost
// everything H3 protects is one bit wide: `ctrl_in_en`, `ctrl_out_en`
// and each of the seven sticky cause bits. Replicating any of them on
// its own would give a netlist with ONE flip-flop and a voter voting it
// against itself, and every test and every proof in this repository
// would still pass.
//
// So they are BUNDLED into one PROT_W-bit word and the WORD is
// replicated, which is docs/41 section 4.2's answer and the move
// hw/rtl/pilot_top.v's own header names. The bank is
// hw/soc/rtl/soc_tmr_bank.v -- already built, already proved, already
// instantiated in the watchdog -- and the voter is hw/rtl/tmr_voter.v,
// read in place out of the frozen directory and not copied.
//
// TWO CONSEQUENCES OF THE BUNDLE, both stated rather than discovered.
//
//   * The bank has NO WRITE ENABLE: the whole word is written from the
//     voted value on every edge, which makes the voter a continuous
//     scrubber and bounds the exposure to a coincident second upset at
//     one clock cycle. soc_tmr_bank.v difference 1 is the argument. It
//     costs nothing here that it does not cost in the watchdog.
//   * THE REPORT IS INSIDE THE PROTECTED WORD. `sticky_cfg_tmr` is a
//     field of the bank, not a register beside it, so the write that
//     repairs a replica and the write that records the repair are the
//     same write on the same edge. docs/16 section 5.8 measured what the
//     other arrangement costs: an upset can erase the announcement of
//     the very event it caused.
//
// ONE DELIBERATE DIVERGENCE FROM docs/41 SECTION 5.3, and it is the
// clearability of that report. The watchdog's `tmr_err` is NOT
// clearable, on the rule that a record software can erase is a record an
// upset can erase. Here every sticky cause bit IS write-1-to-clear,
// including this one, because IRQ_CAUSE is an INTERRUPT cause register
// whose entire contract is acknowledgement: a bit in it that could not
// be acknowledged would hold an enabled interrupt asserted for ever,
// which is docs/40 section 7.2's brick in a new place. The durable
// record lives in BUSSTAT's saturating counter instead, which is
// docs/44 section 6.4's argument for the same choice.
//
// WHAT IS STILL NOT PROTECTED, and it is most of the flip-flops. The
// transport's 40-bit shift register, the event engine's state, the
// window's captured request, the two queues' storage and both frame
// guards are single points by decision. docs/55 section 6 prices each
// one against what docs/52 measured of it, and docs/52 section 12 item 5
// is why parity over the shift register was declined.
// =====================================================================
// 8. H4's GUARD IS UNPROTECTED STATE, AND ITS CORRUPTION IS BENIGN
// =====================================================================
//
// docs/55 added twenty unprotected flip-flops whose upset FAILS A
// HEALTHY ACCESS -- the transport's guard, the window's guard and
// `win_out` -- and said so rather than netting it off. H4 adds three
// more, `oh_guard`, and they are different in kind, which is worth
// stating because "one more guard" would otherwise read as one more of
// the same trade.
//
// An upset that makes `oh_guard` expire early clears `oh_req` while a
// read may still be in flight. It cannot pop a second entry: the refill
// stands off on `!cap_rd_valid` and `!cap_rd_en`, so the earliest
// re-issue is two cycles later, by which time the in-flight read has
// either raised `cap_rd_valid` -- which sets `oh_valid` and blocks the
// refill -- or been discarded, which is the case the bound is for. And
// it cannot lose one, because nothing here touches `oh_valid` or the
// queue's pointers. THE WHOLE COST OF A SPURIOUS EXPIRY IS ONE NEEDLESS
// STICKY BIT. docs/56 section 6.4 draws into these three like any other
// site rather than assuming it.
//
// What H4 does NOT protect is the rest of the adapter. `oh_valid` and
// `oh_data` are single points: an upset that sets `oh_valid` makes the
// block hand software a stale word and report an event that is not
// there, and one that clears it loses the word the adapter is holding.
// docs/56 section 11 item 3 prices tripling the adapter's bundle
// against what the campaign measured of it and declines it in this wave,
// and section 10 of that document is the surviving exposure.
//
// =====================================================================
// 9. H5 COSTS NO STATE AT ALL, AND THAT IS WHY IT IS NOT ENOUGH
// =====================================================================
//
// H5 adds no flip-flop. `aer_in_stb == (ev_state == E_PIN_S)` is an
// invariant of the FSM below -- the flag is set on the edge out of
// E_PIN_A, cleared on the edge out of E_PIN_S, and the flush path
// clears it in the same statement that returns `ev_state` to E_IDLE --
// so the flag is a REDUNDANT ENCODING of a state this module already
// holds, and the pin is now the AND of the two. A spurious strobe needs
// two coincident upsets where it needed one.
//
// FOUR THINGS IT DOES NOT DO, and each is a decision rather than an
// oversight:
//
//   * IT DOES NOT CORRECT. On a disagreement the pin is held quiet.
//     That is the right answer when the FLAG was corrupted -- 18 of 18
//     of docs/56's draws -- and it LOSES AN EVENT when `ev_state` was,
//     and this module cannot tell which. `IRQ_CAUSE.AER_MM` says the
//     inbound path took an upset and does not claim to say more.
//   * IT DOES NOTHING FOR THE ADDRESS AND TYPE PINS. `aer_in_addr` and
//     `aer_in_tick` have no state that implies them, and docs/56
//     measured them at 0 of 65 and 0 of 17: a corrupted address on a
//     strobe that is not happening reaches nothing, and there is one
//     cycle per event in which it would.
//   * IT DOES NOTHING FOR `ev_state` ITSELF, which docs/56 measured at
//     7 of 20 and which is now the largest single site left in the
//     engine. Section 11 of docs/56 ranks it and says what it would
//     cost.
//   * AND IT IS NOT TMR. Tripling the flag is impossible on one bit
//     (section 7) and tripling the bundle would cost twelve flip-flops
//     and correct rather than mask. docs/56 section 6.1 prices that
//     against this and takes this one first because it is free, not
//     because it is stronger; section 11 item 5 is what it would still
//     buy.
//

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
    parameter integer FETCH_MAX = 8,

    // The bound on E_DECIDE, in clk_i cycles. Overridable so that a
    // board with a slow or deliberately throttled die can raise it;
    // there is no value that disables it, because a parameter that can
    // silently turn a liveness guard off is worse than no parameter.
    parameter integer DECIDE_MAX = 4095,
    // H3, the triple-redundant control and cause bank. 0 builds the
    // block as docs/51 shipped it and exists ONLY so that the cost of
    // the hardening can be measured against the same file list with the
    // same recipe -- docs/41 section 6.5 records what a baseline taken
    // against an OLDER file list costs: it credits the hardening with a
    // refactor's saving. Nothing in this repository instantiates 0, and
    // sw/tests/test_soc_npu_guards.py asserts that.
    parameter integer HARDEN = 1,

    // ---- the clock-gate enable, docs/76 ----
    //
    // 1 builds `clk_en_o` out of the block's own quiescence; 0 ties it
    // high and deletes the wake-hold counter with it, which is the
    // like-for-like baseline the gate's area and power are measured
    // against. Same discipline and same reason as HARDEN above.
    // soc_top.v passes ONE parameter to this and to the gate cell, so
    // an enable without a gate or a gate without an enable is not a
    // reachable configuration.
    parameter integer CLKGATE = 1,
    // Cycles the clock keeps running after the last activity. Not a
    // correctness term -- see the enable's own comment -- but the margin
    // that covers a settling chain inside the frozen die that no term
    // of `npu_act` names. 4 covers a two-flop synchroniser and one
    // cycle of slack; sw/tests enforces the value the design ships.
    parameter integer HOLD_CYCLES = 4
) (
    input  wire        clk_i,
    input  wire        rst_ni,

    // THE UNGATED CLOCK, and it clocks exactly one flip-flop in this
    // module: `wake_q`, the registered half of the clock-gate enable.
    // docs/77 section 5 is why it exists and section 6 is the theorem
    // that makes it safe. It is NOT a second clock domain: `clk_i` is
    // this same clock with edges REMOVED by the gate in `soc_top.v`, so
    // every edge of `clk_i` is an edge of `clk_free_i` at the same
    // instant and no crossing is created -- which is why no synchroniser
    // appears here and why OpenSTA analyses the path from this
    // module's registers to `wake_q` as an ordinary same-clock path.
    // At CLKGATE = 0 nothing reads it, and the tie-off at the bottom of
    // the file says so explicitly rather than leaving a dangling port.
    input  wire        clk_free_i,

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

    // ---- fault lines, to soc_busstat (H2 and H3) ----
    //
    // One cycle per event, which is what soc_busstat.v's counters count.
    // All three sources below are single-cycle by construction:
    // aer_fifo.v rewrites all three pointer replicas from the vote on
    // every edge and both rd_valid rails from `rd_pass` on every edge, so
    // a disagreement is exactly one cycle wide from any state; `par_err`
    // is `rd_ok && head_bad`, one cycle per accepted read; and
    // soc_tmr_bank.v is written unconditionally, so the cause bank's
    // voter disagrees for exactly one cycle after an upset.
    //
    // THEY ARE THREE PORTS AND NOT ONE, for docs/44 section 6.2's
    // reason. A corrected pointer, a discarded entry and a masked vote in
    // the register bank are three different structures with three
    // different remedies; folding them into one counter would reproduce
    // exactly what pilot_top.v's own header records costing it -- "a host
    // reading CNT_SEC cannot tell a synapse array correction from a
    // load-path one".
    output wire        q_cor_o,      // a queue pointer vote CORRECTED
    output wire        q_det_o,      // a queue entry was DISCARDED, lost
    output wire        cfg_tmr_o,    // the cause bank's voter masked one

    // ---- observation of the die's pins, for a testbench or a scope ----
    output wire        obs_ser_sck_o,
    output wire        obs_ser_cs_n_o,
    output wire        obs_ser_mosi_o,
    output wire        obs_ser_miso_o,
    output wire        obs_aer_in_stb_o,
    output wire        obs_aer_out_vld_o,

    // ---- clock-gate enable. See its own section near the bottom. ----
    output wire        clk_en_o
);

  // Width of the wake-hold counter, derived rather than parameterised so
  // that HOLD_CYCLES is the only number a reader has to check.
  localparam integer HOLD_W = (HOLD_CYCLES < 2)   ? 1 :
                              (HOLD_CYCLES < 4)   ? 2 :
                              (HOLD_CYCLES < 8)   ? 3 :
                              (HOLD_CYCLES < 16)  ? 4 :
                              (HOLD_CYCLES < 32)  ? 5 : 6;
  localparam [31:0]         HOLD_32   = HOLD_CYCLES;
  localparam [HOLD_W-1:0]   HOLD_LOAD = HOLD_32[HOLD_W-1:0];
  localparam [HOLD_W-1:0]   HOLD_ZERO = {HOLD_W{1'b0}};
  localparam [HOLD_W-1:0]   HOLD_ONE  = {{(HOLD_W-1){1'b0}}, 1'b1};

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
  // ---- the sticky half, contiguous from C_STICKY0 upward -------------
  localparam integer C_INJ_OVF  = 5; // sticky: an EVQ_IN write was refused
  localparam integer C_FETCH_ER = 6; // sticky: an injection fetch expired
  // Five bits added by docs/55, and each names the measurement it
  // answers. The first two are H1's report: a bound that fired and told
  // nobody would be a bounded wait with docs/16 section 5.1's original
  // defect still in it.
  localparam integer C_SER_TO   = 7;  // sticky: a serial frame was aborted
                                      //         by soc_npu_ser's bound
  localparam integer C_WIN_TO   = 8;  // sticky: the node window's own
                                      //         response bound expired
  // H2. docs/52 section 10: 79 upsets in 700 injections were absorbed by
  // aer_fifo's protection and NO SOFTWARE AND NO PIN COULD SEE ANY OF
  // THEM. These two bits and BUSSTAT's two counters are what changes
  // that. They are two and not one because a CORRECTED pointer
  // disagreement and a DISCARDED entry are not the same event: the first
  // lost nothing, the second lost an event.
  localparam integer C_Q_COR    = 9;  // sticky: a queue pointer vote
                                      //         corrected a replica
  localparam integer C_Q_DET    = 10; // sticky: a queue entry was
                                      //         discarded -- parity or
                                      //         a rd_valid rail
  // H3's own report, and it is a FIELD OF THE PROTECTED WORD rather than
  // a register beside it. Section 7 of the header is why.
  localparam integer C_CFG_TMR  = 11; // sticky: the cause bank's voter
                                      //         masked a mismatch
  // H4's report. docs/56 split the event engine into five strata and
  // measured the show-ahead adapter carrying the rate; this bit says the
  // adapter had to re-issue a read that produced no rd_valid. It is the
  // only channel that exists for that event: header section 8.
  localparam integer C_OH_TO    = 12; // sticky: the show-ahead adapter's
                                      //         read bound expired
  // H5's report. The AER strobe flag and the FSM state that implies it
  // disagreed, so a phantom event was suppressed at the pin -- or a real
  // one was. Header section 9.
  localparam integer C_AER_MM   = 13; // sticky: the AER strobe flag and
                                      //         ev_state disagreed
  localparam integer C_EVT_TO   = 14; // sticky: an event in flight was
                                      //         DISCARDED because the die
                                      //         would not take it and there
                                      //         was nothing to drain
  localparam integer NCAUSE     = 15;

  // The sticky bits are contiguous so that the protected word can carry
  // them as one field and the write-1-to-clear can be one part-select.
  // A future bit inserted in the middle of the levels would move
  // C_STICKY0 and everything below follows it.
  localparam integer C_STICKY0  = C_INJ_OVF;
  localparam integer NSTICKY    = NCAUSE - C_STICKY0;   // 10

  // -------------------------------------------------------------------
  // H3: the protected word.
  //
  // ONE WORD, because the replication bound is real: nine of these
  // eleven fields are ONE BIT WIDE and a one-bit bank cannot be tripled
  // (header section 7). The layout is named constants used by the
  // packing, the unpacking and the register reads alike, because docs/40
  // section 7.4 records what one literal bit position cost soc_wdog.v.
  // -------------------------------------------------------------------
  localparam integer P_IN_EN  = 0;
  localparam integer P_OUT_EN = 1;
  localparam integer P_STICKY = 2;                      // NSTICKY bits
  localparam integer P_MASK   = P_STICKY + NSTICKY;     // NCAUSE bits
  localparam integer PROT_W   = P_MASK + NCAUSE;        // 2 + 10 + 15 = 27

  // Per-replica storage transform, and the masks are soc_wdog.v's for
  // its reasons: A is the true image, B and C are MIXED so every stored
  // bit of either is an XOR of two or three distinct word bits and can
  // equal neither x_i nor ~x_i for any i -- provably non-collidable with
  // A rather than measured to be -- and B and C are separated from each
  // other by POL_B = ~POL_C on every bit. Neither reset image is
  // uniform, which is what docs/33 measured mattering at technology
  // mapping.
  localparam [63:0] POL_A = 64'h0000000000000000;
  localparam [63:0] POL_B = 64'h5555555555555555;
  localparam [63:0] POL_C = 64'hAAAAAAAAAAAAAAAA;

  generate
    // soc_tmr_bank refuses below four bits, and PROT_W is derived, so a
    // future field-list edit that narrowed it fails THERE with the
    // reason. This guard is the other direction: POL and RST_VAL are
    // 64-bit parameters.
    if (PROT_W > 64) begin : g_prot_too_wide
      ERROR_soc_npu_protected_word_exceeds_64_bits g ();
    end
    // E_DECIDE's bound against the longest legitimate transient. WIN_MAX
    // is derived from SER_HALF, so this fails HERE, with the reason, if
    // someone slows the transport down and does not raise the bound.
    if (DECIDE_MAX < 8 * WIN_MAX) begin : g_decide_too_tight
      ERROR_soc_npu_DECIDE_MAX_must_be_at_least_8x_WIN_MAX g ();
    end
  endgenerate

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
  wire        ser_timeout;
  wire [31:0] ser_rdata;

  // -------------------------------------------------------------------
  // H1: the node window's own response bound.
  //
  // soc_npu_ser.v now bounds the FRAME. That covers the five of docs/52
  // section 7.1's seven dead machines that were drawn into the
  // transport's phase state. It does NOT cover the other two, which were
  // drawn into `win_state` itself: a window that enters W_WAIT with no
  // frame in flight, or whose `ser_owner_win` is flipped so that
  // `ser_done_win` never asserts, waits for a completion that is never
  // coming and holds `rvalid_o` low for ever. A bound in the transport
  // cannot see that; only the window can.
  //
  // THE BOUND IS DERIVED FROM THE TRANSPORT'S, and the arithmetic is the
  // worst case the arbiter permits: the window may enter W_ISSUE in the
  // cycle an event-engine frame starts, wait a whole frame for it, and
  // then wait a whole frame of its own. Beyond that the engine cannot
  // interpose, because E_SER_RQ and E_DRN_RQ both stand off on
  // `win_wants`, which is high in W_ISSUE and W_WAIT.
  //
  // The two SER_HALVES_ constants restate soc_npu_ser.v's HALVES_FRAME
  // and HALVES_SLACK. Verilog-2005 gives an instantiating module no way
  // to read a submodule's localparam, so they are restated -- and
  // sw/tests/test_soc_npu_guards.py parses BOTH files and fails if they
  // disagree, which is this repository's rule for a constant that has to
  // live in two places (docs/40 section 7.4).
  localparam integer SER_HALVES_FRAME = 2 + 2 * 40 + 3;  // setup+shift+gap
  localparam integer SER_HALVES_SLACK = 2;
  localparam integer SER_GUARD_MAX =
      (SER_HALVES_FRAME + SER_HALVES_SLACK) * SER_HALF;
  // The worst LEGAL wait, counted in clk cycles from the first cycle in
  // W_ISSUE, and every term is a thing that can actually happen:
  //
  //   an event-engine frame already in flight, taken at the transport's
  //   own bound rather than at a healthy frame's length, because a
  //   frame that the transport aborts still had to be waited for
  //                                              SER_GUARD_MAX + 2
  //   the cycle W_ISSUE sees the transport idle, and the start pulse
  //                                              2
  //   the window's own frame, at the same bound  SER_GUARD_MAX + 2
  //
  // That is 2 * (SER_GUARD_MAX + 2) + 2 = 354 at SER_HALF = 2, and the
  // bound is set 16 cycles above it. The margin is small on purpose:
  // every cycle of it is a cycle a stalled CPU spends stalled, and the
  // whole point of this bound is that it is cheaper than the system
  // reset docs/52 section 7.1 measured the watchdog answering with.
  //
  // AN ARGUMENT IS NOT A MEASUREMENT and this one is measured twice:
  // hw/soc/tb/cocotb/test_soc_npu.py's
  // test_the_window_bound_never_fires_on_a_healthy_access reports the
  // largest `win_guard` a real inference produces, and the campaign's
  // clean run is a second, longer one.
  localparam integer WIN_MAX   = 2 * (SER_GUARD_MAX + 2) + 2 + 16;
  localparam integer WIN_GRD_W = $clog2(WIN_MAX + 1);

  // E_DECIDE's bound. See the state itself for why it exists; this is
  // the number.
  //
  // IT IS NOT A PROTOCOL BOUND AND MUST NOT BE READ AS ONE. Every other
  // wait in this file is bounded by something the transport guarantees
  // -- a frame is this many cycles, a synchroniser is two stages -- and
  // expiring means the part is broken. This one bounds a wait on
  // SOFTWARE AND THE BOARD: the die refusing with nothing to drain, a
  // drain switched off at CTRL.OUT_EN, a capture queue nobody is
  // reading. None of those is a transient, so the bound only has to be
  // comfortably longer than the longest legitimate one, and expiring
  // means the part has been configured or driven into a corner rather
  // than that it has failed.
  //
  // The longest legitimate transient here is a node-window frame at
  // WIN_MAX. The default is the next power of two above 8 * WIN_MAX,
  // and the relationship is CHECKED at elaboration rather than written
  // down: SER_HALF changes SER_GUARD_MAX, which changes WIN_MAX, and a
  // bound that quietly became tight when someone slowed the transport
  // down is how a liveness guard turns into an event shredder.
  localparam integer DEC_GRD_W = $clog2(DECIDE_MAX + 1);
  localparam [DEC_GRD_W-1:0] DECMAX_W = DECIDE_MAX[DEC_GRD_W-1:0];

  reg [WIN_GRD_W-1:0] win_guard;

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
      .timeout_o  (ser_timeout),
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

  // THE GRANT IS QUALIFIED ON THE HANDSHAKE AND NOT ON THE STATE ALONE,
  // for the reason the bound below is armed by the grant and not by the
  // state, and it is the same defect one level up.
  //
  // `win_state == W_IDLE` says this FSM believes it is free. `win_out`
  // says the FABRIC is still owed an rvalid. The two move together in
  // every cycle of a healthy access -- `win_out` is set on the only
  // transition out of W_IDLE and cleared by the `rvalid_o` that W_RESP
  // raises as it returns -- so on a healthy part this term is always
  // true and changes nothing. They come apart on exactly docs/52's
  // sixth dead machine: `win_state` bit 1 flipped takes W_WAIT to
  // W_IDLE with a granted request unanswered, and the unqualified form
  // then ADVERTISES THE SLAVE AS FREE WHILE IT OWES A RESPONSE.
  //
  // What that costs is not one wrong response, it is the bound. A grant
  // in that state restarts the window -- W_IDLE captures the new
  // payload and goes to W_ISSUE -- and `win_guard` is cleared by
  // `gnt_o`, so the counter that was five cycles from expiring goes back
  // to zero. A master that holds `req_i` up, which is what Ibex's
  // prefetch buffer does, re-arms it on every access for ever and the
  // bound never fires: the slave stays exactly one rvalid short of the
  // fabric's response-ownership queue and every later response goes to
  // the wrong master. The bound docs/55 section 8.2 built to catch this
  // shape is defeated by the grant that the same shape lets through.
  //
  // WHY THE SECOND TERM IS `|| rvalid_o` AND NOT JUST `!win_out`. The
  // block above says it out loud: W_RESP returns to W_IDLE in the cycle
  // it raises `rvalid_o`, and `win_out` is not cleared until the end of
  // that same cycle, so a healthy back-to-back access is granted in a
  // cycle where `win_out` is still 1. `!win_out` alone would insert a
  // dead cycle into every back-to-back pair of accesses -- a
  // performance change on the healthy path, in a slave that already
  // costs 172 cycles -- and would do it to fix nothing, because the
  // response the fabric is owed is ON THE WIRE in that cycle. The
  // disjunction is soc_bus.v rule 3 read literally: refuse only while a
  // response is owed AND not being returned.
  //
  // The assignment itself is BELOW the `win_out` block and not here,
  // where the decode it reads is: `win_out` is a reg and Verilog-2005
  // wants it declared before it is used, and its declaration belongs
  // with the argument for it rather than being pulled up here.
  reg win_err_q;

  // -------------------------------------------------------------------
  // THE BOUND IS ARMED BY THE GRANT AND NOT BY THE STATE, and the first
  // version of it was armed by the state and MISSED TWO OF THE SEVEN
  // RECORDS IT WAS BUILT FOR.
  //
  // That version ran the counter while `win_state` was W_ISSUE or
  // W_WAIT, on the reasoning that those are the two states that can wait
  // for ever. docs/55 section 8.2 replayed docs/52's seven dead machines
  // against it: the five in the transport's phase state were converted
  // to a bus error, and the two in `win_state` itself were still dead,
  // with `win_to` reading ZERO. The bound had not fired.
  //
  // The reason is that the failure is not the one the state-armed
  // version modelled. `win_state` bit 1 flipped at cycle 566 takes
  // W_WAIT (2) to W_IDLE (0): the window does not WAIT for ever, it
  // FORGETS that it was waiting. The fabric has granted a request and
  // soc_bus.v rule 3 says this slave owes exactly one rvalid for it; the
  // window has dropped back to idle owing one, and a counter that runs
  // only in W_ISSUE and W_WAIT is not running.
  //
  // So the thing that is bounded is THE OUTSTANDING REQUEST, which is a
  // fact about the fabric handshake and not about this FSM's encoding: a
  // grant happened and the rvalid it obliges has not been returned. That
  // covers both shapes with one counter -- a window that waits for ever
  // and a window that forgets -- and it has a second property the
  // state-armed version did not: the bound can never manufacture an
  // rvalid the fabric was not expecting, because `win_out` is set by a
  // grant and by nothing else.
  //
  // ONE MORE FLIP-FLOP, AND IT IS UNPROTECTED. An upset that clears
  // `win_out` while a request is outstanding re-opens the hang the bound
  // closes; an upset that sets it produces one spurious rvalid. Both are
  // in the campaign's `window` stratum and docs/55 section 8.4 reports
  // what the draws found.
  // -------------------------------------------------------------------
  reg win_out;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)        win_out <= 1'b0;
    // A grant in the same cycle as a response is a NEW transaction, so
    // the set arm wins: W_RESP returns to W_IDLE as it raises rvalid_o,
    // and gnt_o is combinational on `win_state == W_IDLE`, so the two
    // can and do coincide.
    else if (gnt_o)     win_out <= 1'b1;
    else if (rvalid_o)  win_out <= 1'b0;
  end

  assign gnt_o = req_i && (win_state == W_IDLE) && (!win_out || rvalid_o);

  // `>=` rather than `==`, for soc_npu_ser.v's reason: an upset that
  // pushes the counter above the bound must expire now, not wrap.
  wire win_expire = win_out && (win_guard >= WIN_MAX[WIN_GRD_W-1:0]);

  // -------------------------------------------------------------------
  // AND THE DUAL FAILURE, WHICH THE BOUND ALONE DOES NOT COVER.
  //
  // The bound answers "a response is owed and has not come". Its dual is
  // "the window is busy and NO response is owed", and docs/52's seventh
  // dead machine is that one: `win_state` bit 0 flipped at cycle 5,658
  // takes W_IDLE (0) to W_ISSUE (1) with nothing outstanding. The window
  // then issues a serial frame nobody asked for and, when it completes,
  // RAISES rvalid_o WITH NO GRANT BEHIND IT -- a response into a fabric
  // that is not expecting one. soc_bus.v keeps one response-ownership
  // queue per slave and rule 3 is exactly one rvalid per granted
  // request; a spurious one puts that queue out of step and every later
  // response goes to the wrong master.
  //
  // A timeout cannot see it, because nothing is waiting. What sees it is
  // that the FSM's state DISAGREES WITH THE HANDSHAKE: `win_out` is the
  // fabric's own record of whether this slave owes anything, and a
  // window that is not idle while owing nothing is in a state no grant
  // put it in.
  //
  // IT IS UNREACHABLE WITHOUT A FAULT, and by construction rather than
  // by argument: `win_out` is set on the same edge as the only
  // transition out of W_IDLE, both arms of it -- W_ISSUE for a good
  // access and W_RESP for a bad address -- and it is cleared by
  // `rvalid_o`, which W_RESP raises in the cycle it returns to W_IDLE.
  // The two move together in every cycle of a healthy access.
  //
  // The recovery is to go back to idle AND SAY NOTHING. Returning a
  // response here would be manufacturing the very thing that made this
  // record fatal.
  wire win_orphan = !win_out && (win_state != W_IDLE);

  // Two ways an access fails rather than completing, and they say
  // different things about the part: the transport aborted a frame it
  // could not finish (`ser_timeout`, handled in W_WAIT below), or the
  // window never got an answer at all (`win_expire`). Both end the
  // access the SAME way -- W_RESP with the error flag, which is a load
  // or store ACCESS FAULT at the core -- and each raises its own sticky
  // cause bit, C_SER_TO and C_WIN_TO.

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      win_state <= W_IDLE;
      win_start <= 1'b0;
      win_we    <= 1'b0;
      win_addr  <= 7'd0;
      win_wdata <= 32'd0;
      win_err_q <= 1'b0;
      win_guard <= {WIN_GRD_W{1'b0}};
      rvalid_o  <= 1'b0;
      // (`win_out` has its own reset, in its own block above.)
      rdata_o   <= 32'd0;
      err_o     <= 1'b0;
    end else begin
      win_start <= 1'b0;
      rvalid_o  <= 1'b0;

      // Restarted by every grant -- otherwise a second access would
      // inherit the first one's count -- and running for as long as a
      // response is owed.
      if (gnt_o)        win_guard <= {WIN_GRD_W{1'b0}};
      else if (win_out) win_guard <= win_guard + {{(WIN_GRD_W-1){1'b0}}, 1'b1};
      else              win_guard <= {WIN_GRD_W{1'b0}};

      if (win_orphan) begin
        // The dual. Back to idle, and NO response: the window is in a
        // state no grant put it in, and the one thing it must not do is
        // manufacture an rvalid the fabric never asked for.
        win_state <= W_IDLE;
        win_guard <= {WIN_GRD_W{1'b0}};
      end else if (win_expire) begin
        // H1. The access is FAILED rather than held, from whatever state
        // the window is in -- including W_IDLE, which is where an upset
        // that made it forget leaves it. `rdata_o` is zeroed by W_RESP's
        // own error path, so nothing here has to.
        win_err_q <= 1'b1;
        win_guard <= {WIN_GRD_W{1'b0}};
        win_state <= W_RESP;
      end else
      case (win_state)
        // THE ARM IS `gnt_o` AND NOT `req_i`, and until the grant was
        // qualified above the two were the same expression inside this
        // state -- `gnt_o` was `req_i && (win_state == W_IDLE)`, so in
        // W_IDLE it WAS `req_i`. They are no longer the same, and
        // leaving `req_i` here would have made the qualification worse
        // than useless: the window would sit in W_IDLE refusing the
        // grant and START THE ACCESS ANYWAY, capture a payload the
        // fabric never broadcast for it (soc_bus.v S2 says the buses
        // are valid only in the cycle req and gnt are both high), and
        // raise an rvalid with no grant behind it -- which is the
        // spurious response `win_orphan` exists to prevent. Measured
        // while writing this fix, in the third test of
        // hw/soc/tb/cocotb/test_soc_npu_defects.py: the window ran a
        // second, ungranted frame and answered the FIRST request with
        // it, so the counts came out right and the bound never fired.
        // The access now begins on the same wire the fabric was told
        // about, which is what it should always have said.
        //
        // ONE CASE THIS ARM IS NOT REACHED IN, named rather than left to
        // be discovered: `win_expire` is tested BEFORE this case, so a
        // grant in the same cycle as an expiry would be a grant nothing
        // captured. It cannot happen. `win_expire` needs `win_out` set
        // with `win_guard` at WIN_MAX, and the qualified `gnt_o` needs
        // `!win_out || rvalid_o`, so the two coincide only with
        // `rvalid_o` high -- and `rvalid_o` is one cycle, raised out of
        // W_RESP, which is reached only from an arm that has just
        // zeroed `win_guard`. The counter is therefore at 1, not at
        // WIN_MAX, in every cycle `rvalid_o` is high.
        W_IDLE: begin
          if (gnt_o) begin
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
            // An aborted frame returns zero and must not be presented as
            // data. The window turns it into the bus error the fabric
            // and the core already know how to carry, which is what
            // docs/52 section 12 item 1 asked for: "a load access fault
            // the program can handle" instead of a system reset.
            rdata_o   <= ser_rdata;
            win_err_q <= win_err_q | ser_timeout;
            win_guard <= {WIN_GRD_W{1'b0}};
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
  // H3. The protected word is DECLARED here, because the queues and the
  // event engine below read `ctrl_in_en`, `ctrl_out_en` and
  // `flush_pulse`; it is DRIVEN in the register-file section at the
  // bottom of the file, where the next-state function and the three
  // replicas are. Everything in this module reads the named views and
  // never the storage, which is what lets the bank be added without
  // rewriting a line of the engine.
  wire [PROT_W-1:0] prot_store;    // the voted word, or the plain one
  wire              prot_mismatch; // this cycle a replica disagrees

  wire              ctrl_in_en  = prot_store[P_IN_EN];
  wire              ctrl_out_en = prot_store[P_OUT_EN];
  wire [NSTICKY-1:0] sticky     = prot_store[P_STICKY +: NSTICKY];
  wire [NCAUSE-1:0]  irq_mask   = prot_store[P_MASK   +: NCAUSE];

  // The two self-clearing pulses are NOT in the bank, and that is
  // docs/41 section 3.1's criterion applied rather than ignored: they
  // are rewritten to zero by this block on every single clock edge, so
  // they shed an upset on their own within one cycle and there is
  // nothing for a vote to protect. Bundling them would cost four more
  // flip-flops -- two replicas of two bits -- for a hold time of one
  // cycle. docs/41 section 7 leaves 36 of the watchdog's 102 flip-flops
  // alone on the same rule.
  reg        flush_pulse, scrub_pulse;

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
  wire        inj_ptr_mm, inj_par_err, inj_rv_mm;
  reg         inj_rd_en;

  wire        inj_wr_en = apb_wr && (paddr_i == R_EVQ_IN);

  aer_fifo #(.WIDTH (16), .DEPTH (INJ_DEPTH), .DROP_W (8)) u_inj (
      .clk (clk_i), .rst_n (blk_rst_n),
      .wr_en (inj_wr_en), .wr_data (pwdata_i[15:0]), .full (inj_full),
      .rd_en (inj_rd_en), .rd_data (inj_rd_data),
      .rd_valid (inj_rd_valid), .empty (inj_empty), .level (inj_level),
      .drop_clr (1'b0), .drop_cnt (inj_drop),
      // rv_mismatch was not brought out of either instance until
      // docs/55. aer_fifo.v's own header calls the rd_valid flag "the
      // design's most dangerous small state" -- docs/16 section 5.7
      // measured 2 of 2 injections into it producing silent corruption
      // -- and the rails that detect an upset in it were reporting to
      // nothing at all.
      .ptr_mismatch (inj_ptr_mm), .rv_mismatch (inj_rv_mm),
      .par_err (inj_par_err)
  );

  wire        cap_full, cap_empty, cap_rd_valid;
  wire [15:0] cap_rd_data;
  wire [$clog2(CAP_DEPTH):0] cap_level;
  wire        cap_ptr_mm, cap_par_err, cap_rv_mm;
  reg         cap_wr_en;
  reg  [15:0] cap_wr_data;
  reg         cap_rd_en;

  aer_fifo #(.WIDTH (16), .DEPTH (CAP_DEPTH), .DROP_W (8)) u_cap (
      .clk (clk_i), .rst_n (blk_rst_n),
      .wr_en (cap_wr_en), .wr_data (cap_wr_data), .full (cap_full),
      .rd_en (cap_rd_en), .rd_data (cap_rd_data),
      .rd_valid (cap_rd_valid), .empty (cap_empty), .level (cap_level),
      .drop_clr (1'b0), .drop_cnt (),
      .ptr_mismatch (cap_ptr_mm), .rv_mismatch (cap_rv_mm),
      .par_err (cap_par_err)
  );

  // -------------------------------------------------------------------
  // H2: the queues' protection, made observable.
  //
  // docs/52 section 10 counted every one of these at the bench and found
  // 74 corrected pointer disagreements, 5 rail disagreements and 2
  // discarded entries in 700 injections, of which an operator could see
  // exactly ZERO. In silicon a corrected pointer upset was
  // indistinguishable from no upset at all, which means nothing could
  // tell "the mechanism has never fired" from "the mechanism is broken"
  // -- docs/16 section 7.6's general form of the argument.
  //
  // A CORRECTION AND A DETECTION ARE NOT THE SAME EVENT and they are not
  // folded together. The pointer vote CORRECTED and lost nothing; a
  // discarded entry or a held-low rd_valid LOST AN EVENT and the queue
  // is merely still consistent. A mission reading a rising `q_det_o`
  // count is reading dropped work; a rising `q_cor_o` count is reading
  // the environment.
  // -------------------------------------------------------------------
  wire q_cor_ev = inj_ptr_mm  || cap_ptr_mm;
  wire q_det_ev = inj_par_err || cap_par_err || inj_rv_mm || cap_rv_mm;

  assign q_cor_o = q_cor_ev;
  assign q_det_o = q_det_ev;

  // The one-entry show-ahead adapter (pilot_top.v section 8, convention
  // C9): the register view of EVQ_OUT is a single-access pop, and
  // aer_fifo presents its data one cycle after an accepted read.
  reg         oh_valid;
  reg  [15:0] oh_data;
  reg         oh_req;      // a read is in flight

  wire        oh_pop = apb_rd && (paddr_i == R_EVQ_OUT) && oh_valid;

  // -------------------------------------------------------------------
  // H4: THE SHOW-AHEAD'S READ IS BOUNDED. Header section 8.
  //
  // Until docs/56 the sentence where this counter now sits read:
  //
  //   "A read whose entry fails its parity check returns no rd_valid;
  //    oh_req simply stays set until the next entry arrives, and the
  //    queue's own level tells software the difference."
  //
  // THAT IS FALSE AND IT IS FALSE IN THE ONE DIRECTION THAT MATTERS.
  // `oh_req` is cleared by `cap_rd_valid` and by nothing else, and the
  // refill below requires `!oh_req`. So a read that produces no
  // `rd_valid` leaves `oh_req` set for ever, no further `cap_rd_en` is
  // ever issued, and EVERY LATER EVENT IS STRANDED IN THE CAPTURE QUEUE
  // -- while `cause[C_EVT]` goes on reporting that an event is waiting,
  // because it reads `!cap_empty`. A driver polling EVQ_OUT polls for
  // ever. docs/56 section 5.1 measures both ways in.
  //
  // The precedent is TWENTY LINES UP IN THIS FILE'S OWN HEADER, applied
  // to the other queue: "aer_fifo may legitimately answer a read with
  // nothing -- an entry whose stored parity fails is DISCARDED and
  // rd_valid is held low. A fetch that never returns would hang the
  // engine, so it expires, counts, and reports." The engine's E_FETCH
  // does exactly that. The adapter did not, and the two reads have the
  // same failure because they are reads of the same queue type.
  //
  // THE BOUND IS DERIVED AND NOT WRITTEN DOWN. `aer_fifo` registers
  // `rd_valid` from `rd_ok = rd_en && !empty`, so a healthy read raises
  // `cap_rd_valid` exactly one cycle after `cap_rd_en`, and `oh_req` is
  // high for the `cap_rd_en` cycle and the `rd_valid` cycle and no
  // others:
  //
  //   OH_WAIT   = 1 (the cap_rd_en cycle) + 1 (the rd_valid cycle) = 2
  //   OH_MAX    = OH_WAIT + OH_SLACK                               = 4
  //   OH_GUARD_W= $clog2(OH_MAX + 1)                               = 3
  //
  // The guard counts cycles in which `oh_req` is set, so on a healthy
  // read it reaches exactly OH_WAIT and never more.
  //
  // `test_the_show_ahead_bound_never_fires_on_a_healthy_read` reports
  // the largest guard it saw over a real inference and requires it to be
  // exactly OH_WAIT, so the bound, the read and the declared slack are
  // three numbers that agree rather than three that are consistent.
  //
  // THE COMPARISON IS `>=` AND NOT `==`, for docs/55 section 4.2's
  // reason: an upset that pushed the counter above the bound would
  // otherwise wrap and take another 2^OH_GUARD_W cycles, rebuilding the
  // stall inside the guard that exists to stop it.
  //
  // ON EXPIRY IT CLEARS `oh_req` AND DOES NOTHING ELSE -- no read is
  // issued here and `oh_valid` is not touched. That matters, and it is
  // why this guard's own corruption is BENIGN where docs/55's two are
  // not (header section 8): the refill below stands off on
  // `!cap_rd_valid` and `!cap_rd_en`, so the earliest a re-issue can
  // happen is two cycles after the expiry, by which time a read that
  // was genuinely in flight has either set `oh_valid` -- which blocks
  // the refill -- or been discarded. A SPURIOUS EXPIRY THEREFORE CANNOT
  // POP A SECOND ENTRY AND CANNOT LOSE ONE. What it costs is one
  // needless `IRQ_CAUSE.OH_TO`.
  // -------------------------------------------------------------------
  localparam integer OH_WAIT    = 2;
  localparam integer OH_SLACK   = 2;
  localparam integer OH_MAX     = OH_WAIT + OH_SLACK;
  localparam integer OH_GUARD_W = (OH_MAX < 2)   ? 1 :
                                  (OH_MAX < 4)   ? 2 :
                                  (OH_MAX < 8)   ? 3 :
                                  (OH_MAX < 16)  ? 4 :
                                  (OH_MAX < 32)  ? 5 : 6;
  localparam [OH_GUARD_W-1:0] OH_MAX_G = OH_MAX[OH_GUARD_W-1:0];

  reg [OH_GUARD_W-1:0] oh_guard;
  wire oh_expire = oh_req && !cap_rd_valid && (oh_guard >= OH_MAX_G);

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      oh_valid  <= 1'b0;
      oh_data   <= 16'd0;
      oh_req    <= 1'b0;
      cap_rd_en <= 1'b0;
      oh_guard  <= {OH_GUARD_W{1'b0}};
    end else if (!blk_rst_n) begin
      oh_valid  <= 1'b0;
      oh_req    <= 1'b0;
      cap_rd_en <= 1'b0;
      oh_guard  <= {OH_GUARD_W{1'b0}};
    end else begin
      cap_rd_en <= 1'b0;
      if (cap_rd_valid) begin
        oh_data  <= cap_rd_data;
        oh_valid <= 1'b1;
        oh_req   <= 1'b0;
      end else begin
        // The pop and the expiry are SEPARATE `if`s and not an
        // `else if` chain, because `oh_valid` and `oh_req` can both be
        // set at once under an upset -- the refill's `!oh_valid` makes
        // that unreachable on a healthy part -- and chaining them would
        // let an expiry swallow an acknowledged pop and hand software
        // the same event twice. With `oh_expire` false this is the
        // arm docs/51 shipped, unchanged.
        if (oh_pop)    oh_valid <= 1'b0;
        // H4. The read produced no rd_valid inside its bound: give the
        // adapter its request back so the refill can re-issue it.
        if (oh_expire) oh_req   <= 1'b0;
      end
      // The guard counts cycles in which a request is outstanding and is
      // cleared by anything that ends one -- including its own expiry,
      // so a second expiry costs a second full bound rather than firing
      // on every cycle after the first.
      if (oh_req && !oh_expire) oh_guard <= oh_guard + 1'b1;
      else                      oh_guard <= {OH_GUARD_W{1'b0}};
      // Refill when the holding register is free and nothing is in
      // flight. A read whose entry fails its parity check returns no
      // rd_valid, and H4's bound above is what gives `oh_req` back so
      // this condition can become true again.
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

  // H5: THE STROBE THE DIE SEES IS NOT THE FLIP-FLOP. Header section 9.
  // Both wires are assigned below the event engine, because both are
  // functions of `ev_state`, which that section declares.
  wire        aer_in_stb_q;   // the flag AND the state that implies it
  wire        aer_stb_mm;     // the two disagreed: an upset in one of them

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
      .aer_in_stb  (aer_in_stb_q),
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
  // The queues' four fault reports are no longer in this list; docs/55
  // gave them a sticky bit each in the cause register and a counter each
  // in BUSSTAT, which is header section 6 item H2.
  wire _unused_node = &{1'b0, node_aer_out_id, 1'b0};

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

  // E_DECIDE's guard counter. Unprotected on purpose and the argument is
  // the same one `reload` and `counter` rest on in soc_wdog.v: the block
  // REWRITES it every cycle it is in E_DECIDE and zeroes it on every
  // exit, so an upset in it is gone by the next event. What an upset can
  // do is end one wait early or late, and both land on the same arm --
  // an event discarded with C_EVT_TO raised, which is a reported
  // discard and not a silent one.
  reg [DEC_GRD_W-1:0] dec_guard;

  // The top bit of an event word says it goes over the serial link:
  // 2'b10 and 2'b11 both have it set, which is what E_DECIDE's first arm
  // tested inline until the bound below needed the same test in a second
  // place. Named once, read twice.
  wire ev_is_ser = ev_word[15];
  reg [15:0] cnt_in, cnt_out;

  // -------------------------------------------------------------------
  // E_DECIDE'S ESCAPE, AND WHY IT NEEDS A BIT OF ITS OWN
  //
  // E_DECIDE holds while the die's input queue is full, and the hold had
  // no bound and no way out. That is a DEADLOCK and not a stall, because
  // of the interlock the header states three paragraphs above: a full
  // EVQ_OUT on the die stalls its update pipeline, a stalled pipeline
  // stops consuming EVQ_IN, and a full EVQ_IN is exactly what holds
  // E_DECIDE. The only thing that unblocks the die is a DRAIN, and
  // E_DRN_RQ was reachable from E_IDLE alone. Reproduced with the pilot
  // in the loop, no upset injected, in
  // hw/soc/tb/cocotb/test_soc_npu_defects.py: eight spikes and a tick
  // into an 8 x 8 node with the host not draining leaves `ev_state` at
  // E_DECIDE and `node_aer_in_rdy` low for ever, and turning CTRL.OUT_EN
  // on afterwards -- which is the operator's whole recovery -- changes
  // nothing, because nothing in E_DECIDE ever looks at it again.
  //
  // THE REVIEW'S SUGGESTION WAS "GO TO E_DRN_RQ", AND ON ITS OWN IT
  // LOSES AN EVENT. E_DRN_RQ and E_DRN_W both end at E_IDLE, and E_IDLE
  // pops the next word out of the injection queue. The event already
  // sitting in `ev_word` -- popped, counted against nothing, never
  // delivered -- would be silently dropped, and docs/10 section 7.2 is
  // that spikes are never dropped. So the diversion has to be a
  // DETOUR AND NOT A RESTART, and this bit is what makes it one: set on
  // the way out of E_DECIDE, tested by E_DRN_W, which returns to
  // E_DECIDE with `ev_word` untouched instead of to E_IDLE.
  //
  // ONE MORE FLIP-FLOP, AND IT IS UNPROTECTED, on soc_npu.v's own
  // accounting for `win_out` and `oh_guard`. Its two corruptions are not
  // symmetric and neither is a new way to lose an event:
  //
  //   * upset to 1 with no detour in progress: the next drain that
  //     completes returns to E_DECIDE instead of E_IDLE. `ev_word` still
  //     holds whatever it last held, so the engine either re-delivers
  //     one event or -- if that word was a SYNC -- sends one extra
  //     serial frame. It is a DUPLICATE, which the die counts, and the
  //     engine leaves E_DECIDE by its normal exits.
  //   * upset to 0 during a detour: the drain completes and the engine
  //     returns to E_IDLE, which is the pre-fix behaviour for that one
  //     event -- it is dropped. One event, once, and the deadlock is
  //     still gone.
  //
  // *Corrected 2026-09-11. This read "It is NOT in
  // `hw/soc/fi/npu_targets.py`, so no campaign draws into it yet and the
  // two paragraphs above are reasoning and not measurement." It went in
  // on 2026-09-10 and the SAME COMMIT that wrote it added the site --
  // `npu_targets.py`'s `ev_seq` stratum carries `ev_resume` and has
  // since 26f4494, which is also where this sentence landed. Two edits
  // in one change, one of them describing the other's absence.*
  //
  // It IS a site. `ev_seq` went from 19 bits to 20 when it was added, so
  // that stratum's draws are not comparable with `docs/52`'s, `docs/55`'s
  // or `docs/56`'s; the other four engine sub-strata are untouched and
  // stay comparable, which is the property `docs/56` section 3 rests on.
  reg        ev_resume;

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
      dec_guard   <= {DEC_GRD_W{1'b0}};
      ev_resume   <= 1'b0;
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
        // CTRL.FLUSH empties the queues and the engine, and a detour
        // back to an event that no longer exists is exactly the state
        // this pulse is for getting rid of.
        ev_resume  <= 1'b0;
      end else begin
      case (ev_state)
        E_IDLE: begin
          aer_in_stb <= 1'b0;
          // Cleared here as well as on every exit from E_DECIDE, so an
          // upset that sets it while the engine is idle cannot shorten
          // the NEXT event's wait.
          dec_guard  <= {DEC_GRD_W{1'b0}};
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
        //
        // `>=` AND NOT `==`, which is this file's own rule and was
        // applied at the window bound (`win_guard >= WIN_MAX`) and at
        // the show-ahead bound (`oh_guard >= OH_MAX_G`) and not here.
        // The reason is soc_npu_ser.v's and it is the same one: an upset
        // that pushes the counter ABOVE the bound must expire now, not
        // count on through 4'hF, wrap to zero and take the long way
        // round -- which is a stall inside the guard that exists to
        // remove stalls, and `ev_wait` is exactly four bits, so the long
        // way round is up to fifteen extra cycles per upset.
        E_FETCH: begin
          if (inj_rd_valid) begin
            ev_word  <= inj_rd_data;
            ev_state <= E_DECIDE;
          end else if (ev_wait >= FETCHMAX_4) begin
            ev_state <= E_IDLE;
          end else begin
            ev_wait <= ev_wait + 4'd1;
          end
        end

        E_DECIDE: begin
          if (ev_is_ser) begin
            dec_guard <= {DEC_GRD_W{1'b0}};
            ev_state <= E_SER_RQ;
          end else if (node_aer_in_rdy) begin
            aer_in_tick <= ev_word[14];
            aer_in_addr <= ev_word[3:0];
            dec_guard   <= {DEC_GRD_W{1'b0}};
            ev_state    <= E_PIN_A;
          end else if (drain_want) begin
            // THE ESCAPE. The die has no room and it has an event to
            // give up; take the detour, and come back here to the same
            // `ev_word` when the drain completes. The declaration of
            // `ev_resume` above is why this is a detour and not a
            // restart, and why the review's shorter form -- go to
            // E_DRN_RQ and let it end at E_IDLE -- drops this event.
            //
            // THE ORDER OF THESE THREE ARMS IS THE WHOLE OF THE HEALTHY
            // PATH BEING UNCHANGED. `node_aer_in_rdy` is tested first,
            // so an engine that CAN deliver still delivers, and this arm
            // is unreachable unless the die is refusing. That is not an
            // inversion of "DRAIN OUTRANKS INJECT": that rule is E_IDLE's
            // and it still holds there. Here the injection is already in
            // flight -- the word is popped and the queue no longer has
            // it -- and draining first on every event that found the die
            // busy would put a 172-cycle frame in front of an event that
            // was about to go over the pins in five cycles.
            ev_resume <= 1'b1;
            dec_guard <= {DEC_GRD_W{1'b0}};
            ev_state  <= E_DRN_RQ;
          end else if (dec_guard >= DECMAX_W) begin
            // THE BOUND. The three arms above did not fire for
            // DECIDE_MAX consecutive cycles, so the die is refusing and
            // there is nothing to drain: CTRL.OUT_EN is off, or the
            // capture queue is full because software stopped reading
            // it, or the die is simply not taking events. None of those
            // ends on its own and the engine used to wait here for ever,
            // which meant one misconfigured register stopped every
            // later event as well as this one.
            //
            // The event IS LOST and that is the whole cost of the bound.
            // It is lost LOUDLY: C_EVT_TO is sticky and write-1-to-clear
            // like every other fault bit, so a discard cannot happen
            // without a record, and IRQCAUSE tells the two apart -- a
            // part that discarded an event reads C_EVT_TO, a part that
            // is merely busy reads nothing. Silent loss is the thing
            // this engine must never do; bounded, reported loss is
            // better than an engine that stops.
            //
            // Back to E_IDLE and not to E_FETCH, so that DRAIN OUTRANKS
            // INJECT gets its turn before the next event is popped: if
            // the die does have something to give, the very next cycle
            // takes it, and the interlock this bound exists beside is
            // cleared without a second discard.
            ev_word   <= 16'd0;
            ev_resume <= 1'b0;
            dec_guard <= {DEC_GRD_W{1'b0}};
            ev_state  <= E_IDLE;
          end else begin
            // `>=` rather than `==` for E_FETCH's reason: an upset in
            // the high bits of the counter must not send it round again.
            dec_guard <= dec_guard + {{(DEC_GRD_W-1){1'b0}}, 1'b1};
          end
          // The hold above is now BOUNDED, and what follows is the
          // record of what it used to be.
          // AER_IN_RDY is !full on the die; a strobe into a full queue
          // would be counted as a software-port drop, which is the one
          // thing this engine must never make the die report.
          //
          // AND THE HOLD IS STILL UNBOUNDED, which is stated rather than
          // implied by the arm above. The escape covers the interlock --
          // the die is full BECAUSE its output has nowhere to go -- and
          // that is the deadlock the engine could construct on its own.
          // It does NOT cover a die that refuses with nothing to drain,
          // nor one whose drain is switched off at CTRL.OUT_EN, nor a
          // capture queue software has stopped reading: in all three
          // `drain_want` is low and this state waits. Those are ended by
          // CTRL.FLUSH, which is a register write and therefore
          // something software still has to do. A bound here would have
          // to end the wait by DISCARDING `ev_word`, and that needs a
          // cause bit to report the discard with; there is no spare one
          // in the protected word and adding one is a register-map
          // change. It is left open on purpose and named here.
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
        //
        // `>=` for E_FETCH's reason. This one is the cheapest of the
        // three to get wrong and the easiest to miss: the bound is 2, so
        // an upset in the high bits of `ev_wait` sends the engine round
        // the whole four-bit range while the die's strobe is already
        // low and the queue already has room -- thirteen cycles of
        // nothing, on a state whose entire job is to be three cycles
        // long.
        E_PIN_G: begin
          if (ev_wait >= 4'd2) begin
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
            // The detour returns to the event it left, not to E_IDLE.
            // `ev_word` was not touched by either drain state, so
            // E_DECIDE re-runs its own decode on the same word. It is
            // cleared unconditionally, so a return to E_IDLE cannot
            // leave the next drain believing it is a detour.
            ev_resume <= 1'b0;
            ev_state  <= ev_resume ? E_DECIDE : E_IDLE;
          end
        end

        default: ev_state <= E_IDLE;
      endcase
      end
    end
  end

  // -------------------------------------------------------------------
  // H5: the AER strobe, gated by and checked against the state that
  // already implies it. Header section 9.
  //
  // `aer_in_stb` is set on the edge out of E_PIN_A and cleared on the
  // edge out of E_PIN_S, and the flush path clears it in the same
  // statement that returns `ev_state` to E_IDLE. So
  //
  //     aer_in_stb == (ev_state == E_PIN_S)
  //
  // IS AN INVARIANT OF THIS FSM, and the flag is therefore a REDUNDANT
  // ENCODING of a state the module already holds. It was not being used
  // as one: the flag drove the die's pin alone, so a single upset in it
  // strobed a phantom SPIKE or TICK into the frozen die -- with whatever
  // `aer_in_addr` and `aer_in_tick` happened to hold -- and the die
  // accepted it as a real event. docs/56 section 3 measured that at
  // 18 SILENT WRONG INFERENCES IN 18 DRAWS, the highest per-bit rate
  // anywhere in this block's campaigns and the whole of the largest
  // sub-stratum's contribution.
  //
  // WHAT IT COSTS IS NOTHING AND THAT IS THE POINT. There is no new
  // flip-flop, no replica, no counter: the redundancy is already in the
  // netlist and this uses it. A spurious strobe now needs TWO
  // coincident upsets -- one in the flag and one in `ev_state`, in the
  // same cycle, landing on the same encoding -- where it needed one.
  // docs/56 section 6.1 is why that is not the same as tripling the
  // flag, and what it does NOT buy.
  //
  // AND IT DOES NOT CORRECT, IT MASKS AND REPORTS. `aer_stb_mm` is the
  // disagreement, and it is the aer_fifo dual-rail pattern
  // (hw/rtl/aer_fifo.v, "the rd_valid rails") with the second rail
  // being state that exists for another reason. Driving the pin from
  // `ev_state` ALONE would also mask the flag's upset, and would delete
  // the flag -- but it would move the whole exposure into `ev_state`,
  // which docs/56 section 3 measured at 7 of 20, and it would report
  // nothing. This keeps both and requires both.
  // -------------------------------------------------------------------
  wire aer_stb_state = (ev_state == E_PIN_S);
  assign aer_in_stb_q = aer_in_stb && aer_stb_state;
  assign aer_stb_mm   = aer_in_stb ^ aer_stb_state;

  // -------------------------------------------------------------------
  // APB register file
  // -------------------------------------------------------------------
  wire [NCAUSE-1:0] cause;
  assign cause[C_EVT]      = !cap_empty || oh_valid;
  assign cause[C_ERR]      = node_err;
  assign cause[C_SEC]      = node_sec;
  assign cause[C_DED]      = node_ded;
  assign cause[C_TMR]      = node_tmr;
  assign cause[NCAUSE-1:C_STICKY0] = sticky;

  assign irq_o = |(cause & irq_mask);

  // `>=` because E_FETCH's own exit is `>=`, and the two have to be the
  // SAME predicate or the sticky bit stops describing the state
  // machine. With `==` here and `>=` there, an upset that pushed
  // `ev_wait` past the bound would end the fetch and report NOTHING:
  // C_FETCH_ER is the only durable record that an injected event was
  // abandoned, and an expiry nobody records is docs/16 section 5.1's
  // defect back again.
  wire fetch_expire = (ev_state == E_FETCH) && !inj_rd_valid
                   && (ev_wait >= FETCHMAX_4);

  // E_DECIDE's three exits and its bound, as wires, so that the state
  // machine above and the cause bit below read the SAME condition.
  //
  // fetch_expire beside it restates E_FETCH's arm in a second place and
  // the file accepts that; this one does not, because it has three arms
  // rather than one and the failure mode of a drifted copy here is an
  // event discarded with no cause bit raised -- `docs/16` section 5.1's
  // defect, which is the thing that comment is about.
  wire dec_hold   = (ev_state == E_DECIDE)
                 && !ev_is_ser && !node_aer_in_rdy && !drain_want;
  // Gated on blk_rst_n, which fetch_expire is not. CTRL.FLUSH exists to
  // discard what is in flight, so a discard IT caused is not a fault of
  // the part, and H3's whole subject is false fault reports. One cycle
  // wide: dec_hold goes low on the same edge, because the state leaves.
  wire dec_expire = dec_hold && blk_rst_n && (dec_guard >= DECMAX_W);

  // ---- the seven sticky events, in cause-bit order -------------------
  //
  // Each is one cycle wide and each sets its bit for good until software
  // acknowledges it. `ser_timeout` is taken UNQUALIFIED by owner: a
  // frame the transport had to abort is a fault of the part whether the
  // window or the event engine owned it, and an engine frame that was
  // aborted would otherwise be reported by nothing at all.
  wire [NSTICKY-1:0] sticky_ev;
  assign sticky_ev[C_INJ_OVF  - C_STICKY0] = inj_wr_en && inj_full;
  assign sticky_ev[C_FETCH_ER - C_STICKY0] = fetch_expire;
  assign sticky_ev[C_SER_TO   - C_STICKY0] = ser_timeout;
  // ONE BIT FOR BOTH OF THE WINDOW'S RECOVERIES -- the bound and its
  // dual -- because what an operator has to know is that the node
  // register window had to repair itself, and the two are told apart at
  // the bench rather than in the register. A second cause bit would be
  // three more flip-flops in the protected word for a distinction no
  // recovery policy acts on differently.
  assign sticky_ev[C_WIN_TO   - C_STICKY0] = win_expire || win_orphan;
  assign sticky_ev[C_Q_COR    - C_STICKY0] = q_cor_ev;
  assign sticky_ev[C_Q_DET    - C_STICKY0] = q_det_ev;
  assign sticky_ev[C_CFG_TMR  - C_STICKY0] = prot_mismatch;
  // H4. The show-ahead adapter had to take its own request back. It is
  // ONE bit and there is no BUSSTAT counter behind it, which is a
  // decision and not an omission: docs/55 section 14 item 2 ranks that
  // block -- 126 unprotected flip-flops whose whole job is to be
  // believed -- as the next thing to protect, and a fourth NPU counter
  // would be eighteen more of them for an event whose durable record
  // nothing yet acts on. docs/56 section 5.2 is the argument and section
  // 10 carries the exposure it leaves: this bit is write-1-to-clear, so
  // software that acknowledges it keeps no record of it anywhere.
  assign sticky_ev[C_OH_TO    - C_STICKY0] = oh_expire;
  // E_DECIDE's bound expired and the event in flight was discarded. One
  // cycle wide: the state leaves for E_IDLE on the same edge.
  assign sticky_ev[C_EVT_TO   - C_STICKY0] = dec_expire;
  // H5. The strobe flag and the state that implies it disagreed. It
  // is a DETECTION and not a correction -- the pin was held quiet,
  // which is right when the flag was the corrupted one and is a lost
  // event when `ev_state` was, and this block cannot tell which. The
  // bit says an upset reached the inbound event path; docs/56 sections
  // 6.2 and 6.3 are why it detects rather than corrects and why it is a
  // bit of its own.
  assign sticky_ev[C_AER_MM   - C_STICKY0] = aer_stb_mm;

  // docs/77: THE ONE STICKY LINE THAT IS NOT A FUNCTION OF THIS BLOCK'S
  // REGISTERS, named and masked rather than left for a cofactor.
  //
  // `C_INJ_OVF` is `inj_wr_en && inj_full`, and `inj_wr_en` is
  // `psel_i && penable_i && pwrite_i` against a register offset. It can
  // therefore only be true in a cycle in which `psel_i` is high -- and
  // `psel_i` is a term of `npu_act_fast`, which stays combinational. The
  // other eight are functions of this block's registers alone, measured
  // rather than asserted: the census in
  // sw/tests/test_soc_clkgate_guards.py walks the fan-in cone of
  // `npu_act_slow` cut at every sequential cell and fails if ANY input
  // port is reachable, and it was that census that found this bit.
  //
  // Masking it out of the SLOW half loses nothing: an overflow still
  // wakes the block in its own cycle, through `psel_i`. What it buys is
  // that the census can be an equality with zero rather than a list of
  // exceptions.
  localparam [NSTICKY-1:0] STICKY_FROZEN =
      ~({{(NSTICKY-1){1'b0}}, 1'b1} << (C_INJ_OVF - C_STICKY0));

  // The clear strobe. Write-1-to-clear, and only the sticky half: a
  // write to a level bit is accepted and does nothing, because the way
  // to clear a level is to fix what is raising it.
  wire [NSTICKY-1:0] sticky_clr =
      (apb_wr && (paddr_i == R_IRQCAUSE)) ? pwdata_i[NCAUSE-1:C_STICKY0]
                                          : {NSTICKY{1'b0}};

  // -------------------------------------------------------------------
  // H3: the next value of the protected word.
  //
  // COMBINATIONAL, and the whole word is written from it on every edge.
  // That is not a style choice: soc_tmr_bank.v has no write enable, so
  // the voter is a continuous scrubber and the exposure to a coincident
  // second upset is one clock cycle rather than the rest of the mission.
  // A bank that HELD its value would repair a corrupted replica only at
  // the next write -- and `ctrl_in_en`, the interrupt mask and every
  // sticky bit are written once by software and then never again, which
  // is exactly the accumulation soc_tmr_bank.v difference 1 describes.
  //
  // Writing it as one function of the current word also means the
  // HARDEN = 0 configuration below runs IDENTICAL policy to HARDEN = 1,
  // which is what makes the area comparison in docs/55 a comparison of
  // the redundancy and not of two different designs. docs/41 section 6.5
  // is the record of getting that baseline wrong once.
  //
  // AN EVENT AND ITS OWN CLEAR IN THE SAME CYCLE RESOLVE IN FAVOUR OF
  // THE EVENT, which is soc_busstat.v's rule and for its reason: the
  // cycle a sticky is being acknowledged is the cycle a telemetry frame
  // is being built, and losing the upset that lands in it is the one
  // loss this block can avoid for free.
  // -------------------------------------------------------------------
  reg [PROT_W-1:0] prot_n;
  integer          pi;
  always @(*) begin
    prot_n = prot_store;

    for (pi = 0; pi < NSTICKY; pi = pi + 1)
      prot_n[P_STICKY + pi] = sticky_ev[pi]
                            | (sticky[pi] & ~sticky_clr[pi]);

    if (apb_wr) begin
      case (paddr_i)
        R_CTRL: begin
          prot_n[P_IN_EN]  = pwdata_i[B_IN_EN];
          prot_n[P_OUT_EN] = pwdata_i[B_OUT_EN];
        end
        R_IRQMASK: prot_n[P_MASK +: NCAUSE] = pwdata_i[NCAUSE-1:0];
        default: ;
      endcase
    end
  end

  // The self-clearing pulses, outside the bank. See their declaration.
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      flush_pulse <= 1'b0;
      scrub_pulse <= 1'b0;
    end else begin
      flush_pulse <= apb_wr && (paddr_i == R_CTRL) && pwdata_i[B_FLUSH];
      scrub_pulse <= apb_wr && (paddr_i == R_CTRL) && pwdata_i[B_SCRUB];
    end
  end

  generate
  if (HARDEN != 0) begin : g_cfg_tmr
    wire [PROT_W-1:0] qa, qb, qc;

    // Three replicas of ONE word. Nine of the eleven fields are one bit
    // wide and could not be tripled on their own -- header section 7 --
    // and the transform that holds these three apart through `opt_merge`
    // is soc_tmr_bank.v's POL/MIX storage coding, not the attributes it
    // also carries. The evidence that it survived is the FLIP-FLOP COUNT
    // in sw/tests/test_soc_synthesis_guards.py, taken with every
    // attribute deleted from the text of the file; docs/33 is the record
    // of what a header claim without that census is worth.
    soc_tmr_bank #(.W(PROT_W), .RST_VAL(64'd0), .POL(POL_A), .MIX(0))
      u_cfg_a (.clk_i(clk_i), .rst_ni(rst_ni), .d_i(prot_n), .q_o(qa));
    soc_tmr_bank #(.W(PROT_W), .RST_VAL(64'd0), .POL(POL_B), .MIX(1))
      u_cfg_b (.clk_i(clk_i), .rst_ni(rst_ni), .d_i(prot_n), .q_o(qb));
    soc_tmr_bank #(.W(PROT_W), .RST_VAL(64'd0), .POL(POL_C), .MIX(1))
      u_cfg_c (.clk_i(clk_i), .rst_ni(rst_ni), .d_i(prot_n), .q_o(qc));

    // hw/rtl/tmr_voter.v, read in place and not copied. Proved
    // exhaustively in formal/tmr_voter.sby and checked against an
    // independent Python majority model in hw/tb/test_tmr_voter.py.
    // Nothing in hw/rtl is modified by this instantiation.
    tmr_voter #(.WIDTH(PROT_W)) u_cfg_vote (
        .in_a     (qa),
        .in_b     (qb),
        .in_c     (qc),
        .out      (prot_store),
        .mismatch (prot_mismatch)
    );
  end else begin : g_cfg_plain
    // HARDEN = 0: the bank as docs/51 shipped it, one flip-flop per bit.
    // MEASUREMENT ONLY -- it is the baseline docs/55 section 7 prices the
    // redundancy against, and nothing in this repository instantiates it.
    reg [PROT_W-1:0] plain;
    always @(posedge clk_i or negedge rst_ni) begin
      if (!rst_ni) plain <= {PROT_W{1'b0}};
      else         plain <= prot_n;
    end
    assign prot_store    = plain;
    // A constant, so `sticky_ev[C_CFG_TMR]` is a constant, so the bit
    // and the fault line below are dead and the optimiser deletes them.
    // That is correct and it is what makes the HARDEN = 0 flip-flop
    // count PROT_W - 1 rather than PROT_W; the census in
    // sw/tests/test_soc_synthesis_guards.py derives that arithmetic
    // rather than writing it down, exactly as docs/41 section 6.3 does
    // for the watchdog's own five missing flip-flops.
    assign prot_mismatch = 1'b0;
  end
  endgenerate

  assign cfg_tmr_o = prot_mismatch;

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

  // -------------------------------------------------------------------
  // THE CLOCK-GATE ENABLE
  //
  // docs/57 section 9 measured that this block multiplies the SoC's idle
  // power by 5.588 and docs/61 section 7.3 measured why: every one of
  // the 2,178 flip-flops `soc_top` gained when this module arrived is on
  // the UNGATED clock net, because the design's one `sg13g2_lgcp_1` is
  // bound inside `ibex_top` and gates Ibex and nothing else. This is the
  // enable for the second one.
  //
  // IT IS ONE DOMAIN AND NOT SEVERAL, and the reason is the transport
  // rather than a preference. `soc_npu_ser` generates `ser_sck` from
  // `clk_i` by division, and `pilot_top` samples that pin on `clk`. Two
  // domains -- the CPU face clocked, the die not -- would make the
  // die's serial port a clock-domain crossing between a divided clock
  // and a stopped one, which is a real CDC in a block that has none and
  // cannot be given one, because `hw/rtl/pilot_top.v` is frozen by
  // docs/34 and only its clock can be reached from outside. The die
  // stops with the transport or not at all.
  //
  // WHAT MAKES IT DIFFERENT FROM soc_bus.v's. That module's enable is
  // PROVED complete -- hw/soc/formal/soc_bus_props.v F10, k-induction,
  // and every one of its five terms is load-bearing under mutation. No
  // such proof is available here: the state this enable has to cover
  // includes 2,152 flip-flops inside a frozen submission whose property
  // set is `formal/` and is not this project's to extend. So the enable
  // is made CONSERVATIVE in two independent ways and then MEASURED:
  //
  //   1. `npu_act` names every reason this block or the die behind it
  //      could have work to do, including every reason it could have a
  //      FAULT to record. That second class is not decoration and it is
  //      the one thing gating a fault-tolerant block gets wrong by
  //      default: a voter's correction and a queue's parity discard are
  //      observed by soc_busstat.v, and a block with no clock cannot
  //      report them. `|sticky_ev` carries all NINE -- the queue
  //      pointer votes, the entry parity, the cause bank's own voter,
  //      the strobe mismatch and the four bounded waits -- so an upset
  //      inside a sleeping accelerator wakes it up rather than being
  //      lost.
  //
  //   2. `wake_hold` keeps the clock running for HOLD_CYCLES more
  //      cycles after the last of those goes away, so a settling chain
  //      inside the die -- pilot_top.v's two-flop input synchronisers,
  //      for instance -- is not cut off by a term nobody wrote down.
  //      This is insurance and it is priced: HOLD_CYCLES cycles of
  //      clock per wake, against 2,178 flip-flops of clock per idle
  //      cycle.
  //
  // AND THE MEASUREMENT IS hw/soc/flow/clkgate_check.py, which reads a
  // whole-SoC dump and reports every bit under this module that changes
  // value at an edge the gate would have removed. Zero is the result
  // that licenses the gate, and it is a statement about the workloads
  // measured and not a theorem.
  //
  // `win_guard` and `oh_guard` are in the list for a reason worth
  // stating: both are cleared to zero the cycle AFTER the thing they
  // were counting goes away, so leaving them out would freeze a stale
  // non-zero count. Neither can cause a spurious expiry -- both
  // expiries are qualified by `win_out` and `oh_req` -- so this is not
  // a correctness term. It is there because the verification instrument
  // is bit-exact equivalence with the ungated design, and a design that
  // is only ALMOST equivalent cannot be checked that way.


  // -------------------------------------------------------------------
  // docs/77: THE SPLIT, AND WHY IT IS NOT THE ONE docs/76 RANKED FIRST
  //
  // docs/76 section 9.5 measured that this gate's clock-gating check
  // misses by 5.0198 ns at the slow corner and attributed the cone to
  // `|sticky_ev`. It is not that cone. Measured on that document's own
  // signed-off netlist by cutting launch domains one at a time
  // (docs/77 section 3): the worst path into this enable that starts
  // inside this block -- which is where every one of the eleven fault
  // lines starts -- is -1.3129 ns, the worst that starts in the ungated
  // domain is -2.6166, and the -5.0198 launches from
  // `u_ibex.gen_regfile_ff.register_file_i.raddr_a_i[2]`, the flip-flop
  // that also gives the whole design its -6.3505 WNS. The enable's late
  // input is `req_i`, and `req_i` is the CPU's register-file read
  // address after the ALU, the load-store address, the fabric's address
  // mux and the slave decode. THE FAULT LINES ARE NOWHERE ON IT.
  //
  // So the split below is by ARRIVAL and not by importance:
  //
  //   FAST -- `req_i` and `psel_i`. These are the only two things that
  //   can rise and fall while this block's clock is stopped, because
  //   they are driven from outside it, and a request that is not seen
  //   at the edge that ends its own cycle is a request this block has
  //   answered `gnt_o` to and then dropped. They stay combinational.
  //
  //   SLOW -- everything else, including eight of the nine fault
  //   lines; the ninth is C_INJ_OVF, which carries `psel_i` and is
  //   therefore already covered by the fast half. (docs/76 called them
  //   eleven in three places and this file did too. NSTICKY is
  //   NCAUSE - C_STICKY0 = 14 - 5 = 9, and nine is what the nine
  //   `assign sticky_ev[...]` lines above come to; docs/77 section 13.)
  //   Every term of `npu_act_slow` is a function of THIS BLOCK'S
  //   REGISTERS -- the die's outputs included, because `pilot_top` is
  //   clocked by the same gated clock and its outputs are therefore
  //   functions of its own registers. A function of registers that
  //   are not being clocked CANNOT PULSE AND VANISH: it rises when the
  //   upset lands and it stays up until the block is clocked. So
  //   registering it costs one cycle of latency on the wake and loses
  //   nothing at all -- which is the whole of what `|sticky_ev` is in
  //   the enable for, kept, and moved off the timing path.
  //
  // THE SIDE CONDITION IS MACHINE-CHECKED AND NOT ASSERTED.
  // `sw/tests/test_soc_clkgate_guards.py` elaborates this module in
  // yosys, flattens it, walks the fan-in cone of `npu_act_slow` cut at
  // every sequential cell, and fails if ANY input port is reachable.
  // That is what makes "a function of this block's registers" a
  // measurement rather than a claim, and it is the condition the
  // theorem in docs/77 section 6 needs. It is also what found
  // C_INJ_OVF, which was not in anyone's list.
  //
  // WHAT IT DOES NOT DO. It does not close the check. The floor is
  // `req_i`'s own arrival, and docs/77 section 9 measures it: at the
  // slow corner the CPU-derived signal reaches this enable AFTER the
  // check's required time, so the check fails with the enable's logic
  // deleted entirely. Closing it needs `gnt_o` qualified by wakefulness
  // -- a fabric-visible cycle on every wake -- and docs/77 section 11
  // prices that and does not take it.
  // -------------------------------------------------------------------
  generate
  if (CLKGATE != 0) begin : g_clkgate
    // TRANSIENT AND EXTERNAL, therefore COMBINATIONAL.
    wire npu_act_fast = req_i | psel_i;

    // FROZEN WHILE THE CLOCK IS STOPPED, therefore REGISTERABLE.
    wire npu_act_slow =
        // the fabric slave face
          rvalid_o | win_out | (win_state != W_IDLE)
        | (win_guard != {WIN_GRD_W{1'b0}})
        // the peripheral face
        | flush_pulse | scrub_pulse
        // anything that has to be recorded, including every fault that
        // is a function of this block's registers -- which is all of
        // them but C_INJ_OVF, and STICKY_FROZEN is where that is said
        | (|(sticky_ev & STICKY_FROZEN))
        // the serial transport
        | ser_busy | ser_start | ser_done | ser_timeout
        // the event engine, the show-ahead adapter and the two queues
        | (ev_state != E_IDLE) | ev_start | aer_in_stb
        | inj_rd_en | inj_rd_valid | cap_wr_en | cap_rd_en | cap_rd_valid
        | oh_req | (oh_guard != {OH_GUARD_W{1'b0}})
        | (~inj_empty) | (~cap_empty)
        // and the die: busy, holding an event, or not ready for one
        | node_busy | node_aer_out_vld | (~node_aer_in_rdy);

    wire npu_act = npu_act_fast | npu_act_slow;

    // THE WAKE BIT, ON THE UNGATED CLOCK. It is set by anything this
    // block is doing or has to record and it is cleared only when all of
    // that has gone away, so it holds the clock on for one cycle past
    // the last activity as well as starting it one cycle after a frozen
    // term rises. Reset to 1 so the block is clocked out of reset,
    // which is what `wake_hold`'s own reset value does and for the same
    // reason.
    reg wake_q;
    always @(posedge clk_free_i or negedge rst_ni) begin
      if (!rst_ni) wake_q <= 1'b1;
      else         wake_q <= npu_act;
    end

    reg [HOLD_W-1:0] wake_hold;
    always @(posedge clk_i or negedge rst_ni) begin
      if (!rst_ni)                   wake_hold <= HOLD_LOAD;
      else if (npu_act)              wake_hold <= HOLD_LOAD;
      else if (wake_hold != HOLD_ZERO) wake_hold <= wake_hold - HOLD_ONE;
    end

    // Written with the LATE term first and alone at the top level, so
    // that what the mapper has to put next to the gate is one OR of a
    // late signal against a signal that settled a cycle ago.
    assign clk_en_o = npu_act_fast
                   || wake_q
                   || (wake_hold != HOLD_ZERO);
  end else begin : g_noclkgate
    // MEASUREMENT ONLY, and it is the baseline the gate's area and power
    // are priced against -- docs/41 section 6.5's rule. Nothing in this
    // repository instantiates it; sw/tests enforces the default.
    // NOTHING of the enable is elaborated in this arm, deliberately.
    // A baseline that kept the enable's gates and merely ignored them
    // would be a baseline that already paid for the gate, and docs/41
    // section 6.5's rule is exactly that the counterfactual must be the
    // design WITHOUT the mechanism rather than the design with it
    // disconnected.
    assign clk_en_o = 1'b1;
  end
  endgenerate

  assign pready_o  = 1'b1;
  assign pslverr_o = psel_i && !hit;

  assign obs_ser_sck_o     = ser_sck;
  assign obs_ser_cs_n_o    = ser_cs_n;
  assign obs_ser_mosi_o    = ser_mosi;
  assign obs_ser_miso_o    = ser_miso;
  // THE GATED STROBE, which is what the die sees. An observation port
  // that showed the flag instead would show a phantom strobe H5 had
  // just suppressed, and hw/soc/tb/tb_soc_npu_fi.v counts pin events
  // through it.
  assign obs_aer_in_stb_o  = aer_in_stb_q;
  assign obs_aer_out_vld_o = node_aer_out_vld;

  wire _unused_apb = &{1'b0, paddr_i[1:0], pwdata_i[31:16], 1'b0};
  // At CLKGATE = 0 the ungated clock reaches nothing, which is what the
  // baseline has to be -- docs/41 section 6.5's rule -- so it is tied
  // off here rather than left to a lint warning.
  wire _unused_free = &{1'b0, clk_free_i, 1'b0};

`ifdef FORMAL
`include "soc_npu_props.v"
`endif

endmodule
