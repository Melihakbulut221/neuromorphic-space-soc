#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Build the SCHEMATIC side of an LVS comparison from a Verilog netlist.

    verilog_to_spice.py <netlist.v> <out.spice> [--macro-blackbox ...]

WHY THIS EXISTS. `docs/54` open item 4 has stayed open through three
restatements, and the block written 2026-09-12 explains that it is not a
deck waiting to be run: the KLayout LVS deck takes its schematic side
through `RBA::NetlistSpiceReader` and nothing else, and every `.spice`
under `hw/soc/pnr/runs/` begins `* NGSPICE file created from
soc_top.ext` -- they are all Magic's extraction of the LAYOUT. Handing
one to the deck as the schematic would compare the layout with itself,
which passes and means nothing.

So the item was "build a Verilog-to-SPICE path", and this is it.

THE FORK THIS SCRIPT TAKES, AND WHY. `docs/54`'s 2026-09-13 block
measured both branches with Netgen on the eight-macro layout. Supplying
the vendor CDL fails -- 64,901 netlist nets against 63,155 layout nets
and a top-level pin-matching failure -- and the cause is NAMING, not
connectivity: the CDL spells buses `A_DIN<32>` and globals `VSS!`,
`VDD!` where the layout has `A_DIN[32]`, `VSS`, `VDD`. Black-boxing the
macro on both sides matches uniquely. This script therefore emits the
macros as empty subcircuits with their pin lists, which is the branch
that compares.

WHAT THAT MEANS FOR A READER, stated because the passing branch is the
weaker one: the comparison it enables checks top-level connectivity into
the macro pins and nothing inside them. That is the correct scope given
`docs/12` section 7.5's NO-GO on this macro in this PDK version, and it
is a smaller claim than "LVS passes".
"""
import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
PDK = pathlib.Path.home() / (
    ".ciel/ciel/ihp-sg13g2/versions/"
    "c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c/ihp-sg13g2")
# The cells come from LIBERTY, not from the vendor Verilog. That file's
# `specify` blocks use the conditional path form -- `if (B1 == 1\'b0)
# (A1 => X) = 0;` -- which yosys 0.33 rejects even with -specify, and
# the timing in it is not wanted here anyway: LVS needs port names and
# directions, which is exactly what read_liberty -lib supplies.
STDCELL_LIB = PDK / ("libs.ref/sg13g2_stdcell/lib/"
                     "sg13g2_stdcell_typ_1p20V_25C.lib")
MACRO_BB = sorted((ROOT / "hw" / "soc" / "pnr").glob("RM_IHPSG13_*_bb.v"))


def _yosys():
    for c in ("yosys", str(pathlib.Path.home() / ".local/bin/yosys")):
        try:
            subprocess.run([c, "-V"], capture_output=True, check=True)
            return c
        except (OSError, subprocess.CalledProcessError):
            continue
    sys.exit("no yosys on PATH")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("out")
    ap.add_argument("--top", default="soc_top")
    a = ap.parse_args()

    assert STDCELL_LIB.is_file(), "no standard-cell Liberty at {}".format(STDCELL_LIB)
    assert MACRO_BB, "no macro black-box Verilog under hw/soc/pnr/"

    # -lib reads a module as a BLACK BOX: its ports are kept and its body
    # discarded. That is exactly the abstraction the layout side has, so
    # reading both the cells and the macros this way is what makes the
    # two sides comparable rather than merely both present.
    reads = ['read_liberty -lib {}'.format(STDCELL_LIB)]
    reads += ['read_verilog -lib {}'.format(m) for m in MACRO_BB]
    reads.append('read_verilog {}'.format(a.netlist))
    script = "; ".join(reads + [
        "hierarchy -top {}".format(a.top),
        "write_spice {}".format(a.out),
    ])

    out = subprocess.run([_yosys(), "-p", script], capture_output=True,
                         text=True, cwd=str(ROOT))
    if out.returncode != 0:
        sys.stderr.write(out.stdout[-4000:] + out.stderr[-4000:])
        sys.exit("yosys failed")

    text = pathlib.Path(a.out).read_text()

    # yosys writes the top module as a bare instance list -- no .subckt,
    # no .ends, no .end -- and the deck needs the wrapper. The port list
    # is read from the netlist's own declarations, buses expanded to
    # bits the way write_spice already expanded them on the instances.
    ports = []
    for m in re.finditer(r"^\s*(?:input|output|inout)\s+(?:\[(\d+):(\d+)\]\s+)?"
                         r"([A-Za-z_][\w$]*)\s*;", pathlib.Path(a.netlist)
                         .read_text(errors="ignore"), re.M):
        hi, lo, name = m.groups()
        if hi is None:
            ports.append(name)
        else:
            ports += ["{}[{}]".format(name, i)
                      for i in range(int(lo), int(hi) + 1)]
    assert ports, "no port declarations found in the netlist"
    body = text[text.index("\nX"):] if "\nX" in text else text
    text = (text[:text.index("\nX")] + "\n.SUBCKT {} {}".format(a.top, " ".join(ports))
            + body + "\n.ENDS {}\n.END\n".format(a.top))
    subckts = len(re.findall(r"^\.SUBCKT ", text, re.M | re.I))
    lines = text.count("\n")

    # The header Magic writes on the LAYOUT side begins "* NGSPICE file
    # created from soc_top.ext". Ours must NOT, or the next person cannot
    # tell the two sides apart -- which is the confusion docs/54 warns
    # about when it says feeding an extracted file as the schematic
    # compares the layout with itself.
    assert "created from" not in text.splitlines()[0], \
        "this file must not carry Magic's extraction header"
    banner = ("* SCHEMATIC side, generated by hw/soc/pnr/lvs/"
              "verilog_to_spice.py from\n* {}\n* Vendor macros are EMPTY "
              "subcircuits: this compares connectivity INTO their pins\n"
              "* and nothing inside them. See docs/54 section 12 item 4.\n"
              .format(a.netlist))
    pathlib.Path(a.out).write_text(banner + text)

    print("wrote {}  ({} subcircuits, {} lines)".format(a.out, subckts, lines))
    print("macros black-boxed: {}".format(
        ", ".join(m.stem.replace("_bb", "") for m in MACRO_BB)))


if __name__ == "__main__":
    main()
