#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""Break one module on purpose, so that the equivalence check can be
seen to fail.

    python3 formal/eqy/mutate.py voter out/mutant_tmr_voter.v
    python3 formal/eqy/mutate.py dec   out/mutant_secded_dec.v

A checker that has never returned red is not a checker. These two
mutations are the negative controls of `formal/eqy/Makefile`, and the
Makefile treats a control that PASSES as an error.

Both are chosen to be invisible to every other instrument in the
repository. The voter mutation drops one term of the majority function:
the module still has the same ports, the same zero flip-flops, and the
same cell count after mapping, so a flip-flop census cannot see it --
which is the whole reason `tmr_voter` is the first module checked here.
The decoder mutation flips one bit of one parity row: the codec still
encodes and decodes, still corrects most single-bit errors, and still
passes a smoke test; what it loses is the property `formal/secded.sby`
proves.

Each mutation asserts that it changed something. A mutation that does
not apply is a control that reports success while testing nothing,
which is the failure this file exists to prevent.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

MUTATIONS = {
    # Drop the (in_b & in_c) term. Two of three still vote when A is one
    # of the two, so this is wrong only when A is the odd one out --
    # precisely the case TMR exists for.
    "voter": (
        "hw/rtl/tmr_voter.v",
        "assign out = (in_a & in_b) | (in_a & in_c) | (in_b & in_c);",
        "assign out = (in_a & in_b) | (in_a & in_c);",
    ),
    # Flip the low bit of H_ROW3. The Hsiao matrix's guarantee is that
    # every column is distinct, nonzero and odd weight; this breaks the
    # weight of one column and so breaks double-error detection for it.
    "dec": (
        "hw/rtl/secded_dec.v",
        "H_ROW3 = 64'h8F2111C22388E38E;",
        "H_ROW3 = 64'h8F2111C22388E38F;",
    ),
}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in MUTATIONS:
        raise SystemExit(f"usage: mutate.py {{{'|'.join(MUTATIONS)}}} <out.v>")
    rel, old, new = MUTATIONS[sys.argv[1]]
    src = (ROOT / rel).read_text()
    if src.count(old) != 1:
        raise SystemExit(
            f"mutate.py: {rel} no longer contains exactly one\n  {old}\n"
            "The mutation did not apply, so the negative control would test "
            "nothing. Re-read the file and update MUTATIONS.")
    pathlib.Path(sys.argv[2]).write_text(src.replace(old, new))
    print(f"mutated {rel} -> {sys.argv[2]}: {old.strip()} => {new.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
