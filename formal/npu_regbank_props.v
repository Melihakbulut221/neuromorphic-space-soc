// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Formal properties for npu_regbank (SymbiYosys harness,
// formal/npu_regbank.sby). Target #6 of docs/09-formal-verification-plan.md
// section B.1: "register file / CSR write-enable logic -- write-enable
// one-hot-or-zero; no write outside decoded address; every architecturally
// read-only bit proven unwritable", method IND k<=2, acceptance "full
// proof" plus the vacuity rule of docs/09 B.1 ("every assert set ships with
// cover obligations; a target with passing asserts but failing covers is
// red").
//
// This file is textually included inside the npu_regbank module body under
// `ifdef FORMAL (end of hw/rtl/npu_regbank.v), so it sees the decode
// signals, the write enables and the register state directly, and it can
// use the generated npu_regs.vh constants. It is invisible to Icarus
// simulation and to synthesis.
//
// Proven by k-induction (mode prove):
//   P1  reset drives the documented values: one clock after rst_n is
//       sampled low, every register holds the RST_* constant of
//       regmap/regmap.yaml, and the read multiplexer returns it.
//   P2  decode integrity: the per-register write enables are one-hot-or-
//       zero, are zero unless a write was accepted at a decoded address,
//       are zero while the configuration lock is engaged, and each one
//       implies its own ADDR_* offset -- no write outside decoded address.
//   P3  no phantom writes: no storage register changes value unless the
//       write enable addressed to it was asserted, or one of the sources
//       documented in the RTL header (W_ADDR auto-increment on the
//       W_DATA_HI commit, ECC_INJ disarm on the exported w_commit strobe
//       that consumes it, the CTRL SC bits self-clearing, the N_DATA
//       hardware load). Written data lands in the addressed register,
//       masked to the declared field width.
//   P4  RO immunity: no write enable is ever decoded at a read-only
//       offset; the identity and version words are constants; the STATUS
//       live bits and EVQ_STAT are pure snapshots of hardware inputs that
//       no bus access can move; FAULT_ADDR moves only on a double-bit
//       event or its own FAULT_CLR bit; the W1C ports hold no state.
//   P5  W1C semantics: a STATUS sticky bit sets only on its own event
//       (sts_evt, which for ERR_CFG includes the two internal
//       configuration violations of C4/C5) and clears only on a STATUS_CLR
//       write-1 to its own position, with the event winning the coincident
//       race (C1 in the RTL header).
//   P6  counter semantics: each fault counter changes only on its event or
//       its FAULT_CLR bit, increments by exactly one, saturates instead of
//       wrapping, clears to 0 on a lone clear and restarts at 1 when the
//       clear races the event.
//   P7  bus response: exactly one response beat per accepted transaction,
//       error exactly on unmapped offsets, read data equal to the
//       multiplexer output at the accepting edge and held otherwise,
//       unmapped reads returning zero, and bus_req_ready low in exactly
//       the cycle after an accepted EVQ_OUT read and high everywhere else.
//   P8  configuration lock and gating: a configuration write while the
//       core is busy changes nothing and latches STATUS.ERR_CFG, and a
//       write to any register outside the locked set still lands. The
//       locked and unlocked sets are restated here from the
//       specification, by generated offset, NOT taken from the design's
//       own sel_cfg_locked / wr_block wires: a property phrased in terms
//       of the design's locked set cannot detect a wrong locked set.
//       en is never asserted while cfg_valid is low, and an enabled core
//       with an out-of-range configuration always reports ERR_CFG.
//   P9  EVQ_OUT read and pop are atomic: no accepted EVQ_OUT read ever
//       receives a queue head that an earlier read already received, so
//       no event is delivered twice and none is destroyed (docs/10
//       section 7.2). Stated over a ghost that tracks whether the
//       presented head has already been handed out, because two distinct
//       events may legitimately carry the same 16-bit word, which makes a
//       plain data-equality property unsound.
//   P10 datapath output ports: P3..P8 assert on the internal r_*
//       registers, which leaves the exported ports -- the only thing the
//       rest of the chip sees -- unchecked. P10 asserts on the ports
//       themselves: the written value reaches the port, the port holds it
//       until the next write or documented hardware source, the bus read
//       path agrees with the port, and cfg_valid is the docs/10 section 6
//       range check over the exported configuration.
//
// Reset is left free after the initial state, so the proof also covers
// reset asserted in the middle of bus traffic.

reg f_past_valid;
initial f_past_valid = 1'b0;
always @(posedge clk)
    f_past_valid <= 1'b1;

// Start in reset so the induction base matches hardware bring-up.
initial assume (!rst_n);

// Convenience mirrors of the packed counter vector.
wire [CNT_W-1:0] f_cnt_sec = r_cnt[CI_SEC*CNT_W +: CNT_W];
wire [CNT_W-1:0] f_cnt_ded = r_cnt[CI_DED*CNT_W +: CNT_W];
wire [CNT_W-1:0] f_cnt_ovf = r_cnt[CI_OVF*CNT_W +: CNT_W];
wire [CNT_W-1:0] f_cnt_oor = r_cnt[CI_OOR*CNT_W +: CNT_W];

// Named mirrors of the expressions the properties sample with $past, so
// that $past is only ever applied to a plain signal.
wire [2:0]  f_live_in       = {hw_evq_out_empty, hw_evq_in_empty, hw_busy};
wire [15:0] f_stat_in       = {hw_evq_out_fill, hw_evq_in_fill};
wire [STS_HI:STS_LO] f_sts_clr = we_status_clr
                               ? bus_req_wdata[STS_HI:STS_LO]
                               : {(STS_HI - STS_LO + 1){1'b0}};
wire        f_set_state_clr = we_ctrl && bus_req_wdata[BIT_CTRL_STATE_CLR];
wire        f_set_soft_rst  = we_ctrl && bus_req_wdata[BIT_CTRL_SOFT_RST];
wire        f_pop_now       = re_evq_out && hw_evq_out_valid;
wire        f_acc_bad       = acc && !dec_hit;
wire        f_ctrl_en_in    = bus_req_wdata[BIT_CTRL_EN];
wire        f_ctrl_scrub_in = bus_req_wdata[BIT_CTRL_SCRUB_EN];
wire [19:0] f_wdata20       = bus_req_wdata[19:0];
wire [15:0] f_wdata16       = bus_req_wdata[15:0];
wire [10:0] f_wdata11       = bus_req_wdata[10:0];
wire [9:0]  f_wdata10       = bus_req_wdata[9:0];
wire [7:0]  f_wdata8        = bus_req_wdata[7:0];
wire [3:0]  f_wdata4        = bus_req_wdata[3:0];
wire [2:0]  f_wdata3        = bus_req_wdata[2:0];
wire [1:0]  f_wdata2        = bus_req_wdata[1:0];
wire        f_wdata_ts      = bus_req_wdata[BIT_CFG_FLAGS_TS_EN];
wire        f_wdata_leak    = bus_req_wdata[BIT_CFG_FLAGS_LEAK_EN];

// Plain aliases of the two halves of the exported weight word, so P10 can
// apply $past to a signal rather than to a part-select.
wire [31:0] f_w_data_lo = w_data[31:0];
wire [31:0] f_w_data_hi = w_data[63:32];

// ---------------------------------------------------------------------
// Reference model of the architectural W_ADDR, written from the register
// description (regmap.yaml: "Weight SRAM word index; auto-increments on
// W_DATA_HI commit") rather than read out of the design. Both views of
// W_ADDR are checked against it: what software reads back, and what the
// exported commit handshake addresses.
// ---------------------------------------------------------------------
reg [31:0] f_waddr;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)             f_waddr <= RST_W_ADDR;
    else if (we_w_addr)     f_waddr <= bus_req_wdata;
    else if (w_commit_now)  f_waddr <= f_waddr + 32'd1;
end

// ---------------------------------------------------------------------
// P9 ghost: has the head the queue is presenting already been handed to a
// read? It is fresh out of reset, fresh again as soon as a pop consumes
// the old head or the queue goes empty, and stale for as long as a read
// has taken it without a pop having been consumed yet.
// ---------------------------------------------------------------------
reg f_head_fresh;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)                                f_head_fresh <= 1'b1;
    else if (evq_out_pop || !hw_evq_out_valid) f_head_fresh <= 1'b1;
    else if (re_evq_out)                       f_head_fresh <= 1'b0;
end

// ---------------------------------------------------------------------
// The configuration lock, restated from the specification (docs/10
// section 6 plus RTL header C4) by generated offset. These lists are
// deliberately independent of sel_cfg_locked: if the design locked one
// register too few or one too many, P8 has to fail rather than follow.
// ---------------------------------------------------------------------
wire f_spec_locked = (bus_req_addr == ADDR_CFG_NEUR)
                   | (bus_req_addr == ADDR_CFG_AXON)
                   | (bus_req_addr == ADDR_CFG_THRESH)
                   | (bus_req_addr == ADDR_CFG_VRESET)
                   | (bus_req_addr == ADDR_CFG_LEAK)
                   | (bus_req_addr == ADDR_CFG_SYNSHIFT)
                   | (bus_req_addr == ADDR_CFG_REFR)
                   | (bus_req_addr == ADDR_CFG_FLAGS)
                   | (bus_req_addr == ADDR_PASS_TILE_OFF)
                   | (bus_req_addr == ADDR_W_BASE)
                   | (bus_req_addr == ADDR_PASS_ID)
                   | (bus_req_addr == ADDR_W_ADDR)
                   | (bus_req_addr == ADDR_W_DATA_LO)
                   | (bus_req_addr == ADDR_W_DATA_HI)
                   | (bus_req_addr == ADDR_N_ADDR)
                   | (bus_req_addr == ADDR_N_DATA)
                   | (bus_req_addr == ADDR_NODE_ID);

wire f_spec_unlocked = (bus_req_addr == ADDR_CTRL)
                     | (bus_req_addr == ADDR_STATUS_CLR)
                     | (bus_req_addr == ADDR_FAULT_CLR)
                     | (bus_req_addr == ADDR_SCRATCH)
                     | (bus_req_addr == ADDR_ECC_INJ)
                     | (bus_req_addr == ADDR_EVQ_IN);

// The specification's busy condition: the core is busy, whether or not
// the one-cycle-late STATUS snapshot of it has caught up (C3, C4).
wire f_spec_busy  = hw_busy || sts_busy;
wire f_lock_hit   = f_spec_busy && acc_wr && f_spec_locked;
wire f_unlock_hit = f_spec_busy && acc_wr && f_spec_unlocked;

// The two configuration-error conditions of docs/10 section 6, likewise
// restated rather than borrowed from the design, so that removing one of
// the design's own event terms is a counterexample and not a vacuity:
//   - a CTRL write that sets EN while the configuration is out of range
//     ("the RTL latches STATUS.ERR_CFG and refuses to start"), and
//   - an enabled core whose configuration is out of range at all, which
//     is the same rule applied to a write that invalidates a running
//     configuration instead of to the write that starts it (C5).
wire f_spec_en_write_bad = acc_wr && (bus_req_addr == ADDR_CTRL)
                        && bus_req_wdata[BIT_CTRL_EN] && !cfg_valid;
wire f_spec_en_bad       = r_ctrl_en && !cfg_valid;

// All per-register write enables in one vector (P2).
wire [22:0] f_we = {we_scratch, we_ctrl, we_status_clr,
                    we_cfg_neur, we_cfg_axon, we_cfg_thresh, we_cfg_vreset,
                    we_cfg_leak, we_cfg_synshift, we_cfg_refr, we_cfg_flags,
                    we_pass_tile_off, we_w_base, we_pass_id,
                    we_w_addr, we_w_data_lo, we_w_data_hi,
                    we_n_addr, we_n_data,
                    we_ecc_inj, we_fault_clr,
                    we_evq_in, we_node_id};

// Every read-only offset of regmap.yaml (P4).
wire f_sel_ro = sel_id | sel_version | sel_status
              | sel_cnt_sec | sel_cnt_ded | sel_cnt_evq_ovf | sel_cnt_axon_oor
              | sel_fault_addr | sel_evq_stat | sel_evq_out;

// ---------------------------------------------------------------------
// P1: reset drives the documented values
//
// Guarded on $past(rst_n) == 0 rather than on the reset level itself, so
// the property holds under both the synchronous and the asynchronous
// modeling of the reset flop. Each assertion compares the read-visible
// composition of a register against the RST_* localparam emitted by
// regmap/generate.py -- the reset values are never re-typed here.
// ---------------------------------------------------------------------

always @(posedge clk) if (f_past_valid && !$past(rst_n)) begin
    assert (r_scratch == RST_SCRATCH);
    assert ({28'd0, r_ctrl_scrub_en, soft_rst, state_clr, r_ctrl_en} == RST_CTRL);
    assert ({25'd0, r_sts_sticky, r_sts_live} == RST_STATUS);
    // C8: these two reset from the parameters, which docs/10 section 6
    // gives as the reset value, not from the generated 512 literal. The
    // literal is cross-checked against the parameter by an elaboration
    // guard in the RTL, so a 512 build still pins both.
    assert (cfg_neur                == NEUR_MAX);
    assert (cfg_axon                == AXON_MAX);
    assert ({16'd0, r_cfg_thresh}   == RST_CFG_THRESH);
    assert ({16'd0, r_cfg_vreset}   == RST_CFG_VRESET);
    assert ({28'd0, r_cfg_leak}     == RST_CFG_LEAK);
    assert ({29'd0, r_cfg_synshift} == RST_CFG_SYNSHIFT);
    assert ({28'd0, r_cfg_refr}     == RST_CFG_REFR);
    assert ({30'd0, r_cfg_flags}    == RST_CFG_FLAGS);
    assert ({22'd0, r_tile_off}     == RST_PASS_TILE_OFF);
    assert (r_w_base                == RST_W_BASE);
    assert ({24'd0, r_pass_id}      == RST_PASS_ID);
    assert (r_w_addr                == RST_W_ADDR);
    assert (r_w_lo                  == RST_W_DATA_LO);
    assert (r_w_hi                  == RST_W_DATA_HI);
    assert (r_n_addr                == RST_N_ADDR);
    assert ({12'd0, r_n_data}       == RST_N_DATA);
    assert (f_cnt_sec == RST_CNT_SEC[CNT_W-1:0]);
    assert (f_cnt_ded == RST_CNT_DED[CNT_W-1:0]);
    assert (f_cnt_ovf == RST_CNT_EVQ_OVF[CNT_W-1:0]);
    assert (f_cnt_oor == RST_CNT_AXON_OOR[CNT_W-1:0]);
    assert (r_fault_addr == RST_FAULT_ADDR);
    assert ({30'd0, ecc_inj_double, ecc_inj_single} == RST_ECC_INJ);
    assert ({16'd0, r_evq_stat} == RST_EVQ_STAT);
    assert ({16'd0, r_evq_in}   == RST_EVQ_IN);
    assert ({28'd0, r_node_id}  == RST_NODE_ID);
    // the bus is idle and no side-effect strobe escapes out of reset
    assert (bus_rsp_valid == 1'b0);
    assert (bus_rsp_error == 1'b0);
    assert (bus_rsp_rdata == 32'h00000000);
    assert (w_commit    == 1'b0);
    assert (n_data_wr   == 1'b0);
    assert (n_data_rd   == 1'b0);
    assert (evq_in_wr   == 1'b0);
    assert (evq_out_pop == 1'b0);
    assert (fault_clr   == 5'b00000);
    assert (state_clr   == 1'b0);
    assert (soft_rst    == 1'b0);
    // the exported commit index and the bus both start at RST_W_ADDR, and
    // no wait state is left pending out of reset
    assert (w_addr        == RST_W_ADDR);
    assert (bus_req_ready == 1'b1);
end

// ---------------------------------------------------------------------
// P2: decode integrity -- one-hot-or-zero, and no write outside the
// decoded address (docs/09 B.1 target #6)
// ---------------------------------------------------------------------

always @(*) begin
    assert ((f_we & (f_we - 23'd1)) == 23'd0);   // at most one write enable
    if (!acc_wr)              assert (f_we == 23'd0);
    if (acc_wr && !dec_hit)   assert (f_we == 23'd0);
    if (wr_block)             assert (f_we == 23'd0);
    if (f_we != 23'd0)        assert (acc_wr && dec_hit);
    // each enable belongs to its own generated offset
    if (we_scratch)       assert (bus_req_addr == ADDR_SCRATCH);
    if (we_ctrl)          assert (bus_req_addr == ADDR_CTRL);
    if (we_status_clr)    assert (bus_req_addr == ADDR_STATUS_CLR);
    if (we_cfg_neur)      assert (bus_req_addr == ADDR_CFG_NEUR);
    if (we_cfg_axon)      assert (bus_req_addr == ADDR_CFG_AXON);
    if (we_cfg_thresh)    assert (bus_req_addr == ADDR_CFG_THRESH);
    if (we_cfg_vreset)    assert (bus_req_addr == ADDR_CFG_VRESET);
    if (we_cfg_leak)      assert (bus_req_addr == ADDR_CFG_LEAK);
    if (we_cfg_synshift)  assert (bus_req_addr == ADDR_CFG_SYNSHIFT);
    if (we_cfg_refr)      assert (bus_req_addr == ADDR_CFG_REFR);
    if (we_cfg_flags)     assert (bus_req_addr == ADDR_CFG_FLAGS);
    if (we_pass_tile_off) assert (bus_req_addr == ADDR_PASS_TILE_OFF);
    if (we_w_base)        assert (bus_req_addr == ADDR_W_BASE);
    if (we_pass_id)       assert (bus_req_addr == ADDR_PASS_ID);
    if (we_w_addr)        assert (bus_req_addr == ADDR_W_ADDR);
    if (we_w_data_lo)     assert (bus_req_addr == ADDR_W_DATA_LO);
    if (we_w_data_hi)     assert (bus_req_addr == ADDR_W_DATA_HI);
    if (we_n_addr)        assert (bus_req_addr == ADDR_N_ADDR);
    if (we_n_data)        assert (bus_req_addr == ADDR_N_DATA);
    if (we_ecc_inj)       assert (bus_req_addr == ADDR_ECC_INJ);
    if (we_fault_clr)     assert (bus_req_addr == ADDR_FAULT_CLR);
    if (we_evq_in)        assert (bus_req_addr == ADDR_EVQ_IN);
    if (we_node_id)       assert (bus_req_addr == ADDR_NODE_ID);
end

// ---------------------------------------------------------------------
// P3: no phantom writes, and the addressed write lands
// ---------------------------------------------------------------------

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // --- registers whose only source is their own write enable ---
    if (!$past(we_scratch))      assert (r_scratch     == $past(r_scratch));
    if (!$past(we_ctrl))         assert (r_ctrl_en     == $past(r_ctrl_en));
    if (!$past(we_ctrl))         assert (r_ctrl_scrub_en == $past(r_ctrl_scrub_en));
    if (!$past(we_cfg_neur))     assert (r_cfg_neur    == $past(r_cfg_neur));
    if (!$past(we_cfg_axon))     assert (r_cfg_axon    == $past(r_cfg_axon));
    if (!$past(we_cfg_thresh))   assert (r_cfg_thresh  == $past(r_cfg_thresh));
    if (!$past(we_cfg_vreset))   assert (r_cfg_vreset  == $past(r_cfg_vreset));
    if (!$past(we_cfg_leak))     assert (r_cfg_leak    == $past(r_cfg_leak));
    if (!$past(we_cfg_synshift)) assert (r_cfg_synshift == $past(r_cfg_synshift));
    if (!$past(we_cfg_refr))     assert (r_cfg_refr    == $past(r_cfg_refr));
    if (!$past(we_cfg_flags))    assert (r_cfg_flags   == $past(r_cfg_flags));
    if (!$past(we_pass_tile_off)) assert (r_tile_off   == $past(r_tile_off));
    if (!$past(we_w_base))       assert (r_w_base      == $past(r_w_base));
    if (!$past(we_pass_id))      assert (r_pass_id     == $past(r_pass_id));
    if (!$past(we_w_data_lo))    assert (r_w_lo        == $past(r_w_lo));
    if (!$past(we_w_data_hi))    assert (r_w_hi        == $past(r_w_hi));
    if (!$past(we_n_addr))       assert (r_n_addr      == $past(r_n_addr));
    if (!$past(we_evq_in))       assert (r_evq_in      == $past(r_evq_in));
    if (!$past(we_node_id))      assert (r_node_id     == $past(r_node_id));

    // --- registers with one extra documented source ---
    // W_ADDR: own write or the W_DATA_HI commit auto-increment (C6)
    if (!$past(we_w_addr) && !$past(w_commit_now))
        assert (r_w_addr == $past(r_w_addr));
    if ($past(w_commit_now) && !$past(we_w_addr))
        assert (r_w_addr == $past(r_w_addr) + 32'd1);
    // N_DATA: own write (which wins) or the datapath load
    if (!$past(we_n_data) && !$past(n_data_ld))
        assert (r_n_data == $past(r_n_data));
    if ($past(we_n_data))
        assert (r_n_data == $past(f_wdata20));
    if (!$past(we_n_data) && $past(n_data_ld))
        assert (r_n_data == $past(n_data_hw));
    // ECC_INJ arm bits: own write, or disarmed by the exported w_commit
    // strobe that consumes them (C7). Disarming on w_commit_now instead --
    // one cycle earlier, at the accepting edge -- would leave no cycle in
    // which an armed hook and the commit it corrupts are both visible,
    // which is what makes the docs/10 section 11.2 hook dead silicon.
    if (!$past(we_ecc_inj) && !$past(w_commit)) begin
        assert (ecc_inj_single == $past(ecc_inj_single));
        assert (ecc_inj_double == $past(ecc_inj_double));
    end
    if (!$past(we_ecc_inj) && $past(w_commit)) begin
        assert (!ecc_inj_single);
        assert (!ecc_inj_double);
    end
    // The hook is usable: an arm is only ever taken down by a cycle in
    // which the exported w_commit strobe was asserted with that arm still
    // standing. Under the old timing the arm fell one cycle before
    // w_commit, so no consumer could ever see the two together and the
    // injection path was dead; that failure shows up right here.
    if (!$past(we_ecc_inj) && $past(ecc_inj_single) && !ecc_inj_single)
        assert ($past(w_commit));
    if (!$past(we_ecc_inj) && $past(ecc_inj_double) && !ecc_inj_double)
        assert ($past(w_commit));
    // CTRL self-clearing bits are exactly one cycle wide and never spurious
    assert (state_clr == $past(f_set_state_clr));
    assert (soft_rst  == $past(f_set_soft_rst));

    // --- the addressed write lands, masked to the declared field width ---
    if ($past(we_scratch))      assert (r_scratch     == $past(bus_req_wdata));
    if ($past(we_ctrl)) begin
        assert (r_ctrl_en       == $past(f_ctrl_en_in));
        assert (r_ctrl_scrub_en == $past(f_ctrl_scrub_in));
    end
    if ($past(we_cfg_neur))     assert (r_cfg_neur    == $past(f_wdata11));
    if ($past(we_cfg_axon))     assert (r_cfg_axon    == $past(f_wdata11));
    if ($past(we_cfg_thresh))   assert (r_cfg_thresh  == $past(f_wdata16));
    if ($past(we_cfg_vreset))   assert (r_cfg_vreset  == $past(f_wdata16));
    if ($past(we_cfg_leak))     assert (r_cfg_leak    == $past(f_wdata4));
    if ($past(we_cfg_synshift)) assert (r_cfg_synshift == $past(f_wdata3));
    if ($past(we_cfg_refr))     assert (r_cfg_refr    == $past(f_wdata4));
    if ($past(we_cfg_flags))    assert (r_cfg_flags   == $past(f_wdata2));
    if ($past(we_pass_tile_off)) assert (r_tile_off   == $past(f_wdata10));
    if ($past(we_w_base))       assert (r_w_base      == $past(bus_req_wdata));
    if ($past(we_pass_id))      assert (r_pass_id     == $past(f_wdata8));
    if ($past(we_w_addr))       assert (r_w_addr      == $past(bus_req_wdata));
    if ($past(we_w_data_lo))    assert (r_w_lo        == $past(bus_req_wdata));
    if ($past(we_w_data_hi))    assert (r_w_hi        == $past(bus_req_wdata));
    if ($past(we_n_addr))       assert (r_n_addr      == $past(bus_req_wdata));
    if ($past(we_evq_in))       assert (r_evq_in      == $past(f_wdata16));
    if ($past(we_node_id))      assert (r_node_id     == $past(f_wdata4));

    // --- side-effect strobes fire only for their own accepted access ---
    assert (w_commit    == $past(we_w_data_hi));
    assert (n_data_wr   == $past(we_n_data));
    assert (n_data_rd   == $past(re_n_data));
    assert (evq_in_wr   == $past(we_evq_in));
    assert (evq_out_pop == $past(f_pop_now));
    if (!$past(we_fault_clr)) assert (fault_clr == 5'b00000);
end

// ---------------------------------------------------------------------
// P4: read-only immunity -- every architecturally read-only bit is
// unwritable, and the constants are constant
// ---------------------------------------------------------------------

always @(*) begin
    if (f_sel_ro) assert (f_we == 23'd0);        // no write path exists
    if (sel_id)      assert (rd_next == RST_ID);
    if (sel_version) assert (rd_next == RST_VERSION);
    // the W1C ports hold no state: they always read as zero
    if (sel_status_clr) assert (rd_next == 32'h00000000);
    if (sel_fault_clr)  assert (rd_next == 32'h00000000);
    // the write-only registers never expose their contents
    if (sel_w_data_lo) assert (rd_next == 32'h00000000);
    if (sel_w_data_hi) assert (rd_next == 32'h00000000);
    if (sel_ecc_inj)   assert (rd_next == 32'h00000000);
    if (sel_evq_in)    assert (rd_next == 32'h00000000);
end

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // STATUS live bits and EVQ_STAT are pure snapshots of hardware inputs:
    // no bus access of any kind can move them
    assert (r_sts_live == $past(f_live_in));
    assert (r_evq_stat == $past(f_stat_in));
    // FAULT_ADDR moves only on a double-bit event or its clear bit, whose
    // position comes from regmap.yaml through BIT_FAULT_CLR_FAULT_ADDR
    if (!$past(hw_ded) && !$past(fclr[CI_ADDR]))
        assert (r_fault_addr == $past(r_fault_addr));
    if ($past(hw_ded))
        assert (r_fault_addr == $past(hw_fault_addr));   // hardware wins
    if (!$past(hw_ded) && $past(fclr[CI_ADDR]))
        assert (r_fault_addr == 32'h00000000);
end

// ---------------------------------------------------------------------
// P5: W1C semantics on the STATUS sticky bits (hardware wins, C1)
// ---------------------------------------------------------------------

// One sticky bit: no change without its event or its clear-1; the event
// always sets it; a clear-1 clears it only when the event is absent.
`define F_W1C_PROPS(B)                                                      \
    if (!$past(sts_evt[B]) && !$past(f_sts_clr[B]))                         \
        assert (r_sts_sticky[B] == $past(r_sts_sticky[B]));                 \
    if ($past(sts_evt[B]))  assert (r_sts_sticky[B]);                       \
    if (!$past(sts_evt[B]) && $past(f_sts_clr[B]))                          \
        assert (!r_sts_sticky[B]);

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    `F_W1C_PROPS(BIT_STATUS_SYNC_DONE)
    `F_W1C_PROPS(BIT_STATUS_ERR_CFG)
    `F_W1C_PROPS(BIT_STATUS_DED_SEEN)
    `F_W1C_PROPS(BIT_STATUS_OVF_SEEN)
end

// ---------------------------------------------------------------------
// P6: fault counter semantics (increment, saturate, clear, race)
// ---------------------------------------------------------------------

`define F_CNT_PROPS(CNT, EVT, CLR)                                          \
    if (!$past(EVT) && !$past(CLR)) assert (CNT == $past(CNT));             \
    if ($past(EVT) && !$past(CLR))                                          \
        assert (CNT == (($past(CNT) == CNT_MAX) ? CNT_MAX                   \
                                                : $past(CNT) + CNT_ONE));   \
    if (!$past(EVT) && $past(CLR)) assert (CNT == CNT_ZERO);                \
    if ($past(EVT) && $past(CLR))  assert (CNT == CNT_ONE);                 \
    if ($past(CNT) == CNT_MAX && !$past(CLR)) assert (CNT == CNT_MAX);

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    `F_CNT_PROPS(f_cnt_sec, cnt_evt[CI_SEC], fclr[CI_SEC])
    `F_CNT_PROPS(f_cnt_ded, cnt_evt[CI_DED], fclr[CI_DED])
    `F_CNT_PROPS(f_cnt_ovf, cnt_evt[CI_OVF], fclr[CI_OVF])
    `F_CNT_PROPS(f_cnt_oor, cnt_evt[CI_OOR], fclr[CI_OOR])
end

// ---------------------------------------------------------------------
// P7: bus response channel
// ---------------------------------------------------------------------

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    assert (bus_rsp_valid == $past(acc));
    assert (bus_rsp_error == $past(f_acc_bad));
    if ($past(acc_rd))  assert (bus_rsp_rdata == $past(rd_next));
    if (!$past(acc_rd)) assert (bus_rsp_rdata == $past(bus_rsp_rdata));
    // an unmapped read is flagged and reads as zero, and changes nothing
    if ($past(acc_rd) && !$past(dec_hit)) begin
        assert (bus_rsp_rdata == 32'h00000000);
        assert (bus_rsp_error);
    end
    // The only wait state: exactly the cycle after an accepted EVQ_OUT
    // read, and only then. Stated in both directions so neither a missing
    // stall (which would let a second read take the same head, P9) nor a
    // spurious one (which would break the documented bus timing) passes.
    if ($past(re_evq_out)) assert (!bus_req_ready);
    else                   assert (bus_req_ready);
end

// ---------------------------------------------------------------------
// P8: configuration lock and start gating (C4, C5)
//
// Stated against the specification's locked set (f_spec_locked /
// f_spec_unlocked above), not against the design's sel_cfg_locked, and
// against the specification's busy condition (the core is busy), not
// against the one-cycle-late STATUS snapshot the design used to key off.
// ---------------------------------------------------------------------

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // a configuration write while the core is busy latches ERR_CFG
    if ($past(f_lock_hit)) assert (r_sts_sticky[BIT_STATUS_ERR_CFG]);
    // enabling the core with an out-of-range configuration latches ERR_CFG
    if ($past(f_spec_en_write_bad)) assert (r_sts_sticky[BIT_STATUS_ERR_CFG]);
    // and so does letting a configuration write invalidate a running one:
    // CTRL.EN reading 1 with en gated off must never be silent (C5)
    if ($past(f_spec_en_bad)) assert (r_sts_sticky[BIT_STATUS_ERR_CFG]);
end

always @(*) begin
    if (!cfg_valid) assert (!en);          // "refuses to start"
    // every one of the 17 locked registers refuses its write while busy
    if (f_lock_hit)   assert (f_we == 23'd0);
    // ... and every one of the 6 unlocked registers still takes its write,
    // so a locked set larger than the specified one fails here
    if (f_unlock_hit) assert (f_we != 23'd0);
    // ... and the two lists together cover every writable register, so a
    // register that is in neither cannot slip through unchecked
    if (f_we != 23'd0) assert (f_spec_locked ^ f_spec_unlocked);
end

// ---------------------------------------------------------------------
// P9: EVQ_OUT read and pop are atomic (docs/10 section 7.2, C9)
//
// The read returns the head presented at the accepting edge and the pop
// that consumes it is asserted one cycle later, so the block must not
// accept another EVQ_OUT read in between. Two distinct events may carry
// the same 16-bit word, so "the two reads returned different data" is not
// a sound way to say this; f_head_fresh tracks the head itself instead.
// ---------------------------------------------------------------------

always @(posedge clk) if (f_past_valid && rst_n) begin
    // no read is ever handed a head an earlier read already took
    if (re_evq_out && hw_evq_out_valid) assert (f_head_fresh);
    // no read is accepted while the pop it would race is still in flight
    assert (!(re_evq_out && evq_out_pop));
    // helper invariant: a head can only be stale inside the wait state the
    // read that took it inserted, which is what makes P9 inductive
    if (!f_head_fresh) assert (evq_out_stall);
end

// ---------------------------------------------------------------------
// P10: the exported datapath ports
//
// Every assertion here names a port, never an r_* register. Three
// obligations per port: the value software wrote reaches it on the cycle
// after the accepting edge, masked to the declared field width; it holds
// that value until the next write to its register or its documented
// hardware source; and, where the register is readable, the bus read path
// returns exactly what the port carries.
// ---------------------------------------------------------------------

`define F_PORT(PORT, WE, IN)                                                \
    if ($past(WE))  assert (PORT == $past(IN));                             \
    if (!$past(WE)) assert (PORT == $past(PORT));

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    `F_PORT(scrub_en,      we_ctrl,          f_ctrl_scrub_in)
    `F_PORT(cfg_neur,      we_cfg_neur,      f_wdata11)
    `F_PORT(cfg_axon,      we_cfg_axon,      f_wdata11)
    `F_PORT(cfg_thresh,    we_cfg_thresh,    f_wdata16)
    `F_PORT(cfg_vreset,    we_cfg_vreset,    f_wdata16)
    `F_PORT(cfg_leak,      we_cfg_leak,      f_wdata4)
    `F_PORT(cfg_synshift,  we_cfg_synshift,  f_wdata3)
    `F_PORT(cfg_refr,      we_cfg_refr,      f_wdata4)
    `F_PORT(cfg_ts_en,     we_cfg_flags,     f_wdata_ts)
    `F_PORT(cfg_leak_en,   we_cfg_flags,     f_wdata_leak)
    `F_PORT(pass_tile_off, we_pass_tile_off, f_wdata10)
    `F_PORT(w_base,        we_w_base,        bus_req_wdata)
    `F_PORT(pass_id,       we_pass_id,       f_wdata8)
    `F_PORT(n_addr,        we_n_addr,        bus_req_wdata)
    `F_PORT(evq_in_data,   we_evq_in,        f_wdata16)
    `F_PORT(node_id,       we_node_id,       f_wdata4)
    `F_PORT(f_w_data_lo,   we_w_data_lo,     bus_req_wdata)
    `F_PORT(f_w_data_hi,   we_w_data_hi,     bus_req_wdata)

    // N_DATA has the documented second source, and the bus write wins
    if ($past(we_n_data))                       assert (n_data == $past(f_wdata20));
    if (!$past(we_n_data) && $past(n_data_ld))  assert (n_data == $past(n_data_hw));
    if (!$past(we_n_data) && !$past(n_data_ld)) assert (n_data == $past(n_data));

    // The weight load port (C6). The reference model f_waddr is the
    // architectural W_ADDR; the exported index is its value at the
    // accepting edge, i.e. the word this commit carries, not the
    // already-incremented one, and it holds until the next commit.
    assert (f_waddr == r_w_addr);                  // model tracks the design
    if (w_commit)             assert (w_addr == $past(f_waddr));
    if (!$past(w_commit_now)) assert (w_addr == $past(w_addr));
end

always @(*) begin
    // the port and the bus read path are two views of one register
    if (sel_ctrl) begin
        assert (rd_next[BIT_CTRL_SCRUB_EN] == scrub_en);
        assert (en == (rd_next[BIT_CTRL_EN] && cfg_valid));
    end
    if (sel_cfg_neur)      assert (rd_next == {21'd0, cfg_neur});
    if (sel_cfg_axon)      assert (rd_next == {21'd0, cfg_axon});
    if (sel_cfg_thresh)    assert (rd_next == {16'd0, cfg_thresh});
    if (sel_cfg_vreset)    assert (rd_next == {16'd0, cfg_vreset});
    if (sel_cfg_leak)      assert (rd_next == {28'd0, cfg_leak});
    if (sel_cfg_synshift)  assert (rd_next == {29'd0, cfg_synshift});
    if (sel_cfg_refr)      assert (rd_next == {28'd0, cfg_refr});
    if (sel_cfg_flags)     assert (rd_next == {30'd0, cfg_leak_en, cfg_ts_en});
    if (sel_pass_tile_off) assert (rd_next == {22'd0, pass_tile_off});
    if (sel_w_base)        assert (rd_next == w_base);
    if (sel_pass_id)       assert (rd_next == {24'd0, pass_id});
    if (sel_n_addr)        assert (rd_next == n_addr);
    if (sel_n_data)        assert (rd_next == {12'd0, n_data});
    if (sel_node_id)       assert (rd_next == {28'd0, node_id});
    if (sel_w_addr)        assert (rd_next == f_waddr);
    // cfg_valid restated over the exported configuration, from the
    // docs/10 section 6 range table (C5): a port wired to the wrong
    // register would make the two disagree.
    assert (cfg_valid == ((cfg_thresh != 16'h0000) && (cfg_thresh[15] == 1'b0)
                          && ($signed(cfg_vreset) < $signed(cfg_thresh))
                          && (cfg_neur != 11'd0) && (cfg_neur <= NEUR_MAX)
                          && (cfg_axon != 11'd0) && (cfg_axon <= AXON_MAX)));
end

// ---------------------------------------------------------------------
// Reachability covers: every proven behavior is demonstrably reachable
// (docs/09 B.1 vacuity rule). Run by the cover task, which parameterizes
// CNT_W down so that counter saturation is reachable within the depth.
// ---------------------------------------------------------------------

always @(posedge clk) if (f_past_valid && rst_n) begin
    // P2/P3: a decoded write changes its register
    cover ($past(we_scratch) && r_scratch != $past(r_scratch));
    cover ($past(we_cfg_thresh) && r_cfg_thresh != $past(r_cfg_thresh));
    // P3: the SC strobes and the commit side effects
    cover (state_clr);
    cover (soft_rst);
    // C6: two commits in a row address consecutive words, and the exported
    // index is the pre-increment one
    cover (w_commit && w_addr == 32'h00000000 && r_w_addr == 32'h00000001);
    cover (w_commit && w_addr == 32'h00000001);
    // C7: the injection hook is usable -- an armed hook and the commit it
    // is supposed to corrupt are visible in the same cycle, and the arm is
    // consumed by that commit
    cover (w_commit && ecc_inj_single);
    cover (w_commit && ecc_inj_double);
    cover ($past(ecc_inj_single) && $past(w_commit) && !ecc_inj_single);
    cover (evq_in_wr);
    cover (evq_out_pop);
    cover (n_data_wr);
    // P4: a write aimed at a read-only offset leaves the value alone
    cover ($past(acc_wr) && $past(sel_status) && !$past(sts_evt[BIT_STATUS_DED_SEEN])
           && r_sts_sticky == $past(r_sts_sticky));
    cover ($past(acc_rd) && $past(sel_id) && bus_rsp_rdata == RST_ID);
    // P5: W1C set by hardware, cleared by write-1, and the race
    cover ($past(hw_ded) && r_sts_sticky[BIT_STATUS_DED_SEEN]);
    cover ($past(r_sts_sticky[BIT_STATUS_DED_SEEN])
           && !r_sts_sticky[BIT_STATUS_DED_SEEN]);
    cover ($past(hw_sync_done) && $past(f_sts_clr[BIT_STATUS_SYNC_DONE])
           && r_sts_sticky[BIT_STATUS_SYNC_DONE]);      // hardware wins
    // P6: counter increment, saturation, clear, and the clear/event race
    cover (f_cnt_sec == CNT_ONE + CNT_ONE);
    cover (f_cnt_sec == CNT_MAX);                       // saturation reached
    cover ($past(f_cnt_ded) != CNT_ZERO && f_cnt_ded == CNT_ZERO);
    cover ($past(fclr[CI_OVF]) && $past(cnt_evt[CI_OVF]) && f_cnt_ovf == CNT_ONE);
    cover (r_fault_addr != 32'h00000000);
    // P7: an unmapped access is flagged, and the EVQ_OUT wait state is
    // both reachable and one cycle wide
    cover (bus_rsp_valid && bus_rsp_error);
    cover (!bus_req_ready);
    cover ($past(evq_out_stall) && bus_req_ready);      // one cycle wide
    // P8: the lock engages on the rising edge of hw_busy before the STATUS
    // snapshot has caught up, and the core refuses to start on a bad config
    cover ($past(wr_block) && r_sts_sticky[BIT_STATUS_ERR_CFG]);
    cover ($past(f_lock_hit) && $past(hw_busy) && !$past(sts_busy)
           && r_sts_sticky[BIT_STATUS_ERR_CFG]);
    cover ($past(f_spec_en_bad) && r_sts_sticky[BIT_STATUS_ERR_CFG]);
    cover (r_ctrl_en && !cfg_valid && !en);
    cover (en);
    // P9: two EVQ_OUT reads that each get their own head, with the pop of
    // the first consumed in between
    cover ($past(evq_out_pop) && re_evq_out && hw_evq_out_valid);
end

`undef F_CNT_PROPS
`undef F_W1C_PROPS
`undef F_PORT
