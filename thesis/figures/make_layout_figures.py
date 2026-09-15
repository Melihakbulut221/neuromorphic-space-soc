#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Draw the thesis's layout maps from a sign-off run's DEF and netlist.

    make_layout_figures.py <soc_top.def> <soc_top.nl.v> <out-dir>

WHAT THIS ANSWERS.  "Where is the SRAM, where is the processor" is a
question about a die that carries 168,592 instances, and after this
flow's synthesis almost none of them says which block it came from.
Only 1,140 instance names in the sign-off DEF contain a dot at all --
632 of those are the RAM's, most of the rest are clock buffers -- and
by this script's own prefix test exactly ONE carries a top-level block
name.  Everything else is a Yosys name, `_12345_`, with no block in it.
A picture that coloured only the named instances would colour nothing
and would answer the question wrongly.

HOW THE OTHER NINETY-SIX PER CENT ARE ATTRIBUTED.  By connectivity, in
three passes over the netlist:

  1. NETS CARRY THE HIERARCHY.  Yosys renames cells but keeps the
     hierarchical name of any net it did not create, so `\\u_ibex.xxx`
     is an Ibex net whatever drives it.  Every net whose name starts
     with a known top-level instance prefix votes for that block.
  2. MAJORITY VOTE.  Each anonymous cell is given the block that most
     of its pins' nets vote for.  Ties and cells with no named net at
     all are left for pass 3.
  3. NEIGHBOUR PROPAGATION, twice.  An unattributed cell takes the
     majority block of the cells its nets connect to.  Two rounds is
     where this converges; the remainder is reported as unattributed
     and drawn in grey, not hidden.

  Clock-tree buffers, tie cells, fill and decap are recognised by name
  or master and form their own class, because they belong to no block
  and would otherwise be attributed to whatever they happen to feed.

WHAT THE PICTURE IS AND IS NOT.  It is a map of where the placer put
the logic of each block, with the attribution above and its error bar
printed in the legend.  It is not a floorplan the design constrained:
apart from the eight macros, which are FIXED, nothing here was told
where to go.  That is the point of figure 1 -- the clusters are the
placer's, not the designer's.

Reads only the two files named on the command line.  Writes PDF and a
200 dpi PNG twin of each figure plus layout_attribution.json.
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import numpy as np

# ---- geometry, from hw/soc/pnr/clint_region.py and the vendor LEFs ----
MACRO_SIZE = {
    "RM_IHPSG13_1P_2048x64_c2_bm_bist": (784.48, 626.70),
    "RM_IHPSG13_1P_1024x32_c2_bm_bist": (416.64, 336.46),
    "RM_IHPSG13_1P_512x16_c2_bm_bist": (236.80, 191.34),
}
MACRO_LABEL = {
    "u_ram.g_ram_2048x64_ecc.u_b0": "RAM bank 0",
    "u_ram.g_ram_2048x64_ecc.u_b1": "RAM bank 1",
    "u_ram.g_ram_2048x64_ecc.u_b2": "RAM bank 2",
    "u_ram.g_ram_2048x64_ecc.u_b3": "RAM bank 3",
    "u_rom.g_rom_1024x32_ecc.u_b0": "ROM 0",
    "u_rom.g_rom_1024x32_ecc.u_b1": "ROM 1",
    "u_rom.g_rom_1024x32_ecc.u_c0": "ROM ECC 0",
    "u_rom.g_rom_1024x32_ecc.u_c1": "ROM ECC 1",
}
CORE = (60.0, 45.36, 2246.4, 2029.86)          # clint_region.py
LROM_Y0, UROM_Y0 = 60.48, 1387.26
ROM_X0, ROM_W, ROM_H = 1769.28, 416.64, 336.46
RAM_H = 626.70
CH_LO, CH_HI = LROM_Y0 + RAM_H, UROM_Y0        # 687.18 .. 1387.26

# ---- blocks: top-level instance prefix -> display name and colour ----
# Okabe-Ito, which stays distinguishable in the three common forms of
# colour blindness and in greyscale print.
BLOCKS = [
    ("u_ibex",    "Ibex RV32IMC core",        "#0072B2"),
    ("u_npu",     "Neuromorphic accelerator", "#D55E00"),
    ("u_ram",     "RAM control and ECC",      "#009E73"),
    ("u_rom",     "ROM control and ECC",      "#56B4E9"),
    ("u_clint",   "CLINT time base",          "#CC79A7"),
    ("u_timer0",  "General-purpose timer",    "#E69F00"),
    ("u_boot",    "Boot controller",          "#8C564B"),
    ("u_scrub",   "Memory scrub engine",      "#7F3FBF"),
    ("u_qspi",    "QSPI flash controller",    "#17BECF"),
    ("u_gpio",    "GPIO",                     "#BCBD22"),
    ("u_uart0",   "Console UART",             "#F0A3FF"),
    ("u_bus",     "Bus fabric and APB",       "#333333"),
    ("u_busstat", "Bus fault counters",       "#9A6324"),
    ("u_pnp",     "Plug-and-play ROM",        "#808000"),
]
BLOCK_COLOUR = {b: c for b, _, c in BLOCKS}
BLOCK_NAME = {b: n for b, n, _ in BLOCKS}
PREFIXES = [b for b, _, _ in BLOCKS]
CLOCK = "__clock__"
FILLER = "__filler__"
UNATTR = "__unattributed__"
CLOCK_COLOUR, UNATTR_COLOUR = "#9E9E9E", "#C7C7C7"

CLOCK_NAME_RE = re.compile(r"^(clkbuf|clkload|clknet|cts_)")
FILLER_NAME_RE = re.compile(r"^(FILLER|TAP|ANTENNA|PHY_)")
FILLER_MASTER_RE = re.compile(r"^sg13g2_(fill|decap|tie|antenna|.*tap)")


def norm(name):
    """DEF and netlist spell the same instance differently."""
    return name.lstrip("\\").strip().rstrip(" ")


def block_of_name(name):
    """Top-level block of an instance or net name, or None.

    norm() first: net names arrive as escaped Verilog identifiers, and
    a leading backslash silently defeats the prefix match -- the first
    run of this script attributed nothing for that reason and drew a
    grey die.
    """
    head = norm(name).split(".", 1)[0].split("/", 1)[0]
    return head if head in BLOCK_COLOUR else None


# ---- 1. the DEF: position and master of every instance ---------------
def read_def(path):
    comp = re.compile(
        r"^\s*- (\S+) (\S+)\s+.*?\+ (?:PLACED|FIXED) \( (-?\d+) (-?\d+) \)\s+(\w+)")
    cells, macros = {}, {}
    inside = False
    with open(path, errors="ignore") as f:
        for line in f:
            if line.startswith("COMPONENTS"):
                inside = True
                continue
            if line.startswith("END COMPONENTS"):
                break
            if not inside:
                continue
            m = comp.match(line)
            if not m:
                continue
            name, master, x, y, orient = m.groups()
            name, x, y = norm(name), int(x) / 1000.0, int(y) / 1000.0
            if master in MACRO_SIZE:
                macros[name] = (master, x, y, orient)
            else:
                cells[name] = (master, x, y)
    return cells, macros


# ---- 2. the netlist: which nets each instance touches -----------------
# An instance runs from its master name to the first `);` at the end of
# a line, over as many lines as the writer chose --
#   sg13g2_dfrbpq_1 _77758_ (.CLK(net),
#     .D(net),
#     .Q(\\u_ibex.x.y [3]));
# -- and the hierarchy survives only in NET names, as escaped Verilog
# identifiers (backslash, then the name, terminated by whitespace).  Of
# the 168,592 instance names in the DEF only 1,140 carry a dot, and 632
# of those are the RAM's: the flat netlist that hw/soc/flow/syn_soc_top.sh
# writes has folded the instance hierarchy away.  The nets are therefore
# the only evidence of where a cell came from, which is what makes the
# vote in attribute() the whole of the method rather than a fallback.
INST_RE = re.compile(
    r"(?m)^[ \t]*(sg13g2_\w+|RM_IHPSG13\w+)\s+(\\?\S+?)\s*\((.*?)\);[ \t]*$",
    re.S)
PIN_RE = re.compile(r"\.\w+\(([^()]*)\)")
NET_RE = re.compile(r"\\\S+|[A-Za-z_][\w$]*")


def read_netlist(path):
    """instance -> list of net names (escaped names keep their backslash)."""
    text = open(path, errors="ignore").read()
    pins = {}
    for m in INST_RE.finditer(text):
        nets = []
        for pin in PIN_RE.findall(m.group(3)):
            nets.extend(NET_RE.findall(pin))
        pins[norm(m.group(2))] = nets
    return pins


# ---- 3. attribution ---------------------------------------------------
def attribute(cells, pins):
    owner = {}
    for name, (master, _, _) in cells.items():
        if FILLER_NAME_RE.match(name) or FILLER_MASTER_RE.match(master):
            owner[name] = FILLER
            continue
        if CLOCK_NAME_RE.match(name):
            owner[name] = CLOCK
            continue
        b = block_of_name(name)
        if b:
            owner[name] = b
    stats = {"named": sum(1 for v in owner.values()
                          if v not in (CLOCK, FILLER)),
             "clock": sum(1 for v in owner.values() if v == CLOCK),
             "filler": sum(1 for v in owner.values() if v == FILLER)}

    # pass 1: nets vote
    net_block = {}
    for nets in pins.values():
        for n in nets:
            if n not in net_block:
                b = block_of_name(n)
                if b:
                    net_block[n] = b
    stats["named_nets"] = len(net_block)

    # pass 2: majority of the nets on each unattributed cell's pins
    def vote(name):
        v = Counter(net_block[n] for n in pins.get(name, ()) if n in net_block)
        if not v:
            return None
        top, cnt = v.most_common(1)[0]
        if len(v) > 1 and v.most_common(2)[1][1] == cnt:
            return None            # tie: leave for propagation
        return top

    for name in cells:
        if name in owner:
            continue
        b = vote(name)
        if b:
            owner[name] = b
    stats["by_net_vote"] = (len(owner) - stats["named"]
                            - stats["clock"] - stats["filler"])

    # pass 3: neighbours, twice. A cell's neighbours are the cells that
    # share a net with it; build the net -> cells index once.
    net_cells = defaultdict(list)
    for name, nets in pins.items():
        for n in nets:
            net_cells[n].append(name)
    for _ in range(2):
        pending = [n for n in cells if n not in owner]
        if not pending:
            break
        newly = {}
        for name in pending:
            v = Counter()
            for n in pins.get(name, ()):
                for other in net_cells.get(n, ()):
                    if other in owner and owner[other] not in (CLOCK, FILLER):
                        v[owner[other]] += 1
            if v:
                newly[name] = v.most_common(1)[0][0]
        if not newly:
            break
        owner.update(newly)
    for name in cells:
        owner.setdefault(name, UNATTR)
    stats["total"] = len(cells)
    stats["logic"] = len(cells) - stats["filler"]
    stats["unattributed"] = sum(1 for v in owner.values() if v == UNATTR)
    return owner, stats


# ---- 4. drawing -------------------------------------------------------
def macro_patches(ax, macros, label=True, fontsize=6.5, facecolor="#F2F2F2"):
    for name, (master, x, y, orient) in sorted(macros.items()):
        w, h = MACRO_SIZE[master]
        ax.add_patch(Rectangle((x, y), w, h, facecolor=facecolor,
                               edgecolor="#222222", linewidth=0.9, zorder=3))
        if label:
            short = MACRO_LABEL.get(name, name.split(".")[-1])
            ax.text(x + w / 2, y + h / 2, short, ha="center", va="center",
                    fontsize=fontsize, zorder=4,
                    bbox=dict(boxstyle="round,pad=0.18", fc="white",
                              ec="none", alpha=0.85))


def frame(ax, title_xlabel=True):
    ax.add_patch(Rectangle((CORE[0], CORE[1]), CORE[2] - CORE[0],
                           CORE[3] - CORE[1], fill=False,
                           edgecolor="#555555", linewidth=0.8,
                           linestyle=(0, (5, 3)), zorder=2))
    ax.set_xlim(-20, 2326)
    ax.set_ylim(-20, 2095)
    ax.set_aspect("equal")
    if title_xlabel:
        ax.set_xlabel("x (um)")
        ax.set_ylabel("y (um)")
    ax.tick_params(labelsize=7)
    for s in ax.spines.values():
        s.set_linewidth(0.6)


def save(fig, out, stem):
    fig.savefig(os.path.join(out, stem + ".pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(out, stem + ".png"), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", stem + ".pdf", "and", stem + ".png")


def fig_blocks(cells, macros, owner, counts, out):
    fig, ax = plt.subplots(figsize=(7.2, 6.6))
    frame(ax)
    # Draw the populous blocks first so the sparse ones stay visible;
    # the placer interleaved them, so no order is "correct" and the
    # centroid markers below are what actually answer "where is X".
    order = sorted((b for b, _, _ in BLOCKS if counts.get(b)),
                   key=lambda b: -counts[b])
    xs = defaultdict(list)
    ys = defaultdict(list)
    for name, (_, x, y) in cells.items():
        o = owner[name]
        if o == FILLER:
            continue
        xs[o].append(x)
        ys[o].append(y)
    for key, colour, z, size, alpha in (
            [(UNATTR, UNATTR_COLOUR, 0.4, 0.3, 0.7),
             (CLOCK, CLOCK_COLOUR, 0.5, 0.3, 0.7)] +
            [(b, BLOCK_COLOUR[b], 1.0, 0.45, 0.85) for b in order]):
        if not xs[key]:
            continue
        ax.scatter(xs[key], ys[key], s=size, c=colour, marker=",",
                   linewidths=0, alpha=alpha, zorder=z, rasterized=True)
    macro_patches(ax, macros)
    # Centroid of each block's cells, with its initial, so that a reader
    # can find a block at a glance in a die the placer has interleaved.
    for i, b in enumerate(order, 1):
        cx, cy = float(np.mean(xs[b])), float(np.mean(ys[b]))
        ax.scatter([cx], [cy], s=120, facecolor="white",
                   edgecolor=BLOCK_COLOUR[b], linewidth=1.6, zorder=6)
        ax.text(cx, cy, str(i), ha="center", va="center", fontsize=6.5,
                fontweight="bold", color=BLOCK_COLOUR[b], zorder=7)
    handles = [Line2D([], [], marker="o", linestyle="", markersize=5,
                      markerfacecolor=BLOCK_COLOUR[b], markeredgecolor="none",
                      label="%d. %s  (%s)"
                            % (i, BLOCK_NAME[b], f"{counts[b]:,}"))
               for i, b in enumerate(order, 1)]
    handles += [
        Line2D([], [], marker="o", linestyle="", markersize=5,
               markerfacecolor=CLOCK_COLOUR, markeredgecolor="none",
               label="clock tree  (%s)" % f"{counts.get(CLOCK,0):,}"),
        Line2D([], [], marker="o", linestyle="", markersize=5,
               markerfacecolor=UNATTR_COLOUR, markeredgecolor="#BBBBBB",
               label="unattributed  (%s)" % f"{counts.get(UNATTR,0):,}"),
        Line2D([], [], marker="s", linestyle="", markersize=6,
               markerfacecolor="#F2F2F2", markeredgecolor="#222222",
               label="vendor macro (fixed)"),
        Line2D([], [], linestyle="", marker="",
               label="fill, decap and diodes not drawn:\n%s instances"
                     % f"{counts.get(FILLER,0):,}"),
    ]
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5),
              fontsize=6.6, frameon=False, handletextpad=0.4, labelspacing=0.5)
    save(fig, out, "layout_blocks")


def fig_density(cells, macros, owner, out):
    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    pts = [(c[1], c[2]) for n, c in cells.items() if owner[n] != FILLER]
    x = np.fromiter((p[0] for p in pts), float, len(pts))
    y = np.fromiter((p[1] for p in pts), float, len(pts))
    hb = ax.hexbin(x, y, gridsize=95, cmap="magma", mincnt=1,
                   linewidths=0, zorder=1)
    for y0, y1, lab in ((CH_LO, CH_HI, "channel"),):
        ax.add_patch(Rectangle((CORE[0], y0), CORE[2] - CORE[0], y1 - y0,
                               fill=False, edgecolor="#00E5FF", linewidth=1.0,
                               linestyle=(0, (4, 2)), zorder=5))
        ax.text(CORE[0] + 14, (y0 + y1) / 2, lab, color="#00E5FF",
                fontsize=7, va="center", zorder=6)
    for y0, y1, lab in ((UROM_Y0 + ROM_H, CORE[3], "upper pocket"),
                        (CORE[1], LROM_Y0, "lower pocket")):
        if y1 - y0 <= 0:
            continue
        ax.add_patch(Rectangle((ROM_X0, y0), CORE[2] - ROM_X0, y1 - y0,
                               fill=False, edgecolor="#39FF14", linewidth=1.0,
                               linestyle=(0, (4, 2)), zorder=5))
        ax.text(ROM_X0 - 6, (y0 + y1) / 2, lab, color="#39FF14", fontsize=7,
                ha="right", va="center", zorder=6)
    macro_patches(ax, macros, label=False, facecolor="#101010")
    frame(ax)
    cb = fig.colorbar(hb, ax=ax, fraction=0.043, pad=0.02)
    cb.set_label("standard cells per bin", fontsize=7.5)
    cb.ax.tick_params(labelsize=7)
    save(fig, out, "layout_density")


def fig_two_blocks(cells, macros, owner, out):
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.9))
    for ax, key in zip(axes, ("u_ibex", "u_npu")):
        pts = [(c[1], c[2]) for n, c in cells.items() if owner[n] == key]
        if not pts:
            ax.text(0.5, 0.5, "no cells attributed", transform=ax.transAxes,
                    ha="center")
            frame(ax)
            continue
        others = [(c[1], c[2]) for n, c in cells.items()
                  if owner[n] not in (key, FILLER)]
        ox, oy = zip(*others)
        ax.scatter(ox, oy, s=0.18, c="#E8E8E8", marker=".", linewidths=0,
                   zorder=0.5, rasterized=True)
        px, py = zip(*pts)
        ax.scatter(px, py, s=0.5, c=BLOCK_COLOUR[key], marker=".",
                   linewidths=0, alpha=0.9, zorder=1, rasterized=True)
        macro_patches(ax, macros, label=False)
        frame(ax)
        ax.set_title("%s  --  %s instances" % (BLOCK_NAME[key], f"{len(pts):,}"),
                     fontsize=9)
    save(fig, out, "layout_ibex_npu")



def fig_panels(cells, macros, owner, counts, out):
    """One panel per block: the clearest answer to "where is X"."""
    keys = [b for b, _, _ in BLOCKS if counts.get(b, 0) >= 300]
    keys = sorted(keys, key=lambda b: -counts[b])[:9]
    ncol = 3
    nrow = (len(keys) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(9.4, 3.15 * nrow))
    axes = np.atleast_1d(axes).ravel()
    bg = [(c[1], c[2]) for n, c in cells.items() if owner[n] != FILLER]
    bx = np.fromiter((p[0] for p in bg), float, len(bg))
    by = np.fromiter((p[1] for p in bg), float, len(bg))
    for ax, key in zip(axes, keys):
        ax.scatter(bx, by, s=0.12, c="#ECECEC", marker=",", linewidths=0,
                   zorder=0.5, rasterized=True)
        pts = [(c[1], c[2]) for n, c in cells.items() if owner[n] == key]
        px, py = zip(*pts)
        ax.scatter(px, py, s=0.9, c=BLOCK_COLOUR[key], marker=",",
                   linewidths=0, alpha=0.85, zorder=1, rasterized=True)
        macro_patches(ax, macros, label=False)
        frame(ax, title_xlabel=False)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title("%s\n%s instances" % (BLOCK_NAME[key], f"{counts[key]:,}"),
                     fontsize=8.2)
    for ax in axes[len(keys):]:
        ax.axis("off")
    fig.subplots_adjust(hspace=0.22, wspace=0.05)
    save(fig, out, "layout_panels")


def fig_floorplan(macros, out):
    fig, ax = plt.subplots(figsize=(6.0, 5.6))
    ax.add_patch(Rectangle((0, 0), 2306.4, 2075.22, facecolor="#FAFAFA",
                           edgecolor="#000000", linewidth=1.1, zorder=0))
    ax.add_patch(Rectangle((CORE[0], CORE[1]), CORE[2] - CORE[0],
                           CORE[3] - CORE[1], facecolor="white",
                           edgecolor="#555555", linewidth=0.9,
                           linestyle=(0, (5, 3)), zorder=1))
    fills = {"RM_IHPSG13_1P_2048x64_c2_bm_bist": "#BFD9EF",
             "RM_IHPSG13_1P_1024x32_c2_bm_bist": "#FBD7B5",
             "RM_IHPSG13_1P_512x16_c2_bm_bist": "#C9E8CE"}
    for name, (master, x, y, orient) in sorted(macros.items()):
        w, h = MACRO_SIZE[master]
        ax.add_patch(Rectangle((x, y), w, h, facecolor=fills[master],
                               edgecolor="#222222", linewidth=1.0, zorder=2))
        ax.text(x + w / 2, y + h / 2 + (14 if h > 300 else 9),
                MACRO_LABEL.get(name, name), ha="center", va="center",
                fontsize=7.4, fontweight="bold", zorder=3)
        ax.text(x + w / 2, y + h / 2 - (10 if h > 300 else 7),
                "%.2f x %.2f um\n(%.0f, %.0f) %s" % (w, h, x, y, orient),
                ha="center", va="center", fontsize=6.0, zorder=3)
    ax.text(2306.4 / 2, 2075.22 - 18, "die 2306.40 x 2075.22 um",
            ha="center", va="top", fontsize=7.5)
    ax.text(CORE[0] + 6, CORE[1] + 8,
            "core %.2f x %.2f um" % (CORE[2] - CORE[0], CORE[3] - CORE[1]),
            ha="left", va="bottom", fontsize=7.0, color="#555555")
    ax.set_xlim(-30, 2336)
    ax.set_ylim(-30, 2105)
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.tick_params(labelsize=7)
    save(fig, out, "floorplan_macros")


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    defp, nlp, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    plt.rcParams.update({"font.size": 8, "axes.linewidth": 0.6,
                         "pdf.fonttype": 42, "savefig.transparent": False})
    print("reading", defp)
    cells, macros = read_def(defp)
    print("  %d standard cells, %d macros" % (len(cells), len(macros)))
    print("reading", nlp)
    pins = read_netlist(nlp)
    print("  %d instances with pin lists" % len(pins))
    owner, stats = attribute(cells, pins)
    counts = Counter(owner.values())
    stats["per_block"] = {BLOCK_NAME.get(k, k): v for k, v in counts.items()}
    stats["unattributed_fraction"] = round(
        counts[UNATTR] / max(1, len(cells) - counts[FILLER]), 5)
    with open(os.path.join(out, "layout_attribution.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print("  attribution: %d named, %d by net vote or neighbour, %d clock, "
          "%d fill/decap/diode, %d unattributed (%.2f %% of logic)"
          % (stats["named"], stats["by_net_vote"], counts[CLOCK],
             counts[FILLER], counts[UNATTR],
             100 * stats["unattributed_fraction"]))
    fig_floorplan(macros, out)
    fig_blocks(cells, macros, owner, counts, out)
    fig_density(cells, macros, owner, out)
    fig_two_blocks(cells, macros, owner, out)
    fig_panels(cells, macros, owner, counts, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
