#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Mutation evidence for the soc_qspi suite.

Each mutation below is one deliberate defect written into a SCRATCH COPY
of hw/soc/rtl/soc_qspi.v -- the tree is never edited -- and the whole
suite is run against it through Makefile.soc_qspi's SOC_QSPI_SRC. A
mutant that every test passes is a mutant the suite cannot see, and it
is reported as such rather than hidden. The map test is excluded from
the "caught by" column: it reads regmap/memmap.yaml and not the RTL, so
it cannot catch a mutant and must not be credited with one.

The suite's Makefile reports a TESTS= line on every mutant, so a mutant
that failed to BUILD is distinguished from one that was caught, which is
the docs/40 section 8.3 harness failure this file refuses to repeat.

Run:  python3 hw/soc/tb/cocotb/mutate_soc_qspi.py [out_dir]
"""

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
RTL = HERE.parents[1] / "rtl" / "soc_qspi.v"
MAP_TEST = "test_the_slot_and_the_line_are_the_frozen_maps"

# (name, what it models, old, new)
MUTANTS = [
    ("m01", "RX packs the first byte into the top lane (big-endian)",
     "2'd0: rx_q <= {24'h0, cur};", "2'd0: rx_q <= {cur, 24'h0};"),
    ("m02", "the opcode goes out LSB first",
     "io_o_q     <= first_unit(pwdata_i[7:0], 1'b0);",
     "io_o_q     <= first_unit({pwdata_i[0], pwdata_i[1], pwdata_i[2], pwdata_i[3], pwdata_i[4], pwdata_i[5], pwdata_i[6], pwdata_i[7]}, 1'b0);"),
    ("m03", "the input is sampled from IO0 instead of IO1 in single mode",
     "cur <= quad_phase ? {cur[3:0], io_i} : {cur[6:0], io_i[1]};",
     "cur <= quad_phase ? {cur[3:0], io_i} : {cur[6:0], io_i[0]};"),
    ("m04", "IO3 (/HOLD) released instead of driven high in single mode",
     "localparam [3:0] OE_SINGLE = 4'b1101;", "localparam [3:0] OE_SINGLE = 4'b0101;"),
    ("m05", "one dummy clock too few",
     "unit_left  <= dummy_q;", "unit_left  <= dummy_q - 4'd1;"),
    ("m06", "the lanes are not released for a quad data phase",
     "io_oe_q <= dquad_q ? 4'b0000 : OE_SINGLE;\n                      io_o_q  <= 4'hF;\n                      cur     <= 8'h0;",
     "io_oe_q <= OE_SINGLE;\n                      io_o_q  <= 4'hF;\n                      cur     <= 8'h0;"),
    ("m07", "no pause at a word boundary: DR set but the frame runs on",
     "dr_q  <= 1'b1;\n                      state <= S_WAITRX;",
     "dr_q  <= 1'b1;\n                      unit_left <= quad_phase ? 4'd2 : 4'd8; byte_idx <= 2'd0;"),
    ("m08", "the deselect gap is one SCK period instead of four",
     "gap_cnt <= 4'd8;\n            state   <= S_GAP;", "gap_cnt <= 4'd2;\n            state   <= S_GAP;"),
    ("m09", "a CMD write while BUSY is accepted",
     "if (busy_q && (cmd_wr || conf_wr || addr_wr)) lost_q <= 1'b1;\n      if (!busy_q) begin",
     "if (busy_q && (conf_wr || addr_wr)) lost_q <= 1'b1;\n      if (1'b1) begin"),
    ("m10", "the interrupt ignores DR",
     "assign irq_o = ien_q && (done_q || dr_q);", "assign irq_o = ien_q && done_q;"),
    ("m11", "the address goes out low byte first",
     "cur        <= addr_q[23:16];\n                    io_o_q     <= first_unit(addr_q[23:16], aquad_q);",
     "cur        <= addr_q[7:0];\n                    io_o_q     <= first_unit(addr_q[7:0], aquad_q);"),
    ("m12", "the second chip select is never asserted",
     "cs_n_q[i] <= !(cs_q == i[CS_W-1:0]);", "cs_n_q[i] <= !(i == 0);"),
    ("m13", "the mode byte after a quad address is 00h, entering continuous read mode",
     "if (aquad_q) begin\n                      io_oe_q <= 4'b1111;\n                      io_o_q  <= 4'hF;",
     "if (aquad_q) begin\n                      io_oe_q <= 4'b1111;\n                      io_o_q  <= 4'h0;"),
    ("m14", "the SCK divider runs at DIV instead of DIV + 1 clocks per half period",
     "if (tick) div_cnt <= div_q;\n      else      div_cnt <= div_cnt - 1'b1;",
     "if (tick) div_cnt <= (div_q == 0) ? div_q : div_q - 1'b1;\n      else      div_cnt <= div_cnt - 1'b1;"),
    ("m15", "a read of RX does not clear DR",
     "if (rx_rd) dr_q <= 1'b0;", "if (rx_rd && 1'b0) dr_q <= 1'b0;"),
    ("m16", "the TX word's first byte out is its top lane",
     "cur       <= lane_byte(tx_wr ? pwdata_i : tx_q, 2'd0);",
     "cur       <= lane_byte(tx_wr ? pwdata_i : tx_q, 2'd3);"),
]


def run(out_dir):
    src = RTL.read_text()
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, what, old, new in MUTANTS:
        assert src.count(old) == 1, (name, "anchor count", src.count(old))
        mut = out_dir / f"{name}.v"
        mut.write_text(src.replace(old, new))
        build = out_dir / f"build_{name}"
        results = out_dir / f"results_{name}.xml"
        env = {"SOC_QSPI_SRC": str(mut), "SIM_BUILD": str(build),
               "COCOTB_RESULTS_FILE": str(results)}
        cmd = ["make", "-f", "Makefile.soc_qspi"] + [f"{k}={v}" for k, v in env.items()]
        p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                           timeout=1200)
        tests_line = [ln for ln in p.stdout.splitlines() if "TESTS=" in ln]
        if not results.is_file() or not tests_line:
            rows.append((name, what, "DID NOT BUILD", []))
            continue
        root = ET.parse(results).getroot()
        failed = []
        total = 0
        for case in root.iter("testcase"):
            total += 1
            if any(ch.tag in ("failure", "error") for ch in case):
                failed.append(case.get("name"))
        real = [f for f in failed if f != MAP_TEST]
        rows.append((name, what, "caught" if real else "NOT CAUGHT", real))
        print(f"{name}: {len(real)} of {total} tests fail -> "
              f"{'caught' if real else 'NOT CAUGHT'}: {what}", flush=True)
    return rows


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "mutants_soc_qspi"
    rows = run(out)
    caught = sum(1 for r in rows if r[2] == "caught")
    print()
    print("| Mutation | Caught by |")
    print("|---|---|")
    for name, what, status, tests in rows:
        if status == "caught":
            first = tests[0]
            more = f" and {len(tests) - 1} other{'s' if len(tests) > 2 else ''}" if len(tests) > 1 else ""
            print(f"| {what} | `{first}`{more} |")
        else:
            print(f"| {what} | **{status}** |")
    print(f"\n{caught} of {len(rows)} mutations caught")
    sys.exit(0 if caught == len(rows) else 1)
