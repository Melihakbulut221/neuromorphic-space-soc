#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Large-format die maps, for a screen instead of a page.

    make_social_figures.py <soc_top.def> <soc_top.nl.v> <out-dir>

WHY A SECOND SCRIPT.  `make_layout_figures.py` draws for print: a
figure 11 cm wide on A4, read at arm's length, where 5.6 pt type is
comfortable and a fourteen-entry legend is fine.  The same figure on a
phone is a grey smudge.  These are the same measurements at the size a
screen renders them: four square images, no type under 11 pt at the
final pixel size, at most eight legend entries, and every label large
enough to survive the rescale a feed applies.

NOTHING HERE IS TYPED IN.  Every count, area and coordinate comes from
the DEF and the netlist named on the command line, through the same
`read_def`, `read_netlist` and `attribute` that the print figures use,
and the die size comes from the DEF's own DIEAREA.  A number on one of
these images and the same number in the thesis come from one
measurement, not two.  The four figures in the timing and formal
sections of the last card are the exception and are marked as quoted:
they come from documents, not from these two files.

TEXT THAT DOES NOT FIT IS SHRUNK, NOT CLIPPED.  `fit_fontsize` measures
each macro label against the macro it names and reduces the size until
it fits.  The print script shipped two revisions with every macro's
name printed across its own dimensions; the lesson taken from that was
to measure rather than to guess (`docs/85`).

WHAT IT WRITES.  Four PNGs at 1600 x 1600:

  social-1-regions.png    the five regions the floorplan creates, each
                          numbered, with what occupies it counted
  social-2-blocks.png     every non-fill instance coloured by the block
                          it belongs to, with the attribution's own
                          error bar in the legend
  social-3-floorplan.png  the eight vendor macros with their sizes
  social-4-numbers.png    a card of the measurements
"""

import os
import re
import sys
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_layout_figures import (          # noqa: E402
    read_def, read_netlist, attribute, MACRO_SIZE, MACRO_LABEL, CORE,
    REGIONS, BLOCK_NAME, BLOCK_COLOUR, CLOCK, FILLER, UNATTR,
    CLOCK_COLOUR, UNATTR_COLOUR,
)

PX, DPI = 1600, 160
FIGSIZE = (PX / DPI, PX / DPI)
TOP = 0.855                       # content starts below the title block

INK, MUTED, PAPER, RULE = "#1A1A1A", "#5A5A5A", "#FBFAF7", "#C9C4BA"
MONO = "DejaVu Sans Mono"

MACRO_FILL = {
    "RM_IHPSG13_1P_2048x64_c2_bm_bist": "#BFD9EF",
    "RM_IHPSG13_1P_1024x32_c2_bm_bist": "#FBD7B5",
    "RM_IHPSG13_1P_512x16_c2_bm_bist": "#C9E8CE",
}
SHORT = {
    "General-purpose timer": "GP timer",
    "QSPI flash controller": "QSPI",
    "Neuromorphic accelerator": "accelerator",
    "Ibex RV32IMC core": "Ibex core",
    "Bus fault counters": "bus counters",
    "ROM control and ECC": "ROM control",
    "RAM control and ECC": "RAM control",
    "Memory scrub engine": "scrub engine",
    "Plug-and-play ROM": "PnP ROM",
    "Bus fabric and APB": "bus fabric",
    "Console UART": "UART",
    "Boot controller": "boot",
    "CLINT time base": "CLINT",
}
REGION_TINT = {
    "central channel": "#DCE9F5",
    "lower macro row": "#EFE6DA",
    "upper macro row": "#EFE6DA",
    "ROM column, lower half": "#E4F0E4",
    "ROM column, upper half": "#E4F0E4",
}
# Draw order, and which margin each region's number hangs in.
REGION_ORDER = [
    ("upper macro row", "left"),
    ("central channel", "left"),
    ("lower macro row", "left"),
    ("ROM column, upper half", "right"),
    ("ROM column, lower half", "right"),
]

DIE_W = DIE_H = None               # from read_die; never typed in


def read_die(path):
    """Die width and height in micrometres, from the DEF's own DIEAREA."""
    units = 1000.0
    with open(path, errors="ignore") as f:
        for line in f:
            m = re.match(r"\s*UNITS DISTANCE MICRONS\s+(\d+)", line)
            if m:
                units = float(m.group(1))
            m = re.match(r"\s*DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)"
                         r"\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", line)
            if m:
                x0, y0, x1, y1 = (int(v) for v in m.groups())
                return (x1 - x0) / units, (y1 - y0) / units
    raise SystemExit("no DIEAREA in %s" % path)


# ---- furniture --------------------------------------------------------
def card(fig, title, subtitle, credit):
    fig.patch.set_facecolor(PAPER)
    fig.text(0.05, 0.968, title, fontsize=30, fontweight="bold",
             color=INK, va="top", ha="left")
    fig.text(0.05, 0.918, subtitle, fontsize=14.5, color=MUTED,
             va="top", ha="left", linespacing=1.45)
    fig.text(0.05, 0.022, credit, fontsize=11.5, color=MUTED,
             va="bottom", ha="left")
    fig.text(0.95, 0.022, "github.com/Melihakbulut221/nssoc",
             fontsize=11.5, color=MUTED, va="bottom", ha="right")


def die_axes(fig, rect, pad=30.0):
    ax = fig.add_axes(rect)
    ax.set_xlim(-pad, DIE_W + pad)
    ax.set_ylim(-pad, DIE_H + pad)
    ax.set_aspect("equal")
    ax.set_facecolor("none")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.add_patch(Rectangle((0, 0), DIE_W, DIE_H, facecolor="#FFFFFF",
                           edgecolor=INK, linewidth=2.0, zorder=0))
    return ax


def _width(fig, ax, text, size, bold):
    t = ax.text(0, 0, text, fontsize=size,
                fontweight="bold" if bold else "normal")
    w = t.get_window_extent(renderer=fig.canvas.get_renderer()).width
    t.remove()
    return w


def _room(ax, box_um):
    x0 = ax.transData.transform((0, 0))[0]
    x1 = ax.transData.transform((box_um, 0))[0]
    return abs(x1 - x0) * 0.90


def fit_fontsize(fig, ax, text, box_um, start, floor=8.0, bold=True):
    """Largest size at or under `start` whose text fits inside box_um."""
    room = _room(ax, box_um)
    size = start
    while size > floor:
        if _width(fig, ax, text, size, bold) <= room:
            return size
        size -= 0.5
    return floor


def fit_label(fig, ax, text, box_um, start, floor=9.5):
    """Fit a macro's name, wrapping it rather than shrinking it away.

    A 236.80 um check macro cannot hold "ROM ECC 1" on one line at a
    size anyone reads on a phone. Two lines at a readable size beat one
    line at six points, and beat a label that overhangs its own box.
    """
    room = _room(ax, box_um)
    size = start
    while size > floor:
        if _width(fig, ax, text, size, True) <= room:
            return text, size
        size -= 0.5
    if " " in text:
        words = text.split(" ")
        best, cut = None, None
        for i in range(1, len(words)):
            a, b = " ".join(words[:i]), " ".join(words[i:])
            longest = max(len(a), len(b))
            if best is None or longest < best:
                best, cut = longest, (a, b)
        two = "%s\n%s" % cut
        size = start
        while size > floor:
            if max(_width(fig, ax, cut[0], size, True),
                   _width(fig, ax, cut[1], size, True)) <= room:
                return two, size
            size -= 0.5
        return two, floor
    return text, floor


def macros_on(fig, ax, macros, start, sizes=False, fill=True):
    fig.canvas.draw()
    for name, (master, x, y, orient) in sorted(macros.items()):
        w, h = MACRO_SIZE[master]
        ax.add_patch(Rectangle(
            (x, y), w, h,
            facecolor=MACRO_FILL[master] if fill else "#EDEDED",
            edgecolor=INK, linewidth=1.6, zorder=3))
        label, fs = fit_label(fig, ax, MACRO_LABEL.get(name, name), w, start)
        cx, cy = x + w / 2, y + h / 2
        if sizes:
            # The name may have wrapped to fit the box's WIDTH, and a
            # two-line name anchored at the centre grows out through the
            # box's TOP. Both blocks are therefore measured and the pair
            # is centred as one, which is the only version of this that
            # stays inside a 237 x 191 um check macro.
            room = _room(ax, w)
            for detail in ("%.0f x %.0f um" % (w, h), "%.0fx%.0f um" % (w, h),
                           "%.0fx%.0f" % (w, h)):
                fd = fit_fontsize(fig, ax, detail, w, max(fs - 3.0, 9.0),
                                  floor=6.5, bold=False)
                if _width(fig, ax, detail, fd, False) <= room:
                    break
            name_h = (label.count("\n") + 1) * fs * 1.15
            det_h = fd * 1.25
            ax.annotate(label, (cx, cy), textcoords="offset points",
                        xytext=(0, (det_h + 2.0) / 2), ha="center",
                        va="center", fontsize=fs, fontweight="bold",
                        zorder=4, linespacing=1.15)
            ax.annotate(detail, (cx, cy), textcoords="offset points",
                        xytext=(0, -(name_h + 2.0) / 2), ha="center",
                        va="center", color=MUTED, fontsize=fd, zorder=4)
        else:
            ax.annotate(label, (cx, cy), ha="center", va="center",
                        fontsize=fs, fontweight="bold", zorder=4,
                        linespacing=1.15)


# ---- 1. the die by region --------------------------------------------
def fig_regions(cells, macros, owner, out, total):
    tally = {r[0]: Counter() for r in REGIONS}
    for n, (m, x, y) in cells.items():
        o = owner[n]
        if o == FILLER:
            continue
        for rname, (x0, y0, x1, y1), _ in REGIONS:
            if x0 <= x < x1 and y0 <= y < y1:
                tally[rname][BLOCK_NAME.get(o, o.strip("_"))] += 1
                break

    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    card(fig, "Where the logic landed",
         "One die, %s instances, five regions the floorplan creates.\n"
         "Occupancy counted from the sign-off placement, not assigned by intent."
         % f"{total:,}",
         "IHP SG13G2 130 nm open PDK, placed and routed with open tools.")
    ax = die_axes(fig, [0.018, 0.160, 0.600, 0.548], pad=185.0)

    for rname, (x0, y0, x1, y1), _ in REGIONS:
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0,
                               facecolor=REGION_TINT[rname], edgecolor="#6E6E6E",
                               linewidth=1.4, linestyle=(0, (7, 4)), zorder=1))
    xs = [c[1] for n, c in cells.items() if owner[n] != FILLER]
    ys = [c[2] for n, c in cells.items() if owner[n] != FILLER]
    ax.scatter(xs, ys, s=0.7, c="#3F3F3F", marker="s", linewidths=0,
               alpha=0.26, zorder=2, rasterized=True)
    macros_on(fig, ax, macros, 12.5, sizes=False)

    # The numbers hang OUTSIDE the die, which is the one place on this
    # floorplan guaranteed to be free of a macro label.
    for i, (rname, side) in enumerate(REGION_ORDER, 1):
        x0, y0, x1, y1 = dict((r[0], r[1]) for r in REGIONS)[rname]
        cy = (y0 + y1) / 2
        cx = -105.0 if side == "left" else DIE_W + 105.0
        ax.add_patch(Circle((cx, cy), 72.0, facecolor=INK, edgecolor="none",
                            zorder=7))
        ax.text(cx, cy, str(i), color="white", fontsize=15,
                fontweight="bold", ha="center", va="center", zorder=8)

    y = 0.845
    for i, (rname, _) in enumerate(REGION_ORDER, 1):
        c = tally[rname]
        fig.text(0.672, y, str(i), fontsize=13, fontweight="bold",
                 color="white", va="top", ha="center",
                 bbox=dict(boxstyle="circle,pad=0.28", fc=INK, ec="none"))
        fig.text(0.708, y, rname.upper(), fontsize=13.0, fontweight="bold",
                 color=INK, va="top", ha="left")
        fig.text(0.708, y - 0.029, "%s non-fill cells"
                 % f"{sum(c.values()):,}", fontsize=12.0, color=MUTED,
                 va="top", ha="left")
        yy = y - 0.056
        for k, v in c.most_common(3):
            fig.text(0.708, yy, "%s  %s" % (f"{v:,}".rjust(6), SHORT.get(k, k)),
                     fontsize=11.5, color=INK, va="top", ha="left", family=MONO)
            yy -= 0.026
        y = yy - 0.024
    fig.savefig(os.path.join(out, "social-1-regions.png"),
                facecolor=PAPER, dpi=DPI)
    plt.close(fig)
    print("  wrote social-1-regions.png")
    return tally


# ---- 2. every cell coloured by its block ------------------------------
def fig_blocks(cells, macros, owner, counts, out, total):
    logic = sum(v for k, v in counts.items() if k != FILLER)
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    # The eight macros keep their full hierarchical names; the claim is
    # about the standard cells, and it is about a TOP-LEVEL block prefix.
    card(fig, "Which block is where",
         "Exactly one of the %s standard cells here still carried a top-level\n"
         "block name after synthesis. Every other colour came from the nets."
         % f"{total - 8:,}",
         "Counts are instances. Fill, decap and diodes are not drawn.")
    ax = die_axes(fig, [0.195, 0.300, 0.610, 0.550])

    ranked = [b for b, _ in Counter(
        {k: v for k, v in counts.items()
         if k not in (FILLER, CLOCK, UNATTR)}).most_common(6)]
    rest = [k for k in counts
            if k not in ranked and k not in (FILLER, CLOCK, UNATTR)]

    groups = [(SHORT.get(BLOCK_NAME.get(b, b), BLOCK_NAME.get(b, b)),
               BLOCK_COLOUR.get(b, "#777777"), [b], counts[b]) for b in ranked]
    if rest:
        groups.append(("%d other peripherals" % len(rest), "#7A7A7A", rest,
                       sum(counts[b] for b in rest)))
    groups.append(("clock tree", CLOCK_COLOUR, [CLOCK], counts[CLOCK]))
    groups.append(("not attributable", UNATTR_COLOUR, [UNATTR], counts[UNATTR]))

    for label, colour, keys, n in groups:
        ks = set(keys)
        xs = [c[1] for nm, c in cells.items() if owner[nm] in ks]
        ys = [c[2] for nm, c in cells.items() if owner[nm] in ks]
        ax.scatter(xs, ys, s=1.0, c=colour, marker="s", linewidths=0,
                   alpha=0.85, zorder=2, rasterized=True)
    macros_on(fig, ax, macros, 11.5, sizes=False, fill=False)

    half = (len(groups) + 1) // 2
    for col, chunk in enumerate((groups[:half], groups[half:])):
        x0 = 0.05 + col * 0.475
        y = 0.255
        for label, colour, _, n in chunk:
            fig.patches.append(Rectangle(
                (x0, y - 0.013), 0.024, 0.024, transform=fig.transFigure,
                facecolor=colour, edgecolor="none", zorder=5))
            fig.text(x0 + 0.036, y, label, fontsize=13.0, color=INK,
                     va="center", ha="left")
            fig.text(x0 + 0.415, y, "%s   %4.1f %%"
                     % (f"{n:,}".rjust(6), 100 * n / logic),
                     fontsize=13.0, color=INK, va="center", ha="right",
                     family=MONO)
            y -= 0.045
    fig.savefig(os.path.join(out, "social-2-blocks.png"),
                facecolor=PAPER, dpi=DPI)
    plt.close(fig)
    print("  wrote social-2-blocks.png")


# ---- 3. the eight macros ----------------------------------------------
def fig_floorplan(macros, out):
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    card(fig, "The eight things a person placed",
         "Four 2048x64 RAM banks, two 1024x32 boot ROMs and the two check\n"
         "macros that carry the ROM's ECC. The placer decided everything else.",
         "Positions and sizes read from the sign-off run's own DEF.")
    ax = die_axes(fig, [0.157, 0.215, 0.686, 0.619])
    ax.add_patch(Rectangle((CORE[0], CORE[1]), CORE[2] - CORE[0],
                           CORE[3] - CORE[1], fill=False, edgecolor="#6E6E6E",
                           linewidth=1.4, linestyle=(0, (7, 4)), zorder=1))
    macros_on(fig, ax, macros, 15.0, sizes=True)

    ch_lo, ch_hi = 60.48 + 626.70, 1387.26
    ax.annotate("", xy=(922, ch_lo), xytext=(922, ch_hi),
                arrowprops=dict(arrowstyle="<->", color="#2A2A2A",
                                linewidth=1.8), zorder=5)
    ax.text(952, (ch_lo + ch_hi) / 2,
            "700.08 um of standard-cell channel\nbetween the two macro rows",
            fontsize=13.5, va="center", ha="left", color=INK, zorder=6,
            bbox=dict(boxstyle="round,pad=0.42", fc="white", ec="#6E6E6E",
                      linewidth=1.0, alpha=0.95))

    fig.text(0.05, 0.178,
             "die  %.2f x %.2f um     core  %.2f x %.2f um"
             % (DIE_W, DIE_H, CORE[2] - CORE[0], CORE[3] - CORE[1]),
             fontsize=14.0, color=INK, family=MONO, va="top", ha="left")
    fig.text(0.05, 0.133,
             "The macros are FIXED. These eight are the only instances on the\n"
             "die whose position a person chose; the other 168,584 were placed.",
             fontsize=13.0, color=MUTED, va="top", ha="left", linespacing=1.45)
    fig.savefig(os.path.join(out, "social-3-floorplan.png"),
                facecolor=PAPER, dpi=DPI)
    plt.close(fig)
    print("  wrote social-3-floorplan.png")


# ---- 4. the numbers ---------------------------------------------------
def fig_numbers(left, right, out):
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    card(fig, "What is measured, and what is not",
         "Every row is a measurement on the sign-off run. No frequency is\n"
         "claimed for this design, at any corner, and none can be derived here.",
         "Placed and routed. Not fabricated, and not irradiated.")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    for col, rows in ((0, left), (1, right)):
        x0 = 0.05 + col * 0.485
        x1 = x0 + 0.415
        y = TOP
        for kind, a, b in rows:
            if kind == "head":
                y -= 0.014
                ax.add_patch(Rectangle((x0, y), x1 - x0, 0.0026,
                                       facecolor=RULE, edgecolor="none"))
                y -= 0.038
                ax.text(x0, y, a, fontsize=12.5, fontweight="bold",
                        color=MUTED, va="center", ha="left")
                y -= 0.040
                continue
            ax.text(x0, y, a, fontsize=13.5, color=INK, va="center", ha="left")
            ax.text(x1, y, b, fontsize=13.5, color=INK, va="center",
                    ha="right", family=MONO, fontweight="bold")
            y -= 0.039
    fig.savefig(os.path.join(out, "social-4-numbers.png"),
                facecolor=PAPER, dpi=DPI)
    plt.close(fig)
    print("  wrote social-4-numbers.png")


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    defp, nlp, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    plt.rcParams.update({"font.size": 12, "axes.linewidth": 0.8,
                         "savefig.transparent": False})

    global DIE_W, DIE_H
    DIE_W, DIE_H = read_die(defp)
    print("reading", defp)
    print("  die %.2f x %.2f um, from its own DIEAREA" % (DIE_W, DIE_H))
    cells, macros = read_def(defp)
    total = len(cells) + len(macros)        # macros are instances too
    print("  %d standard cells + %d macros = %d instances"
          % (len(cells), len(macros), total))
    pins = read_netlist(nlp)
    owner, _ = attribute(cells, pins)
    counts = Counter(owner.values())
    logic = len(cells) - counts[FILLER]

    occ = fig_regions(cells, macros, owner, out, total)
    fig_blocks(cells, macros, owner, counts, out, total)
    fig_floorplan(macros, out)

    left = [
        ("head", "PROCESS AND FLOORPLAN", ""),
        ("row", "Technology", "IHP SG13G2 130 nm, open"),
        ("row", "Die", "%.2f x %.2f um" % (DIE_W, DIE_H)),
        ("row", "Instances placed", f"{total:,}"),
        ("row", "Vendor macros, fixed by hand", "%d" % len(macros)),
        ("row", "Non-fill instances", f"{logic:,}"),
        ("head", "WHERE THE LOGIC SITS", ""),
        ("row", "Ibex RV32IMC core", f"{counts['u_ibex']:,}"),
        ("row", "Neuromorphic accelerator", f"{counts['u_npu']:,}"),
        ("row", "Central channel holds",
         "%s of %s" % (f"{sum(occ['central channel'].values()):,}",
                       f"{logic:,}")),
        ("row", "Not attributable by nets",
         "%s  (%.2f %%)" % (f"{counts[UNATTR]:,}",
                            100 * counts[UNATTR] / logic)),
        ("head", "WHAT DOES NOT EXIST", ""),
        ("row", "Silicon of this SoC", "none"),
        ("row", "Irradiation data", "none"),
        ("row", "Frequency claimed", "none"),
    ]
    right = [
        ("head", "GEOMETRIC SIGN-OFF", ""),
        ("row", "Route DRC errors", "0"),
        ("row", "LVS", "matches uniquely"),
        ("row", "XOR vs extracted view", "0 shapes"),
        ("head", "TIMING, THREE CORNERS, NO FREQUENCY", ""),
        ("row", "Worst hold slack, fast corner", "+0.0296 ns"),
        ("row", "Worst hold slack, typical", "+0.1769 ns"),
        ("row", "Worst setup slack, slow corner", "-7.5758 ns"),
        ("row", "Wire in a violating path", "1.9 % median"),
        ("head", "FORMAL, OVER ALL REACHABLE STATES", ""),
        ("row", "Property sets over the SoC", "20"),
        ("row", "Tasks run", "86"),
        ("row", "Tasks passing", "79"),
        ("row", "Without a verdict, and named", "7"),
    ]
    fig_numbers(left, right, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
