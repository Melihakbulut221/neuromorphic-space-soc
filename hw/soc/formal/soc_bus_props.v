// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Formal properties for the system fabric (SymbiYosys harness,
// hw/soc/formal/soc_bus.sby).
//
// WHERE THESE PROPERTIES COME FROM. Two specifications, both written
// before the RTL, and one generated file:
//
//   * The Ibex memory protocol, quoted in full in the header of
//     hw/soc/rtl/soc_bus.v out of
//     ext/ibex/doc/03_reference/load_store_unit.rst. Four rules:
//     req held until gnt; payload free to change after gnt; exactly one
//     rvalid per grant carrying rdata and err; multiple outstanding
//     requests answered in order.
//   * The slave contract S1-S4 and the same-slave restriction, also in
//     that header, which is the specification the rest of the SoC's
//     slaves are written against.
//   * hw/soc/rtl/soc_memmap.vh, generated from regmap/memmap.yaml. The
//     decode properties compare against those constants, so a decoder
//     that drifts from the frozen map fails here. Restating the RTL's
//     own comparison would have proved nothing.
//
// GHOST STATE, NOT THE DESIGN'S STATE. The outstanding counts, the
// per-slave occupancies and the per-master slave locks below are all
// reconstructed from the ports, independently of cnt_i, cnt_d, lock_i,
// lock_d and q_fill. A property that read the design's own counter would
// be satisfied by a fabric that miscounted consistently.
//
// ONE INTERNAL SIGNAL IS REFERENCED: err_rvalid, the response strobe of
// the error slave, which has no port because the error slave is inside
// this module. It is used to complete the occupancy bookkeeping in F5
// and F6. Nothing is DERIVED from it -- the property it takes part in is
// "every response belongs to a request", which is a specification
// statement, and there is no other way to observe a slave that has no
// pins.
//
// AND FOUR MORE AT REQ_REG = 1, WHICH ARE ASSERTED ON AND NOT READ:
// `xfer`, `xfer_tgt`, `xfer_own` and `req_busy`, the design's own
// request-phase boundary. I6 states that the ghost request phase
// reconstructed from the ports below is exactly them. That is the
// opposite of deriving a property from the design: it makes the ghost
// an OBSERVATION of the design rather than a definition, so that F3c,
// F4b, F8 and the covers -- all of which turn on the ghost -- are not
// circular. A fabric that transferred a request the slave had not
// granted, or that pushed the wrong master's ownership, fails I6 and
// not only the properties downstream of it.
//
// WHAT REQ_REG CHANGES IN THIS FILE, in one paragraph. At REQ_REG = 1
// soc_bus.v captures the arbitration's result into a register and hands
// it to the slave a cycle later, so the GRANT and the TRANSFER are no
// longer the same event. Every clause below that was a statement about
// one of them and silently about the other has been split: the
// per-master outstanding counts stay on the grant, the per-slave queues
// move to the transfer, and the difference between the two -- at most
// one request, sitting in the fabric's register -- is carried by the
// ghost `f_fly` and named `f_out_i_slv` / `f_out_d_slv` where an
// invariant needs it. NOTHING IS WEAKENED: at REQ_REG = 0 every line
// below elaborates to the line that was here before the parameter
// existed, `f_fly` folds to a constant zero, and two properties are
// ADDED at REQ_REG = 1 -- I6 above and F3e, which is Ibex protocol rule
// 1 obeyed by this fabric toward its slaves and which the
// combinational request phase does not obey.
//
// WHAT IS NOT PROVEN HERE:
//
//   * Liveness of any kind. Nothing says a request is ever granted or a
//     response ever arrives. F9 is a bounded fairness property under the
//     assumption that all slaves are ready, which is much weaker than
//     "the fabric cannot deadlock".
//   * That responses are IN ORDER. F4 proves each master's outstanding
//     requests are all at one slave and F7 proves responses are not
//     lost, duplicated or delivered to the wrong master. Ordering then
//     follows from the slave contract S3 (a slave answers in order) and
//     is assumed of the slaves rather than proved of them here.
//   * Anything about the number of slaves or their addresses beyond what
//     soc_memmap.vh says. If the map adds a region and the decode below
//     is not extended, F1 still passes -- the new region simply reaches
//     the error slave. The cocotb suite is what checks the map's regions
//     against the fabric's ports, because it can enumerate the generated
//     map and this file cannot.
//   * Reset behaviour beyond the initial state.
//   * That REQ_REG = 1 costs exactly one cycle of latency and no
//     throughput. That is a performance claim, it is not a safety
//     property, and docs/84 measures it on the whole SoC instead.

localparam integer F_ERRSLV = 6;
localparam integer F_NS     = 7;   // six ports plus the error slave

reg f_past_valid;
initial f_past_valid = 1'b0;
always @(posedge clk_i) f_past_valid <= 1'b1;

initial assume (!rst_ni);

// ---------------------------------------------------------------------
// Observations, in terms of ports only
// ---------------------------------------------------------------------
wire        f_gnt     = mi_gnt_o || md_gnt_o;
wire [2:0]  f_tgt_idx = s_req_o[0] ? 3'd0 :
                        s_req_o[1] ? 3'd1 :
                        s_req_o[2] ? 3'd2 :
                        s_req_o[3] ? 3'd3 :
                        s_req_o[4] ? 3'd4 :
                        s_req_o[5] ? 3'd5 : F_ERRSLV[2:0];

// ---------------------------------------------------------------------
// The request phase, at both settings
// ---------------------------------------------------------------------
//
// AT REQ_REG = 1 THE GRANT AND THE TRANSFER ARE NOT THE SAME CYCLE, and
// every ghost below has to be told which of the two it counts. The rule
// is the design's own, stated in soc_bus.v's REQ_REG section: a
// master's outstanding count turns on the GRANT, because that is when
// the master owns the request, and a slave's queue turns on the
// TRANSFER, because that is when the slave has it.
//
// The transfer is reconstructed FROM THE PORTS. A grant loads the ghost
// register; it unloads when the slave being presented with the request
// answers gnt, or immediately when the target is the error slave --
// which is the one target with no pins, and which f_tgt_idx already
// reports as F_ERRSLV when no slave port is selected. I6 below asserts
// that this reconstruction is the design's own register.
//
// AT REQ_REG = 0 the ghost register is held at zero, `f_take` is
// `f_gnt`, `f_take_i` is `mi_gnt_o`, and every line in this file is the
// line that was here before the parameter existed.
reg f_fly, f_fly_own;

wire f_fly_xfer = f_fly && ((s_req_o == 6'b000000) || |(s_req_o & s_gnt_i));

always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        f_fly     <= 1'b0;
        f_fly_own <= 1'b0;
    end else if (REQ_REG == 0) begin
        f_fly     <= 1'b0;
        f_fly_own <= 1'b0;
    end else if (f_gnt) begin
        f_fly     <= 1'b1;
        f_fly_own <= md_gnt_o;
    end else if (f_fly_xfer) begin
        f_fly     <= 1'b0;
    end
end

wire f_take     = (REQ_REG == 0) ? f_gnt    : f_fly_xfer;
wire f_take_own = (REQ_REG == 0) ? md_gnt_o : f_fly_own;
wire f_take_i   = (REQ_REG == 0) ? mi_gnt_o : (f_fly_xfer && !f_fly_own);
wire f_take_d   = (REQ_REG == 0) ? md_gnt_o : (f_fly_xfer &&  f_fly_own);

// Whether a request is being PRESENTED to a target this cycle, which is
// the only cycle in which s_addr_o means anything. At REQ_REG = 1 the
// register keeps driving the last address after it has been taken, and
// a property that read it then would be reading a stale bus.
wire f_present  = (REQ_REG == 0) ? f_gnt : f_fly;

wire [6:0] f_push = {f_take && (s_req_o == 6'b000000),
                     f_take && s_req_o[5],
                     f_take && s_req_o[4],
                     f_take && s_req_o[3],
                     f_take && s_req_o[2],
                     f_take && s_req_o[1],
                     f_take && s_req_o[0]};
wire [6:0] f_pop  = {err_rvalid, s_rvalid_i};

// ---------------------------------------------------------------------
// Environment: legal masters and legal slaves
// ---------------------------------------------------------------------
//
// Ibex protocol rule 1 on both master ports.
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    if ($past(mi_req_i) && !$past(mi_gnt_o)) begin
        assume (mi_req_i);
        assume (mi_addr_i == $past(mi_addr_i));
    end
    if ($past(md_req_i) && !$past(md_gnt_o)) begin
        assume (md_req_i);
        assume (md_addr_i  == $past(md_addr_i));
        assume (md_we_i    == $past(md_we_i));
        assume (md_be_i    == $past(md_be_i));
        assume (md_wdata_i == $past(md_wdata_i));
    end
end

// ---------------------------------------------------------------------
// Ghost bookkeeping
// ---------------------------------------------------------------------
localparam integer F_QD = 4;      // 2 masters x MAX_OUT

reg [2:0] f_out_i, f_out_d;       // wide enough to SEE an overflow
reg [2:0] f_lock_i, f_lock_d;
reg [3:0] f_occ [0:F_NS-1];       // per-slave occupancy, ditto

integer f_s;
always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        f_out_i  <= 3'd0;
        f_out_d  <= 3'd0;
        f_lock_i <= 3'd0;
        f_lock_d <= 3'd0;
        for (f_s = 0; f_s < F_NS; f_s = f_s + 1) f_occ[f_s] <= 4'd0;
    end else begin
        if (mi_gnt_o && !mi_rvalid_o) f_out_i <= f_out_i + 3'd1;
        if (!mi_gnt_o && mi_rvalid_o) f_out_i <= f_out_i - 3'd1;
        if (md_gnt_o && !md_rvalid_o) f_out_d <= f_out_d + 3'd1;
        if (!md_gnt_o && md_rvalid_o) f_out_d <= f_out_d - 3'd1;
        // The LOCK moves with the request, not with the grant: it
        // names the slave an entry is queued at, and at REQ_REG = 1 a
        // granted request has not reached a slave yet.
        if (f_take_i) f_lock_i <= f_tgt_idx;
        if (f_take_d) f_lock_d <= f_tgt_idx;
        for (f_s = 0; f_s < F_NS; f_s = f_s + 1) begin
            if (f_push[f_s] && !f_pop[f_s]) f_occ[f_s] <= f_occ[f_s] + 4'd1;
            if (!f_push[f_s] && f_pop[f_s]) f_occ[f_s] <= f_occ[f_s] - 4'd1;
        end
    end
end

// Per-master, per-slave occupancy. Needed because F7 and F8 are about
// WHICH master a response belongs to, and the totals above cannot see
// that. A master's response always retires an entry at the slave it is
// locked to, which is what makes these countable from the ports alone
// without reading the design's ownership queues.
reg [2:0] f_occ_i [0:F_NS-1];
reg [2:0] f_occ_d [0:F_NS-1];

always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
        for (f_s = 0; f_s < F_NS; f_s = f_s + 1) begin
            f_occ_i[f_s] <= 3'd0;
            f_occ_d[f_s] <= 3'd0;
        end
    end else begin
        for (f_s = 0; f_s < F_NS; f_s = f_s + 1) begin
            case ({f_take_i && (f_tgt_idx == f_s[2:0]),
                   mi_rvalid_o && (f_lock_i == f_s[2:0])})
                2'b10:   f_occ_i[f_s] <= f_occ_i[f_s] + 3'd1;
                2'b01:   f_occ_i[f_s] <= f_occ_i[f_s] - 3'd1;
                default: ;
            endcase
            case ({f_take_d && (f_tgt_idx == f_s[2:0]),
                   md_rvalid_o && (f_lock_d == f_s[2:0])})
                2'b10:   f_occ_d[f_s] <= f_occ_d[f_s] + 3'd1;
                2'b01:   f_occ_d[f_s] <= f_occ_d[f_s] - 3'd1;
                default: ;
            endcase
        end
    end
end

// THE PART OF A MASTER'S OUTSTANDING COUNT THAT HAS REACHED A SLAVE.
// At REQ_REG = 0 it is all of it, and every clause using it below is
// the clause that read f_out_i directly. At REQ_REG = 1 one granted
// request may still be in the fabric's register: it is counted against
// the master, because the master owns it and MAX_OUT is about the
// master, and it is NOT yet in any slave's queue. Every invariant that
// ties the two sides together needs the second number, and using the
// first is the single most likely way to get this file wrong.
wire [2:0] f_out_i_slv = (REQ_REG == 0) ? f_out_i
                       : (f_out_i - {2'd0, (f_fly && !f_fly_own)});
wire [2:0] f_out_d_slv = (REQ_REG == 0) ? f_out_d
                       : (f_out_d - {2'd0, (f_fly &&  f_fly_own)});

// Slave contract S1/S3, as an assumption on the four external ports: a
// slave does not answer a request it was never given. The error slave is
// internal and gets no such licence -- F5 ASSERTS the same thing of it.
always @(posedge clk_i) if (rst_ni) begin
    if (s_rvalid_i[0]) assume (f_occ[0] != 4'd0);
    if (s_rvalid_i[1]) assume (f_occ[1] != 4'd0);
    if (s_rvalid_i[2]) assume (f_occ[2] != 4'd0);
    if (s_rvalid_i[3]) assume (f_occ[3] != 4'd0);
    if (s_rvalid_i[4]) assume (f_occ[4] != 4'd0);
    if (s_rvalid_i[5]) assume (f_occ[5] != 4'd0);
end

// ---------------------------------------------------------------------
// I1-I5: strengthening invariants
// ---------------------------------------------------------------------
//
// k-induction starts from an arbitrary state, so without these it starts
// from one where the ghost bookkeeping and the design's own counters
// disagree -- a state that is unreachable but not excluded -- and F4, F7,
// F8 and F9 all fail there for reasons that say nothing about the design.
//
// These are the only properties in this file that name the design's own
// state. They are not specification clauses; they say the ghost tracks
// the design, which is the precondition for every specification clause
// below being about the design at all. Each one is also a real check in
// its own right: a fabric that miscounted, or whose broadcast decode
// disagreed with the granted master's own decode, would fail here.
integer f_z;
reg [2:0] f_zeros;
always @(posedge clk_i) if (rst_ni) begin
    // I1. The ghost outstanding counts and the design's agree.
    assert (f_out_i == {1'b0, cnt_i});
    assert (f_out_d == {1'b0, cnt_d});

    // I2. So do the slave locks, while there is anything locked. This is
    //     also the statement that the address broadcast to the slaves
    //     decodes to the same slave the granting master's own address
    //     decoded to.
    if (f_out_i_slv != 3'd0) assert (f_lock_i == lock_i);
    if (f_out_d_slv != 3'd0) assert (f_lock_d == lock_d);

    // I2b. AT REQ_REG = 1 ONLY, and it is the other half of I2 rather
    //      than a weakening of it. The ghost lock is set when a request
    //      REACHES a slave and the design's when it is GRANTED, so in
    //      the cycles a request spends in the fabric's register the two
    //      are about different requests and I2 above excuses them. What
    //      must still hold there is the same statement one step
    //      earlier: the slave the fabric is presenting this request to
    //      is the slave the granting master's own address decoded to.
    //      Without this the excusing antecedent in I2 would be a hole.
    if (REQ_REG != 0 && f_fly && !f_fly_own) assert (f_tgt_idx == lock_i);
    if (REQ_REG != 0 && f_fly &&  f_fly_own) assert (f_tgt_idx == lock_d);

    for (f_s = 0; f_s < F_NS; f_s = f_s + 1) begin
        // I3. Total occupancy is the sum of the two masters' shares.
        assert (f_occ[f_s] == {1'b0, f_occ_i[f_s]} + {1'b0, f_occ_d[f_s]});

        // I4. THE SINGLETON PROPERTY. A master's outstanding requests are
        //     all at the one slave it is locked to and at no other. This
        //     is the same-slave restriction expressed as an invariant
        //     rather than as a check on a grant, and it is what makes F7
        //     true: two slaves cannot both be holding a response for the
        //     same master, so two responses in one cycle cannot collide
        //     on one master's rvalid.
        if (f_s[2:0] == f_lock_i) assert (f_occ_i[f_s] == f_out_i_slv);
        else                      assert (f_occ_i[f_s] == 3'd0);
        if (f_s[2:0] == f_lock_d) assert (f_occ_d[f_s] == f_out_d_slv);
        else                      assert (f_occ_d[f_s] == 3'd0);

        // I5. The design's ownership queue holds exactly the entries the
        //     ghosts count, in the same positions: the number of
        //     instruction-port entries below the write index equals the
        //     ghost's count. Without this the head of the queue -- which
        //     is what steers a response -- is unconstrained under
        //     induction.
        assert (q_fill[f_s] == f_occ[f_s][1:0]);
        f_zeros = 3'd0;
        for (f_z = 0; f_z < 4; f_z = f_z + 1)
            if (({1'b0, f_z[2:0]} < f_occ[f_s]) && !q_owner[f_s][f_z])
                f_zeros = f_zeros + 3'd1;
        assert (f_occ_i[f_s] == f_zeros);
    end

    // I6. THE GHOST REQUEST PHASE IS THE DESIGN'S REQUEST PHASE. The
    //     four signals named here are soc_bus.v's own boundary between
    //     the arbitration and the slaves, and everything above that
    //     turns on `f_take` turns on a reconstruction of them made from
    //     the ports. This is what stops that reconstruction being a
    //     definition: a fabric that handed a request to a slave which
    //     had not granted it, that pushed the wrong master into the
    //     ownership queue, or that held a request the ports say is gone
    //     fails HERE, one step before the properties that would
    //     otherwise have been satisfied by agreeing with it.
    //
    //     At REQ_REG = 0 it is a real check too and a cheap one: the
    //     transfer is `accepted`, and the statement is that `accepted`
    //     is exactly the disjunction of the two grant outputs.
    //     THE ANTECEDENT IS `req_busy || xfer` AND NOT `xfer`, and the
    //     first version of this property was the second. It failed
    //     induction at REQ_REG = 1 and the counterexample is worth
    //     writing down, because it is the shape docs/09 section B.3
    //     warns about rather than a defect: k-induction started in a
    //     state with the fabric's register FULL, the ghost owning it
    //     for the data port and the design owning it for the
    //     instruction port -- a state no reachable trace can produce,
    //     because both are loaded from the same grant, and one no
    //     assertion excluded, because the old antecedent only looked at
    //     the register in the cycle it DRAINS. A hundred idle cycles
    //     later the register drained and the two disagreed.
    //
    //     THE REPAIR IS TO ASSERT IT IN MORE CYCLES AND NOT IN FEWER.
    //     The register's ownership bit is now checked in every cycle
    //     the register is full, which is strictly stronger than the
    //     version that failed and is what makes it inductive: loaded
    //     together, held together, so equal in every cycle it exists.
    //     The RTL was not touched.
    assert (xfer == f_take);
    assert (req_busy == ((REQ_REG != 0) && f_fly));
    if (req_busy || xfer) begin
        assert (xfer_tgt == f_tgt_idx);
        assert (xfer_own == f_take_own);
    end
end

// ---------------------------------------------------------------------
// F1, F2: address decode against the frozen map
// ---------------------------------------------------------------------
always @(posedge clk_i) if (rst_ni) begin
    // F1. At most one slave port is selected. Two selected slaves would
    //     make two copies of one write and two responses for one
    //     request.
    assert (!(s_req_o[0] && s_req_o[1]));
    assert (!(s_req_o[0] && s_req_o[2]));
    assert (!(s_req_o[0] && s_req_o[3]));
    assert (!(s_req_o[0] && s_req_o[4]));
    assert (!(s_req_o[1] && s_req_o[2]));
    assert (!(s_req_o[1] && s_req_o[3]));
    assert (!(s_req_o[1] && s_req_o[4]));
    assert (!(s_req_o[2] && s_req_o[3]));
    assert (!(s_req_o[2] && s_req_o[4]));
    assert (!(s_req_o[3] && s_req_o[4]));
    assert (!(s_req_o[0] && s_req_o[5]));
    assert (!(s_req_o[1] && s_req_o[5]));
    assert (!(s_req_o[2] && s_req_o[5]));
    assert (!(s_req_o[3] && s_req_o[5]));
    assert (!(s_req_o[4] && s_req_o[5]));

    // F2a. A selected slave is the one the frozen map puts the broadcast
    //      address in. Soundness: nothing is routed to the wrong place.
    if (s_req_o[0]) assert ((s_addr_o & SOC_MASK_RAM) == SOC_BASE_RAM);
    if (s_req_o[1]) assert ((s_addr_o & SOC_MASK_ROM) == SOC_BASE_ROM);
    if (s_req_o[2]) assert ((s_addr_o & SOC_MASK_APB) == SOC_BASE_APB);
    if (s_req_o[3]) assert ((s_addr_o & SOC_MASK_PNP) == SOC_BASE_PNP);
    if (s_req_o[4]) assert ((s_addr_o & SOC_MASK_CLINT) == SOC_BASE_CLINT);
    if (s_req_o[5]) assert ((s_addr_o & SOC_MASK_NPU) == SOC_BASE_NPU);

    // F2b. The converse. Completeness: an address the map covers is
    //      never sent to the error slave, and never dropped. Without
    //      this half, a fabric that answered every access with a bus
    //      error would satisfy F2a.
    //
    //      The antecedent is `f_present` and not `f_gnt` because at
    //      REQ_REG = 1 the broadcast bus keeps driving the last request
    //      after that request has been taken, and a stale address is
    //      not an address this fabric is failing to route.
    if (f_present && (s_addr_o & SOC_MASK_RAM) == SOC_BASE_RAM) assert (s_req_o[0]);
    if (f_present && (s_addr_o & SOC_MASK_ROM) == SOC_BASE_ROM) assert (s_req_o[1]);
    if (f_present && (s_addr_o & SOC_MASK_APB) == SOC_BASE_APB) assert (s_req_o[2]);
    if (f_present && (s_addr_o & SOC_MASK_PNP) == SOC_BASE_PNP) assert (s_req_o[3]);
    if (f_present && (s_addr_o & SOC_MASK_CLINT) == SOC_BASE_CLINT) assert (s_req_o[4]);
    if (f_present && (s_addr_o & SOC_MASK_NPU) == SOC_BASE_NPU) assert (s_req_o[5]);
end

// ---------------------------------------------------------------------
// F3: grants
// ---------------------------------------------------------------------
always @(posedge clk_i) if (rst_ni) begin
    // F3a. No grant without a request.
    assert (!mi_gnt_o || mi_req_i);
    assert (!md_gnt_o || md_req_i);

    // F3b. One master at a time. Both granted in one cycle would put two
    //      addresses on one broadcast bus.
    assert (!(mi_gnt_o && md_gnt_o));

    // F3c. A transfer to a real slave requires that slave to have
    //      accepted. The error slave is internal and always ready, so
    //      it is excluded, which is exactly why F2b matters.
    //
    //      `f_take` and not `f_gnt`: at REQ_REG = 0 they are the same
    //      signal, and at REQ_REG = 1 the grant is deliberately NOT
    //      qualified by the slave -- that decoupling is the whole point
    //      of the parameter -- while the transfer still is. What keeps
    //      this from being a tautology there is I6, which asserts that
    //      the design's transfer is this ghost's.
    if (f_take && s_req_o[0]) assert (s_gnt_i[0]);
    if (f_take && s_req_o[1]) assert (s_gnt_i[1]);
    if (f_take && s_req_o[2]) assert (s_gnt_i[2]);
    if (f_take && s_req_o[3]) assert (s_gnt_i[3]);
    if (f_take && s_req_o[4]) assert (s_gnt_i[4]);
    if (f_take && s_req_o[5]) assert (s_gnt_i[5]);

    // F3d. The broadcast payload is the granted master's, and the
    //      instruction port -- which has no write signals at all -- must
    //      never cause a write.
    //
    //      AT REQ_REG = 1 THE GRANTED MASTER'S PINS ARE GONE by the
    //      time a slave sees the payload: protocol rule 2 lets a master
    //      change them in the cycle after its grant, and the fabric's
    //      register is what carries them across. So the comparison is
    //      against `f_cap_*`, a ghost copy taken from the MASTER PORTS
    //      at the grant. It is not a reading of the design's register
    //      -- soc_bus.v's own r_addr, r_we, r_be and r_wdata are named
    //      nowhere in this file -- so a fabric that captured the wrong
    //      master's payload, or the right master's a cycle late, fails
    //      here.
    if (REQ_REG != 0) begin
        if (f_fly) begin
            assert (s_addr_o  == f_cap_addr);
            assert (s_we_o    == f_cap_we);
            assert (s_be_o    == f_cap_be);
            assert (s_wdata_o == f_cap_wdata);
            if (!f_fly_own) assert (s_we_o == 1'b0);
        end
    end else begin
        if (mi_gnt_o) begin
            assert (s_addr_o == mi_addr_i);
            assert (s_we_o == 1'b0);
        end
        if (md_gnt_o) begin
            assert (s_addr_o  == md_addr_i);
            assert (s_we_o    == md_we_i);
            assert (s_be_o    == md_be_i);
            assert (s_wdata_o == md_wdata_i);
        end
    end
end

// The ghost copy F3d compares against at REQ_REG = 1, loaded from the
// master ports in the cycle of the grant. Held and not reset: it is
// read only while f_fly is high, and f_fly is high only after a grant
// has loaded it.
reg [31:0] f_cap_addr, f_cap_wdata;
reg        f_cap_we;
reg  [3:0] f_cap_be;
always @(posedge clk_i) if ((REQ_REG != 0) && f_gnt) begin
    f_cap_addr  <= md_gnt_o ? md_addr_i  : mi_addr_i;
    f_cap_we    <= md_gnt_o ? md_we_i    : 1'b0;
    f_cap_be    <= md_gnt_o ? md_be_i    : 4'hF;
    f_cap_wdata <= md_gnt_o ? md_wdata_i : 32'h0;
end

// ---------------------------------------------------------------------
// F3e: rule 1 toward the SLAVE, at REQ_REG = 1
// ---------------------------------------------------------------------
//
// THIS PROPERTY IS ADDED AND NOT TRANSPORTED, and the combinational
// fabric does not satisfy it. Ibex protocol rule 1 says a request is
// held, unchanged, until it is granted. This fabric requires that of
// its masters and at REQ_REG = 0 does not offer it to its slaves: the
// arbitration winner can change while a slave is still refusing --
// `can_issue_i` and `can_issue_d` turn on as responses return -- so a
// slave sees a request appear and vanish. That is not an argument: this
// same property with the `REQ_REG != 0` guard below removed is
// falsified at REQ_REG = 0 in four steps of bmc, and docs/84 section
// 2.4 records the run.
//
// TWO SLAVES IN THIS SoC WITHHOLD `gnt` -- soc_apb_bridge.v's
// `gnt_o = req_i && (state == ST_IDLE)` and soc_npu.v's
// `gnt_o = req_i && may_accept && (win_state == W_IDLE) && ...` -- so
// a slave that could see it is not hypothetical here. Nothing has
// depended on it because both of those slaves latch nothing until they
// grant; a slave that did would be written against REQ_REG = 1.
//
// At REQ_REG = 1 the request register makes it true, and a slave may
// therefore be written against it. That is a strictly stronger contract
// on this fabric's own outputs, and it is the one structural thing the
// parameter buys besides the depth.
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni
                            && (REQ_REG != 0)) begin
    if ($past(|s_req_o) && !(|($past(s_req_o) & $past(s_gnt_i)))) begin
        assert (s_req_o   == $past(s_req_o));
        assert (s_addr_o  == $past(s_addr_o));
        assert (s_we_o    == $past(s_we_o));
        assert (s_be_o    == $past(s_be_o));
        assert (s_wdata_o == $past(s_wdata_o));
    end
end

// ---------------------------------------------------------------------
// F4: the outstanding limit and the same-slave restriction
// ---------------------------------------------------------------------
always @(posedge clk_i) if (rst_ni) begin
    // F4a. Never more than MAX_OUT outstanding per master. Ibex issues at
    //      most 2 and the fabric's queues are sized for 2 per master; a
    //      third would overflow a queue silently.
    assert (f_out_i <= 3'd2);
    assert (f_out_d <= 3'd2);

    // F4b. All of a master's outstanding requests are at one slave. This
    //      is the restriction the fabric imposes in exchange for not
    //      carrying a reorder buffer, and everything about the response
    //      steering rests on it.
    if (f_take_i && f_out_i_slv != 3'd0) assert (f_tgt_idx == f_lock_i);
    if (f_take_d && f_out_d_slv != 3'd0) assert (f_tgt_idx == f_lock_d);
end

// ---------------------------------------------------------------------
// F5, F6: responses belong to requests
// ---------------------------------------------------------------------
always @(posedge clk_i) if (rst_ni) begin
    // F5. The internal error slave does not answer a request it was
    //     never given. The same statement is an ASSUMPTION for the four
    //     external slaves and an ASSERTION here, because here it is this
    //     module's own behaviour.
    if (err_rvalid) assert (f_occ[F_ERRSLV] != 4'd0);

    // F6. No queue overflows. The design's own q_fill is two bits and
    //     therefore cannot show this; the ghost counter is four bits so
    //     that an overflow is visible rather than wrapped away. This is
    //     the property that justifies the two-bit width in soc_bus.v.
    assert (f_occ[0] <= F_QD[3:0]);
    assert (f_occ[1] <= F_QD[3:0]);
    assert (f_occ[2] <= F_QD[3:0]);
    assert (f_occ[3] <= F_QD[3:0]);
    assert (f_occ[4] <= F_QD[3:0]);
    assert (f_occ[5] <= F_QD[3:0]);
    assert (f_occ[6] <= F_QD[3:0]);

    // No response to a master that has nothing outstanding.
    assert (!mi_rvalid_o || f_out_i != 3'd0);
    assert (!md_rvalid_o || f_out_d != 3'd0);
end

// ---------------------------------------------------------------------
// F7: no response is lost, duplicated or misdelivered
// ---------------------------------------------------------------------
//
// Counting form, which is what makes it provable without modelling the
// queues: in every cycle the number of responses arriving from the
// slaves equals the number of responses leaving to the masters. A
// response steered to the wrong master would still balance, so the
// invariant F8 below is what closes that gap -- it ties each master's
// outstanding count to the occupancy of the slave it is locked to.
wire [2:0] f_resp_in  = {2'b0, f_pop[0]} + {2'b0, f_pop[1]} + {2'b0, f_pop[2]}
                      + {2'b0, f_pop[3]} + {2'b0, f_pop[4]}
                      + {2'b0, f_pop[5]} + {2'b0, f_pop[6]};
wire [2:0] f_resp_out = {2'b0, mi_rvalid_o} + {2'b0, md_rvalid_o};

always @(posedge clk_i) if (rst_ni) begin
    assert (f_resp_in == f_resp_out);
end

// ---------------------------------------------------------------------
// F8: the accounting invariant
// ---------------------------------------------------------------------
//
// Total outstanding at the masters equals total occupancy at the slaves,
// and a master's own outstanding count is entirely accounted for by the
// slave it is locked to. Together these say a request cannot be sitting
// at one slave while its master believes it is at another, which is the
// misdelivery F7 alone cannot see.
wire [3:0] f_occ_total = f_occ[0] + f_occ[1] + f_occ[2] + f_occ[3] + f_occ[4]
                       + f_occ[5] + f_occ[6];

always @(posedge clk_i) if (rst_ni) begin
    assert (f_occ_total == ({1'b0, f_out_i_slv} + {1'b0, f_out_d_slv}));
    if (f_out_i_slv != 3'd0)
        assert (f_occ[f_lock_i] >= {1'b0, f_out_i_slv});
    if (f_out_d_slv != 3'd0)
        assert (f_occ[f_lock_d] >= {1'b0, f_out_d_slv});
end

// ---------------------------------------------------------------------
// F9: bounded fairness
// ---------------------------------------------------------------------
//
// The header claims round-robin arbitration rather than fixed priority,
// and the reason given is that no-starvation should be a property of
// this file rather than an argument about what the core can issue.
//
// The statement proved is the narrow one that is actually true: a master
// that requests for two consecutive cycles, with nothing outstanding at
// the start of them and every slave ready throughout, is granted in one
// of the two. Either it wins the first arbitration, or the other master
// does and the round-robin flop then hands it the second.
//
// THE FIRST VERSION OF THIS PROPERTY WAS FALSE and the bounded check
// found it at depth 3. It required readiness only in the second cycle,
// so the counterexample was: cycle 0, the instruction port requests the
// device table and that slave withholds its grant; cycle 1, every slave
// is ready but the data port also requests, and because nothing had been
// accepted yet the round-robin flop still favoured the data port. Two
// cycles of requesting, no grant, and the fabric was behaving correctly
// -- a slave that refuses a grant is not starvation by the arbiter.
// Readiness has to be part of the antecedent in BOTH cycles.
//
// AND THE SECOND VERSION WAS FALSE TOO, FOR TWO YEARS OF DOCUMENTS'
// WORTH OF RUNS THAT NOBODY MADE. docs/47 section 5 replaced soc_bus.v's
// `rst_ni && ...` request gate with `issue_en`, a flop that is low for
// the FIRST cycle after reset release, and priced it in that file's own
// comment: "one cycle of latency on the first transaction after a reset,
// once, at boot". That cycle is inside this property's two-cycle bound,
// and the property was not re-run. The counterexample is depth 3 and it
// is exactly the sentence that comment wrote down: cycle 1, the
// instruction port requests with every slave ready and is refused
// because issue_en is still 0; cycle 2, issue_en is up but the data port
// requests too and last_was_d is 0, so round-robin gives that cycle
// away. Two cycles of requesting, no grant. docs/50 section 7.
//
// THE REPAIR IS TO EXTEND, NOT TO RELAX. F9's own header says it is
// about the ARBITER, so the arbiter's precondition -- that the fabric is
// open -- belongs in its antecedent, and F9a below adds it. What must
// not happen is for the boot cycle to fall out of the property set
// altogether, so F9b asserts the bound that issue_en obeys: from the
// second cycle in which reset is high, the fabric is open, forever. The
// two together are strictly stronger than the version that was failing,
// because the old one said nothing at all about how long the gate may
// stay shut.
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    // F9a. Arbiter fairness, once the fabric is open.
    if ($past(mi_req_i) && mi_req_i && $past(f_out_i) == 3'd0
        && $past(&s_gnt_i) && (&s_gnt_i) && $past(issue_en))
        assert ($past(mi_gnt_o) || mi_gnt_o);
    if ($past(md_req_i) && md_req_i && $past(f_out_d) == 3'd0
        && $past(&s_gnt_i) && (&s_gnt_i) && $past(issue_en))
        assert ($past(md_gnt_o) || md_gnt_o);

    // F9b. And the fabric is open after exactly one cycle of reset being
    //      high, so F9a's new antecedent excludes one cycle at boot and
    //      not an unbounded silence.
    assert (issue_en);
end

// ---------------------------------------------------------------------
// F10: the clock-gate enable is COMPLETE
// ---------------------------------------------------------------------
//
// THIS IS THE PROPERTY THAT LETS soc_top.v GATE THIS MODULE'S CLOCK
// WITHOUT RE-ARGUING F1 TO F9.
//
// The obligation a gated slave creates is real and docs/50 section 8.1
// is the precedent for how it is discharged. F9 is a fairness bound with
// "every slave ready" in its antecedent, and a slave that cannot answer
// because its clock is stopped is, to a property, indistinguishable from
// one that is refusing to. The tempting repair is to weaken F9 -- to add
// "and the slave is awake" to its antecedent -- and that would be
// exactly the relaxation docs/50 section 8.1 refused. What is done
// instead is to prove that the gate CHANGES NOTHING:
//
//   In every cycle where `clk_en_o` is low, no register in this module
//   changes value.
//
// A design whose state does not change is a design whose state does not
// change whether or not it is clocked, so the gated instance and the
// ungated one have the same state in every cycle, present the same
// outputs in every cycle, and satisfy the same properties. F1 to F9 are
// transported, not restated. THIS IS AN EXTENSION AND NOT A RELAXATION
// in the strict sense: the property set gains a theorem and loses
// nothing, and the version of F9 proved here is the same version that
// was proved before the gate existed.
//
// TWO THINGS F10 DOES NOT SAY, and both matter.
//
//   * It says nothing about ASYNCHRONOUS RESET, and does not have to.
//     Every register here is reset on `negedge rst_ni` with no clock,
//     so the gate cannot hold a stale value through a reset. The guard
//     `$past(rst_ni) && rst_ni` below excludes the reset edge for that
//     reason and not to avoid a failure.
//   * It says nothing about the OTHER slaves. It is a statement about
//     this module's own registers, and the corresponding statement for
//     any other gated block has to be made about that block.
//
// The registers are enumerated rather than sampled in bulk, because
// there is no bulk to sample: `q_owner` and `q_fill` are arrays and
// `$past` of an array element is what has to be written.
//
// AND THE REQUEST REGISTER AT REQ_REG = 1 IS ENUMERATED THROUGH WHAT IT
// DRIVES, which needs saying rather than assuming, because the theorem
// is only about the registers it names. soc_bus.v's `g_req_reg` arm
// declares seven of them and each one is covered by exactly one signal
// in the block below:
//
//   r_val    by `req_busy`, which is it.
//   r_tgt    by `xfer_tgt`, which is it.
//   r_own    by `xfer_own`, which is it.
//   r_addr   by `s_addr_o`   |  the four broadcast outputs, which at
//   r_we     by `s_we_o`     |  REQ_REG = 1 are the register's own
//   r_be     by `s_be_o`     |  output pins and nothing else.
//   r_wdata  by `s_wdata_o`  |
//
// `s_req_o` is asserted as well, and it is not a seventh register: it
// is `r_val` decoded by `r_tgt`, so it adds no coverage and is there
// because a slave that saw a request appear in an unclocked cycle is
// the failure this property exists to exclude.
//
// THEY ARE OBSERVED AND NOT NAMED, and the reason is the parameter. The
// seven live inside a generate arm that does not elaborate at all at
// REQ_REG = 0, so a reference to `g_req_reg.r_val` would not compile in
// the configuration the design ships. The mapping above is total --
// every bit of the register reaches exactly one line below -- which is
// what the theorem needs, and it is what
// sw/tests/test_soc_clkgate_guards.py checks is still written down.
integer f_g;
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni
                            && !$past(clk_en_o)) begin
    assert (issue_en   == $past(issue_en));
    assert (last_was_d == $past(last_was_d));
    assert (err_rvalid == $past(err_rvalid));
    assert (cnt_i      == $past(cnt_i));
    assert (cnt_d      == $past(cnt_d));
    assert (lock_i     == $past(lock_i));
    assert (lock_d     == $past(lock_d));
    for (f_g = 0; f_g < F_NS; f_g = f_g + 1) begin
        assert (q_owner[f_g] == $past(q_owner[f_g]));
        assert (q_fill[f_g]  == $past(q_fill[f_g]));
    end
    // AND THE REQUEST REGISTER AT REQ_REG = 1, which is the whole of G6
    // and the reason `req_busy` is a term of the enable. The register's
    // seven fields are enumerated through the module's own outputs and
    // through the three transfer signals, which between them carry
    // every bit of it: `req_busy` is its valid bit, `xfer_tgt` and
    // `xfer_own` are its target and its owner, and the five broadcast
    // outputs are the payload. An enable that forgot the drain would
    // clear the valid bit in an unclocked cycle and fail here.
    if (REQ_REG != 0) begin
        assert (req_busy  == $past(req_busy));
        assert (xfer_tgt  == $past(xfer_tgt));
        assert (xfer_own  == $past(xfer_own));
        assert (s_req_o   == $past(s_req_o));
        assert (s_addr_o  == $past(s_addr_o));
        assert (s_we_o    == $past(s_we_o));
        assert (s_be_o    == $past(s_be_o));
        assert (s_wdata_o == $past(s_wdata_o));
    end
end

// F10b. And the enable is not the constant 1, which is the vacuity
//       check docs/09 section B.1 requires of a new property: a gate
//       that never closes would satisfy F10 and save nothing. The
//       covers are at the end of this file with the others.

// ---------------------------------------------------------------------
// L1-L4: the slave latency regime docs/50 puts the memories into
// ---------------------------------------------------------------------
//
// NO ASSERTION IN THIS FILE CHANGED WHEN hw/soc/rtl/soc_mem.v GREW A
// SECOND RESPONSE STAGE, AND THAT IS THE RESULT RATHER THAN AN
// OVERSIGHT. The environment above constrains the slave response inputs
// with exactly one assumption -- a slave does not answer a request it
// was never given -- and says nothing whatever about WHEN it answers. So
// the k-induction proof of F1-F9 already quantified over every slave
// latency, including the two cycles docs/50 makes the RAM and the boot
// ROM take, and F4a and F6 were already the statements that the
// outstanding limit and the queue depth hold under it.
//
// What was missing is not a property but a WITNESS. `cover (f_out_i ==
// 2)` shows a master at the limit, but not that a slave was two cycles
// late when it got there; an assert set is only as good as the reachable
// states it is checked on, and docs/09 B.1's vacuity rule applies to a
// new operating regime as much as to a new property. The ghost below
// ages the oldest outstanding request at slave 0 -- the RAM -- so that
// the covers can name the regime instead of hoping it was visited.
//
// The ghost is bookkeeping only. Nothing asserts on it.
reg [2:0] f_age0;
always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)                  f_age0 <= 3'd0;
    else if (f_occ[0] == 4'd0)    f_age0 <= 3'd0;
    else if (f_pop[0])            f_age0 <= 3'd0;   // the oldest retires
    else if (f_age0 != 3'd7)      f_age0 <= f_age0 + 3'd1;
end

// ---------------------------------------------------------------------
// Cover: docs/09 B.1 vacuity rule -- every proven behaviour reachable
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && rst_ni) begin
    // A request REACHING each slave port. `f_push` and not
    // `f_gnt && s_req_o[k]`, which are the same thing at REQ_REG = 0
    // and are the grant of an unrelated, earlier request at 1.
    cover (f_push[0]);
    cover (f_push[1]);
    cover (f_push[2]);
    cover (f_push[3]);
    cover (f_push[4]);
    // docs/51's port. Without this the sixth slave would be covered by
    // every ASSERTION above and witnessed by none of them, which is the
    // vacuity docs/09 section B.1 makes a red result.
    cover (f_push[5]);
    cover (f_push[6]);                      // and to the error slave
    cover (mi_rvalid_o && mi_err_o);        // a bus error reaching a master
    cover (f_out_i == 3'd2);                // both masters at the limit
    cover (f_out_d == 3'd2);
    cover (f_out_i != 3'd0 && f_out_d != 3'd0 && f_lock_i != f_lock_d);
    cover (mi_rvalid_o && md_rvalid_o);     // two responses in one cycle
    cover (f_occ[0] == 4'd4);               // a slave queue completely full

    // L1. THE MEMORY docs/50 BUILDS: slave 0 answers exactly two cycles
    //     after the grant it is answering. This is the regime the whole
    //     assert set above is now relied on in, and it is reachable.
    cover (f_pop[0] && f_age0 == 3'd2);

    // L2. And later than that, so nothing here has quietly fixed the
    //     latency at the one value the RTL happens to use.
    cover (f_pop[0] && f_age0 >= 3'd4);

    // L3. TWO REQUESTS IN FLIGHT AT A TWO-CYCLE SLAVE, which is what the
    //     extra cycle makes routine and what the one-cycle memory never
    //     produced: the pipeline is full and the older response has not
    //     come back yet.
    cover (f_occ[0] == 4'd2 && f_age0 >= 3'd2 && !f_pop[0]);

    // L4. A grant to slave 0 in the same cycle as a response from it,
    //     with a request still outstanding -- the push-and-pop case of
    //     the ownership queue, at a latency where it is not the same
    //     request being pushed and popped.
    cover (f_push[0] && f_pop[0] && f_occ[0] >= 4'd2);

    // G1. THE GATE CLOSES. Without this F10 is satisfied by an enable
    //     that is the constant 1, which is a proof that a clock gate
    //     nobody built is safe. docs/09 section B.1.
    cover (!clk_en_o);

    // G2. And it closes WHILE A REQUEST IS OUTSTANDING, which is the
    //     case the fabric's own header calls out: a master waiting on
    //     the 172-cycle NPU window is a master the fabric has nothing
    //     to do for, and 171 of those cycles are cycles this module
    //     does not need a clock in. A gate that only ever closed with
    //     the fabric completely empty would be worth far less and F10
    //     would not distinguish the two.
    cover (!clk_en_o && f_out_i != 3'd0);
    cover (!clk_en_o && f_out_d != 3'd0);
end

// ---------------------------------------------------------------------
// R1-R4: the request register's own witnesses, REQ_REG = 1 only
// ---------------------------------------------------------------------
//
// IN A GENERATE AND NOT UNDER AN `if`, deliberately. An assert whose
// antecedent is constant-false is vacuously true and costs nothing; a
// COVER whose condition is constant-false is UNREACHABLE, and docs/09
// section B.1 makes an unreachable cover a red result. So these four
// are elaborated only at the setting where they are reachable, and
// REQ_REG = 0's cover task is the task it was before the parameter.
generate
if (REQ_REG != 0) begin : g_f_req_reg
    always @(posedge clk_i) if (f_past_valid && rst_ni) begin
        // R1. THE THROUGHPUT CLAIM, WITNESSED. A request is captured in
        //     the very cycle the register hands the previous one to its
        //     slave. Without this, every property here would be
        //     satisfied by a fabric that accepted one request every two
        //     cycles, which is the failure mode the one-deep skid
        //     buffer exists to avoid and which no assertion can see.
        cover (f_gnt && f_fly && f_fly_xfer);

        // R2. AND THE OTHER HALF: the register holding a request a
        //     slave has not taken. This is the state F3e is about.
        //     TWO SLAVES HERE PRODUCE IT -- soc_apb_bridge.v grants
        //     only in ST_IDLE and soc_npu.v only in W_IDLE -- so this
        //     cover is not a hypothetical, and docs/84 section 2.4a
        //     measures what the state costs, which is nothing the
        //     round-robin arbiter was not already costing.
        cover (f_fly && !f_fly_xfer);

        // R3. A master at the outstanding limit with one of the two
        //     still in the register -- the case where a master's count
        //     and its slave's queue disagree, which is what f_out_i_slv
        //     exists for and what I4 and F8 are checked on.
        cover (f_fly && !f_fly_own && f_out_i == 3'd2);
        cover (f_fly &&  f_fly_own && f_out_d == 3'd2);
    end
end
endgenerate
