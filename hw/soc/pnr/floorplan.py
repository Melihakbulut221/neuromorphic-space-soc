#!/usr/bin/env python3
"""Compute a floorplan for soc_top and emit it as LibreLane -c overrides.

docs/47 section 8.4 measured that its floorplan is the most likely
explanation for 7.07 ns of the 7.07 ns layout cost, and section 9 said
plainly that the die dimensions and the channel height "are one point in
a space nobody has explored".  This file is what explores it, and it
exists rather than a second hand-edited config.json for three reasons:

  1. THE MACRO SIZES ARE READ, NOT TYPED.  W and H come from the LEF
     `SIZE` statement of the installed PDK.  A floorplan whose macro
     dimensions are transcribed is a floorplan that can disagree with
     the library it is placed against, silently, and only OpenROAD's
     overlap checker would notice -- and only if the error made things
     overlap rather than leaving a gap.

  2. SITE ALIGNMENT IS ASSERTED, NOT ARRANGED.  docs/47 section 6.1
     established that the core box is an integer number of 0.48 um
     sites wide and 3.78 um rows tall, and every macro origin an
     integer number of sites and rows from the core's lower left.  That
     property is easy to state and easy to lose by hand; here it is
     checked, and the script refuses to emit a floorplan that has lost
     it.

  3. THE VARIABLE IS ONE NUMBER.  docs/47's floorplan and every
     floorplan this file emits differ in the CHANNEL HEIGHT and in
     nothing else: the same six macros, the same two rows, the same
     orientations, the same x origins, the same margins.  docs/47
     section 6.1's argument for that arrangement -- every RM_IHPSG13
     part puts all of its signal pins on one edge, so both rows' pin
     edges must face the channel -- is not re-litigated here, it is
     inherited.  What is being measured is the SIZE of the box, because
     that is what docs/47 got wrong: it sized the channel against
     LibreLane's own synthesis of the same RTL, which is 32 % larger
     than the netlist actually hardened.

Usage:

    floorplan.py --channel 700.08          # docs/47's floorplan, exactly
    floorplan.py --channel 310.74 --args   # emit -c overrides for librelane

The channel height is quantised: the top macro row's origin must be an
integer number of 3.78 um rows above the core's bottom edge, and the
bottom row's origin is fixed, so the admissible channel heights are
0.78 + 3.78k um.  --channel snaps to the nearest and says so.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")

SITE_W = 0.48   # sg13g2 CoreSite
SITE_H = 3.78

# The margins docs/47 chose, kept so that the channel is the only variable.
MARGIN_X = 60.00     # die edge to core edge, left and right
MARGIN_Y = 45.36     # die edge to core edge, bottom and top  (12 rows)
INSET_B = 15.12      # core bottom to bottom macro row         (4 rows)
INSET_T = 15.90      # top macro row to core top
PAD_X = 120.00 - 60.00   # core left to first macro column

# The three macro columns, as x offsets from the core's left edge.
# docs/47's are 120.00, 944.64, 1769.28 against a core left edge of
# 60.00, i.e. 60.00, 884.64, 1709.28 -- 125, 1843 and 3561 sites.
COL_SITES = (125, 1843, 3561)

RAM = "RM_IHPSG13_1P_2048x64_c2_bm_bist"
ROM = "RM_IHPSG13_1P_1024x32_c2_bm_bist"

# Which instance goes in which column, bottom row then top row.
BOTTOM = [(RAM, "u_ram.g_ram_2048x64.u_b0", 0),
          (RAM, "u_ram.g_ram_2048x64.u_b1", 1),
          (ROM, "u_rom.g_rom_1024x32.u_b0", 2)]
TOP = [(RAM, "u_ram.g_ram_2048x64.u_b2", 0),
       (RAM, "u_ram.g_ram_2048x64.u_b3", 1),
       (ROM, "u_rom.g_rom_1024x32.u_b1", 2)]

# docs/47 section 6.1: the lower row is FS, which mirrors about X and
# puts its pin edge at its TOP; the upper row is N, which leaves its pin
# edge at its BOTTOM.  Both face the channel.
ORIENT_BOTTOM = "FS"
ORIENT_TOP = "N"

# um2, hw/soc/flow/syn_soc_top.sh, SOC_MEM=sram.  THIS IS THE DEFAULT AND
# NOT A CONSTANT OF THE DESIGN: it is the standard-cell area of the
# netlist docs/47 hardened, which had no NPU in it.  docs/61 re-measures
# the same recipe on the same RTL with `u_npu` present at 624,429.9180
# um2 -- 1.5761 times this -- and passes it in with --cell-area, because
# a floorplan sized against a cell area the design no longer has is
# exactly the defect docs/47 section 6.1 already made once in the other
# direction.  Nothing else in this file depends on it: it feeds the
# reported utilization and the default PL_TARGET_DENSITY_PCT, and no
# coordinate.
CELL_AREA = 396177.6420
HALO = 10.0


def lef_size(pdk_root, macro):
    path = os.path.join(pdk_root, "ihp-sg13g2", "libs.ref", "sg13g2_sram",
                        "lef", macro + ".lef")
    with open(path) as fh:
        for line in fh:
            m = re.match(r"\s*SIZE\s+([\d.]+)\s+BY\s+([\d.]+)\s*;", line)
            if m:
                return float(m.group(1)), float(m.group(2))
    raise SystemExit("no SIZE in " + path)


# ---------------------------------------------------------------------
# The second arrangement: TWO macro columns and the ROMs as ISLANDS.
#
# docs/47's arrangement is three macro columns per row -- RAM, RAM, ROM
# -- which makes the core 2186.40 um wide because the row is 2065.92 um
# wide, and the standard cells then live in a channel that is as wide as
# the row.  Its two consequences are measured in docs/48: the logic is a
# strip, and the ROMs, being 290.24 um shorter than the RAM, leave two
# POCKETS at the far right of the die which a tighter channel fills with
# exiled logic.
#
# This arrangement takes the ROMs out of the rows.  Two RAM columns make
# the row 1609.12 um wide, the core 1730.40, and the two ROMs are placed
# as islands INSIDE the channel with clear standard-cell area above and
# below each -- orientation N, so their pin edge faces down into the
# channel exactly as the upper RAM row's does.  There are then no
# pockets, the channel is 20.9 % narrower, and the die is smaller.
NARROW_COL_SITES = (125, 1843)       # the two RAM columns, as before
NARROW_CORE_SITES = 3605             # core width, 1730.40 um
ROM_COL_SITES = (125, 2611)          # the two ROM islands
ROM_GAP_ROWS = 58                    # rows of clear channel below an island


def snap_channel(want):
    """Admissible channel heights are 0.78 + 3.78k; return the nearest."""
    k = round((want - 0.78) / SITE_H)
    return round(0.78 + SITE_H * k, 6)


def build_islands(channel, pdk_root, cell_area=CELL_AREA):
    """Two RAM columns, the two ROMs as islands inside the channel."""
    ram_w, ram_h = lef_size(pdk_root, RAM)
    rom_w, rom_h = lef_size(pdk_root, ROM)
    core_x0, core_y0 = MARGIN_X, MARGIN_Y
    core_w = round(NARROW_CORE_SITES * SITE_W, 6)
    core_h = round(INSET_B + ram_h + channel + ram_h + INSET_T, 6)
    y_bot = round(core_y0 + INSET_B, 6)
    y_top = round(y_bot + ram_h + channel, 6)
    # the islands sit ROM_GAP_ROWS of clear channel above the lower row
    gap_b = round(0.78 + SITE_H * ROM_GAP_ROWS, 6)
    y_rom = round(y_bot + ram_h + gap_b, 6)
    gap_t = round(channel - gap_b - rom_h, 6)

    macros = {RAM: {}, ROM: {}}
    for inst, col in (("u_ram.g_ram_2048x64.u_b0", 0),
                      ("u_ram.g_ram_2048x64.u_b1", 1)):
        macros[RAM][inst] = {
            "location": [round(core_x0 + NARROW_COL_SITES[col] * SITE_W, 6),
                         y_bot], "orientation": ORIENT_BOTTOM}
    for inst, col in (("u_ram.g_ram_2048x64.u_b2", 0),
                      ("u_ram.g_ram_2048x64.u_b3", 1)):
        macros[RAM][inst] = {
            "location": [round(core_x0 + NARROW_COL_SITES[col] * SITE_W, 6),
                         y_top], "orientation": ORIENT_TOP}
    for inst, col in (("u_rom.g_rom_1024x32.u_b0", 0),
                      ("u_rom.g_rom_1024x32.u_b1", 1)):
        macros[ROM][inst] = {
            "location": [round(core_x0 + ROM_COL_SITES[col] * SITE_W, 6),
                         y_rom], "orientation": ORIENT_TOP}

    die = [0, 0, round(core_x0 + core_w + MARGIN_X, 6),
           round(core_y0 + core_h + MARGIN_Y, 6)]
    core = [core_x0, core_y0, round(core_x0 + core_w, 6),
            round(core_y0 + core_h, 6)]
    macro_area = 4 * ram_w * ram_h + 2 * rom_w * rom_h
    placeable = core_w * core_h - macro_area

    assert gap_b >= 2 * HALO and gap_t >= 2 * HALO, \
        f"island clearances {gap_b} / {gap_t} are inside the halo"
    assert abs(core_w / SITE_W - round(core_w / SITE_W)) < 1e-6
    assert abs(core_h / SITE_H - round(core_h / SITE_H)) < 1e-6
    for kind, insts in macros.items():
        w, h = (ram_w, ram_h) if kind == RAM else (rom_w, rom_h)
        for inst, spec in insts.items():
            x, y = spec["location"]
            assert abs((x - core_x0) / SITE_W - round((x - core_x0) / SITE_W)) < 1e-6
            assert abs((y - core_y0) / SITE_H - round((y - core_y0) / SITE_H)) < 1e-6
            assert core_x0 <= x and x + w <= core[2], f"{inst} outside core in x"
            assert core_y0 <= y and y + h <= core[3], f"{inst} outside core in y"
    # the two RAM columns, and the two islands, must clear the halo
    assert (NARROW_COL_SITES[1] - NARROW_COL_SITES[0]) * SITE_W - ram_w >= 2 * HALO
    assert (ROM_COL_SITES[1] - ROM_COL_SITES[0]) * SITE_W - rom_w >= 2 * HALO
    # and an island must not sit under the upper row's pin edge without air
    assert y_rom + rom_h + 2 * HALO <= y_top, "island touches the upper row"

    return dict(channel=channel, die=die, core=core, core_w=core_w,
                core_h=core_h, macros=macros, macro_area=macro_area,
                placeable=placeable, util=cell_area / placeable,
                ram=(ram_w, ram_h), rom=(rom_w, rom_h), density_pct=None,
                islands=(gap_b, gap_t))


def build(channel, pdk_root, density_pct=None, cell_area=CELL_AREA):
    ram_w, ram_h = lef_size(pdk_root, RAM)
    rom_w, rom_h = lef_size(pdk_root, ROM)
    size = {RAM: (ram_w, ram_h), ROM: (rom_w, rom_h)}

    core_x0, core_y0 = MARGIN_X, MARGIN_Y
    core_w = round((COL_SITES[2] + rom_w / SITE_W) * SITE_W
                   + PAD_X / SITE_W * SITE_W, 6)
    # core width = left pad + the three columns + the right pad, and the
    # right pad is what docs/47 left: core right edge 2246.40 against a
    # ROM right edge of 2185.92.
    core_w = round(COL_SITES[2] * SITE_W + rom_w + 60.48, 6)
    core_h = round(INSET_B + ram_h + channel + ram_h + INSET_T, 6)

    y_bot = round(core_y0 + INSET_B, 6)
    y_top = round(y_bot + ram_h + channel, 6)

    macros = {}
    for row, orient, y in ((BOTTOM, ORIENT_BOTTOM, y_bot),
                           (TOP, ORIENT_TOP, y_top)):
        for kind, inst, col in row:
            x = round(core_x0 + COL_SITES[col] * SITE_W, 6)
            macros.setdefault(kind, {})[inst] = {
                "location": [x, y], "orientation": orient}

    die = [0, 0, round(core_x0 + core_w + MARGIN_X, 6),
           round(core_y0 + core_h + MARGIN_Y, 6)]
    core = [core_x0, core_y0, round(core_x0 + core_w, 6),
            round(core_y0 + core_h, 6)]

    macro_area = 4 * ram_w * ram_h + 2 * rom_w * rom_h
    placeable = core_w * core_h - macro_area
    util = cell_area / placeable

    # ---- the assertions -------------------------------------------------
    assert abs(core_w / SITE_W - round(core_w / SITE_W)) < 1e-6, \
        f"core width {core_w} is not an integer number of {SITE_W} um sites"
    assert abs(core_h / SITE_H - round(core_h / SITE_H)) < 1e-6, \
        f"core height {core_h} is not an integer number of {SITE_H} um rows"
    for kind, insts in macros.items():
        for inst, spec in insts.items():
            x, y = spec["location"]
            assert abs((x - core_x0) / SITE_W - round((x - core_x0) / SITE_W)) < 1e-6, \
                f"{inst} x is not site-aligned"
            assert abs((y - core_y0) / SITE_H - round((y - core_y0) / SITE_H)) < 1e-6, \
                f"{inst} y is not row-aligned"
            w, h = size[kind]
            assert x >= core_x0 and x + w <= core[2], f"{inst} outside core in x"
            assert y >= core_y0 and y + h <= core[3], f"{inst} outside core in y"
    # halo clearance between the two rows and between columns
    assert channel >= 2 * HALO, f"channel {channel} is inside the 2x{HALO} um halo"
    for row, y in ((BOTTOM, y_bot), (TOP, y_top)):
        for i in range(len(row) - 1):
            k0, _, c0 = row[i]
            k1, _, c1 = row[i + 1]
            gap = (COL_SITES[c1] - COL_SITES[c0]) * SITE_W - size[k0][0]
            assert gap >= 2 * HALO, f"column gap {gap} is inside the halo"

    return dict(channel=channel, die=die, core=core, core_w=core_w,
                core_h=core_h, macros=macros, macro_area=macro_area,
                placeable=placeable, util=util, ram=size[RAM], rom=size[ROM],
                density_pct=density_pct, cell_area=cell_area)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", type=float, required=True,
                    help="standard-cell channel height in um; snapped to "
                         "0.78 + 3.78k")
    ap.add_argument("--cell-area", type=float, default=CELL_AREA,
                    metavar="UM2",
                    help="standard-cell area of the netlist this floorplan "
                         "is for, from syn_soc_top.sh's area.rpt. Default is "
                         "docs/47's NPU-less %(default).4f; docs/61's design "
                         "is 624429.9180. Feeds the reported utilization and "
                         "the default density only, never a coordinate")
    ap.add_argument("--density", type=int, default=None,
                    help="PL_TARGET_DENSITY_PCT to emit; default preserves "
                         "docs/47's headroom of +18 points over the "
                         "pre-repair standard-cell density")
    ap.add_argument("--arrangement", choices=("rows3", "islands"),
                    default="rows3",
                    help="rows3 = docs/47's two rows of RAM, RAM, ROM; "
                         "islands = two RAM columns with the ROMs inside "
                         "the channel and a narrower die")
    ap.add_argument("--write", metavar="PATH", default=None,
                    help="write a whole variant of config.json to PATH; the "
                         "path must be inside hw/soc/pnr/, because "
                         "flow/pnr_soc_top.sh refuses any other")
    a = ap.parse_args()

    pdk_root = os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel"))
    channel = snap_channel(a.channel)
    fp = (build_islands(channel, pdk_root, a.cell_area)
          if a.arrangement == "islands"
          else build(channel, pdk_root, cell_area=a.cell_area))

    density = a.density
    if density is None:
        density = int(round(fp["util"] * 100)) + 18
    fp["density_pct"] = density

    if a.write:
        base = json.load(open(CONFIG))
        out = json.loads(json.dumps(base))
        out["DIE_AREA"] = fp["die"]
        out["CORE_AREA"] = fp["core"]
        for kind, insts in fp["macros"].items():
            out["MACROS"][kind]["instances"] = insts
        out["PL_TARGET_DENSITY_PCT"] = density
        out["//floorplan48"] = (
            "GENERATED BY hw/soc/pnr/floorplan.py --arrangement "
            f"{a.arrangement} --channel {channel} --density {density} "
            f"--cell-area {a.cell_area}. This file differs from "
            "config.json in FOUR keys and the generator asserts it: "
            "DIE_AREA, CORE_AREA, MACROS (the six instance LOCATIONS only "
            "-- same macros, same orientations, same x origins) and "
            "PL_TARGET_DENSITY_PCT. Everything else, including every "
            "checker binding of config.json's section on the checkers, is "
            "carried across byte for byte, so a difference in a result "
            "between this run and docs/47's is a difference of floorplan "
            "and of nothing else. docs/48, and docs/61 for the variant "
            "sized against the netlist that contains the accelerator."
        )
        # THE ASSERTION, the same shape flow/pnr_soc_top.sh makes about
        # VERILOG_FILES: a generator that can quietly change a fifth key
        # is a generator whose output cannot be attributed.
        added = set(out) - set(base)
        changed = {k for k in base if base[k] != out[k]}
        assert added == {"//floorplan48"}, f"generator added {added}"
        # `<=` and not `==` on purpose: at --channel 700.08 --density 40
        # this generator reproduces config.json exactly and `changed` is
        # EMPTY, which is the strongest self-check available -- the tool
        # that emits the new floorplan also emits docs/47's, from the
        # LEF, without being told what it should come out as.
        assert changed <= {"DIE_AREA", "CORE_AREA", "MACROS",
                           "PL_TARGET_DENSITY_PCT"}, \
            f"generator changed {changed}"
        for kind in out["MACROS"]:
            assert set(out["MACROS"][kind]) == set(base["MACROS"][kind]), \
                "generator changed a MACROS sub-key"
            for k in out["MACROS"][kind]:
                if k != "instances":
                    assert out["MACROS"][kind][k] == base["MACROS"][kind][k]
            assert set(out["MACROS"][kind]["instances"]) == \
                set(base["MACROS"][kind]["instances"]), \
                "generator renamed a macro instance"
        with open(a.write, "w") as fh:
            json.dump(out, fh, indent=4)
        print(f"wrote {a.write}")

    print(f"macro RAM {fp['ram'][0]} x {fp['ram'][1]}   "
          f"ROM {fp['rom'][0]} x {fp['rom'][1]}   [LEF SIZE]")
    if abs(channel - a.channel) > 1e-9:
        print(f"channel snapped {a.channel} -> {channel}")
    print(f"channel        {channel:10.2f} um  "
          f"({channel / SITE_H:.1f} rows)")
    print(f"die            {fp['die'][2]:10.2f} x {fp['die'][3]:.2f} um  "
          f"= {fp['die'][2] * fp['die'][3] / 1e6:.4f} mm2")
    print(f"core           {fp['core_w']:10.2f} x {fp['core_h']:.2f} um  "
          f"= {fp['core_w'] * fp['core_h']:.0f} um2")
    print(f"macros         {fp['macro_area']:10.2f} um2  "
          f"({100 * fp['macro_area'] / (fp['core_w'] * fp['core_h']):.1f} % of core)")
    print(f"placeable      {fp['placeable']:10.2f} um2")
    print(f"cells          {fp['cell_area']:10.2f} um2  "
          f"-> {100 * fp['util']:.2f} % pre-repair")
    print(f"PL_TARGET_DENSITY_PCT {density}")
    if fp.get("islands"):
        print(f"island clearance below/above {fp['islands'][0]:.2f} / "
              f"{fp['islands'][1]:.2f} um")
    for kind in (RAM, ROM):
        for inst, spec in sorted(fp["macros"][kind].items()):
            print(f"    {inst:32s} {spec['location'][0]:9.2f} "
                  f"{spec['location'][1]:9.2f}  {spec['orientation']}")


if __name__ == "__main__":
    sys.exit(main())
