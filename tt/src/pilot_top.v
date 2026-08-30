// pilot_top: TTIHP26b pilot integration (ROADMAP phase P1 default content).
//
// One self-contained NPU node slice, sized for a Tiny Tapeout block and
// built only from blocks that are already verified in this repository:
//
//   hw/rtl/lif_core.v    reduced LIF datapath, docs/10 sections 1-4,
//                        bit-exact against sw/golden/lif_core.py
//   hw/rtl/aer_fifo.v    EVQ_IN and EVQ_OUT, docs/10 section 7.2
//                        (formally proven: prove, prove_d4, bmc, cover)
//   hw/rtl/tmr_voter.v   configuration TMR domain, docs/10 section 11.4
//   hw/rtl/secded_enc.v  weight-word (72,64) SECDED codec, docs/10
//   hw/rtl/secded_dec.v  section 5 and 11.2, including E10
//
// Everything added here is glue: a serial host port, the register-bank
// subset of regmap/regmap.yaml, an event dispatcher, an ECC-checked
// weight loader, and the fault counters. No new arithmetic, no second
// copy of an equation. Addresses, reset values and field positions come
// from the generated header hw/rtl/npu_regs.vh, never from hand-copied
// literals; a drift guard below fails elaboration if the generator moves
// a field this module encodes structurally.
//
// This file is technology-independent and carries no Tiny Tapeout port
// names. hw/rtl/tt_um_melihakbulut_nssoc.v is the thin wrapper that maps
// these ports
// onto ui_in / uo_out / uio and adds the reset synchronizer.
//
// =====================================================================
// 1. Pin contract (as mapped by hw/rtl/tt_um_melihakbulut_nssoc.v)
// =====================================================================
//
// Dedicated inputs (ui_in), 8:
//
//   [0] SER_SCK       serial clock, mode 0, <= clk/4 (section 2)
//   [1] SER_CS_N      frame select, active low; must fall at least one
//                     full SER_SCK period before the first SER_SCK edge
//   [2] SER_MOSI      serial data in, MSB first
//   [3] AER_IN_STB    external AER event strobe, rising-edge triggered
//   [4] AER_IN_TICK   0 = SPIKE with axon id AER_IN_ADDR, 1 = TICK
//   [5] AER_OUT_ACK   external AER consumer acknowledge, rising-edge
//   [6] SCRUB_STB     ECC scrub / re-check pulse, rising-edge triggered
//   [7] reserved, tie low
//
// Dedicated outputs (uo_out), 8:
//
//   [0] SER_MISO      serial data out, MSB first
//   [1] BUSY          STATUS.BUSY
//   [2] AER_IN_RDY    EVQ_IN has room for one more event
//   [3] AER_OUT_VLD   an event id is presented on AER_OUT_ID
//   [4] ERR           STATUS.ERR_CFG | STATUS.OVF_SEEN, section 7
//                     (configuration fault, or an upset that parked the
//                     neuron core's FSM in its safe state)
//   [5] SEC           sticky: SECDED corrected at least one single-bit
//                     error since the last FAULT_CLR
//   [6] DED           sticky STATUS.DED_SEEN
//   [7] TMR           sticky: the configuration voter masked at least one
//                     replica disagreement since the last FAULT_CLR
//
// Bidirectionals (uio), 8 -- direction is fixed at elaboration:
//
//   [3:0] AER_IN_ADDR   inputs  (uio_oe[3:0] = 0), axon id, N_AXONS <= 16
//   [7:4] AER_OUT_ID    outputs (uio_oe[7:4] = 1), emitted neuron id,
//                       N_NEURONS <= 16
//
// The four fault pins make every hardening event visible on a scope with
// no host software, which is the docs/08 section 2.3 fault-visibility
// convention carried into the pin budget. The full 16-bit event word of
// docs/10 section 7.1 is always available over the serial EVQ_OUT
// register; the uio nibble is the low four bits of its ID field.
//
// =====================================================================
// 2. Serial host protocol
// =====================================================================
//
// Mode-0 SPI slave (CPOL = 0, CPHA = 0), MSB first, one register per
// frame. The slave lives entirely in the clk domain: SER_SCK, SER_CS_N
// and SER_MOSI are two-flop synchronized and edge-detected. Three host
// obligations follow, and all three are real:
//
//   H1. SER_SCK <= clk/4.
//   H2. SER_CS_N falls at least one full SER_SCK period before the first
//       SER_SCK edge. The frame-start reset has to clear the
//       synchronizer before the first sampled clock edge arrives; a host
//       that drops the select and clocks immediately risks losing the
//       first command bit. The same trap is recorded in the sibling
//       project's shipped submission.
//   H3. SER_CS_N stays high at least one full SER_SCK period BETWEEN
//       frames. The bit counter is held at zero only while the
//       synchronized select reads inactive, so a deselect that is never
//       seen leaves the counter running and the next frame decodes at
//       the wrong offset. Found during this pilot's bring-up with a
//       half-period gap; hw/tb/test_pilot_top.py holds the boundary.
//
// Frame: 40 SER_SCK cycles.
//
//   bits 39..32   command byte { WR, ADDR[6:0] }, WR = 1 writes
//   bits 31..0    register data, MSB first
//
// ADDR[6:0] is the regmap byte offset shifted right by two, i.e. the
// register's word index. Every offset in regmap/regmap.yaml is below
// 0x100, so the whole map is reachable in seven bits.
//
// Reads: the addressed register is captured when the command byte
// completes and shifted out on the following falling edges, so the host
// samples data bit 31 on SER_SCK cycle 9. Read side effects (the EVQ_OUT
// pop) happen once, at that capture. Writes commit on the 40th rising
// edge, not at CS_N release, so an aborted frame changes nothing.
//
// =====================================================================
// 3. Register subset
// =====================================================================
//
// Implemented from regmap/regmap.yaml (docs/10 section 10):
//
//   ID VERSION SCRATCH CTRL STATUS STATUS_CLR CFG_NEUR CFG_AXON
//   CFG_THRESH CFG_VRESET CFG_LEAK CFG_SYNSHIFT CFG_REFR CFG_FLAGS
//   PASS_TILE_OFF W_ADDR W_DATA_LO W_DATA_HI N_ADDR N_DATA CNT_SEC
//   CNT_DED CNT_EVQ_OVF CNT_AXON_OOR FAULT_ADDR ECC_INJ FAULT_CLR
//   EVQ_STAT EVQ_IN EVQ_OUT NODE_ID
//
// Not implemented in the pilot: W_BASE and PASS_ID (both are multi-pass
// sequencer bookkeeping with no hardware effect in a single-pass build,
// docs/10 section 9). They read as zero and reject writes like any other
// unmapped offset.
//
// Deliberate, documented deviations from the full block:
//
//   D1. Fault counters are CNT_W bits wide (default 8), not 32, and
//       saturate. Reads zero-extend to 32 bits. Four 32-bit counters
//       would cost about 11,000 um2 on sg13g2 -- an eighth of a 2x2
//       tile budget -- to count events a pilot reads out every few
//       seconds. CNT_EVQ_OVF is the EVQ_IN drop counter of aer_fifo,
//       whose DROP_W is set to CNT_W for the same reason.
//   D2. CFG_NEUR is read-only and reports N_NEURONS. lif_core carries no
//       runtime active-neuron count by design (see its header): a
//       runtime CFG_NEUR would be RTL with no golden reference. CFG_AXON
//       is fully writable and does drive the docs/10 section 6 drop rule.
//   D3. W_ADDR is a weight-word index, not a byte address, and counts
//       0 .. N_AXONS*N_NEURONS/16 - 1. It auto-increments on W_DATA_HI
//       commit exactly as regmap.yaml specifies.
//   D4. W_DATA_LO / W_DATA_HI are not a write-only staging pair here:
//       together with an eight-bit check field they ARE the physical
//       ECC-protected word (section 5). An injected upset is therefore
//       visible when they are read back, and disappears after a scrub.
//       That is the demonstrator, not an accident.
//   D5. Four registers outside regmap.yaml occupy the unmapped region
//       of the same 4 KB window (section 5). They are pilot-only
//       observability and do not change the register-map contract.
//
// =====================================================================
// 4. Datapath
// =====================================================================
//
// Weight load, per 16-weight word (docs/10 section 5 packing: weight k
// of word w is data bit range [4k+3:4k], linear index 16w + k,
// axon-major):
//
//   W_DATA_LO / W_DATA_HI written  ->  data field of the stored word
//   W_DATA_HI commit               ->  check field = secded_enc(data),
//                                      then the armed ECC_INJ pattern is
//                                      XORed into the stored 72-bit word
//   next cycle                     ->  secded_dec runs, CNT_SEC / CNT_DED
//                                      update, FAULT_ADDR latches W_ADDR
//                                      on DED, and the loader writes 16
//                                      weights into lif_core -- always
//                                      the DECODED word, so a correctable
//                                      upset never reaches the datapath,
//                                      or all zeros if the word was
//                                      uncorrectable (E10, docs/10
//                                      section 11.2)
//
// The stored word keeps its injected error, so a bench can re-check it
// with the SCRUB_STB pin as many times as it likes. With CTRL.SCRUB_EN
// set (its reset value) a correctable word is written back repaired on
// every check, which is the scrubber loop of docs/10 section 11.2 at
// pilot scale.
//
// Event path:
//
//   EVQ_IN  <- serial EVQ_IN writes and the AER_IN_STB pin
//   dispatcher pops one word and decodes docs/10 section 7.1 TYPE:
//     00 SPIKE  ID >= CFG_AXON -> dropped, CNT_AXON_OOR++ (section 6)
//               otherwise      -> lif_core synaptic event
//     01 TICK   -> lif_core tick
//     10 SYNC   -> held until lif_core is idle, then echoed into EVQ_OUT
//                  and STATUS.SYNC_DONE is set (section 7.1 barrier)
//     11        -> dropped; the register map defines no counter for it
//   EVQ_OUT <- lif_core spikes (held, not dropped: lif_core keeps a
//              refused spike in out_pend and re-presents it, so the
//              write is retried, never lost) and SYNC echoes (a
//              one-shot pulse, so a refused echo IS lost -- section
//              5.1), drained through a one-deep holding register
//              shared by the AER_OUT pins and the serial EVQ_OUT read.
//
// That holding register is not a buffer for its own sake: it is the
// one-entry show-ahead adapter that turns a registered-output queue into
// the single-access pop the register map defines. Section 8.
//
// Configuration TMR domain (docs/10 section 11.4): every configuration
// bit that reaches lif_core is held in three replicas and voted by
// tmr_voter before it leaves this module. Software reads the voted
// value, so a masked upset is invisible to it; CNT_TMR and the TMR pin
// make it visible to the operator. TMR_INJ emulates an upset on one
// replica's read path. The storage flops are not disturbed, so no
// replica resynchronization is implemented -- consistent with
// tmr_voter.v's header, which leaves resynchronization to the protected
// block.
//
// =====================================================================
// 5. Pilot-only registers (D5)
// =====================================================================
//
//   0x0A0 ECC_INJ_POS  RW  POS[6:0], the codeword bit that
//                          ECC_INJ.SINGLE flips. ECC_INJ.DOUBLE flips
//                          POS and its neighbour (POS + 1 mod 72), which
//                          is a valid double error for any Hsiao code.
//                          Reset 0, so an ECC_INJ write alone is already
//                          deterministic.
//   0x0A4 TMR_INJ      RW  { REP[1:0] at [9:8], BIT[5:0] at [5:0] }
//                          REP 00 = no injection, 01 = replica A,
//                          10 = replica B, 11 = replica C; BIT selects a
//                          bit of the voted configuration vector.
//   0x0A8 CNT_TMR      RO  saturating count of voter disagreement
//                          episodes (one per rising edge of mismatch),
//                          cleared by FAULT_CLR bit 5.
//   0x0AC CNT_EVQ_OUT_OVF
//                      RO  saturating count of OUTPUT-queue writes that
//                          were refused and lost. Cleared by FAULT_CLR
//                          bit 6. Section 5.1 is why this register
//                          exists, why it is pilot-only, and why it is
//                          NOT aer_fifo's own drop counter.
//   0x0B0 CNT_EVQ_PAR  RO  saturating count of queue entries DISCARDED
//                          because the stored word failed its entry
//                          parity check, both queue instances in one
//                          count. Cleared by FAULT_CLR bit 7. Section
//                          5.2 is why it exists and why it is one
//                          counter and not two.
//
// FAULT_CLR bits 5, 6 and 7 are pilot-only objects of this section and
// they are allocated the same way as the registers
// above: from space the architecture register map leaves unassigned.
// regmap/regmap.yaml is the
// single source of truth for FAULT_CLR and it allocates exactly five
// bits, b0 CNT_SEC, b1 CNT_DED, b2 CNT_EVQ_OVF, b3 CNT_AXON_OOR, b4
// FAULT_ADDR, with "bits [31:5] ignored". All five are implemented here
// with the meaning the map gives them -- b4 clears FAULT_ADDR, it does
// NOT clear CNT_TMR -- and every position is read from the generated
// header, with an elaboration guard that fires if the map renumbers
// them. CNT_TMR is not in the map, so its clear cannot be either; b5 is
// the first free bit and is inert in the architecture block, so one
// FAULT_CLR write of 0x3F clears everything in either implementation.
// CNT_EVQ_OUT_OVF takes b6 on the same argument and CNT_EVQ_PAR takes
// b7, so the portable clear-everything write is now 0xFF.
//
// ---------------------------------------------------------------------
// 5.1 Why EVQ_OUT gets its own counter, and why it is not fo_drop
// ---------------------------------------------------------------------
//
// The fault-injection campaign (docs/16 section 5.2) found one pointer
// injection that raised STATUS.OVF_SEEN while CNT_EVQ_OVF still read
// zero: the overflow was on the OUTPUT queue and only the input queue's
// drop counter is exposed. The obvious repair is to stop sinking
// u_evq_out's drop_cnt (`fo_drop`) and give it a register. That repair
// is wrong, and the reason is measured rather than argued.
//
// aer_fifo counts `wr_en && full` -- a REFUSED write. Its header is
// explicit that this is EVQ_IN semantics, where the software port
// presents a word once and loses it: "a link-side producer gets lossless
// backpressure by gating wr_en with !full". EVQ_OUT's producers are not
// that. lif_core holds a refused spike in out_pend and re-presents it on
// every subsequent cycle until out_ready, so `fo_wr_en` stays high for
// the whole stall and aer_fifo counts one "drop" per CLOCK CYCLE of
// ordinary backpressure while losing nothing at all. Measured on this
// design [fact]: 8 x 8 with EVQ_OUT_DEPTH = 4, one SPIKE event that
// fires all eight neurons, host not draining -- fo_drop reaches 223 and
// is heading for its 255 saturation, and every one of the eight spikes
// is eventually delivered. Publishing that number as an event-loss count
// would be worse than publishing nothing. The original sink was right;
// only the reason recorded next to it was incomplete.
//
// The same measurement condemns the sticky. Until now STATUS.OVF_SEEN
// was set by `fo_wr_en && fo_full`, so the run above also latched
// OVF_SEEN and lit the ERR pin with no event lost and no upset present.
// That contradicts regmap/regmap.yaml, which defines the bit as "at
// least one software-port event dropped at a full input queue", and a
// fault pin that lights during ordinary bursty inference is a pin an
// operator learns to ignore. No existing test caught it because the
// end-to-end harness drains after every command, which its own docstring
// says is deliberate.
//
// So the question is not "which register does fo_drop deserve" but "what
// does EVQ_OUT actually lose". Exactly one writer can lose a word:
//
//   lif_core spikes  cannot be lost at the write port. out_pend holds
//                    the spike and lif_core's busy output includes
//                    out_pend, so the write is retried, not dropped.
//   SYNC echo        CAN be lost. sync_push is a one-shot pulse: the
//                    dispatcher qualifies the D_ISSUE decision with
//                    !fo_full, but the write lands one cycle later, and
//                    if the queue reports full in that cycle the echo is
//                    gone with no retry. Under normal operation the
//                    guard is airtight -- the decision also requires
//                    !lif_busy, which forbids any lif_core write in the
//                    same or the next cycle, so fo_full cannot change
//                    underneath it. It is breakable only by an upset to
//                    the queue pointers in that one cycle, which is
//                    precisely the class docs/16 section 5.2 measures.
//
// A lost SYNC echo is the worst-shaped fault in this block: sticky_sync
// is set from the same pulse, so STATUS.SYNC_DONE reports the barrier
// complete while the barrier word the host is waiting for never arrives.
// That is a fault the chip announces and could not quantify, which is
// the defect docs/16 named. `evqo_drop = sync_push && fo_full` is
// therefore both the counter's increment and the output-queue term of
// STATUS.OVF_SEEN, and the backpressure term is gone from both.
//
// Two costs, stated rather than hidden:
//
//   - the campaign's one flagged pointer injection was flagged by the
//     backpressure term, so with this change it is no longer flagged.
//     That is not a loss of coverage: the term also fired on a clean
//     run, so it carried no information about the upset [fact].
//   - an upset that clears `full` while the queue really is full makes
//     aer_fifo accept and OVERWRITE a stored word. That is a genuine
//     EVQ_OUT event loss and this counter cannot see it, because no
//     write was refused. It is a read/write pointer integrity problem
//     and it belongs to pointer protection, not to a drop counter.
//
// Pilot-only rather than an entry in regmap/regmap.yaml, for three
// reasons. The architecture block cannot lose a SYNC echo any more than
// this one can outside an upset, so every mesh node would carry a
// counter for a condition its own map calls impossible. The fault block
// is contiguous from 0x70 to 0x88, so a new counter lands at 0x8C and
// the checked convention "one clear bit per fault-block register in
// offset order" (sw/tests/test_regmap.py) would hand it FAULT_CLR bit 5
// -- the bit the pilot already spends on CNT_TMR -- renumbering CNT_TMR
// and breaking the portable clear write that regmap.yaml's own FAULT_CLR
// description promises. And the YAML edit would pull in
// sw/golden/secded.py, docs/10 section 10 and hw/rtl/npu_regbank.v for a
// register whose whole content is a pilot measurement. CNT_TMR set the
// precedent for exactly this shape and this register follows it.
//
// Unlike CNT_EVQ_OVF, this counter lives in this module's register
// process on rst_n, not inside aer_fifo on blk_rst_n. docs/16 section
// 5.1 records the consequence of the other arrangement: CTRL.SOFT_RST --
// the recovery for this very fault -- zeroes CNT_EVQ_OVF while
// STATUS.OVF_SEEN stays set, leaving the telemetry self-inconsistent.
// The counter and its sticky share a reset domain here, so a recovery
// cannot make them disagree.
//
// ---------------------------------------------------------------------
// 5.2 CNT_EVQ_PAR: one counter for two queues, and why
// ---------------------------------------------------------------------
//
// hw/rtl/aer_fifo.v stores one even-parity bit per queue entry and
// checks it on the read. A failed check DISCARDS the entry: the read
// pointer still advances, rd_valid is held low, and `par_err` says that
// is what happened. Until now this module connected par_err to nothing,
// so the discard reached the host only through the consumer's bounded
// wait -- fetch_expire for EVQ_IN, oh_expire for EVQ_OUT -- which
// latches STATUS.ERR_CFG and says "a configuration fault happened here"
// for what is in fact an integrity discard. docs/29 section 8 item 5
// named that and explicitly left it to this file.
//
// That is the same defect commit 2d59ec2 fixed for the lif_core memory
// ECC, in the same shape: a mechanism did its work, and the evidence
// went to no register and no pin. For a part whose stated purpose is
// measuring the upset environment, an unreported correction -- or here,
// an unreported detected loss -- is indistinguishable from no upset.
//
// ONE counter for both instances, not one each, and the precedent is
// the pointer telemetry twelve lines below rather than section 5.1:
//
//   CNT_TMR already merges fi_ptr_mm and fo_ptr_mm into a single
//   episode count, because a corrected pointer upset is the same event
//   with the same consequence whichever queue it happened in, and the
//   operator's question is about the environment rather than about the
//   instance. A parity discard is that shape exactly: one stored event
//   lost, announced through a bounded wait, in a 16-bit word of the
//   same width in both queues.
//
//   Section 5.1 split EVQ_OUT off from CNT_EVQ_OVF for the opposite
//   reason, and the difference is real: `wr_en && full` MEANS something
//   different in the two instances -- refused software writes in one,
//   ordinary lossless backpressure cycles in the other -- so one
//   register could not have carried both without publishing a number
//   that is not an event-loss count. par_err carries no such asymmetry.
//   Both instances produce it from `rd_ok && head_bad`, and in both it
//   is one event that existed and no longer does.
//
//   The instance distinction is not free: a second CNT_W counter, a
//   second register offset, a second FAULT_CLR bit, and a second entry
//   in every document and test that lists the map. That is 8 more
//   flip-flops to answer a question no operator action depends on --
//   the recovery for either is the same, and a host that wants the
//   instance can already read EVQ_STAT and STATUS. Two counters would
//   also break the symmetry with CNT_TMR, which is the register a host
//   reads next to this one.
//
// Counted on the rising edge of `fi_par_err || fo_par_err`, so a
// discard that persists across cycles counts once and simultaneous
// discards in the two queues count once -- the same episode convention
// CNT_TMR uses and stated in the same words, because a host that reads
// them side by side must not have to remember two conventions.
//
// The edge register sits in the fault-counter process on rst_n rather
// than on blk_rst_n, so CTRL.SOFT_RST -- the recovery for exactly this
// class of fault -- cannot erase the record that it happened. Same
// arrangement, same reason, as CNT_TMR and CNT_EVQ_OUT_OVF.
//
// It does NOT latch a sticky of its own, and that is deliberate rather
// than an omission. Every discard already reaches STATUS.ERR_CFG
// through the bounded wait that the suppressed rd_valid triggers --
// measured, docs/29 section 5: all seven discards moved status 0x06 ->
// 0x16 -- so a second sticky would report the same event twice, and
// there is no free STATUS bit to spend on it. What was missing was
// never the alarm; it was the distinction between "the queue lost an
// event to a configuration fault" and "the queue discarded a corrupted
// entry", and a counter is exactly that distinction.
//
// Pilot-only, on section 5.1's three arguments unchanged. The fault
// block of regmap/regmap.yaml is contiguous from 0x70 to 0x88, so a
// promoted counter lands at 0x8C and the checked convention "one clear
// bit per fault-block register in offset order" (sw/tests/test_regmap.py)
// hands it FAULT_CLR bit 5 -- the bit the pilot already spends on
// CNT_TMR -- renumbering CNT_TMR and CNT_EVQ_OUT_OVF and breaking the
// portable clear write that regmap.yaml's own FAULT_CLR description
// promises. Deviation D5 covers it and docs/15's D5 row is the record.
//
// =====================================================================
// 6. Geometry
// =====================================================================
//
// N_NEURONS and N_AXONS are elaboration parameters. The default 8 x 8 is
// the geometry measured to fit the recommended tile count in
// docs/15-pilot-tile-plan.md; that document also carries the measured
// area of the alternatives. Constraints, all guarded below: both powers
// of two, both in [4, 16] so the uio nibbles address them exactly, and
// at least 32 synapses so the weight word index is at least one bit.
//
// The parameter defaults are additionally overridable by macro. The
// Tiny Tapeout top level cannot carry parameters, and Icarus only
// applies -P to a root module, so a geometry sweep of the wrapped design
// has no other handle; the same macros are what a LibreLane
// VERILOG_DEFINES entry would set. Parameters remain the primary
// interface for anything that instantiates pilot_top directly.
//
// =====================================================================
// 7. Fault visibility: STATUS.ERR_CFG and the ERR pin
// =====================================================================
//
// STATUS.ERR_CFG is the OR of two level signals, and the ERR pin is that
// OR again with STATUS.OVF_SEEN. The two sources clear differently, so
// they are kept apart in the RTL rather than merged into one flop:
//
//   sticky_errcfg  configuration faults raised in this module: a write
//                  to a configuration-locked register while BUSY, and a
//                  configuration outside its legal range with CTRL.EN
//                  set (docs/10 section 6). Cleared by STATUS_CLR.
//   lif_err_cfg    lif_core's err_cfg output. The neuron core's control
//                  FSM uses a Hamming-distance-2 state encoding; a
//                  single-bit upset in that register lands on a word no
//                  legal transition can produce, the core parks in
//                  S_SAFE and latches this flag (docs/10 section 11.4).
//                  That is the single-event-upset signature this pilot
//                  exists to demonstrate, so it reaches the host and the
//                  ERR pin unconditionally.
//
// The second source is both ORed in live and latched into the first, and
// each half does a job the other cannot:
//
//   live    while the core is parked, STATUS_CLR cannot clear the bit.
//           Reporting a fault as gone while the core is still parked and
//           refusing work would be worse than not reporting it at all.
//   latched CTRL.SOFT_RST is the recovery for this fault -- it resets
//           the queues, the dispatcher and lif_core, the FSM returns to
//           S_IDLE, err_cfg drops, and the neuron state file survives
//           because it is not on the reset net. Without the latch the
//           recovery would also erase the evidence, and an operator who
//           recovers before polling would never learn an upset happened.
//           After the reset the bit is a plain sticky and STATUS_CLR
//           clears it, which is the operator saying "recorded".
//
// A parked core is also permanently BUSY, so the configuration lock will
// latch the first source on the next configuration write as well; that
// is a consequence, not a second fault.
//
// =====================================================================
// 8. EVQ_OUT queue contract (why there is a holding register)
// =====================================================================
//
// hw/rtl/aer_fifo.v is a registered-output queue: rd_data appears one
// cycle AFTER an accepted read, flagged by a one-cycle rd_valid. The
// register-map view of EVQ_OUT is the opposite shape -- read one word,
// see VALID and EVENT in the same access -- and hw/rtl/npu_regbank.v
// states that as convention C9: its hw_evq_out_* inputs must be
// show-ahead (first-word-fall-through).
//
// Three ways to close that gap were considered:
//
//   (a) a show-ahead read port on aer_fifo. Rejected: a combinational
//       read of mem[] makes the storage an asynchronous-read register
//       file, which no synchronous SRAM macro can implement, so the
//       queue could never be retargeted to a macro at NPU scale. It
//       would also invalidate the four proofs that hold today.
//   (b) a one-entry adapter between the queue and the register view.
//       Chosen.
//   (c) relaxing npu_regbank's expectation to the registered shape.
//       Rejected: it pushes a two-access read protocol into the
//       architecture register map, which regmap/regmap.yaml defines as a
//       single-access pop.
//
// oh_valid / oh_data / oh_pop below ARE that adapter, and they are the
// reference implementation of C9 for this repository: oh_valid means a
// word is presented now (and since 2026-08-30 it is a checked pair of
// rails rather than a flip-flop -- section 8.2), oh_data is that word,
// both hold until a pop
// (a serial EVQ_OUT read or an AER_OUT_ACK edge), and the queue advances
// behind them. EVQ_STAT.OUT_FILL counts the held word, so the fill level
// a host reads is the number of events it can still get out. The cost is
// one event per three clock cycles of drain bandwidth, far above what
// either observer can consume. Nothing here reads aer_fifo's rd_data
// combinationally, so the queue stays retargetable.
//
// oh_req is the adapter's "a read is outstanding" flag, and it is the
// second structure in this module that can wait forever. It is set only
// together with fo_rd_en and cleared only by fo_rd_valid, so a
// single-bit upset that sets it with no read outstanding waits for a
// grant that will never be requested: the arming condition below is
// gated on !oh_req, so no further read is ever issued, EVQ_OUT never
// advances again, and the queue fills. lif_core then holds its next
// spike against a full queue, STATUS.BUSY stays high and nothing is
// flagged. Unlike the ordinary full-queue backpressure this looks like,
// the host cannot clear it by reading EVQ_OUT -- oh_valid is low, so a
// read pops nothing -- so only CTRL.SOFT_RST or a reset recovers it.
// That is the same silent-hang failure class as the D_FETCH wait of
// section 5.1 in docs/16, reached from a different flip-flop, and it is
// measured: the fault-injection campaign's `evq_hold` group hits it from
// a deposit into oh_req.
//
// It gets the same treatment. A granted read answers in one cycle, so
// OH_WAIT_MAX = 63 cycles of waiting is far past any legitimate reply;
// past it the adapter clears oh_req, re-arms on the next cycle and
// latches sticky_errcfg on that same edge, exactly as the dispatcher's
// bounded wait does. Nothing is lost by the recovery: oh_req without a
// read outstanding is by construction a state in which the queue has
// dequeued nothing, so the re-armed read fetches the word that was next
// all along.
//
// ---------------------------------------------------------------------
// 8.1 Why the two expiry terms are wires and not one-cycle pulses
// ---------------------------------------------------------------------
//
// Until 2026-08-30 each bounded wait reported through a one-bit pulse
// register -- fetch_timeout and oh_timeout -- set for exactly one cycle
// when the wait expired, and sampled by the register process on the
// following edge to latch sticky_errcfg. The wait counters and the
// pulses were injected into and the result is docs/16 section 5.8:
//
//   * the COUNTERS are sound, and structurally so. A monotone increment
//     compared for equality against its all-ones maximum reaches that
//     value from every state, and no single flip from zero can reach
//     it, so an upset in a counter delays or advances the expiry but
//     cannot abolish it. Twelve of twelve injections masked. They are
//     left alone; TMR on them would buy nothing.
//   * the PULSES were the weakness, in both directions. Set by an
//     upset, a pulse fabricated a configuration error that had not
//     happened -- six of six random-phase injections, every one of them
//     a clean run reported as faulty. Cleared by an upset during the
//     single cycle it was high, it erased the report entirely: the
//     deadlock happened, the bounded wait recovered it, the run
//     returned a wrong answer, and STATUS read 0x06 with every counter
//     zero and the ERR pin low, against a control injected at the same
//     cycle with byte-identical wrong output that read 0x16.
//
// The repair removes the state rather than protecting it. fetch_expire
// and oh_expire are combinational terms, and the same wire both ends
// the wait and latches sticky_errcfg, on one edge. There is no cycle in
// which the report exists as separate storage, so there is nothing for
// a single upset to set or clear: an upset must now corrupt the
// counter, which is the part that was measured sound, or sticky_errcfg
// itself, which every sticky in this module shares and which the
// campaign covers as its own target. Cost: minus two flip-flops.
//
// Duplicate-and-OR on the pulses was the alternative, at plus two
// flip-flops, and it closes only the erased direction -- an OR of two
// copies still fabricates when either copy is set. It is the fallback
// if the combinational form ever becomes unacceptable, and nothing here
// suggests it is: the terms are three-input ANDs of registers that
// already drive control logic on the same edge.
//
// ---------------------------------------------------------------------
// 8.2 Why oh_valid is two rails and not three replicas
// ---------------------------------------------------------------------
//
// docs/16 section 6.2 ranked the show-ahead adapter first for wave 6 on
// benefit per flip-flop, and the concentration is real: of the group's
// six silent-corruption records, four sit in two one-bit valid flags
// (oh_valid here, and u_evq_out.rd_valid in hw/rtl/aer_fifo.v), 2 of 2
// each. A valid flag upset fabricates an event out of stale oh_data or
// drops the one it was holding, and no consumer downstream can tell
// either from a real spike.
//
// The proposal there was to triplicate them on the aer_ptr_bank
// pattern. THAT PATTERN DOES NOT REACH ONE BIT, and the reason is a
// proof rather than a measurement. Section 9 records what the merge
// hazard costs and what defeats it: three replicas written from the
// same expression are provably equivalent, opt_dff normalises them and
// opt_merge hashes them into one, and what holds them apart without
// depending on any attribute is that each replica stores a DIFFERENT
// FUNCTION of the value. Over a value of one bit there are exactly two
// storage functions -- x and ~x. Two replicas can take one each. A
// third has nothing left to take, and whichever function it picks it
// is bit-for-bit identical to one of the other two. Section 9's
// measured result for the 55-bit configuration word is the same
// statement one step up: POL alone gave two distinct functions there
// too, replica C collapsed under a forced flatten, and it took the MIX
// layer -- which needs at least four bits to give every stored bit a
// weight of two or three -- to give C a function of its own. There is
// no MIX at one bit.
//
// So the options for a single flag are: three replicas held apart by
// keep_hierarchy ALONE, which this repository has twice decided is not
// enough (section 9, and docs/20 section 11); or four bits of unrelated
// state bundled into one W >= 4 bank so that MIX applies, at +8
// flip-flops for this one flag's two records; or two rails, at +1.
//
// Two rails it is, and what they buy is stated exactly: an upset in
// either rail is DETECTED, not corrected. The rails disagree, the
// adapter presents nothing rather than presenting a word it can no
// longer vouch for, sticky_errcfg latches and the ERR pin lights.
// The held event is still lost -- the run is still wrong -- but it is
// wrong LOUDLY, which is the whole difference between the SDC class
// and the DETECTED class in docs/16, and it is the same difference
// section 8.1 above is about. The disagreement heals on the next clock
// edge: the rails take a next VALUE rather than an enable, and that
// value is written from the CHECKED flag, which reads 0 while they
// disagree, so the safe reading becomes the stored one and a second
// upset cannot land on top of the first.
//
// One caveat that belongs here rather than in the rail module, because
// it is about the CALLER: a next-value rail is only correct when every
// term of that next value is X-free. hw/rtl/lif_core.v's copy of this
// rail takes an enable instead, for exactly that reason, and its
// header carries the measurement. oh_valid's next value is built from
// fo_rd_valid, oh_valid and oh_pop, all defined out of reset, so the
// next-value form is safe here.
//
// Cost: +1 flip-flop, one XOR of two rails, and one term in the fault
// process. The other two flags of the same class are in files this
// change does not own -- u_evq_out.rd_valid in aer_fifo.v and out_pend
// in lif_core.v -- and the same two-rail construction applies to each
// at the same price.
//
// =====================================================================
// 9. Configuration TMR: why the replicas are submodules, not three regs
// =====================================================================
//
// Until 2026-08-26 the three 55-bit replicas of the configuration TMR
// domain were three `reg [TMR_W-1:0]` vectors (cfg_a, cfg_b, cfg_c) in
// this module's register process, written from the same expression on
// the same cycle. That is correct RTL and it is a defect in silicon.
// It takes two yosys passes, which is why a single-pass reading of the
// tool missed it: `opt_dff` first rewrites each bank's hold-mux into an
// enable flip-flop, which erases the only structural difference between
// them, and `opt_merge` then hashes the three now-identical cells into
// one and rewires the other two names to it. Bisected on this design:
// `opt_merge` alone leaves all 1161 declared flip-flops standing, and
// `opt_dff; opt_merge` takes it to 1045 [fact].
// Measured on the artifact that fed the 4x2 harden,
// tt/runs/tt-harden/06-yosys-synthesis/tt_um_melihakbulut_nssoc.nl.v:
// 362 references to `cfg_a[` and zero to `cfg_b[` or `cfg_c[` [fact].
// The voter therefore read one physical bank three times; a real upset
// corrupted all three inputs together and the majority vote returned the
// corrupted value. RTL fault injection (docs/16) cannot see this,
// because at RTL the three vectors are still distinct signals.
//
// Four mechanisms were considered. Every number below is measured with
// Yosys 0.33 on sg13g2, `synth -flatten` + dfflibmap + abc, whole
// design; the pre-fix reference point is 1045 flip-flops and the RTL
// declares 1161.
//
//   (a) `(* keep *)` on the three regs. REJECTED, and it is worse than
//       useless because it looks like it works. Measured: flip-flop
//       count unchanged at 1045, and the netlist now contains 110
//       references to `cfg_b[` -- all of them of the form
//       `assign \u_pilot.cfg_b[3] = \u_pilot.cfg_a[3] ;` [fact]. The
//       attribute lands on the wire, not on the flip-flop cell, so
//       opt_clean preserves the name while opt_merge still deletes the
//       storage. This is why the guard test counts flip-flops and never
//       greps for a signal name.
//   (b) `(* syn_keep *)`. REJECTED: it is a vendor attribute for
//       Synplify/Vivado front ends and Yosys ignores it outright.
//       Measured: 1045 flip-flops and zero references to `cfg_b[` in
//       the netlist, so unlike (a) it does not even leave a name behind
//       [fact].
//   (c) one module per replica plus `(* keep_hierarchy *)`. CHOSEN as
//       the primary mechanism. `flatten` skips modules carrying the
//       attribute, and `opt_merge` does not merge instances of
//       user-defined modules unless it is asked with `-share_all`, so
//       the three banks are two independent steps away from collapse
//       rather than one. It is the same M-4 recipe the sibling
//       rad-hard programme validated through LibreLane after its own
//       constant-folding loss (its docs/20 finding F-1).
//   (d) an architectural difference that makes the three genuinely
//       non-equivalent to structural hashing. ADDED ON TOP of (c),
//       because (c) is still one tool honouring one attribute. Each
//       bank takes a POL parameter and stores `value ^ POL`, presenting
//       `bits ^ POL` at its output: replica A stores the value true
//       (POL = 0), replica B stores its exact complement (POL = all
//       ones) and replica C stores it with the odd bits complemented
//       (POL = 0x2AAAAAAAAAAAAA). Two consequences, both intended:
//         - the three instances carry different parameters, so Yosys
//           derives three different module types and nothing can hash
//           them together even with `-share_all`;
//         - if some future flow flattens the hierarchy anyway, bit i of
//           bank A is driven by `x_i` and bit i of bank B by `~x_i`,
//           which are different cells, so at least two physical banks
//           survive a total loss of the attributes. Measured: 110
//           flip-flops under a deliberately forced flatten against 55
//           before this fix [fact].
//       Honest limit, and it is a hard one: only two distinct functions
//       of x_i exist (x_i and ~x_i), so under a forced flatten bank C
//       merges bitwise into A and B and the domain degrades to
//       duplication-with-detection. Measured 2026-08-26 on pinned
//       sources: keep_hierarchy stripped, POL as designed, 1,100
//       flip-flops -- replica C entirely gone [fact]. No assignment of
//       CFG_POL_C avoids this; with three replicas and two polarities
//       one replica always collides bit for bit. Polarity coding
//       cannot do better, and neither can a constant XOR mask, which is
//       the same mechanism spelled differently.
//       Secondary, and tagged as an estimate because this project has
//       no beam data: complementary storage also decorrelates any
//       upset mechanism with a preferred direction (a strike or a
//       total-dose shift that favours 1->0), because the same physical
//       bias lands as the opposite logical error in replica B
//       [estimate].
//   (e) a per-replica STORAGE TRANSFORM that is not a polarity: replica
//       C stores an invertible XOR mixing of the configuration word
//       (MIX = 1), so every one of its 55 stored bits is an XOR of two
//       or three distinct configuration bits. ADDED 2026-08-26 on top
//       of (d), because (d) provably cannot hold a third bank and the
//       header used to claim it could. Nothing of the form
//       `x_i ^ x_j (^ x_k)` equals `x_i` or `~x_i`, so no per-bit hash
//       can match replica C against A or B -- this is a proof, not a
//       measurement, and the measurement agrees: keep_hierarchy
//       stripped, 1,155 flip-flops with no loss at all, in both the
//       ASIC flow and synth_ecp5 [fact].
//       What was evaluated and rejected on the way there:
//         - a per-replica bit ROTATION, the obvious candidate, because
//           `cfg[(i+k) % 55]` is neither `cfg[i]` nor its inverse. It
//           does not work. Structural hashing matches on the
//           flip-flop's (D, EN, reset) signature, not on bit position,
//           so a rotation relabels which cell holds which bit and
//           leaves the SET of stored functions unchanged; the rotated
//           bank hashes into the unrotated one flop for flop. Measured,
//           replica C rotated by 7, keep_hierarchy stripped: 1,100
//           flip-flops, identical to polarity alone [fact].
//         - a per-replica constant XOR MASK. It is a polarity choice by
//           definition, so it is (d) and inherits (d)'s two-function
//           ceiling. Not run; it is the design that was already there.
//       The construction and its inverse are documented at
//       pilot_cfg_bank. Cost, and it is the real objection to answer:
//       mixing means one upset in replica C decodes to two or three
//       wrong bits at its output. That is harmless, because they are
//       all in one replica and a bitwise majority masks every bit on
//       which one replica disagrees, however many. An earlier revision
//       of this header asserted the opposite and used it to conclude
//       that "no encoding can" do better than (d); both halves of that
//       were wrong.
//
// Flow portability, stated plainly rather than assumed:
//
//   (c) is portable across every flow this repository runs, because
//       both of them are yosys: the LibreLane/yosys ASIC flow and the
//       plain `synth_ecp5` FPGA run use the same `flatten` pass, which
//       honours the attribute. It is NOT portable to a front end that
//       does not read yosys attributes. That is a real limit, not a
//       theoretical one, and it is why (d) and (e) exist.
//   (d) and (e) are plain Verilog-2005 and depend on no attribute in
//       any tool. Together they are the layer that still holds when (c)
//       does not, and (e) is the half of it that holds the THIRD bank:
//       (d) on its own bounds the loss at one bank and, as measured
//       above, sits exactly on that bound. Do not read (d) as a
//       standalone fallback; until 2026-08-26 this header did, and it
//       was wrong for the whole of that time.
//   None is trusted. sw/tests/test_synthesis_guards.py runs both
//       flows, counts the flip-flops in the mapped netlist per replica
//       bank, and fails if any of them collapses. It also strips
//       keep_hierarchy and requires the count to be unchanged, which is
//       the assertion that holds (e) honest. That test -- not any
//       attribute -- is what keeps this fixed, and it is mutation-checked
//       against a scratch copy with the fix removed.
//
// One flow consequence to carry forward. Because (d) parameterises the
// bank, yosys derives three module types whose names begin with
// `$paramod`, and LibreLane's Checker.YosysUnmappedCells counts every
// cell type starting with `$` as an unmapped instance. Under the default
// SYNTH_HIERARCHY_MODE ("flatten") the hardening run would therefore
// abort. scripts/gen_tt_submission.py now emits
// SYNTH_HIERARCHY_MODE = "deferred_flatten", which flattens AFTER the
// banks are standard cells: measured 1155 flip-flops, 55 under each of
// u_cfg_a / u_cfg_b / u_cfg_c, and no `$` cell type left [fact]. Any
// other LibreLane configuration that hardens this module needs the same
// key.
//
// Cost, measured, against the pre-fix design [fact]:
//   sg13g2   1045 -> 1155 flip-flops; 106,174 -> 109,058 um2 (+2.7%)
//            on a 4x2 tile of 268,059 um2
//   ECP5 85F 1045 -> 1155 TRELLIS_FF, 3449 -> 4503 TRELLIS_COMB,
//            Fmax 47.87 -> 46.45 MHz at speed grade 6, seed 0
//            (target 25 MHz, PASS both before and after)
// The LUT growth is larger than the flip-flop growth because the voter
// was not being paid for either: with one physical bank feeding all
// three of its inputs, `(a&b)|(a&c)|(b&c)` folded to a wire.
//
// Cost of (e) on top of that, measured 2026-08-27 as a matched A/B on
// one tree with `.MIX(1)` on u_cfg_c as the only difference [fact]:
//   sg13g2   +1,490.60 um2, +1.06 % (141,842.95 against 140,352.35);
//            +89 xor2, -30 mux2, +3 mux4, and ZERO extra flip-flops --
//            it is combinational rewiring on one bank's write and read
//            sides, not storage. The mux2 delta is negative because
//            making the hold explicit lets some per-field enable muxing
//            collapse.
//   ECP5 85F +209 TRELLIS_COMB, no extra TRELLIS_FF; Fmax 28.63 ->
//            26.62 MHz at speed grade 6, seed 0 (target 25 MHz, PASS
//            both). Read that as congestion, not path delay: nextpnr
//            reports the critical path through u_pilot.u_lif.wmem and
//            the busy logic in BOTH runs, so the mixing is not on it
//            [estimate]. Inside the bank the added paths are
//            Q -> dec -> mux -> enc -> D, five gate levels, and
//            Q -> dec -> q, two levels on top of the existing one;
//            neither is near critical at CLOCK_PERIOD 20 on sg13g2.
//   docs/20 section 11.6 carries the full tables.
//
// =====================================================================
// 10. The dispatcher check field: two bits, and what they cover
// =====================================================================
//
// The fault-injection campaign's residual after the queue-storage
// hardening is 11 silent corruptions across four structures, and
// `dispatch` leads at 5 of 18. All five are in this module and all five
// are DATA corruption rather than deadlock, which is what makes this
// wave different in kind from the two the dispatcher has already had --
// docs/16 section 5.1's D_FETCH deadlock, closed with a bounded wait,
// and section 8.1's erasable report pulse, closed by deleting the
// state. Read out of hw/tb/fi_campaign_results.json [fact]:
//
//   dstate bit 0, D_ISSUE -> 2'b10, the illegal code. The default arm
//                 already recovers to D_IDLE, so nothing hangs -- and
//                 the event being issued is dropped on the way, with no
//                 counter, no sticky and no pin. One event lost, run
//                 silently wrong.
//   dstate bit 1, D_FETCH -> D_ISSUE. The worst of the five: 2'b01 and
//                 2'b11 are both LEGAL codes, so nothing anywhere can
//                 tell them apart, and the FSM issues whatever evw
//                 happens to hold. Measured: a spurious event 7 in
//                 place of the real event 2.
//   evw bit 0     the ID field. A spike is delivered to the wrong axon
//                 and the run diverges from the golden model in both
//                 the event stream and the retained neuron state.
//   evw bits 14, 15  the TYPE field. A SPIKE becomes a TICK or a
//                 reserved code; the event is silently dropped or
//                 silently reinterpreted.
//
// So the failure is not "the dispatcher stops", it is "the dispatcher
// acts on a word or a state it should not trust", and no bounded wait
// can see that: a wait fires on an answer that does not arrive, and
// here every answer arrives, on time, wrong.
//
// ---------------------------------------------------------------------
// 10.1 The one-bit pigeonhole, checked at two bits rather than assumed
// ---------------------------------------------------------------------
//
// Section 8.2 proves that three replicas cannot be held apart over ONE
// bit: there are exactly two storage functions, x and ~x, and a third
// replica is bit-for-bit identical to one of the other two. dstate is
// two bits, so the bar has to be re-derived rather than carried over.
// It does not clear it, and the derivation is short.
//
// A replica of a two-bit value is two flip-flops, each storing some
// boolean function of the pair, and the replica is only a replica if
// the two functions together determine the value -- that is, if the
// map is a bijection on the four states. Every coordinate function of
// a bijection on two bits is BALANCED (two ones out of four), and there
// are exactly six balanced functions of two variables:
//
//     d0, ~d0, d1, ~d1, d0^d1, ~(d0^d1)
//
// Replica A takes d1 and d0. Replica B, on the polarity transform,
// takes ~d1 and ~d0. Four of the six are now spent, and the two that
// remain -- d0^d1 and its complement -- are complements OF EACH OTHER,
// so a replica built from both stores one bit of information twice and
// determines nothing. There is no third replica. The MIX layer of
// section 9, which rescued the 55-bit configuration domain, is the same
// construction one step up and it does not help here either: over W
// bits the affine transforms give 2*(2^W - 1) coordinate functions, six
// at W = 2, which is the same six.
//
// The bar therefore moves from "one bit" to "fewer than three bits",
// and the general statement is the one section 8.2 should have made:
// triple modular redundancy needs at least six distinct balanced
// storage functions, and a W-bit value has only 2*(2^W - 1) affine ones
// -- 2 at W = 1, 6 at W = 2, 14 at W = 3. Three bits is the first width
// at which a third replica has functions left to take.
//
// ---------------------------------------------------------------------
// 10.2 What was chosen: two check bits, +2 flip-flops
// ---------------------------------------------------------------------
//
// Correction is therefore unavailable for dstate at any price this
// design would pay, and detection is what is left. u_disp_chk is one
// pilot_chk_bank instance holding two bits:
//
//   dstate_par = ^dstate. Storing the parity of a 2-bit state next to
//                it makes {dstate, dstate_par} a 3-bit code whose three
//                legal words -- 000 for D_IDLE, 011 for D_FETCH, 110
//                for D_ISSUE -- are pairwise at Hamming distance 2. So
//                EVERY single-bit upset in dstate or in its check bit
//                lands on an illegal word and is detected, including
//                the D_FETCH -> D_ISSUE flip that the two-bit encoding
//                cannot see at all. This is exactly the encoding
//                hw/rtl/lif_core.v gives its own FSM, which the
//                campaign credits with 12 of 12 DETECTED, reached here
//                by adding a check bit rather than by re-encoding --
//                the same cost, +1 flip-flop, and it keeps dstate's
//                three literals and every case arm as they were.
//   evw_par    = ^{evw[15:14], evw[9:0]}, the parity of the twelve bits
//                the dispatcher ACTS on. evw[13:10] is deliberately
//                outside the check: nothing reads those bits (they are
//                in the _unused sink at the bottom of this module), an
//                upset in them is MASKED today, and covering them would
//                convert a harmless upset into a reported fault. A
//                check field must not manufacture alarms for state that
//                does not matter.
//
// The evw check is qualified with `dstate == D_ISSUE` for the same
// reason: outside D_ISSUE the word is about to be overwritten by the
// next capture, an upset in it costs nothing, and the campaign records
// several such injections as MASKED. Checking it unconditionally would
// turn every one of those into a false alarm. The check is applied at
// the one moment the word is used.
//
// One trap in this construction, recorded because the first version of
// it walked straight into it. The two check bits CANNOT both be written
// the same way. dstate is rewritten every edge, so its check bit takes
// a plain next value and a disagreement is one cycle wide -- the
// dual-rail construction of section 8.2, and the combinational term
// reports it on the very edge that heals it. evw is not: it holds its
// word for the whole of D_ISSUE, and a next-value check bit would be
// recomputed from the held word on every edge, so an upset landing IN
// the held word would be recomputed into the check bit one edge later
// and the two would agree on the corrupted event from the second cycle
// onward. The check would then only ever catch an upset in the single
// cycle it arrived, which is a small fraction of the exposure and is
// precisely what the campaign's 3 evw records are outside of. So evw's
// check bit takes an ENABLE, written only when the word is written, and
// stays the parity of the word that was actually captured.
//
// On a failed check, `disp_chk_bad`:
//
//   - the combinational issue is suppressed, so lif_ev_valid,
//     lif_tick_valid and ev_dropped_oor all read low in the same cycle.
//     This matters: a dstate check failure means dstate may READ
//     D_ISSUE while being untrustworthy, and lif_ev_valid is
//     combinational from dstate, so a next-cycle-only recovery would
//     issue the bad event before recovering from it.
//   - the FSM TAKES THE D_IDLE ARM rather than being assigned D_IDLE.
//     That distinction is worth two of the campaign's records and it is
//     the same one docs/16 section 5.8 records for the bounded wait:
//     D_IDLE's arm captures a read answer that arrived in this cycle and
//     re-arms the fetch, while an assignment throws that answer away and
//     turns a reported recovery into a reported recovery WITH a lost
//     event. Measured, the first version of this change assigned the
//     state and two upsets that the design used to absorb harmlessly
//     came back as announced event losses; taking the arm returns both
//     to "announced, nothing lost". The untrusted event is dropped
//     either way -- it is the one whose word or state failed -- and the
//     queue has already dequeued it.
//   - sticky_errcfg latches, on the same clock edge, from the same
//     wire. Section 8.1's rule applies here without amendment: the term
//     is combinational and there is no cycle in which the report exists
//     as separate storage for a second upset to erase or fabricate.
//
// This DETECTS and does not correct, exactly as the dual-rail flags and
// the queue entry parity do, and the claim is the same narrow one: the
// five events are still lost. What changes is that the pilot says so.
//
// The restructure that pays for it: the dispatcher's next state is now
// computed in a combinational block and registered in a separate one,
// because the check bits have to be written from the same next values
// as the registers they cover, on the same edge, or they would drift by
// a cycle and check nothing. The case arms are unchanged line for line.
//
// Cost: +2 flip-flops, one 3-input XOR and one 13-input XOR reduction
// on paths that end at dstate and at lif_core's valid inputs. docs/30
// carries the measured timing.
//
// The merge trap, in its fourth form. These are not replicas, so
// opt_merge has nothing to hash them against -- the hazard is the one
// hw/rtl/lif_core.v's check fields carry and section 3b of
// sw/tests/test_synthesis_guards.py already names: a check bit is a
// pure FUNCTION of the register it covers in every reachable state, so
// a tool able to reason across sequential state could delete the
// storage, rebuild the bit from the parity tree and leave a checker
// that reports every state legal. Nothing in yosys does that today.
// pilot_chk_bank is a keep_hierarchy module with a (* keep *) register
// for the same reason aer_par_bank is: under deferred_flatten abc
// renumbers every cell before the flatten, so an instance path is the
// only naming that reaches the shipped netlist and can be counted
// there.
//
// Plain Verilog-2005, Icarus-clean.
`default_nettype none

`ifndef PILOT_N_NEURONS
  `define PILOT_N_NEURONS 8
`endif
`ifndef PILOT_N_AXONS
  `define PILOT_N_AXONS 8
`endif
`ifndef PILOT_EVQ_IN_DEPTH
  `define PILOT_EVQ_IN_DEPTH 4
`endif
`ifndef PILOT_EVQ_OUT_DEPTH
  `define PILOT_EVQ_OUT_DEPTH 4
`endif
`ifndef PILOT_CNT_W
  `define PILOT_CNT_W 8
`endif

module pilot_top #(
    parameter N_NEURONS     = `PILOT_N_NEURONS,   // see section 6
    parameter N_AXONS       = `PILOT_N_AXONS,
    parameter EVQ_IN_DEPTH  = `PILOT_EVQ_IN_DEPTH,  // power of two >= 2
    parameter EVQ_OUT_DEPTH = `PILOT_EVQ_OUT_DEPTH,
    parameter CNT_W         = `PILOT_CNT_W,       // counter width (D1)
    // derived, do not override
    parameter NEUR_W = (N_NEURONS <= 1) ? 1 : $clog2(N_NEURONS),
    parameter AXON_W = (N_AXONS   <= 1) ? 1 : $clog2(N_AXONS),
    parameter LIN_W  = AXON_W + NEUR_W,
    parameter WORD_W = LIN_W - 4
) (
    input  wire       clk,
    input  wire       rst_n,        // already synchronized by the wrapper

    // serial host port (section 2)
    input  wire       ser_sck,
    input  wire       ser_cs_n,
    input  wire       ser_mosi,
    output wire       ser_miso,

    // parallel AER port (section 1)
    input  wire       aer_in_stb,
    input  wire       aer_in_tick,
    input  wire [3:0] aer_in_addr,
    output wire       aer_in_rdy,
    output wire       aer_out_vld,
    output wire [3:0] aer_out_id,
    input  wire       aer_out_ack,

    // ECC scrub / re-check pulse
    input  wire       scrub_stb,

    // status and fault pins
    output wire       busy,
    output wire       err,
    output wire       sec_seen,
    output wire       ded_seen,
    output wire       tmr_seen
);

`include "npu_regs.vh"

    // -----------------------------------------------------------------
    // Elaboration guards, aer_fifo house style: an illegal configuration
    // references a module that deliberately does not exist, so
    // elaboration fails with the reason as the message in every tool.
    // -----------------------------------------------------------------
    generate
        if (N_NEURONS < 4 || N_NEURONS > 16
            || (N_NEURONS & (N_NEURONS - 1)) != 0) begin : g_bad_neur
            ERROR_pilot_top_N_NEURONS_must_be_4_8_or_16 guard ();
        end
        if (N_AXONS < 4 || N_AXONS > 16
            || (N_AXONS & (N_AXONS - 1)) != 0) begin : g_bad_axon
            ERROR_pilot_top_N_AXONS_must_be_4_8_or_16 guard ();
        end
        if (N_AXONS * N_NEURONS < 32) begin : g_bad_words
            ERROR_pilot_top_needs_at_least_32_synapses_for_one_weight_word guard ();
        end
        if (CNT_W < 2 || CNT_W > 32) begin : g_bad_cnt
            ERROR_pilot_top_CNT_W_must_be_between_2_and_32 guard ();
        end
        // Drift guards for the field layouts this module encodes
        // structurally rather than through a named constant.
        if (BIT_CTRL_EN != 0 || BIT_CTRL_STATE_CLR != 1
            || BIT_CTRL_SOFT_RST != 2 || BIT_CTRL_SCRUB_EN != 3) begin : g_ctrl_moved
            ERROR_pilot_top_CTRL_field_layout_changed_in_regmap_yaml guard ();
        end
        if (BIT_STATUS_BUSY != 0 || BIT_STATUS_EVQ_IN_EMPTY != 1
            || BIT_STATUS_EVQ_OUT_EMPTY != 2 || BIT_STATUS_SYNC_DONE != 3
            || BIT_STATUS_ERR_CFG != 4 || BIT_STATUS_DED_SEEN != 5
            || BIT_STATUS_OVF_SEEN != 6) begin : g_status_moved
            ERROR_pilot_top_STATUS_field_layout_changed_in_regmap_yaml guard ();
        end
        if (BIT_N_DATA_V != 0 || WIDTH_N_DATA_V != 16
            || BIT_N_DATA_R != 16 || WIDTH_N_DATA_R != 4) begin : g_ndata_moved
            ERROR_pilot_top_N_DATA_field_layout_changed_in_regmap_yaml guard ();
        end
        if (BIT_EVQ_STAT_IN_FILL != 0 || WIDTH_EVQ_STAT_IN_FILL != 8
            || BIT_EVQ_STAT_OUT_FILL != 8 || WIDTH_EVQ_STAT_OUT_FILL != 8
            || BIT_EVQ_OUT_EVENT != 0 || WIDTH_EVQ_OUT_EVENT != 16
            || BIT_EVQ_OUT_VALID != 31) begin : g_aer_moved
            ERROR_pilot_top_EVQ_field_layout_changed_in_regmap_yaml guard ();
        end
        if (BIT_ECC_INJ_SINGLE != 0 || BIT_ECC_INJ_DOUBLE != 1) begin : g_inj_moved
            ERROR_pilot_top_ECC_INJ_field_layout_changed_in_regmap_yaml guard ();
        end
        // The five normative FAULT_CLR bits are pinned here for two
        // reasons: this module re-exports bit 2 straight into two aer_fifo
        // drop_clr ports, and the pilot-only CNT_TMR and CNT_EVQ_OUT_OVF
        // clears are allocated immediately above them (section 5). Both
        // break silently if regmap.yaml renumbers the register.
        if (BIT_FAULT_CLR_CNT_SEC != 0 || BIT_FAULT_CLR_CNT_DED != 1
            || BIT_FAULT_CLR_CNT_EVQ_OVF != 2
            || BIT_FAULT_CLR_CNT_AXON_OOR != 3
            || BIT_FAULT_CLR_FAULT_ADDR != 4) begin : g_fclr_moved
            ERROR_pilot_top_FAULT_CLR_field_layout_changed_in_regmap_yaml guard ();
        end
    endgenerate

    localparam integer N_WORDS = (N_AXONS * N_NEURONS) / 16;

    // Configuration TMR vector layout (docs/10 section 11.4). One
    // localparam per field base so the packing appears exactly once.
    localparam integer T_THRESH = 0;    // 16
    localparam integer T_VRESET = 16;   // 16
    localparam integer T_LEAK   = 32;   // 4
    localparam integer T_SYN    = 36;   // 3
    localparam integer T_REFR   = 39;   // 4
    localparam integer T_FLAGS  = 43;   // 2
    localparam integer T_TILE   = 45;   // 10
    localparam integer TMR_W    = 55;

    // Serial register indices: the regmap byte offset, word-addressed.
    localparam [6:0] SA_ID            = ADDR_ID            >> 2;
    localparam [6:0] SA_VERSION       = ADDR_VERSION       >> 2;
    localparam [6:0] SA_SCRATCH       = ADDR_SCRATCH       >> 2;
    localparam [6:0] SA_CTRL          = ADDR_CTRL          >> 2;
    localparam [6:0] SA_STATUS        = ADDR_STATUS        >> 2;
    localparam [6:0] SA_STATUS_CLR    = ADDR_STATUS_CLR    >> 2;
    localparam [6:0] SA_CFG_NEUR      = ADDR_CFG_NEUR      >> 2;
    localparam [6:0] SA_CFG_AXON      = ADDR_CFG_AXON      >> 2;
    localparam [6:0] SA_CFG_THRESH    = ADDR_CFG_THRESH    >> 2;
    localparam [6:0] SA_CFG_VRESET    = ADDR_CFG_VRESET    >> 2;
    localparam [6:0] SA_CFG_LEAK      = ADDR_CFG_LEAK      >> 2;
    localparam [6:0] SA_CFG_SYNSHIFT  = ADDR_CFG_SYNSHIFT  >> 2;
    localparam [6:0] SA_CFG_REFR      = ADDR_CFG_REFR      >> 2;
    localparam [6:0] SA_CFG_FLAGS     = ADDR_CFG_FLAGS     >> 2;
    localparam [6:0] SA_PASS_TILE_OFF = ADDR_PASS_TILE_OFF >> 2;
    localparam [6:0] SA_W_ADDR        = ADDR_W_ADDR        >> 2;
    localparam [6:0] SA_W_DATA_LO     = ADDR_W_DATA_LO     >> 2;
    localparam [6:0] SA_W_DATA_HI     = ADDR_W_DATA_HI     >> 2;
    localparam [6:0] SA_N_ADDR        = ADDR_N_ADDR        >> 2;
    localparam [6:0] SA_N_DATA        = ADDR_N_DATA        >> 2;
    localparam [6:0] SA_CNT_SEC       = ADDR_CNT_SEC       >> 2;
    localparam [6:0] SA_CNT_DED       = ADDR_CNT_DED       >> 2;
    localparam [6:0] SA_CNT_EVQ_OVF   = ADDR_CNT_EVQ_OVF   >> 2;
    localparam [6:0] SA_CNT_AXON_OOR  = ADDR_CNT_AXON_OOR  >> 2;
    localparam [6:0] SA_FAULT_ADDR    = ADDR_FAULT_ADDR    >> 2;
    localparam [6:0] SA_ECC_INJ       = ADDR_ECC_INJ       >> 2;
    localparam [6:0] SA_FAULT_CLR     = ADDR_FAULT_CLR     >> 2;
    localparam [6:0] SA_EVQ_STAT      = ADDR_EVQ_STAT      >> 2;
    localparam [6:0] SA_EVQ_IN        = ADDR_EVQ_IN        >> 2;
    localparam [6:0] SA_EVQ_OUT       = ADDR_EVQ_OUT       >> 2;
    localparam [6:0] SA_NODE_ID       = ADDR_NODE_ID       >> 2;
    // pilot-only block (D5), in the unmapped region of the same window
    localparam [6:0] SA_ECC_INJ_POS   = 12'h0A0 >> 2;
    localparam [6:0] SA_TMR_INJ       = 12'h0A4 >> 2;
    localparam [6:0] SA_CNT_TMR       = 12'h0A8 >> 2;
    localparam [6:0] SA_CNT_EVQ_OUT_OVF = 12'h0AC >> 2;
    localparam [6:0] SA_CNT_EVQ_PAR   = 12'h0B0 >> 2;

    // -----------------------------------------------------------------
    // Input synchronizers. Every asynchronous pin gets two flops before
    // it is used, and the strobe pins are then edge-detected: an
    // external driver cannot be expected to meet a single-cycle
    // valid/ready handshake at the clk rate, so the parallel AER port
    // and the scrub pin transfer one item per RISING EDGE of the strobe.
    // -----------------------------------------------------------------
    reg [1:0] sck_s, csn_s, mosi_s, ain_s, aack_s, scr_s;
    reg [3:0] ain_addr_s0, ain_addr_s1;
    reg [1:0] ain_tick_s;
    reg       sck_q, ain_q, aack_q, scr_q;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sck_s <= 2'b00; csn_s <= 2'b11; mosi_s <= 2'b00;
            ain_s <= 2'b00; aack_s <= 2'b00; scr_s <= 2'b00;
            ain_addr_s0 <= 4'd0; ain_addr_s1 <= 4'd0;
            ain_tick_s <= 2'b00;
            sck_q <= 1'b0; ain_q <= 1'b0; aack_q <= 1'b0; scr_q <= 1'b0;
        end else begin
            sck_s  <= {sck_s[0],  ser_sck};
            csn_s  <= {csn_s[0],  ser_cs_n};
            mosi_s <= {mosi_s[0], ser_mosi};
            ain_s  <= {ain_s[0],  aer_in_stb};
            aack_s <= {aack_s[0], aer_out_ack};
            scr_s  <= {scr_s[0],  scrub_stb};
            ain_addr_s0 <= aer_in_addr;
            ain_addr_s1 <= ain_addr_s0;
            ain_tick_s  <= {ain_tick_s[0], aer_in_tick};
            sck_q  <= sck_s[1];
            ain_q  <= ain_s[1];
            aack_q <= aack_s[1];
            scr_q  <= scr_s[1];
        end
    end

    wire sck_rise = sck_s[1] && !sck_q;
    wire sck_fall = !sck_s[1] && sck_q;
    wire cs_active = !csn_s[1];
    wire ain_rise  = ain_s[1]  && !ain_q;
    wire aack_rise = aack_s[1] && !aack_q;
    wire scr_rise  = scr_s[1]  && !scr_q;

    // -----------------------------------------------------------------
    // Serial shift engine (section 2)
    // -----------------------------------------------------------------
    reg [5:0]  bit_cnt;
    reg [31:0] rx_sh;
    reg [31:0] tx_sh;
    reg        cmd_wr;
    reg [6:0]  cmd_addr;
    reg        rd_strobe;   // one cycle: command byte complete, read
    reg        wr_strobe;   // one cycle: frame complete, write commits

    wire [31:0] rdata;      // combinational register read multiplexer

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bit_cnt <= 6'd0; rx_sh <= 32'd0; tx_sh <= 32'd0;
            cmd_wr <= 1'b0; cmd_addr <= 7'd0;
            rd_strobe <= 1'b0; wr_strobe <= 1'b0;
        end else begin
            rd_strobe <= 1'b0;
            wr_strobe <= 1'b0;
            if (!cs_active) begin
                bit_cnt <= 6'd0;
            end else begin
                if (sck_rise) begin
                    rx_sh   <= {rx_sh[30:0], mosi_s[1]};
                    bit_cnt <= bit_cnt + 6'd1;
                    if (bit_cnt == 6'd7) begin
                        // command byte completes on this edge; rx_sh has
                        // seven bits shifted in, the eighth is mosi now.
                        cmd_wr    <= rx_sh[6];
                        cmd_addr  <= {rx_sh[5:0], mosi_s[1]};
                        rd_strobe <= !rx_sh[6];
                    end
                    if (bit_cnt == 6'd39)
                        wr_strobe <= cmd_wr;
                end
                // bit_cnt is 8 for the whole window between the
                // command byte and the first data bit; the read result
                // is loaded there by rd_strobe, so that one falling edge
                // must not shift it out from under itself.
                if (sck_fall && bit_cnt != 6'd8)
                    tx_sh <= {tx_sh[30:0], 1'b0};
            end
            if (rd_strobe) tx_sh <= rdata;
        end
    end

    assign ser_miso = cs_active ? tx_sh[31] : 1'b0;

    // rd_strobe is registered, so the read lands in tx_sh one clk cycle
    // after the eighth rising edge. With SER_SCK <= clk/4 the eighth
    // falling edge is at least two clk cycles further on, so the host
    // always samples data bit 31 on SER_SCK cycle 9.
    wire [6:0]  reg_addr  = cmd_addr;
    wire [31:0] reg_wdata = rx_sh;
    wire        reg_wr    = wr_strobe;
    wire        reg_rd    = rd_strobe;

    // -----------------------------------------------------------------
    // Address decode
    // -----------------------------------------------------------------
    wire s_scratch      = (reg_addr == SA_SCRATCH);
    wire s_ctrl         = (reg_addr == SA_CTRL);
    wire s_status_clr   = (reg_addr == SA_STATUS_CLR);
    wire s_cfg_axon     = (reg_addr == SA_CFG_AXON);
    wire s_cfg_thresh   = (reg_addr == SA_CFG_THRESH);
    wire s_cfg_vreset   = (reg_addr == SA_CFG_VRESET);
    wire s_cfg_leak     = (reg_addr == SA_CFG_LEAK);
    wire s_cfg_synshift = (reg_addr == SA_CFG_SYNSHIFT);
    wire s_cfg_refr     = (reg_addr == SA_CFG_REFR);
    wire s_cfg_flags    = (reg_addr == SA_CFG_FLAGS);
    wire s_tile_off     = (reg_addr == SA_PASS_TILE_OFF);
    wire s_w_addr       = (reg_addr == SA_W_ADDR);
    wire s_w_data_lo    = (reg_addr == SA_W_DATA_LO);
    wire s_w_data_hi    = (reg_addr == SA_W_DATA_HI);
    wire s_n_addr       = (reg_addr == SA_N_ADDR);
    wire s_n_data       = (reg_addr == SA_N_DATA);
    wire s_ecc_inj      = (reg_addr == SA_ECC_INJ);
    wire s_fault_clr    = (reg_addr == SA_FAULT_CLR);
    wire s_evq_in       = (reg_addr == SA_EVQ_IN);
    wire s_evq_out      = (reg_addr == SA_EVQ_OUT);
    wire s_node_id      = (reg_addr == SA_NODE_ID);
    wire s_inj_pos      = (reg_addr == SA_ECC_INJ_POS);
    wire s_tmr_inj      = (reg_addr == SA_TMR_INJ);

    // Configuration lock set (docs/10 section 6 / npu_regbank C4): every
    // register whose value enters the pass configuration or the load
    // port. CTRL, STATUS_CLR, FAULT_CLR, SCRATCH, EVQ_IN and ECC_INJ
    // stay writable while BUSY.
    wire s_locked = s_cfg_axon | s_cfg_thresh | s_cfg_vreset | s_cfg_leak
                  | s_cfg_synshift | s_cfg_refr | s_cfg_flags | s_tile_off
                  | s_w_addr | s_w_data_lo | s_w_data_hi | s_n_addr
                  | s_n_data | s_node_id;

    wire status_busy;
    wire wr_ok     = reg_wr && !(s_locked && status_busy);
    wire wr_locked = reg_wr &&  (s_locked && status_busy);

    // -----------------------------------------------------------------
    // Register storage
    // -----------------------------------------------------------------
    reg [31:0] scratch;
    reg        ctrl_en, ctrl_scrub_en;
    reg        state_clr_req, soft_rst;
    reg [10:0] cfg_axon;
    reg [3:0]  node_id;
    reg [NEUR_W-1:0] n_addr;
    reg [WORD_W-1:0] w_addr;
    reg [6:0]  ecc_inj_pos;
    reg [9:0]  tmr_inj;
    reg        inj_single, inj_double;

    // sticky STATUS bits 3..6
    reg sticky_sync, sticky_errcfg, sticky_ded, sticky_ovf;
    // fault-pin stickies not present in STATUS
    reg sticky_sec, sticky_tmr;

    // Configuration replicas (TMR domain). Three pilot_cfg_bank
    // instances at the bottom of this file, NOT three regs here; see
    // header section 9 for why, and sw/tests/test_synthesis_guards.py
    // for the check that keeps it true.
    wire [TMR_W-1:0] cfg_a, cfg_b, cfg_c;

    // ECC-protected weight staging word: data field is W_DATA_LO/HI
    reg [63:0] ecc_data;
    reg [7:0]  ecc_check;

    // fault counters. cnt_evqo is the pilot-only EVQ_OUT event-loss
    // counter of section 5.1; it is a register here and not u_evq_out's
    // own drop_cnt on purpose, and that section is the whole argument.
    // cnt_evqp is the pilot-only entry-parity discard counter of section
    // 5.2, shared by both queue instances.
    reg [CNT_W-1:0] cnt_sec, cnt_ded, cnt_oor, cnt_tmr, cnt_evqo, cnt_evqp;
    reg [WORD_W-1:0] fault_addr;

    // FAULT_CLR decode. regmap/regmap.yaml is the single source of truth
    // for the five normative bits ("one bit per fault-block register in
    // offset order from 0x70"), so every position below comes from the
    // generated header and none is written as a literal. The guard above
    // fails elaboration if one of them moves.
    wire fclr_wr   = wr_ok && s_fault_clr;
    wire fclr_sec  = fclr_wr && reg_wdata[BIT_FAULT_CLR_CNT_SEC];
    wire fclr_ded  = fclr_wr && reg_wdata[BIT_FAULT_CLR_CNT_DED];
    wire fclr_ovf  = fclr_wr && reg_wdata[BIT_FAULT_CLR_CNT_EVQ_OVF];
    wire fclr_oor  = fclr_wr && reg_wdata[BIT_FAULT_CLR_CNT_AXON_OOR];
    wire fclr_addr = fclr_wr && reg_wdata[BIT_FAULT_CLR_FAULT_ADDR];

    // Pilot-only extension, same class as the three pilot-only registers
    // of section 5 (deviation D5). CNT_TMR does not exist in
    // regmap/regmap.yaml, so neither can its clear bit; it is allocated
    // the first position the map leaves free, in the range regmap.yaml
    // declares ignored ("bits [31:5] ignored"). Nothing in the
    // architecture block acts on it, so a host that clears the whole
    // register is portable across both. If the TMR counter is ever
    // promoted into regmap.yaml, delete this localparam and index
    // reg_wdata with the generated BIT_FAULT_CLR_CNT_TMR instead.
    localparam integer PILOT_BIT_FAULT_CLR_CNT_TMR = 5;
    wire fclr_tmr = fclr_wr && reg_wdata[PILOT_BIT_FAULT_CLR_CNT_TMR];

    // Second pilot-only clear, allocated on the same argument: the next
    // free bit above the five the map declares (section 5.1 is why
    // CNT_EVQ_OUT_OVF is pilot-only in the first place). Bit 2 is NOT
    // reused for it -- one clear bit per counter is the convention the
    // architecture block is checked against, and a host that cleared the
    // input-queue counter would otherwise silently zero an unrelated
    // output-queue measurement.
    localparam integer PILOT_BIT_FAULT_CLR_CNT_EVQ_OUT_OVF = 6;
    wire fclr_evqo = fclr_wr && reg_wdata[PILOT_BIT_FAULT_CLR_CNT_EVQ_OUT_OVF];

    // Third pilot-only clear, section 5.2, allocated by the same rule:
    // the next free bit above the ones already taken. Bit 2 is not
    // reused here either -- CNT_EVQ_OVF counts refused writes into
    // EVQ_IN and this counts discarded reads out of either queue, and a
    // host clearing one must not zero the other.
    localparam integer PILOT_BIT_FAULT_CLR_CNT_EVQ_PAR = 7;
    wire fclr_evqp = fclr_wr && reg_wdata[PILOT_BIT_FAULT_CLR_CNT_EVQ_PAR];

    localparam [CNT_W-1:0] CNT_MAX = {CNT_W{1'b1}};

    // -----------------------------------------------------------------
    // Configuration TMR domain (header section 9)
    // -----------------------------------------------------------------
    // Packed write port shared by the three banks. Every field position
    // is taken from the T_* layout localparams, so the elaboration drift
    // guard above still covers this packing, and the payload of each
    // field is reg_wdata[width-1:0] exactly as the register map defines
    // it. wr_ok is the qualified write strobe, so the enable term here
    // is identical to the `if (wr_ok) ... if (s_cfg_x)` nesting these
    // assignments used to sit inside.
    wire [TMR_W-1:0] cfg_wr_d;
    wire [TMR_W-1:0] cfg_wr_en;

    assign cfg_wr_d [T_THRESH +: 16] = reg_wdata[15:0];
    assign cfg_wr_d [T_VRESET +: 16] = reg_wdata[15:0];
    assign cfg_wr_d [T_LEAK   +: 4]  = reg_wdata[3:0];
    assign cfg_wr_d [T_SYN    +: 3]  = reg_wdata[2:0];
    assign cfg_wr_d [T_REFR   +: 4]  = reg_wdata[3:0];
    assign cfg_wr_d [T_FLAGS  +: 2]  = reg_wdata[1:0];
    assign cfg_wr_d [T_TILE   +: 10] = reg_wdata[9:0];

    assign cfg_wr_en[T_THRESH +: 16] = {16{wr_ok && s_cfg_thresh}};
    assign cfg_wr_en[T_VRESET +: 16] = {16{wr_ok && s_cfg_vreset}};
    assign cfg_wr_en[T_LEAK   +: 4]  = {4 {wr_ok && s_cfg_leak}};
    assign cfg_wr_en[T_SYN    +: 3]  = {3 {wr_ok && s_cfg_synshift}};
    assign cfg_wr_en[T_REFR   +: 4]  = {4 {wr_ok && s_cfg_refr}};
    assign cfg_wr_en[T_FLAGS  +: 2]  = {2 {wr_ok && s_cfg_flags}};
    assign cfg_wr_en[T_TILE   +: 10] = {10{wr_ok && s_tile_off}};

    // Reset image of the TMR vector (docs/10 section 6), assembled from
    // the generated RST_* constants at the T_* positions. Shifted-OR
    // rather than a concatenation so the packing stays expressed in the
    // same localparams the drift guard checks, and so a field that moves
    // cannot be silently mis-packed by a concatenation whose order was
    // never updated.
    localparam [63:0] CFG_RST_VAL =
          ({{(64-16){1'b0}}, RST_CFG_THRESH[15:0]}   << T_THRESH)
        | ({{(64-16){1'b0}}, RST_CFG_VRESET[15:0]}   << T_VRESET)
        | ({{(64-4) {1'b0}}, RST_CFG_LEAK[3:0]}      << T_LEAK)
        | ({{(64-3) {1'b0}}, RST_CFG_SYNSHIFT[2:0]}  << T_SYN)
        | ({{(64-4) {1'b0}}, RST_CFG_REFR[3:0]}      << T_REFR)
        | ({{(64-2) {1'b0}}, RST_CFG_FLAGS[1:0]}     << T_FLAGS)
        | ({{(64-10){1'b0}}, RST_PASS_TILE_OFF[9:0]} << T_TILE);

    // Per-replica storage polarity, header section 9 option (d). These
    // are TMR_W = 55 bits wide inside the bank; the parameter is carried
    // as 64 bits so the port declaration does not depend on W.
    //
    // Polarity separates A from B and can do no more than that: it
    // offers two functions per bit and there are three replicas. C is
    // held apart by MIX = 1 below, not by CFG_POL_C, which survives only
    // for the storage-direction decorrelation argument in the bank
    // header. Do not add a fourth replica expecting a fourth polarity.
    localparam [63:0] CFG_POL_A = 64'h0000000000000000;  // true
    localparam [63:0] CFG_POL_B = 64'h007FFFFFFFFFFFFF;  // 55 ones
    localparam [63:0] CFG_POL_C = 64'h002AAAAAAAAAAAAA;  // odd bits

    // A width change to the TMR vector must not silently truncate the
    // reset image or the polarity masks, both of which are carried as
    // 64-bit parameters.
    generate
        if (TMR_W > 64) begin : g_tmr_too_wide
            ERROR_pilot_top_TMR_W_exceeds_the_64_bit_cfg_bank_parameters guard ();
        end
        // The MIX = 1 bank splits the word at W/2 and mixes each half
        // into the other. Below four bits a half is one bit wide and the
        // layer-2 rotation `(i+1) % LO` degenerates to the identity, so
        // a stored bit could fall back to weight 1 and collide with a
        // polarity bank. Nothing can reach this today -- TMR_W is 55 and
        // fixed by the register map -- but a future narrowing must not
        // silently disarm the defence.
        if (TMR_W < 4) begin : g_tmr_too_narrow
            ERROR_pilot_top_TMR_W_below_4_disarms_the_cfg_bank_MIX_transform guard ();
        end
    endgenerate

    pilot_cfg_bank #(.W(TMR_W), .RST_VAL(CFG_RST_VAL), .POL(CFG_POL_A))
        u_cfg_a (.clk(clk), .rst_n(rst_n), .wr_en(cfg_wr_en),
                 .wr_d(cfg_wr_d), .q(cfg_a));

    pilot_cfg_bank #(.W(TMR_W), .RST_VAL(CFG_RST_VAL), .POL(CFG_POL_B))
        u_cfg_b (.clk(clk), .rst_n(rst_n), .wr_en(cfg_wr_en),
                 .wr_d(cfg_wr_d), .q(cfg_b));

    // MIX = 1 on exactly one replica. A and B are already bit-for-bit
    // distinct from each other by polarity; C is the one that needs a
    // third storage function, and the XOR mixing is only paid for once.
    pilot_cfg_bank #(.W(TMR_W), .RST_VAL(CFG_RST_VAL), .POL(CFG_POL_C),
                     .MIX(1))
        u_cfg_c (.clk(clk), .rst_n(rst_n), .wr_en(cfg_wr_en),
                 .wr_d(cfg_wr_d), .q(cfg_c));

    wire [TMR_W-1:0] inj_bit = {{(TMR_W-1){1'b0}}, 1'b1} << tmr_inj[5:0];
    wire [TMR_W-1:0] inj_a = (tmr_inj[9:8] == 2'b01) ? inj_bit : {TMR_W{1'b0}};
    wire [TMR_W-1:0] inj_b = (tmr_inj[9:8] == 2'b10) ? inj_bit : {TMR_W{1'b0}};
    wire [TMR_W-1:0] inj_c = (tmr_inj[9:8] == 2'b11) ? inj_bit : {TMR_W{1'b0}};

    wire [TMR_W-1:0] cfg_v;
    wire             cfg_mismatch;

    tmr_voter #(.WIDTH(TMR_W)) u_cfg_vote (
        .in_a     (cfg_a ^ inj_a),
        .in_b     (cfg_b ^ inj_b),
        .in_c     (cfg_c ^ inj_c),
        .out      (cfg_v),
        .mismatch (cfg_mismatch)
    );

    wire [15:0] cfg_thresh   = cfg_v[T_THRESH +: 16];
    wire [15:0] cfg_vreset   = cfg_v[T_VRESET +: 16];
    wire [3:0]  cfg_leak     = cfg_v[T_LEAK   +: 4];
    wire [2:0]  cfg_synshift = cfg_v[T_SYN    +: 3];
    wire [3:0]  cfg_refr     = cfg_v[T_REFR   +: 4];
    wire [1:0]  cfg_flags    = cfg_v[T_FLAGS  +: 2];
    wire [9:0]  cfg_tile_off = cfg_v[T_TILE   +: 10];

    reg  mismatch_q;
    wire mismatch_edge = cfg_mismatch && !mismatch_q;

    // Configuration validity (docs/10 section 6). CFG_NEUR is a constant
    // (D2) so only THETA, V_RESET and CFG_AXON can leave their range;
    // every other field is exactly as wide as its range.
    wire cfg_valid = (cfg_thresh != 16'd0) && (cfg_thresh[15] == 1'b0)
                  && ($signed(cfg_vreset) < $signed(cfg_thresh))
                  && (cfg_axon != 11'd0) && (cfg_axon <= N_AXONS[10:0]);

    wire core_en = ctrl_en && cfg_valid;

    // -----------------------------------------------------------------
    // Soft reset (CTRL.SOFT_RST): flushes the queues and the pipeline,
    // keeps the configuration. It is a registered one-cycle pulse, so
    // the reset it drives is glitch-free.
    // -----------------------------------------------------------------
    wire blk_rst_n = rst_n && !soft_rst;

    // -----------------------------------------------------------------
    // Input event queue (EVQ_IN)
    // -----------------------------------------------------------------
    wire        fi_full, fi_empty, fi_rd_valid, fi_rv_mm;
    wire [15:0] fi_rd_data;
    wire [$clog2(EVQ_IN_DEPTH):0] fi_level;
    wire [CNT_W-1:0] fi_drop;
    wire        fi_ptr_mm, fi_par_err;
    reg         fi_rd_en;

    // Two producers: the serial EVQ_IN register and the AER_IN pin
    // strobe. They are independent and can collide; the pin wins and the
    // software write is dropped and counted, which is exactly the
    // EVQ_IN-on-full rule of docs/10 section 7.2 applied one level up.
    wire        pin_push = ain_rise;
    wire [15:0] pin_word = {ain_tick_s[1] ? 2'b01 : 2'b00, 4'b0000,
                            6'b000000, ain_addr_s1};
    wire        sw_push  = wr_ok && s_evq_in;
    wire        fi_wr_en = pin_push || sw_push;
    wire [15:0] fi_wr_data = pin_push ? pin_word : reg_wdata[15:0];

    aer_fifo #(
        .WIDTH (16), .DEPTH (EVQ_IN_DEPTH), .DROP_W (CNT_W)
    ) u_evq_in (
        .clk      (clk),
        .rst_n    (blk_rst_n),
        .wr_en    (fi_wr_en),
        .wr_data  (fi_wr_data),
        .full     (fi_full),
        .rd_en    (fi_rd_en),
        .rd_data  (fi_rd_data),
        .rd_valid (fi_rd_valid),
        .empty    (fi_empty),
        .level    (fi_level),
        .drop_clr (fclr_ovf),
        .drop_cnt (fi_drop),
        .ptr_mismatch (fi_ptr_mm),
        .rv_mismatch  (fi_rv_mm),
        .par_err      (fi_par_err)
    );

    // -----------------------------------------------------------------
    // Output event queue (EVQ_OUT) and its one-deep holding register
    // -----------------------------------------------------------------
    wire        fo_full, fo_empty, fo_rd_valid, fo_rv_mm;
    wire [15:0] fo_rd_data;
    wire [$clog2(EVQ_OUT_DEPTH):0] fo_level;
    wire [CNT_W-1:0] fo_drop;
    wire        fo_ptr_mm, fo_par_err;
    reg         fo_rd_en;
    reg         oh_req;
    reg [15:0]  oh_data;

    // Bound on the oh_req wait (header section 8). Same shape and same
    // width as the dispatcher's FETCH_WAIT: a granted queue read answers
    // in one cycle, so 63 is generous, and 6 bits keeps the counter to 6
    // flip-flops.
    localparam integer OH_WAIT_W = 6;
    localparam [OH_WAIT_W-1:0] OH_WAIT_MAX = {OH_WAIT_W{1'b1}};
    reg [OH_WAIT_W-1:0] oh_wait;

    // The expiry term, combinational rather than a registered pulse
    // (header section 8.1). oh_expire is the exact condition under which
    // the wait is abandoned, and it is the same wire that abandons it
    // below and that latches sticky_errcfg in the register process, so
    // recovery and report happen on the same clock edge and there is no
    // cycle in which the report exists as separate corruptible state.
    // blk_rst_n is part of the term because the register process that
    // consumes it sits on rst_n and keeps running through a block reset.
    wire oh_expire = blk_rst_n && oh_req && !fo_rd_valid
                     && (oh_wait == OH_WAIT_MAX);

    wire        lif_out_valid;
    wire [15:0] lif_out_event;
    reg         sync_push;
    reg [15:0]  sync_word;

    wire        fo_wr_en   = lif_out_valid || sync_push;
    wire [15:0] fo_wr_data = sync_push ? sync_word : lif_out_event;
    wire        lif_out_ready = !fo_full && !sync_push;

    aer_fifo #(
        .WIDTH (16), .DEPTH (EVQ_OUT_DEPTH), .DROP_W (CNT_W)
    ) u_evq_out (
        .clk      (clk),
        .rst_n    (blk_rst_n),
        .wr_en    (fo_wr_en),
        .wr_data  (fo_wr_data),
        .full     (fo_full),
        .rd_en    (fo_rd_en),
        .rd_data  (fo_rd_data),
        .rd_valid (fo_rd_valid),
        .empty    (fo_empty),
        .level    (fo_level),
        .drop_clr (fclr_ovf),
        .drop_cnt (fo_drop),
        .ptr_mismatch (fo_ptr_mm),
        .rv_mismatch  (fo_rv_mm),
        .par_err      (fo_par_err)
    );

    // Pointer-TMR telemetry from the two queues. hw/rtl/aer_fifo.v votes
    // three replicas of each queue pointer and reports a corrected
    // disagreement on ptr_mismatch. That report is half the protection:
    // an upset that is corrected and not counted is indistinguishable
    // from no upset at all, and measuring the upset environment is what
    // this part is for. The queues therefore feed the counter the
    // configuration domain already has, on the same convention -- one
    // CNT_TMR event per rising edge, so a disagreement that persists
    // across cycles is counted once and simultaneous edges from two
    // sources are counted once. CNT_TMR is an episode counter, not a
    // bit-error count (section 5).
    //
    // The edge register sits in the fault-counter block on rst_n rather
    // than on blk_rst_n, so CTRL.SOFT_RST -- the recovery for exactly
    // this class of fault -- cannot erase the evidence that it happened
    // (docs/16 section 5.1 records what the other arrangement costs).
    wire evq_ptr_mismatch = fi_ptr_mm || fo_ptr_mm;
    reg  evq_mm_q;
    wire evq_ptr_edge = evq_ptr_mismatch && !evq_mm_q;

    // Every TMR correction in the pilot, from the configuration domain
    // or from a queue pointer, in one event.
    wire tmr_event = mismatch_edge || evq_ptr_edge;

    // Entry-parity telemetry from the two queues (header section 5.2).
    // aer_fifo raises par_err when an accepted read found the stored
    // word inconsistent with its parity bit and threw the entry away.
    // The event already reaches the host as STATUS.ERR_CFG through the
    // consumer's bounded wait; what this adds is the distinction
    // between a configuration fault and an integrity discard, which is
    // the number a part flown to measure an upset environment has to
    // return. One counter for both instances, on the CNT_TMR precedent
    // rather than section 5.1's -- the argument is in section 5.2.
    wire evq_par_err = fi_par_err || fo_par_err;
    reg  evq_par_q;
    wire evq_par_event = evq_par_err && !evq_par_q;

    // The EVQ_OUT event loss, and the only one there is: a SYNC echo
    // refused by a full queue. sync_push is a one-shot, so a refused
    // echo is gone, while a refused lif_core spike is merely held and
    // retried -- which is why fo_drop above, an aer_fifo "wr_en && full"
    // count, measures stall cycles here rather than lost events and is
    // still sunk. Section 5.1 carries the measurement and the argument.
    wire evqo_drop = sync_push && fo_full;

    // -----------------------------------------------------------------
    // oh_valid, dual-rail (header section 8.2)
    // -----------------------------------------------------------------
    // Both rail ports present the flag in true polarity, so the rails
    // AGREE when they are equal and one of them has been upset when
    // they are not. On a disagreement the adapter presents nothing --
    // dropping a held event is a smaller fault than fabricating one out
    // of stale oh_data, and section 5.7's general finding is that a
    // valid flag can do either -- and the disagreement is reported
    // through sticky_errcfg in the fault process. It is not corrected:
    // two rails detect, they do not vote. It clears itself on the next
    // clock edge, because oh_valid_d below reads this checked value.
    wire oh_valid_a, oh_valid_b;
    wire oh_valid_mm = (oh_valid_a != oh_valid_b);
    wire oh_valid    = oh_valid_a && oh_valid_b;

    // The one-entry show-ahead adapter of section 8, and what both
    // output observers see. A pop by either one frees it; if both pop in
    // the same cycle the entry is consumed once, by both.
    wire evq_out_rd  = reg_rd && s_evq_out && oh_valid;
    wire pin_pop     = aack_rise && oh_valid;
    wire oh_pop      = evq_out_rd || pin_pop;

    // The flag's next state, hoisted out of the sequential block below
    // so that both rails are written from ONE expression. It is the
    // same priority that block used to carry -- a fill beats a pop, and
    // the entry is held otherwise -- with the hold written as a MUX
    // rather than as a flip-flop enable, so both rails are rewritten
    // every cycle.
    //
    // The mux is load bearing. oh_valid_d reads the CHECKED oh_valid,
    // which is low while the rails disagree, so a disagreement rewrites
    // both rails to the safe value on the next edge from any state: the
    // fault cannot persist into a second upset and oh_valid_mm cannot
    // stick high with no traffic to clear it. hw/rtl/lif_core.v records
    // what the enable form cost that module's bounded proof; the shape
    // here is the same for the same reason, and all three rail modules
    // in this repository take a next value rather than an enable.
    wire oh_valid_set = fo_rd_valid;
    wire oh_valid_d   = oh_valid_set || (oh_valid && !oh_pop);

    pilot_flag_rail #(.POL(1'b0)) u_ohv_a (
        .clk (clk), .rst_n (blk_rst_n),
        .d (oh_valid_d), .q (oh_valid_a));
    pilot_flag_rail #(.POL(1'b1)) u_ohv_b (
        .clk (clk), .rst_n (blk_rst_n),
        .d (oh_valid_d), .q (oh_valid_b));

    always @(posedge clk or negedge blk_rst_n) begin
        if (!blk_rst_n) begin
            oh_req     <= 1'b0;
            oh_data    <= 16'd0;
            fo_rd_en   <= 1'b0;
            oh_wait    <= {OH_WAIT_W{1'b0}};
        end else begin
            fo_rd_en   <= 1'b0;
            if (fo_rd_valid) begin
                oh_data  <= fo_rd_data;
                oh_req   <= 1'b0;
                oh_wait  <= {OH_WAIT_W{1'b0}};
            end
            // The bounded wait of header section 8. An oh_req that no
            // read will ever answer is abandoned rather than waited on
            // forever, and the abandonment is reported. The arm below
            // reads the CURRENT oh_req, which is still set in this
            // cycle, so the re-arm happens on the next one.
            if (oh_req && !fo_rd_valid) begin
                if (oh_expire) begin
                    oh_req     <= 1'b0;
                    oh_wait    <= {OH_WAIT_W{1'b0}};
                end else begin
                    oh_wait <= oh_wait + 1'b1;
                end
            end
            if (!oh_valid && !oh_req && !fo_rd_valid && !fo_empty && !fo_rd_en) begin
                fo_rd_en <= 1'b1;
                oh_req   <= 1'b1;
                oh_wait  <= {OH_WAIT_W{1'b0}};
            end
        end
    end

    assign aer_out_vld = oh_valid;
    assign aer_out_id  = oh_data[3:0];

    // -----------------------------------------------------------------
    // SECDED weight word (docs/10 sections 5 and 11.2)
    // -----------------------------------------------------------------
    // The decoder reads the stored codeword directly, so it always
    // reports what is physically in the flops. The encoder is shared by
    // the two writers of the check field -- a W_DATA_HI commit and a
    // scrub writeback -- and is therefore fed from a mux, not from the
    // stored data: at commit time the stored data field is still the
    // PREVIOUS word, and encoding that would store a check field that
    // does not belong to the data next to it. (Wiring the encoder to
    // the register instead of the mux is exactly the bug this comment
    // exists to prevent; it presents as an immediate DED on the first
    // word whose two halves differ.)
    reg        ecc_commit;   // W_DATA_HI committed, check the word next cycle
    reg        ld_pend;      // a checked word is waiting for the core
    reg        ld_zero;      // that word was uncorrectable (E10)
    reg [WORD_W-1:0] ld_word_idx;
    reg [WORD_W-1:0] w_addr_cmt;   // word index of the stored codeword
    reg        ld_run;
    reg [3:0]  ld_k;

    wire [63:0] dec_data;
    wire [7:0]  dec_syndrome;
    wire        dec_sec, dec_ded;

    secded_dec u_dec (
        .code_in   ({ecc_check, ecc_data}),
        .data_out  (dec_data),
        .syndrome  (dec_syndrome),
        .sec       (dec_sec),
        .ded       (dec_ded)
    );

    // ecc_commit is a registered pulse: it is high in the cycle AFTER a
    // W_DATA_HI commit, when the stored word already carries the
    // injected pattern, so the decoder observes exactly what is in the
    // flops. SCRUB_STB raises the same observation without a load.
    wire ecc_obs = ecc_commit || scr_rise;

    wire [63:0] ecc_data_nxt = (wr_ok && s_w_data_hi)
                             ? {reg_wdata, ecc_data[31:0]} : ecc_data;
    wire scrub_now = ecc_obs && ctrl_scrub_en && dec_sec;
    wire [63:0] enc_in = scrub_now ? dec_data : ecc_data_nxt;

    wire [7:0]  enc_check;
    wire [71:0] enc_code;

    secded_enc u_enc (
        .data_in   (enc_in),
        .check_out (enc_check),
        .code_out  (enc_code)
    );

    // Injection masks over the 72-bit codeword. The position lives in
    // the pilot-only ECC_INJ_POS register (D5); its reset value selects
    // bit 0, so an ECC_INJ write alone is already deterministic.
    wire [71:0] one72   = {{71{1'b0}}, 1'b1};
    wire [71:0] mask_a  = one72 << ecc_inj_pos;
    // The second flipped bit is the neighbour of the first, rotated
    // inside the codeword. Any two distinct positions form a valid
    // double error for a Hsiao code -- every 2-bit syndrome is nonzero
    // and of even parity, so it can never match a column -- and a second
    // barrel shifter would cost more than the whole SECDED decoder.
    wire [71:0] mask_b  = {mask_a[70:0], mask_a[71]};
    wire [71:0] inj_code = (inj_single ? mask_a : 72'd0)
                         ^ (inj_double ? (mask_a ^ mask_b) : 72'd0);

    // -----------------------------------------------------------------
    // Weight loader. Runs 16 cycles per committed word and writes the
    // lif_core flip-flop synapse file one weight per cycle. It only
    // starts when the core is idle, which is the lif_core contract for
    // the w_wr_en port.
    // -----------------------------------------------------------------

    wire lif_busy;
    wire ld_busy = ld_run || ld_pend || ecc_commit;

    wire [LIN_W-1:0] ld_lin = {ld_word_idx, ld_k};
    // The loader reads its nibbles out of the DECODER, not out of the
    // stored word: docs/10 section 5 requires single-bit errors to be
    // corrected inline on the read path, independently of whether the
    // scrubber is enabled. No register is needed for it -- the whole
    // configuration-locked set, W_DATA_LO/HI included, is write blocked
    // while STATUS.BUSY is high and ld_busy is part of BUSY, so the
    // stored word cannot move under the loader and dec_data is stable
    // for the whole sixteen-cycle sweep. Only the E10 verdict is latched.
    wire [3:0] ld_nibble = ld_zero ? 4'd0
                                   : dec_data[{ld_k, 2'b00} +: 4];

    // -----------------------------------------------------------------
    // Event dispatcher
    // -----------------------------------------------------------------
    localparam [1:0] D_IDLE = 2'b00, D_FETCH = 2'b01, D_ISSUE = 2'b11;

    // Bound on the D_FETCH wait. A granted read answers in one cycle, so
    // any value well above that is generous; 6 bits keeps the counter to
    // 6 flip-flops and still allows 63 cycles of queue latency before the
    // wait is declared a fault.
    localparam integer FETCH_WAIT_W   = 6;
    localparam [FETCH_WAIT_W-1:0] FETCH_WAIT_MAX = {FETCH_WAIT_W{1'b1}};
    reg [FETCH_WAIT_W-1:0] fetch_wait;

    reg [1:0]  dstate;
    reg [15:0] evw;

    // Next values, computed combinationally and registered below. The
    // split exists so the check bits of header section 10.2 can be
    // written from the same next values, on the same edge, as the
    // registers they cover; a check field written a cycle later would
    // spend that cycle disagreeing with a state that is perfectly good.
    reg [1:0]  dstate_n;
    reg [15:0] evw_n;
    reg        fi_rd_en_n, sync_push_n;
    reg [15:0] sync_word_n;
    reg [FETCH_WAIT_W-1:0] fetch_wait_n;
    reg        evw_load;      // this edge captures a new event word

    // The dispatcher check field (header section 10). Two bits in one
    // pilot_chk_bank instance: the parity of dstate, which turns the
    // 2-bit state into a Hamming-distance-2 code and is the only
    // protection a 2-bit register can have (section 10.1 proves that a
    // third replica does not exist over two bits), and the parity of
    // the twelve bits of evw the dispatcher acts on.
    wire dstate_par, evw_par;

    // The twelve bits of the event word that are read. evw[13:10] is
    // out of the check on purpose: nothing reads it, so covering it
    // would turn an upset that costs nothing into a reported fault.
    wire [11:0] evw_cov   = {evw[15:14],   evw[9:0]};
    wire [11:0] evw_cov_n = {evw_n[15:14], evw_n[9:0]};

    // The two bits are written on different terms, and the difference is
    // the whole correctness of the evw half.
    //
    //   dstate_par takes a plain NEXT VALUE. dstate is rewritten from
    //   dstate_n on every edge whatever happens, so `^dstate_n` is the
    //   parity of the value actually being stored, and an upset in
    //   either is a one-cycle disagreement that the combinational check
    //   below reports on that same edge before the rewrite heals it.
    //   That is the dual-rail flags' construction and it is safe here
    //   for the same reason: every term of dstate_n is X-free.
    //
    //   evw_par takes an ENABLE, and must. evw HOLDS its value across
    //   the whole of D_ISSUE, so a next-value check bit would be
    //   recomputed from the held word every cycle -- and an upset that
    //   landed IN that held word would be recomputed into the check bit
    //   one edge later, healing the check into agreement with the
    //   corrupted event and detecting nothing from the second cycle on.
    //   Written only when the word is, the check bit stays the parity of
    //   the word that was captured, which is the only thing worth
    //   comparing against. hw/rtl/lif_core.v's rail takes an enable for
    //   a different reason (X-freedom) and this is the second reason a
    //   check bit ever needs one.
    pilot_chk_bank #(.W(2)) u_disp_chk (
        .clk   (clk),
        .rst_n (blk_rst_n),
        .d     ({evw_load ? ^evw_cov_n : evw_par, ^dstate_n}),
        .q     ({evw_par,                         dstate_par})
    );

    // The two check terms, combinational and not registered pulses, on
    // header section 8.1's rule: the wire that recovers is the wire
    // that reports, so there is no cycle in which the report is
    // separate state. blk_rst_n is a term for the same reason it is one
    // in fetch_expire -- the fault process that consumes this sits on
    // rst_n and keeps running through a block reset.
    //
    // {dstate, dstate_par} is 000 / 011 / 110 and nothing else, so an
    // odd parity over the three bits is exactly "a single-bit upset
    // landed here".
    wire dstate_chk_bad = blk_rst_n && (^{dstate, dstate_par});

    // The event word is checked at the one moment it is acted on.
    // Outside D_ISSUE it is about to be overwritten by the next
    // capture, and the campaign records upsets there as MASKED; a check
    // that fired on them would be manufacturing alarms.
    wire evw_chk_bad = blk_rst_n && (dstate == D_ISSUE)
                       && (^{evw_cov, evw_par});

    wire disp_chk_bad = dstate_chk_bad || evw_chk_bad;

    // The expiry term, combinational rather than a registered pulse
    // (header section 8.1), and the exact counterpart of oh_expire. It
    // is both the condition that abandons the wait below and the
    // condition that latches sticky_errcfg in the register process, on
    // the same edge, so the report cannot be erased or fabricated
    // separately from the recovery it reports. blk_rst_n is part of the
    // term because that register process sits on rst_n.
    wire fetch_expire = blk_rst_n && (dstate == D_FETCH) && !fi_rd_valid
                        && (fetch_wait == FETCH_WAIT_MAX);

    wire [9:0] ev_id   = evw[9:0];
    wire [1:0] ev_type = evw[15:14];
    wire       ev_oor  = ({1'b0, ev_id} >= cfg_axon);

    wire lif_ev_ready, lif_tick_ready;
    reg  lif_ev_valid, lif_tick_valid;

    wire disp_busy = (dstate != D_IDLE);
    assign status_busy = lif_busy || ld_busy || disp_busy || state_clr_req;
    assign busy = status_busy;

    // STATE_CLR is only presented to the core when the core is fully
    // idle, so the pulse can never be missed (lif_core samples it in
    // S_IDLE only) and can never be taken twice.
    wire state_clr_go = state_clr_req && !lif_busy && !ld_busy && !disp_busy;

    always @(*) begin
        dstate_n     = dstate;
        evw_n        = evw;
        fi_rd_en_n   = 1'b0;
        sync_push_n  = 1'b0;
        sync_word_n  = sync_word;
        fetch_wait_n = fetch_wait;
        evw_load     = 1'b0;
        // A failed check means the state, or the word, is not
        // trustworthy. The recovery is to take the D_IDLE arm -- not to
        // assign D_IDLE -- and the difference is measured rather than
        // stylistic (header section 10.2). D_IDLE's arm captures a read
        // answer that arrived and re-arms the fetch; assigning the state
        // instead throws that answer away, which is docs/16 section
        // 5.8's fire_spurious defect exactly, and test_04 already holds
        // the same property for the bounded wait: a spurious recovery
        // must cost the report and nothing else. The untrusted event is
        // dropped either way, and sticky_errcfg latches from this same
        // wire on this same edge.
        case (disp_chk_bad ? D_IDLE : dstate)
            // A read answered while the FSM is in D_IDLE cannot
            // happen in a fault-free run -- fi_rd_en is asserted only
            // by the arm below, which moves to D_FETCH on the same
            // edge -- but it is reachable after an upset, and after
            // the bounded wait above gives up one cycle before a
            // slow grant arrives. Without the first arm that word is
            // read out of the queue and dropped, which turns a
            // reported recovery into a reported recovery WITH a lost
            // event (measured: docs/16 section 5.8, the
            // fire_spurious case). Capturing it costs no state --
            // evw and dstate already exist -- and is what the
            // show-ahead adapter has always done, whose capture is
            // `if (fo_rd_valid)` and is not gated on oh_req.
            D_IDLE: begin
                if (fi_rd_valid) begin
                    evw_n    = fi_rd_data;
                    evw_load = 1'b1;
                    dstate_n = D_ISSUE;
                end else if (core_en && !fi_empty && !ld_busy
                             && !state_clr_req && !fi_rd_en) begin
                    fi_rd_en_n = 1'b1;
                    dstate_n   = D_FETCH;
                end
            end
            // D_FETCH waits for the read it requested in D_IDLE. An
            // upset that lands the FSM here without a read outstanding
            // would otherwise wait forever with STATUS.BUSY high and
            // nothing flagged -- the one failure class this chip exists
            // to rule out. The bounded wait converts that silent hang
            // into a latched configuration fault the host can see.
            // Measured by the fault-injection campaign (docs/16
            // section 5.1): reachable from a direct dstate flip and
            // from an EVQ_IN write-pointer flip.
            D_FETCH: begin
                if (fi_rd_valid) begin
                    evw_n        = fi_rd_data;
                    evw_load     = 1'b1;
                    dstate_n     = D_ISSUE;
                    fetch_wait_n = {FETCH_WAIT_W{1'b0}};
                end else if (fetch_expire) begin
                    dstate_n     = D_IDLE;
                    fetch_wait_n = {FETCH_WAIT_W{1'b0}};
                end else begin
                    fetch_wait_n = fetch_wait + 1'b1;
                end
            end
            D_ISSUE: begin
                case (ev_type)
                    2'b00: if (ev_oor || lif_ev_ready) dstate_n = D_IDLE;
                    2'b01: if (lif_tick_ready)         dstate_n = D_IDLE;
                    2'b10: if (!lif_busy && !fo_full && !sync_push) begin
                               sync_push_n = 1'b1;
                               sync_word_n = evw;
                               dstate_n    = D_IDLE;
                           end
                    default: dstate_n = D_IDLE;   // reserved TYPE
                endcase
            end
            default: dstate_n = D_IDLE;
        endcase
    end

    always @(posedge clk or negedge blk_rst_n) begin
        if (!blk_rst_n) begin
            dstate     <= D_IDLE;
            evw        <= 16'd0;
            fi_rd_en   <= 1'b0;
            sync_push  <= 1'b0;
            sync_word  <= 16'd0;
            fetch_wait <= {FETCH_WAIT_W{1'b0}};
            // u_disp_chk resets itself, to 2'b00 -- which is exactly the
            // parity of D_IDLE and of the all-zero event word, so the
            // check field is consistent out of reset with no assignment
            // here and no first-cycle false alarm.
        end else begin
            dstate     <= dstate_n;
            evw        <= evw_n;
            fi_rd_en   <= fi_rd_en_n;
            sync_push  <= sync_push_n;
            sync_word  <= sync_word_n;
            fetch_wait <= fetch_wait_n;
        end
    end

    // The issue decision is combinational from dstate and evw, so a
    // failed check has to suppress it in the SAME cycle: recovering only
    // on the next edge would let the untrusted event reach lif_core
    // first, which is the whole failure being closed (header 10.2).
    always @(*) begin
        lif_ev_valid   = 1'b0;
        lif_tick_valid = 1'b0;
        if (dstate == D_ISSUE && !disp_chk_bad) begin
            if (ev_type == 2'b00 && !ev_oor) lif_ev_valid   = 1'b1;
            if (ev_type == 2'b01)            lif_tick_valid = 1'b1;
        end
    end

    // Same gate, same reason: an event dropped because its word failed
    // its check is not an out-of-range axon and must not be counted as
    // one. It is counted by STATUS.ERR_CFG, in the fault process.
    wire ev_dropped_oor = (dstate == D_ISSUE) && !disp_chk_bad
                          && (ev_type == 2'b00) && ev_oor;

    // -----------------------------------------------------------------
    // LIF core
    // -----------------------------------------------------------------
    wire [15:0] dbg_v;
    wire [3:0]  dbg_r;

    // lif_core raises err_cfg when its Hamming-distance-2 state register
    // decodes to an illegal word and the FSM parks in S_SAFE (section 7).
    // It is a level output, sticky inside lif_core until that block is
    // reset, so it needs no sticky flop on this side.
    wire lif_err_cfg;

    // ECC status from the neuron core's own protected memories. These are
    // level outputs, asserted for the cycle in which a read used a word
    // the decoder acted on. Until 2026-08-27 all four were left
    // unconnected here, so the codes corrected and nothing on the chip
    // said so: the fault-injection campaign measured 84 corrections and
    // had to classify every one MASKED, because a host with an SPI master
    // sees no counter move, no sticky latch and no fault pin. For a part
    // whose stated purpose is to measure the upset environment, the
    // counters are the product (docs/16 section 4.1).
    wire lif_wmem_sec, lif_wmem_ded, lif_state_sec, lif_state_ded;
    wire lif_pend_mm;

    // The core's corrections join the same CNT_SEC/CNT_DED counters as
    // the weight-load and scrub codec. Those registers are defined
    // generically ("Corrected single-bit ECC events", regmap.yaml 0x70),
    // so the aggregate is what the map already promises. The cost, stated
    // rather than hidden: a host reading CNT_SEC cannot tell a synapse
    // array correction from a load-path one. Per-domain attribution needs
    // its own counters, a regmap entry and the checked conventions that
    // come with one (docs/10 section 10, npu_regbank.v, test_regmap.py);
    // it is a named follow-up, not a thing to bolt on here.
    wire lif_ecc_sec = lif_wmem_sec  || lif_state_sec;
    wire lif_ecc_ded = lif_wmem_ded  || lif_state_ded;

    // Both ECC domains can report in the same cycle, and a counter that
    // is written from two branches of one always block keeps only the
    // last one -- which would silently drop an event on exactly the busy
    // cycles a radiation counter exists to record. So the increment is
    // computed once, adds the number of events, and saturates; the codec
    // path below no longer touches cnt_sec/cnt_ded itself.
    wire [1:0] sec_events = {1'b0, lif_ecc_sec} + {1'b0, (ecc_obs && dec_sec)};
    wire [1:0] ded_events = {1'b0, lif_ecc_ded} + {1'b0, (ecc_obs && dec_ded)};

    wire [CNT_W:0]     cnt_sec_sum  = {1'b0, cnt_sec} + {{(CNT_W-1){1'b0}}, sec_events};
    wire [CNT_W:0]     cnt_ded_sum  = {1'b0, cnt_ded} + {{(CNT_W-1){1'b0}}, ded_events};
    wire [CNT_W-1:0]   cnt_sec_next = cnt_sec_sum[CNT_W] ? CNT_MAX : cnt_sec_sum[CNT_W-1:0];
    wire [CNT_W-1:0]   cnt_ded_next = cnt_ded_sum[CNT_W] ? CNT_MAX : cnt_ded_sum[CNT_W-1:0];

    lif_core #(
        .N_NEURONS (N_NEURONS),
        .N_AXONS   (N_AXONS)
    ) u_lif (
        .clk            (clk),
        .rst_n          (blk_rst_n),
        .cfg_thresh     (cfg_thresh),
        .cfg_vreset     (cfg_vreset),
        .cfg_leak_shift (cfg_leak),
        .cfg_syn_shift  (cfg_synshift),
        .cfg_refr       (cfg_refr),
        .cfg_leak_en    (cfg_flags[1]),
        .cfg_tile_off   (cfg_tile_off),
        .state_clr      (state_clr_go),
        .busy           (lif_busy),
        .err_cfg        (lif_err_cfg),
        .w_wr_en        (ld_run),
        .w_wr_axon      (ld_lin[LIN_W-1:NEUR_W]),
        .w_wr_neuron    (ld_lin[NEUR_W-1:0]),
        .w_wr_data      (ld_nibble),
        .ev_valid       (lif_ev_valid),
        .ev_axon        (ev_id[AXON_W-1:0]),
        .ev_ready       (lif_ev_ready),
        .tick_valid     (lif_tick_valid),
        .tick_ready     (lif_tick_ready),
        .out_valid      (lif_out_valid),
        .out_event      (lif_out_event),
        .out_ready      (lif_out_ready),
        .dbg_addr       (n_addr[NEUR_W-1:0]),
        .dbg_v          (dbg_v),
        .dbg_r          (dbg_r),
        .dbg_wr_en      (wr_ok && s_n_data),
        .dbg_wr_v       (reg_wdata[15:0]),
        .dbg_wr_r       (reg_wdata[19:16]),
        .wmem_sec       (lif_wmem_sec),
        .wmem_ded       (lif_wmem_ded),
        .state_sec      (lif_state_sec),
        .state_ded      (lif_state_ded),
        .pend_mismatch  (lif_pend_mm)
    );

    // -----------------------------------------------------------------
    // Register file, counters and side effects
    // -----------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            scratch       <= RST_SCRATCH;
            ctrl_en       <= RST_CTRL[BIT_CTRL_EN];
            ctrl_scrub_en <= RST_CTRL[BIT_CTRL_SCRUB_EN];
            state_clr_req <= 1'b0;
            soft_rst      <= 1'b0;
            cfg_axon      <= N_AXONS[10:0];
            node_id       <= RST_NODE_ID[3:0];
            n_addr        <= {NEUR_W{1'b0}};
            w_addr        <= {WORD_W{1'b0}};
            w_addr_cmt    <= {WORD_W{1'b0}};
            ecc_inj_pos   <= 7'd0;              // codeword bit 0
            tmr_inj       <= 10'd0;
            inj_single    <= 1'b0;
            inj_double    <= 1'b0;
            sticky_sync   <= 1'b0;
            sticky_errcfg <= 1'b0;
            sticky_ded    <= 1'b0;
            sticky_ovf    <= 1'b0;
            sticky_sec    <= 1'b0;
            sticky_tmr    <= 1'b0;
            ecc_data      <= 64'd0;
            ecc_check     <= 8'd0;
            cnt_sec       <= {CNT_W{1'b0}};
            cnt_ded       <= {CNT_W{1'b0}};
            cnt_oor       <= {CNT_W{1'b0}};
            cnt_tmr       <= {CNT_W{1'b0}};
            cnt_evqo      <= {CNT_W{1'b0}};
            cnt_evqp      <= {CNT_W{1'b0}};
            fault_addr    <= {WORD_W{1'b0}};
            mismatch_q    <= 1'b0;
            evq_mm_q      <= 1'b0;
            evq_par_q     <= 1'b0;
            ecc_commit    <= 1'b0;
            ld_pend       <= 1'b0;
            ld_zero       <= 1'b0;
            ld_word_idx   <= {WORD_W{1'b0}};
            ld_run        <= 1'b0;
            ld_k          <= 4'd0;
            // The TMR replicas reset themselves inside pilot_cfg_bank,
            // from the CFG_RST_VAL image assembled next to their
            // instantiation. They are not driven from this process on
            // purpose: three identical assignments here are exactly what
            // synthesis proved equivalent and merged (header section 9).
        end else begin
            // self-clearing strobes
            state_clr_req <= state_clr_req && !state_clr_go;
            soft_rst      <= 1'b0;
            ecc_commit    <= wr_ok && s_w_data_hi;
            mismatch_q    <= cfg_mismatch;
            evq_mm_q      <= evq_ptr_mismatch;
            evq_par_q     <= evq_par_err;

            // ---- writes ----------------------------------------------
            if (wr_locked)
                sticky_errcfg <= 1'b1;              // docs/10 section 6

            if (wr_ok) begin
                if (s_scratch) scratch <= reg_wdata;
                if (s_ctrl) begin
                    ctrl_en       <= reg_wdata[BIT_CTRL_EN];
                    ctrl_scrub_en <= reg_wdata[BIT_CTRL_SCRUB_EN];
                    if (reg_wdata[BIT_CTRL_STATE_CLR]) state_clr_req <= 1'b1;
                    if (reg_wdata[BIT_CTRL_SOFT_RST])  soft_rst      <= 1'b1;
                end
                if (s_status_clr) begin
                    if (reg_wdata[BIT_STATUS_SYNC_DONE]) sticky_sync   <= 1'b0;
                    if (reg_wdata[BIT_STATUS_ERR_CFG])   sticky_errcfg <= 1'b0;
                    if (reg_wdata[BIT_STATUS_DED_SEEN])  sticky_ded    <= 1'b0;
                    if (reg_wdata[BIT_STATUS_OVF_SEEN])  sticky_ovf    <= 1'b0;
                end
                if (s_cfg_axon) cfg_axon <= reg_wdata[10:0];
                if (s_node_id)  node_id  <= reg_wdata[3:0];
                if (s_n_addr)   n_addr   <= reg_wdata[NEUR_W-1:0];
                if (s_w_addr)   w_addr   <= reg_wdata[WORD_W-1:0];
                if (s_inj_pos)  ecc_inj_pos <= reg_wdata[6:0];
                if (s_tmr_inj)  tmr_inj     <= reg_wdata[9:0];
                if (s_ecc_inj) begin
                    inj_single <= reg_wdata[BIT_ECC_INJ_SINGLE];
                    inj_double <= reg_wdata[BIT_ECC_INJ_DOUBLE];
                end
                // TMR-protected configuration: one write updates all
                // three replicas, so a masked replica error is repaired
                // by the next configuration write as well as by a scrub.
                // The write itself happens in the three pilot_cfg_bank
                // instances, driven by cfg_wr_en / cfg_wr_d, which carry
                // the same wr_ok && s_cfg_x enable this branch used to
                // apply. Do not reintroduce the assignments here: three
                // identical ones are what synthesis merged into one bank
                // (header section 9).
                // ECC-protected staging word (D4)
                if (s_w_data_lo) ecc_data[31:0] <= reg_wdata;
                if (s_w_data_hi) begin
                    // data field takes the new word, then the armed
                    // injection pattern is XORed into the stored
                    // codeword; the check field is the encoding of the
                    // clean data, likewise corrupted where selected.
                    ecc_data   <= ecc_data_nxt ^ inj_code[63:0];
                    ecc_check  <= enc_check    ^ inj_code[71:64];
                    inj_single <= 1'b0;          // one-shot, deterministic
                    inj_double <= 1'b0;
                    w_addr_cmt <= w_addr;
                    w_addr     <= w_addr + 1'b1; // regmap auto-increment
                end
            end

            // ---- Neuron-core memory ECC ------------------------------
            // Counted on the same registers as the codec path below. The
            // core's outputs are levels, one cycle per acted-on read, so
            // they are sampled here exactly like any other event; a read
            // that the decoder did not act on holds them low.
            // FAULT_ADDR is deliberately NOT written from here: it holds
            // a weight-word index from the loader's address space, and a
            // neuron-state or synapse-array address is not in it. A
            // DED_SEEN with an unchanged FAULT_ADDR therefore means the
            // uncorrectable word was inside the core, which is the one
            // bit of attribution this aggregate does preserve.
            if (sec_events != 2'd0) begin
                sticky_sec <= 1'b1;
                cnt_sec    <= cnt_sec_next;
            end
            if (ded_events != 2'd0) begin
                sticky_ded <= 1'b1;
                cnt_ded    <= cnt_ded_next;
            end

            // ---- ECC observation, scrub and load hand-off ------------
            if (ecc_obs) begin
                if (dec_ded) begin
                    fault_addr <= w_addr_cmt;
                end
                if (scrub_now) begin
                    ecc_data  <= dec_data;
                    ecc_check <= enc_check;      // enc_in == dec_data here
                end
                if (ecc_commit) begin
                    // E10: an uncorrectable word contributes zero
                    // (docs/10 section 11.2, fail-operational). A
                    // correctable one is repaired in place by the scrub
                    // above before the loader reads it; with SCRUB_EN
                    // clear the loader sees the raw stored nibbles,
                    // which is the honest behaviour of a core running
                    // without a scrubber.
                    ld_zero     <= dec_ded;
                    ld_word_idx <= w_addr_cmt;
                    ld_pend     <= 1'b1;
                end
            end

            // ---- weight loader --------------------------------------
            if (ld_run) begin
                ld_k <= ld_k + 4'd1;
                if (ld_k == 4'd15) ld_run <= 1'b0;
            end else if (ld_pend && !lif_busy && !state_clr_req && !disp_busy) begin
                ld_pend <= 1'b0;
                ld_run  <= 1'b1;
                ld_k    <= 4'd0;
            end

            // ---- fault counters and stickies -------------------------
            if (ev_dropped_oor && cnt_oor != CNT_MAX) cnt_oor <= cnt_oor + 1'b1;
            if (tmr_event) begin
                sticky_tmr <= 1'b1;
                if (cnt_tmr != CNT_MAX) cnt_tmr <= cnt_tmr + 1'b1;
            end
            // STATUS.OVF_SEEN is "an event was dropped", not "a queue
            // was busy". The EVQ_IN term is a software-port write into a
            // full queue, exactly as regmap.yaml defines the bit. The
            // EVQ_OUT term used to be `fo_wr_en && fo_full`, which also
            // fires on ordinary lossless backpressure -- measured, one
            // eight-spike event latches it and lights the ERR pin with
            // nothing lost -- so it is now the one output-side write
            // that is genuinely lost. Section 5.1.
            if ((fi_wr_en && fi_full) || evqo_drop)
                sticky_ovf <= 1'b1;
            if (evqo_drop && cnt_evqo != CNT_MAX) cnt_evqo <= cnt_evqo + 1'b1;
            // The entry-parity discard, both queues in one episode count
            // (section 5.2). No sticky: the discard suppresses rd_valid
            // and the consumer's bounded wait latches sticky_errcfg
            // below, so the alarm already exists and this is the
            // distinction the alarm cannot carry.
            if (evq_par_event && cnt_evqp != CNT_MAX)
                cnt_evqp <= cnt_evqp + 1'b1;
            if (sync_push) sticky_sync <= 1'b1;
            if (!cfg_valid && ctrl_en) sticky_errcfg <= 1'b1;
            // A parked neuron core is latched into the sticky bit as
            // well as ORed into STATUS live (section 7). The live term
            // is what stops STATUS_CLR from hiding a fault that is
            // still present; the sticky term is what stops CTRL.SOFT_RST
            // -- the recovery for exactly this fault -- from erasing the
            // evidence that it happened. A chip built to measure upset
            // rates must not lose an upset to its own recovery.
            if (lif_err_cfg) sticky_errcfg <= 1'b1;
            // A dispatcher that waited out D_FETCH was hung; the recovery
            // to D_IDLE is silent unless it is recorded here. This reads
            // the combinational expiry term, not a pulse register, so
            // this latch and the return to D_IDLE happen on the same
            // edge (header section 8.1).
            if (fetch_expire) sticky_errcfg <= 1'b1;
            // The same for the show-ahead adapter (header section 8): an
            // oh_req with no read behind it wedges the output path
            // outright, and its recovery must not be silent either.
            if (oh_expire) sticky_errcfg <= 1'b1;
            // The dispatcher check field (header section 10). A state or
            // an event word that failed its parity is DETECTED and not
            // corrected -- over two bits a third replica provably does
            // not exist (section 10.1) -- so the event is dropped and
            // the drop is announced. It is not counted in CNT_TMR:
            // nothing was masked. Reading the combinational term rather
            // than a pulse register is section 8.1's rule, and it is
            // what makes this report unerasable.
            if (disp_chk_bad) sticky_errcfg <= 1'b1;
            // The show-ahead valid flag's two rails disagreeing (header
            // section 8.2). This is a DETECTED and not a corrected
            // upset: the held event is dropped rather than presented,
            // and dropping it silently is exactly the failure the
            // campaign measured this flag doing. It is not counted in
            // CNT_TMR, which is an episode counter for corrections that
            // the voter MASKED, and nothing was masked here.
            if (oh_valid_mm) sticky_errcfg <= 1'b1;
            // The same for the other two dual-rail flags of that class:
            // the queues' registered read-valid (hw/rtl/aer_fifo.v, one
            // report per instance) and the neuron core's output holding
            // flag (hw/rtl/lif_core.v). All three are DETECTED and not
            // corrected, all three drop rather than fabricate, and all
            // three land here rather than in CNT_TMR for the reason
            // above: nothing was masked. A per-cause counter is the same
            // open item as CNT_TIMEOUT (docs/16 section 5.8).
            if (fi_rv_mm || fo_rv_mm) sticky_errcfg <= 1'b1;
            if (lif_pend_mm)          sticky_errcfg <= 1'b1;

            // ---- FAULT_CLR (npu_regbank C2 re-export) ----------------
            // A clear coincident with its own event restarts the
            // counter at 1 rather than losing the event -- the same
            // convention aer_fifo.v uses for drop_clr. These assignments
            // come last in the block on purpose, so a clear beats the
            // increment above it for the same register.
            if (fclr_sec) begin
                cnt_sec    <= {{(CNT_W-1){1'b0}}, (ecc_obs && dec_sec)};
                sticky_sec <= ecc_obs && dec_sec;
            end
            if (fclr_ded)
                cnt_ded <= {{(CNT_W-1){1'b0}}, (ecc_obs && dec_ded)};
            if (fclr_oor)
                cnt_oor <= {{(CNT_W-1){1'b0}}, ev_dropped_oor};
            if (fclr_addr)
                fault_addr <= (ecc_obs && dec_ded) ? w_addr_cmt
                                                   : {WORD_W{1'b0}};
            if (fclr_tmr) begin
                cnt_tmr    <= {{(CNT_W-1){1'b0}}, tmr_event};
                sticky_tmr <= tmr_event;
            end
            // sticky_ovf is deliberately NOT touched here: it is cleared
            // by STATUS_CLR like every other STATUS sticky, and it is
            // shared with the input queue, so a FAULT_CLR of one of the
            // two counters must not clear a record the other one made.
            if (fclr_evqo)
                cnt_evqo <= {{(CNT_W-1){1'b0}}, evqo_drop};
            if (fclr_evqp)
                cnt_evqp <= {{(CNT_W-1){1'b0}}, evq_par_event};
        end
    end

    // -----------------------------------------------------------------
    // Read multiplexer
    // -----------------------------------------------------------------
    wire evq_out_empty = fo_empty && !oh_valid;

    // STATUS.ERR_CFG (section 7). sticky_errcfg carries the configuration
    // faults raised in this module and, latched above, the fact that the
    // neuron core parked; lif_err_cfg is ORed in live on top of it so that
    // STATUS_CLR cannot report a still-parked core as recovered. The two
    // together are the bit, and the ERR pin below is the same bit.
    wire err_cfg_any = sticky_errcfg || lif_err_cfg;

    wire [31:0] status_word = {25'd0, sticky_ovf, sticky_ded, err_cfg_any,
                               sticky_sync, evq_out_empty, fi_empty,
                               status_busy};

    wire [7:0] in_fill  = {{(8 - $clog2(EVQ_IN_DEPTH) - 1){1'b0}}, fi_level};
    wire [7:0] out_fill = {{(8 - $clog2(EVQ_OUT_DEPTH) - 1){1'b0}}, fo_level}
                        + {7'd0, oh_valid};

    reg [31:0] rdata_r;
    assign rdata = rdata_r;

    always @(*) begin
        case (reg_addr)
            SA_ID:            rdata_r = RST_ID;
            SA_VERSION:       rdata_r = RST_VERSION;
            SA_SCRATCH:       rdata_r = scratch;
            SA_CTRL:          rdata_r = {28'd0, ctrl_scrub_en, 1'b0,
                                         state_clr_req, ctrl_en};
            SA_STATUS:        rdata_r = status_word;
            SA_CFG_NEUR:      rdata_r = N_NEURONS;
            SA_CFG_AXON:      rdata_r = {21'd0, cfg_axon};
            SA_CFG_THRESH:    rdata_r = {16'd0, cfg_thresh};
            SA_CFG_VRESET:    rdata_r = {16'd0, cfg_vreset};
            SA_CFG_LEAK:      rdata_r = {28'd0, cfg_leak};
            SA_CFG_SYNSHIFT:  rdata_r = {29'd0, cfg_synshift};
            SA_CFG_REFR:      rdata_r = {28'd0, cfg_refr};
            SA_CFG_FLAGS:     rdata_r = {30'd0, cfg_flags};
            SA_PASS_TILE_OFF: rdata_r = {22'd0, cfg_tile_off};
            SA_W_ADDR:        rdata_r = {{(32 - WORD_W){1'b0}}, w_addr};
            SA_W_DATA_LO:     rdata_r = ecc_data[31:0];
            SA_W_DATA_HI:     rdata_r = ecc_data[63:32];
            SA_N_ADDR:        rdata_r = {{(32 - NEUR_W){1'b0}}, n_addr};
            SA_N_DATA:        rdata_r = {12'd0, dbg_r, dbg_v};
            SA_CNT_SEC:       rdata_r = {{(32 - CNT_W){1'b0}}, cnt_sec};
            SA_CNT_DED:       rdata_r = {{(32 - CNT_W){1'b0}}, cnt_ded};
            SA_CNT_EVQ_OVF:   rdata_r = {{(32 - CNT_W){1'b0}}, fi_drop};
            SA_CNT_AXON_OOR:  rdata_r = {{(32 - CNT_W){1'b0}}, cnt_oor};
            SA_FAULT_ADDR:    rdata_r = {{(32 - WORD_W){1'b0}}, fault_addr};
            SA_ECC_INJ:       rdata_r = {30'd0, inj_double, inj_single};
            SA_EVQ_STAT:      rdata_r = {16'd0, out_fill, in_fill};
            SA_EVQ_OUT:       rdata_r = {oh_valid, 15'd0, oh_data};
            SA_NODE_ID:       rdata_r = {28'd0, node_id};
            SA_ECC_INJ_POS:   rdata_r = {25'd0, ecc_inj_pos};
            SA_TMR_INJ:       rdata_r = {22'd0, tmr_inj};
            SA_CNT_TMR:       rdata_r = {{(32 - CNT_W){1'b0}}, cnt_tmr};
            SA_CNT_EVQ_OUT_OVF:
                              rdata_r = {{(32 - CNT_W){1'b0}}, cnt_evqo};
            SA_CNT_EVQ_PAR:   rdata_r = {{(32 - CNT_W){1'b0}}, cnt_evqp};
            default:          rdata_r = 32'd0;   // unmapped, incl. WO
        endcase
    end

    // -----------------------------------------------------------------
    // Pin outputs
    // -----------------------------------------------------------------
    assign aer_in_rdy = !fi_full;
    assign err        = err_cfg_any || sticky_ovf;
    assign sec_seen   = sticky_sec;
    assign ded_seen   = sticky_ded;
    assign tmr_seen   = sticky_tmr;

    // Deliberately unread bits, sunk so lint and synthesis agree that
    // they are unused rather than accidentally dropped. fo_drop is here
    // by measurement, not by omission: for this instance aer_fifo's
    // "wr_en && full" counter counts backpressure CYCLES rather than
    // lost events, so it is not the output queue's drop count and must
    // not be published as one. CNT_EVQ_OUT_OVF at 0x0AC is, and section
    // 5.1 is the whole argument.
    wire _unused = &{1'b0, dec_syndrome, enc_code, fo_drop,
                     tmr_inj[7:6], evw[13:10], 1'b0};

endmodule

// =====================================================================
// pilot_chk_bank: storage for a check field, held apart from its encoder
// =====================================================================
//
// A plain register bank with one job that a `reg [W-1:0]` in pilot_top
// could not do: exist under an instance path in the shipped netlist.
// Under SYNTH_HIERARCHY_MODE = deferred_flatten, abc renumbers every
// cell to `_NNNN_` before the flatten, so a net name is evidence in
// this repository's MODEL of synthesis and nothing at all in the
// artifact that becomes silicon. hw/rtl/aer_fifo.v's aer_par_bank is
// the same module for the same reason and its header carries the
// argument in full; sw/tests/test_synthesis_guards.py section 4 is what
// reads the result.
//
// The hazard here is NOT opt_merge. A check bit has no twin to be
// hashed against -- that is the pointer replicas' and the valid flags'
// problem, and it is why those modules carry a POL or MIX storage
// transform and this one does not. The hazard is the one every check
// field carries: the stored bit is a pure FUNCTION of the register it
// covers in every reachable state, so a tool able to reason across
// sequential state could delete the storage, rebuild the bit from the
// parity tree, and leave a checker that reports every state legal --
// protection that passes every simulation in this repository and
// detects nothing in silicon. Nothing in yosys does that today. The
// keep_hierarchy attribute, the (* keep *) on the register and the
// netlist guard are three independent answers to the same question,
// and none of them is trusted alone.
//
// Reset to zero, and the caller is responsible for choosing an encoding
// in which zero is the check of the reset state, so that nothing has to
// be assigned here and there is no first-cycle false alarm.
(* keep_hierarchy *)
module pilot_chk_bank #(
    parameter integer W = 1
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [W-1:0] d,
    output wire [W-1:0] q
);
    (* keep *) reg [W-1:0] bits;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) bits <= {W{1'b0}};
        else        bits <= d;
    end

    assign q = bits;
endmodule

// =====================================================================
// pilot_flag_rail: one physical rail of a dual-rail one-bit flag
// =====================================================================
//
// pilot_cfg_bank below, cut down to one bit and to two replicas, and
// for the reason header section 8.2 gives: over ONE variable there are
// exactly two storage functions, x and ~x, so two rails can be held
// apart by polarity alone and provably, while three cannot be held
// apart at all without an attribute. This module is therefore the
// widest redundancy a single flag can carry under this repository's own
// rule that the structural difference must not depend on a tool
// honouring a hint.
//
// Both defences of pilot_cfg_bank are here and neither is trusted
// alone:
//
//   keep_hierarchy   `flatten` skips this module and `opt_merge` does
//                    not merge instances of user-defined modules unless
//                    invoked with -share_all. Portable across the
//                    LibreLane/yosys ASIC flow and synth_ecp5; NOT
//                    portable to a front end that ignores attributes,
//                    which is why POL exists.
//   POL              the per-rail storage transform. One rail stores
//                    the flag and the other stores its complement, so
//                    for as long as the design is RTLIL the two rails
//                    are a $_DFF_PN0_ and a $_DFF_PN1_ -- different D
//                    net, different reset value -- and structural
//                    hashing has nothing to match with the hierarchy
//                    gone. Plain Verilog-2005; depends on no attribute.
//                    At 55 bits this same layer was measured to hold
//                    the configuration domain's replicas A and B apart
//                    under a forced flatten while the third, which had
//                    no third function available, collapsed. At one bit
//                    there is no third function to want.
//
// What POL is measured to buy, and it is measured rather than argued.
// With EVERY `keep` and `keep_hierarchy` deleted from hw/rtl -- not
// just stripped by attrmap after elaboration -- both the ASIC and the
// ECP5 recipes keep all 1296 flip-flops, no rail and no bank merged.
// Mutating `.POL(1'b1)` on u_ohv_b to `.POL(1'b0)`, which no simulation
// can tell from the original, takes both to 1295: the pair collapses to
// one flip-flop that agrees with itself. Measured 2026-08-31 [fact];
// sw/tests/test_synthesis_guards.py section 1e is that experiment kept
// running.
//
// What POL does NOT buy, and what the shipped netlist actually holds.
// POL does not reach silicon. The stored reset value is `1'b0 ^ POL`,
// so the POL=1 rail is a flip-flop that resets to 1, and the only
// asynchronous flip-flop dfflibmap will take from sg13g2 is
// sg13g2_dfrbpq, which resets to 0. (The library's one set-capable
// cell, sg13g2_sdfbbp_1, is a scan flop carrying SET_B, RESET_B, SCD
// and SCE; dfflibmap does not use it and prints `unmapped dff cell:
// $_DFF_PN1_`.) It therefore builds the reset-to-1 flop by inverting D
// and Q around a reset-to-0 one, those two inverters land next to this
// module's own `d ^ POL` and `bits ^ POL`, and abc folds each pair to a
// buffer. Measured in the sign-off netlist
// hw/openlane/pilot_ihp/runs/signoff-6x2/final/nl/ [fact]:
//
//   u_ohv_a   1 x sg13g2_dfrbpq_1
//   u_ohv_b   1 x sg13g2_dfrbpq_1, 2 x sg13g2_buf_1
//
// no inverter in either and both storing the flag in true polarity. The
// other two copies of this module land the same way -- u_rdv_a/b in
// each queue instance, u_op_a/b in lif_core, the last pair carrying the
// enable mux2 as well.
//
// That erasure is safe here and it is not a third defence. dfflibmap
// runs after the last pass that could merge anything: LibreLane's
// deferred_flatten performs no optimisation after mapping, which is why
// the measurement above comes out at 1296 either way. But it does mean
// the SHIPPED netlist carries no structural difference between the two
// rails, so a flow that ran a merge pass after technology mapping would
// find two identical dfrbpq cells and only `keep`, keep_hierarchy and
// the netlist census would be standing there. Do not read the two
// flip-flops in the netlist as evidence that POL worked; the
// attribute-stripped synthesis is that evidence, and the netlist census
// in sw/tests/test_synthesis_guards.py is what would catch the day it
// stops being true.
//
// No portable RTL avoids this at one bit. A rail storing the complement
// of a flag whose safe value is 0 must reset to 1, there being no other
// storage function over one variable to choose (section 8.2), so the
// reset-to-1 flop and dfflibmap's inversion of it are both forced.
// Moving the read-side XOR out to the consumer does not help: the
// inverters dfflibmap adds sit on the same two combinational cones and
// fold against the consumer's just as they fold against this module's.
// docs/33-rail-transform.md records the full measurement.
//
// The port presents `bits ^ POL`, so both rails read in true polarity
// and a reader compares them for EQUALITY. A debugger reading
// u_ohv_b.bits in an RTL simulation sees the complement of the flag, by
// design; in the mapped netlist there is nothing left to see, per the
// paragraph above.
//
// Two rails DETECT and do not correct: the consumer is responsible for
// choosing the safe interpretation of a disagreement and for reporting
// it. hw/rtl/pilot_top.v drops the held event and latches
// sticky_errcfg.
//
// No enable port. The caller drives the hold into d, so both rails are
// rewritten every cycle and a disagreement is exactly one cycle wide
// from any state at all -- which is what lets the consumer's safe
// reading become the stored one, and what keeps the rails out of the
// inductive invariants of the proofs over the other two copies of this
// module (hw/rtl/aer_fifo.v, hw/rtl/lif_core.v).
(* keep_hierarchy *)
module pilot_flag_rail #(
    parameter POL = 1'b0              // per-rail storage polarity
) (
    input  wire clk,
    input  wire rst_n,
    input  wire d,                    // next value, true polarity
    output wire q                     // stored value, true polarity
);
    (* keep *) reg bits;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) bits <= 1'b0 ^ POL;
        else        bits <= d ^ POL;
    end

    assign q = bits ^ POL;
endmodule

// =====================================================================
// pilot_cfg_bank: one physical replica of the configuration TMR domain
// =====================================================================
//
// One instance per replica. The reason this is a module at all, rather
// than a reg vector in pilot_top, is header section 9: three identical
// flip-flop banks written from the same expression are one bank after
// yosys opt_merge, and the voter above them then votes three copies of
// the same corrupted value.
//
// Two independent defences live here and neither is trusted alone:
//
//   keep_hierarchy   `flatten` skips this module, and `opt_merge` does
//                    not merge instances of user-defined modules unless
//                    it is invoked with -share_all. Flow-portable across
//                    the LibreLane/yosys ASIC flow and synth_ecp5, both
//                    of which use the same `flatten` pass; NOT portable
//                    to a front end that does not read yosys attributes,
//                    which is why the storage transform below exists.
//   POL + MIX        the per-replica storage TRANSFORM. Each bank stores
//                    a different function of the configuration word, so
//                    no two banks have a flip-flop with the same
//                    (D, EN, reset) signature and structural hashing has
//                    nothing to match even with the hierarchy gone.
//                    Plain Verilog-2005; depends on no attribute.
//
// The transform, and why it is what it is. What opt_merge hashes is the
// stored FUNCTION, so the question is how many distinct functions of the
// configuration word the three banks present:
//
//   POL alone gives two. A storage bit has exactly two polarities, x_i
//   and ~x_i, so with three replicas one of them always collides
//   bit-for-bit with another. Measured under a forced flatten: 1,100
//   flip-flops, replica C entirely gone [fact]. No choice of POL
//   constant improves this, and a constant XOR mask is the same
//   mechanism under another name -- a per-bit polarity choice -- so it
//   does not either.
//
//   A per-replica bit ROTATION does not help, which is worth stating
//   because it looks like it should. Structural hashing is indifferent
//   to bit position: rotating relabels which physical flip-flop holds
//   which value bit but leaves the SET of stored functions identical, so
//   the rotated bank hashes into the unrotated one flop for flop.
//   Measured, replica C rotated by 7 with POL = 0, forced flatten:
//   1,100 flip-flops -- exactly the polarity result [fact].
//
//   MIX = 1 gives a third function by making every stored bit an XOR of
//   TWO OR THREE distinct configuration bits. Nothing of that form can
//   equal x_i or ~x_i for any i, so replica C is provably
//   non-collidable against A and B rather than measured to be. The map
//   is two unit-triangular XOR layers over GF(2) -- the low half absorbs
//   the high half, then the high half absorbs the mixed low half through
//   a rotation -- which is invertible by construction (a product of two
//   unit-triangular matrices) and whose inverse is the same two layers
//   run backwards. One XOR per bit each way, no adders, no state.
//   Measured, forced flatten: 1,155 flip-flops, no loss at all [fact].
//
// A note on the objection an earlier revision of this header raised
// against exactly this construction -- that mixing turns a single upset
// into a multi-bit error and so defeats the voter. It does turn one
// upset into two or three wrong bits at q, and against a SINGLE fault
// that is free: they are all in ONE replica, which is precisely the
// failure TMR masks. A bitwise majority over three banks corrects every
// bit on which a single replica disagrees, however many bits that is.
// The objection confused a multi-bit error inside one replica with a
// multi-replica error.
//
// What it does cost, stated rather than glossed:
//   - against a DOUBLE fault, two upsets in different replicas are
//     uncorrectable only if they land on the same bit of the voted
//     word, and widening replica C's error from one bit to about three
//     raises that coincidence for a (C, A) or (C, B) pair by about the
//     same factor -- order 3/55 instead of 1/55 [estimate on the
//     factor; the widening itself is fact]. It buys the third replica
//     existing at all, which is a first-order effect traded against a
//     second-order one.
//   - replica C alone can no longer be read out bit-for-bit by a
//     debugger. hw/tb/test_fi_campaign.py deposits into u_cfg_c.bits
//     and its comment on bit positions being preserved by the storage
//     transform is true of A and B and no longer true of C; the
//     campaign still classifies CORRECTED, because the voter masks the
//     whole replica.
//   - 1,490 um2 on sg13g2, +1.06 % (section 9 cost table).
//
// keep on `bits` is a third, weakest layer: measured on this design it
// does NOT stop the merge on its own (it preserves the wire name while
// the storage still disappears), so it is here only to stop opt_clean,
// never as evidence that the bank survived. The evidence is the
// flip-flop count in sw/tests/test_synthesis_guards.py, which now
// asserts the forced-flatten count as well as the intact one.
//
// The stored image is `enc(value) ^ POL` and the port presents
// `dec(bits ^ POL)`, so every user of q sees the true configuration
// value and only the physical cells differ. A debugger reading
// u_cfg_b.bits sees the complement of the configuration and
// u_cfg_c.bits sees its mixed image, both by design.
(* keep_hierarchy *)
module pilot_cfg_bank #(
    parameter integer W       = 55,   // <= 64, guarded at the instance
    parameter [63:0]  RST_VAL = 64'd0,
    parameter [63:0]  POL     = 64'd0,
    parameter integer MIX     = 0     // 0 = polarity only, 1 = + XOR mix
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [W-1:0] wr_en,   // per-bit write enable, already qualified
    input  wire [W-1:0] wr_d,    // per-bit write data, true polarity
    output wire [W-1:0] q        // stored value, true polarity
);
    // Split point of the two XOR layers. W >= 4 keeps both halves at
    // least two bits wide; TMR_W is 55, so LO = 27 and HI = 28.
    localparam integer LO = W / 2;
    localparam integer HI = W - LO;

    // enc: true value -> stored image. Layer 1 makes every low bit
    // `v[i] ^ v[LO+i]` (weight 2). Layer 2 makes every high bit
    // `v[LO+i] ^ enc_lo[(i+1) % LO]` (weight 3, and the rotation by one
    // is what stops the layer-2 term cancelling the bit's own value).
    // No output row has weight 1, which is the whole property.
    function [W-1:0] cfg_enc(input [W-1:0] v);
        reg [W-1:0] t;
        integer i;
        begin
            t = v;
            for (i = 0; i < LO; i = i + 1)
                t[i] = v[i] ^ v[LO + i];
            for (i = 0; i < HI; i = i + 1)
                t[LO + i] = v[LO + i] ^ t[(i + 1) % LO];
            cfg_enc = t;
        end
    endfunction

    // dec: stored image -> true value. The same two layers in reverse.
    // Layer 2 never touched the low half, so c[(i+1) % LO] below is
    // still the layer-1 output that enc used.
    function [W-1:0] cfg_dec(input [W-1:0] c);
        reg [W-1:0] t;
        integer i;
        begin
            t = c;
            for (i = 0; i < HI; i = i + 1)
                t[LO + i] = c[LO + i] ^ c[(i + 1) % LO];
            for (i = 0; i < LO; i = i + 1)
                t[i] = c[i] ^ t[LO + i];
            cfg_dec = t;
        end
    endfunction

    (* keep *) reg [W-1:0] bits;

    generate
    if (MIX == 0) begin : g_polarity
        // Polarity-only replica. Left byte-for-byte as it was: yosys
        // folds the per-bit hold into an enable flip-flop and the bank
        // costs W flip-flops and nothing else.
        integer i;
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n)
                bits <= RST_VAL[W-1:0] ^ POL[W-1:0];
            else
                for (i = 0; i < W; i = i + 1)
                    if (wr_en[i]) bits[i] <= wr_d[i] ^ POL[i];
        end
        assign q = bits ^ POL[W-1:0];
    end else begin : g_mixed
        // Mixed replica. A stored bit is a function of several value
        // bits, so a partial write has to re-encode the whole word:
        // decode, substitute the written bits, encode again. That makes
        // the hold explicit as a mux instead of a flip-flop enable,
        // which is the cell cost of this defence.
        wire [W-1:0] cur = cfg_dec(bits ^ POL[W-1:0]);
        wire [W-1:0] nxt = (wr_d & wr_en) | (cur & ~wr_en);
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n)
                bits <= cfg_enc(RST_VAL[W-1:0]) ^ POL[W-1:0];
            else
                bits <= cfg_enc(nxt) ^ POL[W-1:0];
        end
        assign q = cur;
    end
    endgenerate
endmodule

`default_nettype wire
