#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

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
import math
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

# docs/67: the SAME four RAM macros, in the SAME places, under the
# generate label of soc_mem_sram.v's codec arm. The instance path is a
# property of that file -- `u_ram.<generate label>.<macro instance>` --
# and the label changed when the arm did, so a floorplan for the
# protected design names the same silicon by a different path. The ROM
# keeps docs/47's label: docs/67 section 5's layout is taken with the
# ROM as docs/47 built it, because its two check-bit macros have no
# place in this floorplan (docs/67 section 8).
# `ecc-rom` is `ecc` plus the ROM's own codec arm: soc_mem_sram.v's
# `WORDS == 2048 && HARDEN != 0` branch is labelled g_rom_1024x32_ecc,
# so the two ROM banks are named through that label as well, and the two
# check macros exist to be placed.
ROM_ECC = {"u_rom.g_rom_1024x32.u_b0": "u_rom.g_rom_1024x32_ecc.u_b0",
           "u_rom.g_rom_1024x32.u_b1": "u_rom.g_rom_1024x32_ecc.u_b1"}
ROM_CHK_INSTS = ("u_rom.g_rom_1024x32_ecc.u_c0",
                 "u_rom.g_rom_1024x32_ecc.u_c1")
ROM_BOT_INST = "u_rom.g_rom_1024x32_ecc.u_b0"
ROM_TOP_INST = "u_rom.g_rom_1024x32_ecc.u_b1"

LABELS = {
    "docs47": {},
    "ecc": {"u_ram.g_ram_2048x64.u_b0": "u_ram.g_ram_2048x64_ecc.u_b0",
            "u_ram.g_ram_2048x64.u_b1": "u_ram.g_ram_2048x64_ecc.u_b1",
            "u_ram.g_ram_2048x64.u_b2": "u_ram.g_ram_2048x64_ecc.u_b2",
            "u_ram.g_ram_2048x64.u_b3": "u_ram.g_ram_2048x64_ecc.u_b3"},
}
LABELS["ecc-rom"] = dict(LABELS["ecc"], **ROM_ECC)

# The ROM's check-bit macro (docs/67). The RTL as it ships instantiates
# two of these under u_rom.g_rom_1024x32_ecc, and LibreLane's
# Yosys.JsonHeader elaborates the RTL -- not the netlist this flow
# hardens -- so it has to know the module even in a run whose netlist
# was synthesised with ROM_HARDEN = 0 and contains none. It is entered
# with NO instances: the LEF and Liberty are read, nothing is placed,
# and OpenROAD.CheckMacroInstances has nothing to check. Placing it is
# docs/67 section 8's open item.
ROM_CHK = "RM_IHPSG13_1P_512x16_c2_bm_bist"

# --- placing it, 2026-09-12 -------------------------------------------
#
# docs/67 section 8's open item, closed. The paragraph above is left as
# it was written because it is still true of `--memory ecc`; what is new
# is `--memory ecc-rom`, which places the two check macros and therefore
# does NOT force ROM_HARDEN = 0.
#
# WHERE THEY GO, AND WHY THERE IS ROOM AT ALL. The macro rows are as
# tall as the RAM, 626.70 um, and the ROM is 336.46 um, so column 2 has
# 290.24 um of unused height in each row. The check macro is 191.34 um
# tall and 236.80 um wide against the ROM's 416.64, so it fits inside
# that pocket twice over. Nothing else in the floorplan has to move to
# make room -- the die, the core and the four RAM macros are untouched,
# which is what keeps every measurement taken on this floorplan
# comparable with one taken on the new one.
#
# WHY THE BOTTOM ROM MOVES AND THE TOP ONE DOES NOT. Both rows put their
# pin edge against the channel: the bottom row is FS, which mirrors the
# macro about X and lifts its pins to its top, and the top row is N,
# which leaves them at its bottom. So the pocket in the BOTTOM row lies
# on top of the ROM, directly over its pins, and a macro parked there
# would sit across every wire leaving them. The bottom ROM is therefore
# raised to the top of its own band -- its pins end up at the channel
# rather than 290 um below it, which is better for it as well -- and the
# check macro takes the space underneath, on the ROM's blind edge. The
# top row needs none of this: its ROM's pins are already at the bottom
# of the band facing the channel, and the pocket is above, on its blind
# edge.
#
# Both check macros keep their row's orientation, so each one's pins
# face the same way as the ROM it serves.
ROM_CHK_W_UM = 236.80
ROM_CHK_H_UM = 191.34

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


def _relabel_pdn(line, relabel):
    """One PDN_MACRO_CONNECTIONS entry -- a regular expression over the
    instance path, then the nets -- with docs/47's generate label
    replaced by the codec arm's. The expression is rewritten by the
    same table that renames the instances, so the two cannot disagree."""
    pattern, nets = line.split(" ", 1)
    # One replacement per distinct label, not per instance: four
    # instances share one label and the first version of this function
    # rewrote the label four times over.
    prefixes = {(old.rsplit(".", 1)[0], new.rsplit(".", 1)[0])
                for old, new in relabel.items()}
    for old_p, new_p in sorted(prefixes):
        old_re = old_p.replace(".", "\\.")
        new_re = new_p.replace(".", "\\.")
        if old_re in pattern:
            pattern = pattern.replace(old_re, new_re)
    return pattern + " " + nets


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

    # ---- the ROM's two check macros, docs/67 section 8 ------------------
    #
    # Computed rather than written down, so that a change to the ROM's
    # size, the row pitch or the insets moves them instead of silently
    # putting them somewhere they no longer fit.
    chk_w, chk_h = lef_size(pdk_root, ROM_CHK)

    def _row_align(y):
        """The highest row-aligned y not above `y`."""
        rows = math.floor((y - core_y0) / SITE_H + 1e-9)
        return round(core_y0 + rows * SITE_H, 6)

    band_bot_top = round(y_bot + ram_h, 6)      # top of the bottom band
    band_top_top = round(y_top + ram_h, 6)      # top of the top band
    rom_x = round(core_x0 + COL_SITES[2] * SITE_W, 6)

    # Bottom row: the ROM rises to the top of its band so its pins meet
    # the channel, and the check macro takes the blind space beneath it.
    rom_bot_y = _row_align(band_bot_top - rom_h)
    chk_bot_y = y_bot
    # Top row: the ROM stays where it is, pins already at the channel,
    # and the check macro takes the blind space above it.
    rom_top_y = y_top
    chk_top_y = _row_align(band_top_top - chk_h)

    chk_place = {ROM_CHK_INSTS[0]: (chk_bot_y, ORIENT_BOTTOM),
                 ROM_CHK_INSTS[1]: (chk_top_y, ORIENT_TOP)}
    rom_moved = {ROM_BOT_INST: rom_bot_y, ROM_TOP_INST: rom_top_y}

    macro_area = (4 * ram_w * ram_h + 2 * rom_w * rom_h
                  + 2 * chk_w * chk_h)
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
                density_pct=density_pct, cell_area=cell_area,
                chk=(chk_w, chk_h), chk_place=chk_place, rom_moved=rom_moved,
                core_x0=core_x0, core_y0=core_y0, rom_x=rom_x,
                band_tops=(band_bot_top, band_top_top))


def place_rom_check(fp):
    """Put the ROM's two check macros into a built floorplan, and move
    the bottom ROM off its own pins to make room.

    Separate from build() so that `--memory ecc-rom` is the ONLY
    arrangement that differs: every other mode returns exactly the
    floorplan it returned before this function existed, which is what
    keeps docs/47, docs/61 and docs/67's measurements comparable.

    The assertions are the point. A macro that lands a row out of
    alignment, inside another macro's halo, or over the die edge is a
    run that fails eighty steps later with a message about routing, so
    the geometry is checked here where the reason is still legible.
    """
    chk_w, chk_h = fp["chk"]
    rom_w, rom_h = fp["rom"]
    core = fp["core"]
    rom_x = fp["rom_x"]

    roms = fp["macros"][ROM]
    for inst, y in fp["rom_moved"].items():
        assert inst in roms, (
            "%s is not in this floorplan's ROM instances %s -- "
            "place_rom_check() is being called on an arrangement whose "
            "labels it does not know" % (inst, sorted(roms)))
        roms[inst]["location"][1] = y

    chks = fp["macros"].setdefault(ROM_CHK, {})
    for inst, (y, orient) in fp["chk_place"].items():
        chks[inst] = {"location": [rom_x, y], "orientation": orient}

    # ---- the assertions -------------------------------------------------
    for inst, spec in chks.items():
        x, y = spec["location"]
        assert abs((x - fp["core_x0"]) / SITE_W
                   - round((x - fp["core_x0"]) / SITE_W)) < 1e-6, \
            "%s x is not site-aligned" % inst
        assert abs((y - fp["core_y0"]) / SITE_H
                   - round((y - fp["core_y0"]) / SITE_H)) < 1e-6, \
            "%s y is not row-aligned" % inst
        assert x >= core[0] and x + chk_w <= core[2], \
            "%s outside core in x" % inst
        assert y >= core[1] and y + chk_h <= core[3], \
            "%s outside core in y" % inst

    # Each check macro clears the ROM it shares a column with, by the
    # halo, on the side it was put.
    bot_chk_y = fp["chk_place"][ROM_CHK_INSTS[0]][0]
    bot_rom_y = fp["rom_moved"][ROM_BOT_INST]
    gap_bot = round(bot_rom_y - (bot_chk_y + chk_h), 6)
    assert gap_bot >= 2 * HALO, (
        "the bottom check macro is %.2f um below its ROM, inside the "
        "2x%.0f um halo" % (gap_bot, HALO))

    top_chk_y = fp["chk_place"][ROM_CHK_INSTS[1]][0]
    top_rom_y = fp["rom_moved"][ROM_TOP_INST]
    gap_top = round(top_chk_y - (top_rom_y + rom_h), 6)
    assert gap_top >= 2 * HALO, (
        "the top check macro is %.2f um above its ROM, inside the "
        "2x%.0f um halo" % (gap_top, HALO))

    # And neither leaves its own macro row -- a check macro that spilled
    # into the channel would be standing in the cell field.
    band_bot_top, band_top_top = fp["band_tops"]
    assert bot_chk_y + chk_h <= band_bot_top, \
        "the bottom check macro reaches above its macro row"
    assert top_chk_y + chk_h <= band_top_top, \
        "the top check macro reaches above its macro row"

    fp["chk_gaps"] = (gap_bot, gap_top)
    return fp


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
    ap.add_argument("--memory", choices=sorted(LABELS), default="docs47",
                    help="which soc_mem_sram.v arm the RAM instances are "
                         "named for: docs47 = two words per row, ecc = "
                         "docs/67's one protected word per row. Same "
                         "macros, same places, different instance paths")
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

    relabel = LABELS[a.memory]
    if relabel:
        for kind in fp["macros"]:
            fp["macros"][kind] = {relabel.get(inst, inst): spec
                                  for inst, spec in fp["macros"][kind].items()}
        if a.memory == "ecc-rom":
            # The ROM's codec arm, placed. No ROM_HARDEN override: the
            # instances this floorplan names are the instances the RTL
            # builds at its own default, which is the whole difference
            # between this mode and `ecc`.
            place_rom_check(fp)
        else:
            fp["macros"][ROM_CHK] = {}
            # And the RTL the JSON header elaborates is told to build the
            # ROM as docs/47 did, so that the instances it finds are the
            # instances this floorplan places: soc_top.v's ROM_HARDEN
            # measurement knob, applied through LibreLane's own chparam
            # list.
            fp["synth_parameters"] = ["ROM_HARDEN=0"]

    if a.write:
        base = json.load(open(CONFIG))
        out = json.loads(json.dumps(base))
        out["DIE_AREA"] = fp["die"]
        out["CORE_AREA"] = fp["core"]
        for kind, insts in fp["macros"].items():
            if kind not in out["MACROS"]:
                # the ROM's check-bit macro, known and unplaced; see ROM_CHK
                out["MACROS"][kind] = {
                    "gds": ["pdk_dir::libs.ref/sg13g2_sram/gds/%s.gds" % kind],
                    "lef": ["pdk_dir::libs.ref/sg13g2_sram/lef/%s.lef" % kind],
                    "vh": ["dir::%s_bb.v" % kind],
                    "lib": {
                        "nom_typ_1p20V_25C": [
                            "pdk_dir::libs.ref/sg13g2_sram/lib/%s_typ_1p20V_25C.lib" % kind],
                        "nom_slow_1p08V_125C": [
                            "pdk_dir::libs.ref/sg13g2_sram/lib/%s_slow_1p08V_125C.lib" % kind],
                        "nom_fast_1p32V_m40C": [
                            "pdk_dir::libs.ref/sg13g2_sram/lib/%s_fast_1p32V_m55C.lib" % kind],
                    },
                    "instances": {},
                }
            else:
                out["MACROS"][kind]["instances"] = insts
        out["PL_TARGET_DENSITY_PCT"] = density
        if fp.get("synth_parameters"):
            out["SYNTH_PARAMETERS"] = fp["synth_parameters"]
        # The PDN hookup names the macro instances by regular expression,
        # so a relabelled instance path has to be relabelled there too or
        # OpenROAD.Floorplan finds no macro to power and stops.
        if relabel:
            out["PDN_MACRO_CONNECTIONS"] = [
                _relabel_pdn(line, relabel)
                for line in base["PDN_MACRO_CONNECTIONS"]]
        out["//floorplan48"] = (
            "GENERATED BY hw/soc/pnr/floorplan.py --arrangement "
            f"{a.arrangement} --channel {channel} --density {density} "
            f"--cell-area {a.cell_area} --memory {a.memory}. This file differs from "
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
        allowed_added = {"//floorplan48"}
        if fp.get("synth_parameters"):
            allowed_added.add("SYNTH_PARAMETERS")
        assert added == allowed_added, f"generator added {added}"
        # `<=` and not `==` on purpose: at --channel 700.08 --density 40
        # this generator reproduces config.json exactly and `changed` is
        # EMPTY, which is the strongest self-check available -- the tool
        # that emits the new floorplan also emits docs/47's, from the
        # LEF, without being told what it should come out as.
        allowed_changed = {"DIE_AREA", "CORE_AREA", "MACROS",
                           "PL_TARGET_DENSITY_PCT"}
        if relabel:
            allowed_changed.add("PDN_MACRO_CONNECTIONS")
        assert changed <= allowed_changed, f"generator changed {changed}"
        for kind in out["MACROS"]:
            if kind == ROM_CHK and kind not in base["MACROS"]:
                assert out["MACROS"][kind]["instances"] == {}, \
                    "the ROM check macro is entered unplaced, by design"
                continue
            assert set(out["MACROS"][kind]) == set(base["MACROS"][kind]), \
                "generator changed a MACROS sub-key"
            for k in out["MACROS"][kind]:
                if k != "instances":
                    assert out["MACROS"][kind][k] == base["MACROS"][kind][k]
            # The instance SET is config.json's unless --memory asked for
            # the codec arm's labels, in which case it is that arm's,
            # applied to config.json's set by the table above and nothing
            # else: a renamed instance is still the same macro in the
            # same place.
            want = {relabel.get(i, i)
                    for i in base["MACROS"][kind]["instances"]}
            if a.memory == "ecc-rom" and kind == ROM_CHK:
                # The one place the set is allowed to GROW, and only by
                # exactly these two. config.json carries this macro with
                # an empty instance dict -- known and unplaced, docs/67
                # section 8 -- and `--memory ecc-rom` is the mode that
                # places them. Naming them here rather than relaxing the
                # comparison keeps the check as strict as it was for
                # every other macro and for every other mode: a THIRD
                # check instance, or a differently named one, still
                # fails.
                want |= set(ROM_CHK_INSTS)
            assert set(out["MACROS"][kind]["instances"]) == want, \
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
    for kind in (RAM, ROM, ROM_CHK):
        for inst, spec in sorted(fp["macros"].get(kind, {}).items()):
            print(f"    {inst:32s} {spec['location'][0]:9.2f} "
                  f"{spec['location'][1]:9.2f}  {spec['orientation']}")
    if fp.get("chk_gaps"):
        print(f"ROM check macro clearance  bottom {fp['chk_gaps'][0]:.2f} um"
              f"  top {fp['chk_gaps'][1]:.2f} um  (halo {HALO:.0f} um)")


if __name__ == "__main__":
    sys.exit(main())
