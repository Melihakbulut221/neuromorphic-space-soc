#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""One mechanical rewrite of the sv2v output, so yosys-slang can read it.

docs/63 section 3. Same rule as hw/soc/flow/ibex_fault_port.py: a
generated file derived from a pinned input by a tracked script, never
vendored and never edited by hand. hw/soc/ext/ibex stays pristine and
hw/soc/genrvfi/ stays exactly what sv2v wrote.

WHY IT IS NEEDED. Ibex's RVFI block reads sixteen signals out of
submodules by hierarchical reference -- `id_stage_i.controller_i.exc_req_d`
and fifteen others. sv2v carries those through verbatim, and Yosys's
Verilog-2005 front end cannot resolve them: it treats each dotted name
as an implicitly declared net and fails width inference with
"Don't know how to detect sign and width for AST_AUTOWIRE node".
yosys-slang, which is in the pinned oss-cad-suite and which docs/38
section 6 already established reads this design, resolves them properly
-- and fails on exactly one other construct, the same one docs/38 found:

    ibex_top.sv:659  logic unused_scramble_inputs = <expression over nets>;

slang reports "reading net state during design initialization
unsupported" for each net in the initialiser. The fix docs/38 named is a
declaration plus a continuous assign, which is semantically identical.
docs/38 proposed doing it to Ibex; doing it HERE instead is what keeps
"patches required to Ibex: zero" true.

WHAT THIS DOES NOT DO. It does not touch anything else, it refuses to
run if the construct is not found exactly once, and it refuses to run if
it finds a second one -- so an upstream commit that adds another
initialiser of this shape is an error here and not a quietly different
core.

Usage: rvfi_slangfix.py <genrvfi dir> <out dir>
"""

import os
import re
import sys

DECL = re.compile(
    r'^(?P<ind>[ \t]*)reg (?P<name>unused_scramble_inputs) = (?P<rhs>.*);[ \t]*$',
    re.M)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(__doc__)
        return 2
    src_dir, out_dir = argv[1], argv[2]
    src = os.path.join(src_dir, "ibex_top.v")
    if not os.path.isfile(src):
        sys.stderr.write(f"rvfi_slangfix: no such file: {src}\n")
        return 2

    text = open(src).read()
    hits = DECL.findall(text)
    if len(hits) != 1:
        sys.stderr.write(
            f"rvfi_slangfix: expected exactly ONE 'reg unused_scramble_inputs ='\n"
            f"               declaration in {src}, found {len(hits)}. The pinned\n"
            f"               Ibex commit has moved; re-read docs/63 section 3\n"
            f"               before changing this number.\n")
        return 1

    fixed = DECL.sub(
        lambda m: (f"{m.group('ind')}wire {m.group('name')};\n"
                   f"{m.group('ind')}assign {m.group('name')} = {m.group('rhs')};"),
        text)

    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, "ibex_top.v")
    with open(dst, "w") as f:
        f.write(fixed)

    added = len(fixed.splitlines()) - len(text.splitlines())
    sys.stderr.write(
        f"== rvfi_slangfix: 1 declaration rewritten in ibex_top.v "
        f"(+{added} line), written to {dst}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
