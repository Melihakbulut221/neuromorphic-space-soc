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

localparam integer F_ERRSLV = 5;
localparam integer F_NS     = 6;   // five ports plus the error slave

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
                        s_req_o[4] ? 3'd4 : F_ERRSLV[2:0];

wire [5:0] f_push = {f_gnt && (s_req_o == 5'b00000),
                     f_gnt && s_req_o[4],
                     f_gnt && s_req_o[3],
                     f_gnt && s_req_o[2],
                     f_gnt && s_req_o[1],
                     f_gnt && s_req_o[0]};
wire [5:0] f_pop  = {err_rvalid, s_rvalid_i};

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
        if (mi_gnt_o) f_lock_i <= f_tgt_idx;
        if (md_gnt_o) f_lock_d <= f_tgt_idx;
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
            case ({mi_gnt_o && (f_tgt_idx == f_s[2:0]),
                   mi_rvalid_o && (f_lock_i == f_s[2:0])})
                2'b10:   f_occ_i[f_s] <= f_occ_i[f_s] + 3'd1;
                2'b01:   f_occ_i[f_s] <= f_occ_i[f_s] - 3'd1;
                default: ;
            endcase
            case ({md_gnt_o && (f_tgt_idx == f_s[2:0]),
                   md_rvalid_o && (f_lock_d == f_s[2:0])})
                2'b10:   f_occ_d[f_s] <= f_occ_d[f_s] + 3'd1;
                2'b01:   f_occ_d[f_s] <= f_occ_d[f_s] - 3'd1;
                default: ;
            endcase
        end
    end
end

// Slave contract S1/S3, as an assumption on the four external ports: a
// slave does not answer a request it was never given. The error slave is
// internal and gets no such licence -- F5 ASSERTS the same thing of it.
always @(posedge clk_i) if (rst_ni) begin
    if (s_rvalid_i[0]) assume (f_occ[0] != 4'd0);
    if (s_rvalid_i[1]) assume (f_occ[1] != 4'd0);
    if (s_rvalid_i[2]) assume (f_occ[2] != 4'd0);
    if (s_rvalid_i[3]) assume (f_occ[3] != 4'd0);
    if (s_rvalid_i[4]) assume (f_occ[4] != 4'd0);
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
    if (f_out_i != 3'd0) assert (f_lock_i == lock_i);
    if (f_out_d != 3'd0) assert (f_lock_d == lock_d);

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
        if (f_s[2:0] == f_lock_i) assert (f_occ_i[f_s] == f_out_i);
        else                      assert (f_occ_i[f_s] == 3'd0);
        if (f_s[2:0] == f_lock_d) assert (f_occ_d[f_s] == f_out_d);
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

    // F2a. A selected slave is the one the frozen map puts the broadcast
    //      address in. Soundness: nothing is routed to the wrong place.
    if (s_req_o[0]) assert ((s_addr_o & SOC_MASK_RAM) == SOC_BASE_RAM);
    if (s_req_o[1]) assert ((s_addr_o & SOC_MASK_ROM) == SOC_BASE_ROM);
    if (s_req_o[2]) assert ((s_addr_o & SOC_MASK_APB) == SOC_BASE_APB);
    if (s_req_o[3]) assert ((s_addr_o & SOC_MASK_PNP) == SOC_BASE_PNP);
    if (s_req_o[4]) assert ((s_addr_o & SOC_MASK_CLINT) == SOC_BASE_CLINT);

    // F2b. The converse. Completeness: an address the map covers is
    //      never sent to the error slave, and never dropped. Without
    //      this half, a fabric that answered every access with a bus
    //      error would satisfy F2a.
    if (f_gnt && (s_addr_o & SOC_MASK_RAM) == SOC_BASE_RAM) assert (s_req_o[0]);
    if (f_gnt && (s_addr_o & SOC_MASK_ROM) == SOC_BASE_ROM) assert (s_req_o[1]);
    if (f_gnt && (s_addr_o & SOC_MASK_APB) == SOC_BASE_APB) assert (s_req_o[2]);
    if (f_gnt && (s_addr_o & SOC_MASK_PNP) == SOC_BASE_PNP) assert (s_req_o[3]);
    if (f_gnt && (s_addr_o & SOC_MASK_CLINT) == SOC_BASE_CLINT) assert (s_req_o[4]);
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

    // F3c. A grant to a real slave requires that slave to have accepted.
    //      The error slave is internal and always ready, so it is
    //      excluded, which is exactly why F2b matters.
    if (f_gnt && s_req_o[0]) assert (s_gnt_i[0]);
    if (f_gnt && s_req_o[1]) assert (s_gnt_i[1]);
    if (f_gnt && s_req_o[2]) assert (s_gnt_i[2]);
    if (f_gnt && s_req_o[3]) assert (s_gnt_i[3]);
    if (f_gnt && s_req_o[4]) assert (s_gnt_i[4]);

    // F3d. The broadcast payload is the granted master's, and the
    //      instruction port -- which has no write signals at all -- must
    //      never cause a write.
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
    if (mi_gnt_o && f_out_i != 3'd0) assert (f_tgt_idx == f_lock_i);
    if (md_gnt_o && f_out_d != 3'd0) assert (f_tgt_idx == f_lock_d);
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
                      + {2'b0, f_pop[5]};
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
                       + f_occ[5];

always @(posedge clk_i) if (rst_ni) begin
    assert (f_occ_total == ({1'b0, f_out_i} + {1'b0, f_out_d}));
    if (f_out_i != 3'd0)
        assert (f_occ[f_lock_i] >= {1'b0, f_out_i});
    if (f_out_d != 3'd0)
        assert (f_occ[f_lock_d] >= {1'b0, f_out_d});
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
// Readiness has to be part of the antecedent in BOTH cycles, and the
// corrected property below says so.
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    if ($past(mi_req_i) && mi_req_i && $past(f_out_i) == 3'd0
        && $past(&s_gnt_i) && (&s_gnt_i))
        assert ($past(mi_gnt_o) || mi_gnt_o);
    if ($past(md_req_i) && md_req_i && $past(f_out_d) == 3'd0
        && $past(&s_gnt_i) && (&s_gnt_i))
        assert ($past(md_gnt_o) || md_gnt_o);
end

// ---------------------------------------------------------------------
// Cover: docs/09 B.1 vacuity rule -- every proven behaviour reachable
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && rst_ni) begin
    cover (f_gnt && s_req_o[0]);            // a grant to each slave port
    cover (f_gnt && s_req_o[1]);
    cover (f_gnt && s_req_o[2]);
    cover (f_gnt && s_req_o[3]);
    cover (f_gnt && s_req_o[4]);
    cover (f_gnt && s_req_o == 5'b00000);   // and to the error slave
    cover (mi_rvalid_o && mi_err_o);        // a bus error reaching a master
    cover (f_out_i == 3'd2);                // both masters at the limit
    cover (f_out_d == 3'd2);
    cover (f_out_i != 3'd0 && f_out_d != 3'd0 && f_lock_i != f_lock_d);
    cover (mi_rvalid_o && md_rvalid_o);     // two responses in one cycle
    cover (f_occ[0] == 4'd4);               // a slave queue completely full
end
