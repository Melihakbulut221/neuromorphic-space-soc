#!/usr/bin/env python3
"""Mutation evidence for the memory codec suite (docs/67).

    python3 hw/soc/tb/cocotb/mutate_soc_mem.py

Each mutation is a small edit to a COPY of hw/soc/rtl/soc_mem_ecc.v,
built with the RAM configuration of Makefile.soc_mem, and the claim is
that the suite FAILS on every one of them. A suite that passes on a
mutant is a suite whose green result is narrower than what it examined
-- the shape docs/41 section 6.6 counts -- and the mutations below are
the wrong-way-round edits soc_mem_ecc.v's header argues against, every
one of which is functionally invisible in a fault-free machine:

  wb_raw        the scrubber writes back the RAW word instead of the
                corrected one: the syndrome is re-encoded into a valid
                codeword over the wrong value -- soc_clint.v H6's "ECC
                counter that silently does nothing"
  wb_on_ded     the scrubber writes back an UNCORRECTABLE lane too,
                laundering a double error into a clean wrong byte
  no_err        an uncorrectable read is answered without err: the wrong
                word is delivered as data
  rd_raw        the read path returns the raw word: the codec detects
                and reports and corrects nothing the core sees
  sec_never     the report line sec_o is tied low: the repair is silent
  scrub_takes   the scrubber ignores the bus: a scrub write-back lands
                on top of a bus write in the same cycle
  ptr_stuck     the scrub pointer never advances: one row is scrubbed
                for ever and the rest never
  lane_swap     lane 1's check bits are computed from lane 0's data: a
                valid codeword on a clean write, wrong on every byte
                write to lane 1 alone

Every mutation is applied to the RTL text and asserted to have changed
it; a mutation that does not apply is a hard failure, not a pass. The
source list, the parameters and the seed are the suite's own.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
RTL = os.path.normpath(os.path.join(HERE, "..", "..", "rtl", "soc_mem_ecc.v"))

MUTATIONS = {
    "wb_raw": [
        ("  wire [31:0] enc_in = req_i ? wdata_i : rd_word;",
         "  wire [31:0] enc_in = req_i ? wdata_i : row_dout_i[31:0];"),
    ],
    "wb_on_ded": [
        ("        assign bm_wb[8*l +: 8]        = {8{sec[l]}};\n"
         "        assign bm_wb[32+8*l +: 8]     = {8{sec[l]}};",
         "        assign bm_wb[8*l +: 8]        = {8{sec[l] | ded[l]}};\n"
         "        assign bm_wb[32+8*l +: 8]     = {8{sec[l] | ded[l]}};"),
        ("      assign s_wb   = s_hit && sec_any;",
         "      assign s_wb   = s_hit && (sec_any || ded_any);"),
    ],
    "no_err": [
        ("  wire err0 = er0 || (rsp_rd && ded_any);",
         "  wire err0 = er0;"),
    ],
    "rd_raw": [
        ("        assign rd_word[8*l +: 8] = row_dout_i[8*l +: 8] ^ mask;",
         "        assign rd_word[8*l +: 8] = row_dout_i[8*l +: 8];"),
    ],
    "sec_never": [
        ("  assign sec_o      = s_wb;",
         "  assign sec_o      = 1'b0;"),
    ],
    "scrub_takes": [
        ("      assign s_hit  = srd_q && idle;",
         "      assign s_hit  = srd_q;"),
    ],
    "ptr_stuck": [
        ("          if (s_hit) sptr <= sptr + {{(AW-1){1'b0}}, 1'b1};",
         "          if (s_hit) sptr <= sptr;"),
    ],
    "lane_swap": [
        ("            .data_in   ({56'h0, enc_in[8*l +: 8]}),",
         "            .data_in   ({56'h0, enc_in[8*(l == 1 ? 0 : l) +: 8]}),"),
    ],
}


def run_suite(src, tag):
    env = dict(os.environ)
    build = os.path.join(HERE, "sim_build_mut_" + tag)
    results = os.path.join(HERE, "results_mut_%s.xml" % tag)
    if os.path.exists(results):
        os.remove(results)
    cmd = ["make", "-f", "Makefile.soc_mem",
           "SOC_MEM_ECC_SRC=" + src, "SIM_BUILD=" + build,
           "COCOTB_RESULTS_FILE=results_mut_%s.xml" % tag]
    subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True)
    if not os.path.exists(results):
        return None, None
    root = ET.parse(results).getroot()
    cases = [e for e in root.iter() if e.tag.endswith("testcase")]
    failed = [c.get("name") for c in cases
              if any(ch.tag.endswith(("failure", "error")) for ch in c)]
    shutil.rmtree(build, ignore_errors=True)
    os.remove(results)
    return len(cases), failed


def main():
    text = open(RTL).read()
    tmp = tempfile.mkdtemp(prefix="mutate_soc_mem_")
    caught = 0
    print("%-12s %6s  %s" % ("mutation", "tests", "failing tests"))
    for name, edits in MUTATIONS.items():
        mutant = text
        for old, new in edits:
            if old not in mutant:
                sys.exit("mutation %s does not apply: %r not in soc_mem_ecc.v"
                         % (name, old))
            mutant = mutant.replace(old, new)
        assert mutant != text
        path = os.path.join(tmp, "soc_mem_ecc_%s.v" % name)
        open(path, "w").write(mutant)
        n, failed = run_suite(path, name)
        if n is None:
            print("%-12s %6s  %s" % (name, "-", "no results: the build failed"))
            caught += 1
            continue
        print("%-12s %6d  %s" % (name, n, ", ".join(failed) if failed else "NONE"))
        if failed:
            caught += 1
    shutil.rmtree(tmp, ignore_errors=True)
    print("caught %d of %d" % (caught, len(MUTATIONS)))
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    sys.exit(main())
