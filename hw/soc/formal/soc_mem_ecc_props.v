// The memory codec and scrubber over a four-row array, stated as
// properties. soc_mem_ecc.sby's header says what is and is not proved.
//
// The harness owns the array, in exactly soc_mem.v's shape -- a read
// lands in the row register at the edge and holds, a write changes the
// row register not at all -- and a GHOST word per row that records what
// the bus last wrote, lane by lane. M2 is the statement that the codec
// between the two is the identity.

`default_nettype none

module soc_mem_ecc_props (
    input wire        clk_i,
    input wire        rst_ni,
    input wire        req_i,
    input wire [31:0] addr_i,
    input wire        we_i,
    input wire [3:0]  be_i,
    input wire [31:0] wdata_i,
    input wire        scrub_en_i,
    input wire [15:0] scrub_ivl_i
);

    localparam integer WORDS = 4;
    localparam integer AW = 2;
    localparam integer RW = 64;

    wire        gnt_o, rvalid_o, err_o;
    wire [31:0] rdata_o;
    wire        row_en, row_we;
    wire [AW-1:0] row_addr;
    wire [RW-1:0] row_din, row_bm;
    wire        sec_o, rd_o, ded_o;
    wire [31:0] evt_addr_o;

    // ---- the array, soc_mem.v's g_ecc shape -----------------------
    reg [31:0] mem [0:WORDS-1];
    reg [31:0] chk [0:WORDS-1];
    reg [31:0] q_mem;
    reg [31:0] q_chk;

    soc_mem_ecc #(
        .WORDS (WORDS), .RO (1'b0), .HARDEN (1), .ECC_BYTE (1'b1),
        .RDREG (1'b0), .RW (RW)
    ) dut (
        .clk_i (clk_i), .rst_ni (rst_ni),
        .req_i (req_i), .addr_i (addr_i), .we_i (we_i), .be_i (be_i),
        .wdata_i (wdata_i), .gnt_o (gnt_o), .rvalid_o (rvalid_o),
        .rdata_o (rdata_o), .err_o (err_o),
        .row_en_o (row_en), .row_we_o (row_we), .row_addr_o (row_addr),
        .row_din_o (row_din), .row_bm_o (row_bm),
        .row_dout_i ({q_chk, q_mem}),
        .scrub_en_i (scrub_en_i), .scrub_ivl_i (scrub_ivl_i),
        .sec_o (sec_o), .rd_o (rd_o), .ded_o (ded_o),
        .evt_addr_o (evt_addr_o)
    );

    integer i;
    initial begin
        for (i = 0; i < WORDS; i = i + 1) begin
            mem[i] = 32'h0;
            chk[i] = 32'h0;
        end
        q_mem = 32'h0;
        q_chk = 32'h0;
    end

    always @(posedge clk_i) begin
        if (row_en) begin
            if (row_we) begin
                mem[row_addr] <= (mem[row_addr] & ~row_bm[31:0])
                               | (row_din[31:0] & row_bm[31:0]);
                chk[row_addr] <= (chk[row_addr] & ~row_bm[63:32])
                               | (row_din[63:32] & row_bm[63:32]);
            end else begin
                q_mem <= mem[row_addr];
                q_chk <= chk[row_addr];
            end
        end
    end

    // ---- the ghost: what the bus last wrote, lane by lane ---------
    reg [31:0] ghost [0:WORDS-1];
    reg [AW-1:0] rd_row_q;      // the row of the read in flight
    reg          rd_q;
    wire [AW-1:0] bus_row = addr_i[AW+1:2];

    initial begin
        for (i = 0; i < WORDS; i = i + 1) ghost[i] = 32'h0;
        rd_row_q = {AW{1'b0}};
        rd_q = 1'b0;
    end

    always @(posedge clk_i) begin
        if (req_i && we_i) begin
            if (be_i[0]) ghost[bus_row][7:0]   <= wdata_i[7:0];
            if (be_i[1]) ghost[bus_row][15:8]  <= wdata_i[15:8];
            if (be_i[2]) ghost[bus_row][23:16] <= wdata_i[23:16];
            if (be_i[3]) ghost[bus_row][31:24] <= wdata_i[31:24];
        end
        rd_q     <= req_i && !we_i && rst_ni;
        rd_row_q <= bus_row;
    end

    // ---- the encoder beside every row, for M1 ---------------------
    // The check field each row SHOULD hold, from the frozen encoder over
    // the row's data, lane by lane, exactly as g_enc_byte builds it.
    wire [31:0] want_chk [0:WORDS-1];
    genvar r, l;
    generate
        for (r = 0; r < WORDS; r = r + 1) begin : g_row
            for (l = 0; l < 4; l = l + 1) begin : g_lane
                wire [7:0]  c;
                wire [71:0] unused;
                secded_enc u_enc (
                    .data_in   ({56'h0, mem[r][8*l +: 8]}),
                    .check_out (c),
                    .code_out  (unused)
                );
                assign want_chk[r][8*l +: 8] = c;
            end
        end
    endgenerate

    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk_i) f_past_valid <= 1'b1;

    initial assume (!rst_ni);
    // The bus is quiet in reset, as the fabric's is.
    always @(*) if (!rst_ni) assume (!req_i);

    // ---- M1. Every row is a codeword, and the row register too ----
    generate
        for (r = 0; r < WORDS; r = r + 1) begin : g_m1
            always @(*) begin
                assert (chk[r] == want_chk[r]);
                assert (mem[r] == ghost[r]);
            end
        end
    endgenerate

    // The row register holds a codeword of the row it last read, so
    // the decoders see a clean word whenever anything consumes them.
    wire [31:0] q_want_chk;
    generate
        for (l = 0; l < 4; l = l + 1) begin : g_qlane
            wire [7:0]  c;
            wire [71:0] unused;
            secded_enc u_enc (
                .data_in   ({56'h0, q_mem[8*l +: 8]}),
                .check_out (c),
                .code_out  (unused)
            );
            assign q_want_chk[8*l +: 8] = c;
        end
    endgenerate
    always @(*) assert (q_chk == q_want_chk);

    // A read in flight has the row register holding ITS row: the read
    // loaded it at the last edge and nothing writes that row before
    // the response cycle ends (one port).
    always @(*)
        if (rd_q) assert (q_mem == ghost[rd_row_q]);

    // ---- M2. The codec is invisible ---------------------------------
    always @(*) begin
        if (rvalid_o && rd_q) begin
            assert (rdata_o == ghost[rd_row_q]);
            assert (!err_o);
        end
        assert (!sec_o);
        assert (!rd_o);
        assert (!ded_o);
    end

    // ---- M3. The protocol ---------------------------------------------
    always @(*) assert (gnt_o == req_i);
    always @(posedge clk_i)
        if (f_past_valid && $past(rst_ni) && rst_ni)
            assert (rvalid_o == $past(req_i));
    always @(*) if (err_o) assert (rvalid_o);

    // ---- M4. The bus owns the port in its cycle -------------------
    always @(*)
        if (req_i) begin
            assert (row_en);
            assert (row_addr == bus_row);
            assert (row_we == we_i);
            assert (row_din[31:0] == wdata_i);
            assert (row_bm[7:0]   == {8{be_i[0]}});
            assert (row_bm[31:24] == {8{be_i[3]}});
            assert (row_bm[39:32] == {8{be_i[0]}});
        end

    // ---- M5. The scrubber writes back only what it corrected ------
    // In a fault-free machine that is nothing: a write on the row port
    // is a bus write.
    always @(*)
        if (row_we) assert (req_i && we_i);

    // ---- M6 and the scrubber's own covers are stated INSIDE
    // soc_mem_ecc.v, in soc_mem_ecc_int_props.v under `ifdef FORMAL,
    // because the pointer and the examine strobe are internal state and
    // a hierarchical reference into a submodule is not something the
    // formal front end resolves. This harness sees the scrubber only
    // through the row port, which is the point of M4 and M5.

    // ---- vacuity ------------------------------------------------------
    always @(posedge clk_i) begin
        cover (f_past_valid && rst_ni && rvalid_o && rd_q && rdata_o != 32'h0);
        cover (f_past_valid && rst_ni && $past(req_i && we_i && be_i == 4'b0010));
        // a scrub read: the row port enabled with no bus request
        cover (f_past_valid && rst_ni && row_en && !req_i);
        cover (f_past_valid && rst_ni && $past(row_en && !req_i) && req_i);
        cover (f_past_valid && rst_ni && chk[1] != 32'h0 && chk[2] != 32'h0);
    end

endmodule

`default_nettype wire
