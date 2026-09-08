// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// FABRIC OCCUPANCY PROBE. NOT PART OF THE DESIGN.
//
// A second elaboration root that only observes. It is compiled into the
// whole-SoC run by hw/soc/flow/sim_soc.sh at SOC_PROBE=1, drives nothing,
// and is connected to nothing: every signal it reads is a hierarchical
// reference into tb_soc. Nothing in hw/soc/rtl/ knows it exists.
//
// WHY IT EXISTS. docs/50 registers the memories' read return, which makes
// every RAM and ROM response arrive two cycles after its grant instead of
// one. The obvious consequence is a fabric question: soc_bus.v enforces
// its per-master outstanding limit with `cnt < MAX_OUT`, cnt is a
// REGISTER, and a response arriving now is not subtracted from it until
// the next clock edge -- so in the cycle a response returns, a master at
// the limit is refused a grant it could have had. At one cycle of slave
// latency a master never reaches the limit and the conservatism is
// invisible; at two cycles the arithmetic says it should cost a third of
// the fetch bandwidth.
//
// IT DOES NOT, AND THIS FILE IS WHY THAT IS A MEASUREMENT RATHER THAN AN
// ARGUMENT. `blk_i` and `blk_d` below count the cycles in which a master
// is AT the limit, locked to the slave it is addressing, and still
// requesting -- which is exactly the population any credit scheme would
// act on. docs/50 section 3 reports both as ZERO, at one cycle of latency
// and at two, because Ibex's own NUM_REQS is 2 and equals the fabric's
// MAX_OUT: the core stops asking before the fabric stops granting. A
// fabric change was designed for a case that cannot arise, and was not
// kept.
//
// `sw_i` and `sw_d` count the other thing docs/39's header claims a cost
// for: a master refused because its target region changed while it still
// had responses outstanding -- the same-slave restriction's dead cycle,
// whose price rises with slave latency.
//
// The occupancy histograms and the per-slave response counts are what
// turn the cycle count of docs/50 section 5 into a breakdown instead of
// one number.
//
// EVERYTHING HERE IS A COUNTER AND A $display. If this file ever drives
// or forces anything, it stops being a probe.

`timescale 1ns / 1ps

module soc_bus_probe;

  integer cyc;
  integer occ_i0, occ_i1, occ_i2;
  integer occ_d0, occ_d1, occ_d2;
  integer blk_i, blk_d;
  integer sw_i, sw_d;
  integer gnt_i, gnt_d;
  integer rv_ram, rv_rom, rv_apb, rv_pnp, rv_clint;

  initial begin
    cyc = 0;
    occ_i0 = 0; occ_i1 = 0; occ_i2 = 0;
    occ_d0 = 0; occ_d1 = 0; occ_d2 = 0;
    blk_i = 0; blk_d = 0;
    sw_i = 0; sw_d = 0;
    gnt_i = 0; gnt_d = 0;
    rv_ram = 0; rv_rom = 0; rv_apb = 0; rv_pnp = 0; rv_clint = 0;
  end

  always @(posedge tb_soc.clk) if (tb_soc.rst_n) begin
    cyc = cyc + 1;

    case (tb_soc.dut.u_bus.cnt_i)
      2'd0:    occ_i0 = occ_i0 + 1;
      2'd1:    occ_i1 = occ_i1 + 1;
      default: occ_i2 = occ_i2 + 1;
    endcase
    case (tb_soc.dut.u_bus.cnt_d)
      2'd0:    occ_d0 = occ_d0 + 1;
      2'd1:    occ_d1 = occ_d1 + 1;
      default: occ_d2 = occ_d2 + 1;
    endcase

    // At the limit, locked to the slave being addressed, still asking.
    if (tb_soc.dut.u_bus.mi_req_i &&
        tb_soc.dut.u_bus.cnt_i  == 2'd2 &&
        tb_soc.dut.u_bus.lock_i == tb_soc.dut.u_bus.tgt_i) blk_i = blk_i + 1;
    if (tb_soc.dut.u_bus.md_req_i &&
        tb_soc.dut.u_bus.cnt_d  == 2'd2 &&
        tb_soc.dut.u_bus.lock_d == tb_soc.dut.u_bus.tgt_d) blk_d = blk_d + 1;

    // Refused by the same-slave restriction rather than by the limit.
    if (tb_soc.dut.u_bus.mi_req_i &&
        tb_soc.dut.u_bus.cnt_i  != 2'd0 &&
        tb_soc.dut.u_bus.lock_i != tb_soc.dut.u_bus.tgt_i) sw_i = sw_i + 1;
    if (tb_soc.dut.u_bus.md_req_i &&
        tb_soc.dut.u_bus.cnt_d  != 2'd0 &&
        tb_soc.dut.u_bus.lock_d != tb_soc.dut.u_bus.tgt_d) sw_d = sw_d + 1;

    if (tb_soc.dut.u_bus.mi_gnt_o) gnt_i = gnt_i + 1;
    if (tb_soc.dut.u_bus.md_gnt_o) gnt_d = gnt_d + 1;

    if (tb_soc.dut.u_bus.s_rvalid_i[0]) rv_ram   = rv_ram   + 1;
    if (tb_soc.dut.u_bus.s_rvalid_i[1]) rv_rom   = rv_rom   + 1;
    if (tb_soc.dut.u_bus.s_rvalid_i[2]) rv_apb   = rv_apb   + 1;
    if (tb_soc.dut.u_bus.s_rvalid_i[3]) rv_pnp   = rv_pnp   + 1;
    if (tb_soc.dut.u_bus.s_rvalid_i[4]) rv_clint = rv_clint + 1;
  end

  final begin
    $display("[PROBE] cycles observed        %0d", cyc);
    $display("[PROBE] instr occupancy 0/1/2  %0d %0d %0d",
             occ_i0, occ_i1, occ_i2);
    $display("[PROBE] data  occupancy 0/1/2  %0d %0d %0d",
             occ_d0, occ_d1, occ_d2);
    $display("[PROBE] at limit and asking    instr %0d  data %0d",
             blk_i, blk_d);
    $display("[PROBE] refused, target change instr %0d  data %0d",
             sw_i, sw_d);
    $display("[PROBE] grants                 instr %0d  data %0d",
             gnt_i, gnt_d);
    $display("[PROBE] responses ram/rom/apb/pnp/clint  %0d %0d %0d %0d %0d",
             rv_ram, rv_rom, rv_apb, rv_pnp, rv_clint);
  end

endmodule
