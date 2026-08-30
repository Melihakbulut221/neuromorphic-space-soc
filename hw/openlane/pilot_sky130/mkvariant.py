#!/usr/bin/env python3
"""Generate a corner-experiment variant of config.json.

Written for the docs/20 PNR_CORNERS experiments. A variant must be
byte-identical to the baseline except for a small, named set of keys,
otherwise a difference in the result cannot be attributed to the knob
under test. Hand-copying a 60-key config invites exactly that drift, so
the variants are generated: this script reads config.json, applies one
named delta from the table below, and writes config.<name>.json beside
the baseline.

Beside it on purpose. Every `dir::` path in config.json -- the RTL
sources, the include directory, the pin-frame DEF template -- resolves
relative to the directory holding the config file. A variant written
anywhere else would resolve to different files without erroring.

The `//variant` key it emits records the delta in the artefact itself,
so a run directory's resolved.json is self-describing.

Usage:
    ./mkvariant.py pnrcorners
    ./mkvariant.py --list
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "config.json")

# Each entry: (one-line rationale, {key: value}).
#
# Corner names are the sky130A STA_CORNERS as LibreLane resolves them
# (see any runs/*/resolved.json): <interconnect>_<process>_<temp>_<volt>,
# nine of them, nom/min/max crossed with tt/ss/ff.
VARIANTS = {
    "pnrcorners": (
        "docs/18's named hypothesis: make the failing corner visible to the "
        "PnR optimization loop instead of only to the final sign-off STA. "
        "max_ss_100C_1v60 is the corner that misses setup by 3.85 ns in "
        "sky-02-signoff; DEFAULT_CORNER is kept in the list so the baseline "
        "behaviour is a subset of this one rather than replaced by it.",
        {
            "PNR_CORNERS": ["nom_tt_025C_1v80", "max_ss_100C_1v60"],
        },
    ),
    "postgrt": (
        "The follow-on hypothesis. Same PNR_CORNERS as the pnrcorners "
        "variant, plus the two repair steps the Classic flow skips by "
        "default. Both are ResizerSteps, so both already load all nine "
        "STA_CORNERS; what they add is a repair pass that runs AFTER "
        "global routing, on GRT-estimated parasitics rather than on the "
        "pre-route wire-load estimate the post-CTS resizer works from.",
        {
            "PNR_CORNERS": ["nom_tt_025C_1v80", "max_ss_100C_1v60"],
            "RUN_POST_GRT_DESIGN_REPAIR": True,
            "RUN_POST_GRT_RESIZER_TIMING": True,
        },
    ),
    # docs/23. The twelve-tile shape decision is taken on ihp-sg13g2,
    # which is the shuttle PDK; these two exist so the cross-PDK claim of
    # docs/18 can be re-measured at the shape that wins rather than
    # staying stale at a 4x2 that stopped routing (docs/22 section 5).
    # DIE_AREA is copied verbatim from tt/tt/tech/sky130A/tile_sizes.yaml
    # and the DEF is the matching `pg` pin-frame from the same clone, so
    # the sky130 tile geometry is the tooling's own and not a conversion
    # of the IHP one. 3x4 is the larger of the two shapes in both PDKs by
    # closely similar margins -- 452,649 / 404,499 = +11.90 % on IHP,
    # 260,160 / 232,623 = +11.84 % on sky130 -- but that is read off the
    # two tile_sizes.yaml files, not assumed from one of them.
    "3x4": (
        "docs/23: the 3x4 twelve-tile shape, 508.76 x 511.36 um of sky130A "
        "die. Two keys against the 4x2 baseline, both taken from "
        "tt/tt/tech/sky130A.",
        {
            "DIE_AREA": "0 0 508.76 511.36",
            "FP_DEF_TEMPLATE": "dir::../../../tt/tt/tech/sky130A/def/tt_block_3x4_pg.def",
        },
    ),
    "6x2": (
        "docs/23: the 6x2 twelve-tile shape, 1030.40 x 225.76 um of sky130A "
        "die. Two keys against the 4x2 baseline, both taken from "
        "tt/tt/tech/sky130A.",
        {
            "DIE_AREA": "0 0 1030.40 225.76",
            "FP_DEF_TEMPLATE": "dir::../../../tt/tt/tech/sky130A/def/tt_block_6x2_pg.def",
        },
    ),
    # docs/25. docs/23 open item 6 records that docs/18's PNR_CORNERS
    # hypothesis was never re-tested at twelve tiles: docs/20 section 5
    # tested it at 4x2, where the design still routed, and docs/22
    # section 5 removed the routed netlist that a re-test needs. This is
    # the 6x2 arm. It is the "6x2" delta plus the "pnrcorners" delta and
    # nothing else, so a difference against the 6x2 baseline is
    # attributable to PNR_CORNERS alone.
    "6x2-pnrcorners": (
        "docs/25: the 6x2 shape with docs/18's named hypothesis applied. "
        "max_ss_100C_1v60 is the corner the 6x2 sign-off misses by "
        "7.3054 ns; nom_tt_025C_1v80 is DEFAULT_CORNER and is kept in the "
        "list so the baseline behaviour is a subset of this one rather "
        "than replaced by it, exactly as in the 4x2 arm of docs/20 "
        "section 5.1.",
        {
            "DIE_AREA": "0 0 1030.40 225.76",
            "FP_DEF_TEMPLATE": "dir::../../../tt/tt/tech/sky130A/def/tt_block_6x2_pg.def",
            "PNR_CORNERS": ["nom_tt_025C_1v80", "max_ss_100C_1v60"],
        },
    ),
    # docs/25 section 7. `LAYERS_RC` is the docs/20 section 6.3 candidate
    # that outranks PNR_CORNERS and had never been run.
    #
    # Why it is the right instrument, and why nothing here is a fitted
    # number. sky130A ships THREE tech LEFs -- `sky130_fd_sc_hd__nom`,
    # `__min` and `__max` -- and LibreLane maps them onto the corner
    # prefixes in TECH_LEFS. But OpenROAD's ODB holds exactly one
    # technology, read once by `13-openroad-floorplan` and carried in the
    # ODB from there, and the one it reads is `nom` (DEFAULT_CORNER is
    # `nom_tt_025C_1v80`). So the `max` interconnect model is not present
    # inside place-and-route at all, for any step, whatever PNR_CORNERS,
    # RSZ_CORNERS or CTS_CORNERS say. LAYERS_RC is the only channel
    # through which a per-corner wire RC can enter PnR.
    #
    # The values below are the three tech LEFs' own RPERSQ /
    # CPERSQDIST / EDGECAPACITANCE, converted by exactly the formula
    # `set_layers_default_rc` in `librelane/scripts/openroad/common/set_rc.tcl`
    # applies to the one LEF it has -- res = RPERSQ / WIDTH in kohm/um,
    # cap = CPERSQDIST * WIDTH + 2 * EDGECAPACITANCE in pF/um. So this
    # variant hands PnR the data the PDK already ships and the flow
    # already knows how to read; it does not invent a corner.
    "6x2-layersrc": (
        "docs/25: the 6x2 shape with a per-corner LAYERS_RC built from "
        "sky130A's own nom/min/max tech LEFs, so that the max interconnect "
        "model exists inside place-and-route instead of only in OpenRCX. "
        "One key against the 6x2 baseline.",
        {
            "DIE_AREA": "0 0 1030.40 225.76",
            "FP_DEF_TEMPLATE": "dir::../../../tt/tt/tech/sky130A/def/tt_block_6x2_pg.def",
            "LAYERS_RC": {
                "nom_*": {
                    "li1": {"res": 0.0752941176, "cap": 8.76817e-05},
                    "met1": {"res": 0.0008928571, "cap": 8.4743e-05},
                    "met2": {"res": 0.0008928571, "cap": 7.78899e-05},
                    "met3": {"res": 0.0001566667, "cap": 8.56899e-05},
                    "met4": {"res": 0.0001566667, "cap": 7.58766e-05},
                    "met5": {"res": 1.78125e-05, "cap": 8.7815e-05},
                },
                "min_*": {
                    "li1": {"res": 0.0541176471, "cap": 8.76817e-05},
                    "met1": {"res": 0.00075, "cap": 8.4743e-05},
                    "met2": {"res": 0.00075, "cap": 7.78899e-05},
                    "met3": {"res": 0.0001266667, "cap": 8.56899e-05},
                    "met4": {"res": 0.0001266667, "cap": 7.58766e-05},
                    "met5": {"res": 1.325e-05, "cap": 8.7815e-05},
                },
                "max_*": {
                    "li1": {"res": 0.1, "cap": 8.76817e-05},
                    "met1": {"res": 0.0010357143, "cap": 8.4743e-05},
                    "met2": {"res": 0.0010357143, "cap": 7.78899e-05},
                    "met3": {"res": 0.0001866667, "cap": 8.56899e-05},
                    "met4": {"res": 0.0001866667, "cap": 7.58766e-05},
                    "met5": {"res": 2.2375e-05, "cap": 8.7815e-05},
                },
            },
        },
    ),
    # docs/25 section 7. The upper bound: the best wire model the PDK's
    # own data supports, all three known terms at once. It is deliberately
    # a bundle and not a single-variable arm -- the 6x2-layersrc run above
    # isolates the corner term, and this one answers the different
    # question of whether the parasitic model is the WHOLE story.
    #
    # Term 2, layer mix. `set_wire_rc` averages over the constrained
    # routing layers and `14-openroad-dumprcvalues` prints what that
    # average is: Signal Avg 4.402703e-04 kohm/um. The design does not
    # route that way -- at 6x2 it puts 190,189 um on met1 and 159,961 um
    # on met2 against 75,808 um on met3 and 6,454 um on met4, so 81.0 % of
    # its length is on the two layers that are 5.70x more resistive than
    # the other two, and the usage-weighted figure is 7.528e-04. The
    # estimate is 1.71x optimistic. Restricting SIGNAL_WIRE_RC_LAYERS to
    # met1 and met2 gives 8.929e-04.
    #
    # Term 3, vias. `resizer_values_after.rpt` reports every via cut
    # resistance as 0.000000e+00, while the tech LEF declares mcon 9.30,
    # via 4.50, via2 3.41 and via3 3.41 (kohm) and the 6x2 route contains
    # 76,686 vias. `RCX_MERGE_VIA_WIRE_RES` is true, so extraction charges
    # them and PnR does not. VIAS_R is the only lever on this.
    #
    # VIAS_R is applied under "*" and not per corner ON PURPOSE. In
    # LibreLane 3.0.5 `openroad.py:407` passes the VIAS_R corner wildcard
    # to `Filter()` as a bare string where `LAYERS_RC` at :400 passes
    # `Filter([wildcard])`; `Filter.__init__` iterates its argument, so a
    # string wildcard is split per character and any wildcard containing
    # `*` then matches every corner. Verified directly. So the nom values
    # are used, which is the tech LEF the ODB actually carries; the
    # nom-to-max via spread (mcon 9.30 -> 23.0) stays unmodelled and
    # docs/25 section 7 says so.
    "6x2-rcmodel": (
        "docs/25: the 6x2 shape with all three parasitic-model terms "
        "corrected from PDK-shipped data at once -- per-corner LAYERS_RC, "
        "SIGNAL_WIRE_RC_LAYERS restricted to the layers the design "
        "actually routes on, and non-zero via resistance. A bundle, not a "
        "single-variable arm.",
        {
            "DIE_AREA": "0 0 1030.40 225.76",
            "FP_DEF_TEMPLATE": "dir::../../../tt/tt/tech/sky130A/def/tt_block_6x2_pg.def",
            "LAYERS_RC": {
                "nom_*": {
                    "li1": {"res": 0.0752941176, "cap": 8.76817e-05},
                    "met1": {"res": 0.0008928571, "cap": 8.4743e-05},
                    "met2": {"res": 0.0008928571, "cap": 7.78899e-05},
                    "met3": {"res": 0.0001566667, "cap": 8.56899e-05},
                    "met4": {"res": 0.0001566667, "cap": 7.58766e-05},
                    "met5": {"res": 1.78125e-05, "cap": 8.7815e-05},
                },
                "min_*": {
                    "li1": {"res": 0.0541176471, "cap": 8.76817e-05},
                    "met1": {"res": 0.00075, "cap": 8.4743e-05},
                    "met2": {"res": 0.00075, "cap": 7.78899e-05},
                    "met3": {"res": 0.0001266667, "cap": 8.56899e-05},
                    "met4": {"res": 0.0001266667, "cap": 7.58766e-05},
                    "met5": {"res": 1.325e-05, "cap": 8.7815e-05},
                },
                "max_*": {
                    "li1": {"res": 0.1, "cap": 8.76817e-05},
                    "met1": {"res": 0.0010357143, "cap": 8.4743e-05},
                    "met2": {"res": 0.0010357143, "cap": 7.78899e-05},
                    "met3": {"res": 0.0001866667, "cap": 8.56899e-05},
                    "met4": {"res": 0.0001866667, "cap": 7.58766e-05},
                    "met5": {"res": 2.2375e-05, "cap": 8.7815e-05},
                },
            },
            "SIGNAL_WIRE_RC_LAYERS": ["met1", "met2"],
            "VIAS_R": {
                "*": {
                    "mcon": {"res": 0.0093},
                    "via": {"res": 0.0045},
                    "via2": {"res": 0.00341},
                    "via3": {"res": 0.00341},
                },
            },
        },
    ),
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 1
    name = sys.argv[1]
    if name == "--list":
        for k, (why, delta) in VARIANTS.items():
            print(f"{k}: {json.dumps(delta)}")
            print(f"    {why}")
        return 0
    if name not in VARIANTS:
        print(f"unknown variant {name!r}; try --list", file=sys.stderr)
        return 1

    why, delta = VARIANTS[name]

    # object_pairs_hook=list keeps the duplicate "//" comment keys that
    # the baseline inherits from the Tiny Tapeout config. A plain
    # json.load would collapse them and the variant would quietly lose
    # the documentation the baseline carries.
    pairs = json.load(open(BASE), object_pairs_hook=list)

    out, applied = [], set()
    for k, v in pairs:
        if k in delta:
            out.append((k, delta[k]))
            applied.add(k)
        else:
            out.append((k, v))
    out.append(("//variant", f"GENERATED by mkvariant.py {name} -- {why}"))
    for k, v in delta.items():
        if k not in applied:
            out.append((k, v))

    dest = os.path.join(HERE, f"config.{name}.json")
    with open(dest, "w") as f:
        # Duplicate keys are legal JSON and LibreLane's parser keeps the
        # last, which is what the baseline already relies on, so the file
        # is assembled textually rather than through a dict.
        f.write("{\n")
        f.write(",\n".join(f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in out))
        f.write("\n}\n")
    print(dest)
    for k in delta:
        print(f"  {k} = {json.dumps(delta[k])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
