#!/usr/bin/env python3
"""Give `ibex_top` one output port, so a corrected upset can be counted.

    ibex_fault_port.py <gen_dir> <out_dir> [secded|upstream]

=======================================================================
WHY THIS FILE EXISTS AT ALL
=======================================================================

`docs/43-core-hardening.md` put a SECDED codec around the architectural
register file and then said, in section 6.5 and again as the first
bullet of section 10, that nothing could read its report:

    the correction is SILENT: in silicon, a corrected upset is
    indistinguishable from no upset at all

and section 12 ranked closing that first, because an unobservable
correction is indistinguishable from an absent one at any distance
greater than a simulator. A spacecraft that cannot count its corrected
upsets cannot tell a healthy part from one about to fail, and this
project's own pilot learned the same lesson the same way -- `pilot_top.v`
carried four unconnected ECC status wires until 2026-08-27, so a
campaign measured 84 corrections and had to classify every one MASKED.

docs/43 also said what closing it would cost: "a port on `ibex_top` --
a patch to Ibex, which section 3 explains the price of -- or a route out
of the core that does not exist yet."

THERE IS NO SUCH ROUTE, and this was checked rather than assumed:

  * `alert_major_internal_o` DOES leave `ibex_top` and IS already
    connected in `soc_top.v`, and in `ibex_core.v` it is
    `rf_ecc_err_comb | pc_mismatch_alert | csr_shadow_err | ...`. But
    `rf_ecc_err_comb` is `1'b0` unless `RegFileECC`, and `RegFileECC`
    follows `SecureIbex`, and turning it on makes `ibex_core`
    instantiate `prim_secded_inv_39_32_{enc,dec}` -- the SECOND codec on
    one die that `docs/38` section 8.5 declined `SecureIbex` over. The
    route exists; its gate is the thing this project refuses to buy.
  * The register file's own unused ports (`rcap_a_o`, `rcap_b_o`) go
    INTO `ibex_core` and stop there. They reach no boundary.
  * Verilog has no other channel out of a module.

So a port it is, and this file is the smallest form of it: THREE HUNKS
IN ONE GENERATED FILE, applied mechanically and never committed.

=======================================================================
WHAT IT COSTS THE PINNING STORY, PLAINLY
=======================================================================

`docs/38` section 4.2's headline is "patches required to Ibex for the
sv2v path: zero", and `docs/43` section 3 already recorded what
substituting the register file did to it. This does more, and the
document that ships it has to say so rather than let a reader discover
it:

  1. `hw/soc/ext/ibex` IS STILL PRISTINE and `hw/soc/gen` IS STILL
     UNEDITED. This reads `gen/ibex_top.v` and writes `genp/ibex_top.v`;
     it never writes to its input. `git -C hw/soc/ext/ibex status` is
     still clean and `hw/soc/gen` is still exactly what `sv2v_ibex.sh`
     produced.
  2. BUT THE BUILD'S `ibex_top` IS NO LONGER THE ONE sv2v EMITTED. That
     is a patch to Ibex in every sense that matters, and calling it a
     "generated file" does not make it not one. What is true is that it
     is DERIVED rather than VENDORED: nothing here is committed, the
     three hunks are visible in eighty lines of Python, and regenerating
     from a moved pin re-applies them or fails.
  3. IT FAILS LOUDLY OR NOT AT ALL. Every anchor below is asserted to
     occur EXACTLY ONCE in the input. A pin that moves the port list, or
     renames `alert_major_bus_o`, or restructures the register file
     instantiation, stops the build with the anchor named -- it does not
     silently patch the wrong place. That is the one property a
     text-substitution patch has to have, and it is why this is a
     Python script with assertions rather than a `.patch` file whose
     context would match three near-identical register-file
     instantiations equally well.
  4. THE OBLIGATION IS REAL AND IT IS NEW. `docs/43` section 3 cost 3
     already required `ibex_regfile_secded.v` to be re-read against
     upstream whenever the pin moves. This adds `ibex_top`'s port list
     and its register-file instantiation to that reading.

=======================================================================
WHAT IT DOES
=======================================================================

    output wire [2:0] rf_ecc_err_o;        <- new port on ibex_top

At `secded` it is driven by the substituted register file's own port; at
`upstream` it is tied to zero, because upstream's register file has no
codec and therefore nothing to report. BOTH MODES GET THE PORT, and that
is deliberate: `soc_top.v` connects it unconditionally, so the
`IBEX_REGFILE=upstream` isolation builds `docs/43` section 5.4 depends on
keep working and report an honest zero, and no `ifdef` has to be kept in
step with a file list.

An unpatched `ibex_top` under a `soc_top` that connects the port fails at
elaboration with the port's name in the message. That is the coupling
between this script and `soc_top.v`, and it is loud by construction.
"""

import pathlib
import sys

PORT = "rf_ecc_err_o"

# The three anchors. Each is asserted to occur exactly once.
A_PORTLIST = "\talert_major_bus_o,\n"
A_DECL = "\toutput wire alert_major_bus_o;\n"
A_INSTANCE = "\t\t\tibex_register_file_ff #(\n"
A_LASTCONN = "\t\t\t\t.we_a_i(rf_we_wb)\n"


def _once(text, needle, what):
    n = text.count(needle)
    if n != 1:
        raise SystemExit(
            "ibex_fault_port.py: anchor for {} occurs {} times in "
            "ibex_top.v, expected exactly once.\n"
            "  anchor: {!r}\n"
            "The pinned Ibex has moved under this patch. Re-read\n"
            "hw/soc/gen/ibex_top.v against it before going further; do "
            "NOT relax the anchor.".format(what, n, needle))
    return n


def patch(text, mode):
    _once(text, A_PORTLIST, "the port list entry")
    _once(text, A_DECL, "the port declaration")
    _once(text, A_INSTANCE, "the register file instantiation")

    text = text.replace(A_PORTLIST, A_PORTLIST + "\t%s,\n" % PORT)
    text = text.replace(
        A_DECL,
        A_DECL
        + "\t// hw/soc/flow/ibex_fault_port.py -- docs/44 section 4.\n"
          "\t// {2, 1, 0} = {DED, corrected on read, corrected by the "
          "scrub}.\n"
          "\toutput wire [2:0] %s;\n" % PORT)

    if mode == "secded":
        # The last connection of the FF branch's instantiation. The
        # string itself appears three times -- the _ff, _fpga and _latch
        # branches are near-identical -- so it is located RELATIVE TO the
        # (unique) _ff instantiation rather than matched globally. This
        # is the hunk a `.patch` file could not place unambiguously.
        at = text.index(A_INSTANCE)
        conn = text.index(A_LASTCONN, at)
        text = (text[:conn]
                + A_LASTCONN.rstrip("\n") + ",\n"
                + "\t\t\t\t.%s(%s)\n" % (PORT, PORT)
                + text[conn + len(A_LASTCONN):])
    else:
        # upstream's register file has no codec, so it has nothing to
        # report and the port says so. Placed immediately before the
        # `endmodule`, which sv2v emits exactly once.
        _once(text, "\nendmodule\n", "the end of ibex_top")
        text = text.replace(
            "\nendmodule\n",
            "\n\t// IBEX_REGFILE=upstream: no codec, nothing to report.\n"
            "\tassign %s = 3'b000;\n"
            "endmodule\n" % PORT)
    return text


def main(argv):
    if len(argv) not in (3, 4):
        raise SystemExit(__doc__.strip().splitlines()[2].strip())
    gen = pathlib.Path(argv[1])
    out = pathlib.Path(argv[2])
    mode = argv[3] if len(argv) == 4 else "secded"
    if mode not in ("secded", "upstream"):
        raise SystemExit("mode must be 'secded' or 'upstream', got %r" % mode)

    src = gen / "ibex_top.v"
    if not src.is_file():
        raise SystemExit(
            "%s does not exist: run hw/soc/flow/sv2v_ibex.sh first" % src)

    out.mkdir(parents=True, exist_ok=True)
    dst = out / "ibex_top.v"
    dst.write_text(patch(src.read_text(), mode))
    print("wrote %s (mode=%s)" % (dst, mode))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
