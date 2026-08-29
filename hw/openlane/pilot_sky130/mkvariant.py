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
