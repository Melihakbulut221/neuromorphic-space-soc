#!/usr/bin/env python3
"""The mapped netlist's flip-flops, parsed once, for the gate-level core
campaign of docs/74.

    hw/soc/fi/gl_netlist.py <netlist.v> --census
    hw/soc/fi/gl_netlist.py <netlist.v> --emit <fi_gl_sites.vh>
    hw/soc/fi/gl_netlist.py <netlist.v> --list  <flops.tsv>

WHAT THIS IS

docs/42's campaign injects into the RTL by hierarchical name, through a
case statement hw/soc/fi/targets.py generates. The netlist has no
hierarchy: LibreLane's final `soc_top.nl.v` is one flattened module in
which every sequential element is an `sg13g2_dfrbpq_*` cell with an
anonymous instance name (`_77486_`) and a Q net that carries whatever
name yosys let survive -- an RTL name when one did, a consumer's name
when opt_clean preferred that alias (docs/32 section 4.2), `_NNNN_` when
none did. So the gate-level site list is NOT a list a person writes: it
is every sequential cell in the file, in file order, and this module is
the only thing that reads the file.

Three things come out of one parse, and the campaign checks the first
against the elaborated design before it injects anything:

  * a numbered list of every flip-flop -- index, cell, instance, Q net;
  * the Verilog the gate-level bench includes: a concatenation of every
    Q net (so a run can dump the whole flop state per cycle and so the
    bench can read any flop by index), and a force/release case over
    every flop (so the bench can upset any flop by index);
  * a census against docs/42's RTL site table: which RTL bits have a
    netlist flip-flop of the same name, which do not, and which netlist
    flip-flops under `u_ibex.` carry no RTL site's name at all.

The census by NAME is deliberately only the first word on the mapping.
docs/32 section 4.2 found four rails whose flip-flops carried the
consumer's name and one whose name moved between hardens; here the
IF/ID instruction register turns up as the register file's read-address
port. The mapping the campaign injects through is the one
hw/soc/fi/gl_map.py derives from a per-cycle trace of both designs on
the clean run, and this file's name census is what that derivation is
checked against.
"""

import argparse
import collections
import re
import sys

Flop = collections.namedtuple("Flop", "idx cell inst q d clk rst")

# Every sequential cell in sg13g2_stdcell.v. A latch here would be a
# finding, and the parse refuses to continue past one rather than
# injecting into it as if it were a flip-flop.
DFF_CELLS = ("sg13g2_dfrbpq_1", "sg13g2_dfrbpq_2",
             "sg13g2_dfrbp_1", "sg13g2_dfrbp_2")
LATCH_CELLS = ("sg13g2_dlhq_1", "sg13g2_dlhr_1", "sg13g2_dlhrq_1",
               "sg13g2_dllr_1", "sg13g2_dllrq_1", "sg13g2_sdfbbp_1")

_INST = re.compile(r"^\s*(sg13g2_\w+) (\S+) \((.*?)\);", re.M | re.S)
_PIN = re.compile(r"\.(\w+)\(([^()]*)\)")


def parse(path):
    text = open(path).read()
    flops = []
    latches = 0
    cells = collections.Counter()
    for m in _INST.finditer(text):
        cell, inst, body = m.group(1), m.group(2), m.group(3)
        cells[cell] += 1
        if cell in LATCH_CELLS:
            latches += 1
            continue
        if cell not in DFF_CELLS:
            continue
        pins = {k: v.strip() for k, v in _PIN.findall(body)}
        flops.append(Flop(len(flops), cell, inst, pins["Q"], pins.get("D"),
                          pins.get("CLK"), pins.get("RESET_B")))
    if latches:
        sys.exit("the netlist contains %d latch cells; this campaign "
                 "injects into flip-flops only and refuses to go on"
                 % latches)
    return flops, cells


# ---------------------------------------------------------------------
# names
# ---------------------------------------------------------------------
def plain(net):
    """`\\u_ibex.core_busy_q [0]` -> ('u_ibex.core_busy_q', 0);
    `net123` -> ('net123', None)."""
    net = net.strip()
    if net.startswith("\\"):
        body = net[1:]
        m = re.match(r"^(\S+) \[(\d+)\]$", body)
        if m:
            return m.group(1), int(m.group(2))
        return body.strip(), None
    m = re.match(r"^(\S+)\[(\d+)\]$", net)
    if m:
        return m.group(1), int(m.group(2))
    return net, None


def verilog_ref(net, prefix="dut."):
    """The hierarchical reference the bench writes for a Q net.

    An escaped identifier ends at whitespace, so the space after it is
    part of the syntax and is emitted on purpose."""
    net = net.strip()
    if net.startswith("\\"):
        body = net[1:]
        m = re.match(r"^(\S+) \[(\d+)\]$", body)
        if m:
            return "%s\\%s [%s]" % (prefix, m.group(1), m.group(2))
        return "%s\\%s " % (prefix, body.strip())
    return prefix + net


# ---------------------------------------------------------------------
# the census against the RTL site table
# ---------------------------------------------------------------------
def rtl_bits():
    """Every (site, bit) of hw/soc/fi/targets.py, with the name the
    flattened netlist would carry if yosys kept the RTL's."""
    import targets
    out = []
    for k, s in enumerate(targets.SITES):
        for b in range(s.width):
            out.append((k, s, b))
    return out


def name_map(flops):
    """Q net -> flop, by plain name and bit."""
    by_name = {}
    for f in flops:
        by_name[plain(f.q)] = f
    return by_name


def census(flops, cells, say=print):
    import targets
    by_name = name_map(flops)
    say("sequential cells: %s" % ", ".join(
        "%s x %d" % (c, n) for c, n in sorted(cells.items())
        if c in DFF_CELLS))
    say("flip-flops parsed: %d" % len(flops))
    core = [f for f in flops if plain(f.q)[0].startswith("u_ibex.")]
    say("  with a Q net named under u_ibex.: %d" % len(core))
    anon = [f for f in flops if re.match(r"^_\d+_$", plain(f.q)[0])
            or re.match(r"^net\d+$", plain(f.q)[0])]
    say("  with an anonymous Q net (_NNNN_ or netNNN): %d" % len(anon))

    found = 0
    missing = collections.defaultdict(list)
    matched = set()
    for k, s, b in rtl_bits():
        key = ("u_ibex." + s.path, b if s.width > 1 else None)
        alt = ("u_ibex." + s.path, b)
        f = by_name.get(key) or by_name.get(alt)
        if f is None:
            missing[(s.stratum, s.name)].append(b)
        else:
            found += 1
            matched.add(f.idx)
    total = sum(s.width for s in targets.SITES)
    say("")
    say("RTL site bits (targets.py): %d" % total)
    say("  with a netlist flip-flop of the SAME name: %d" % found)
    say("  without: %d" % (total - found))
    for (stratum, name), bits in sorted(missing.items()):
        say("    %-12s %-28s %d bit(s): %s" % (
            stratum, name, len(bits),
            _ranges(bits)))
    say("")
    extra = [f for f in core if f.idx not in matched]
    say("netlist flip-flops under u_ibex. carrying no RTL site's name: %d"
        % len(extra))
    groups = collections.Counter()
    for f in extra:
        n, _ = plain(f.q)
        groups[n] += 1
    for n, c in sorted(groups.items()):
        say("    %-70s %d" % (n, c))
    return missing, extra


def _ranges(bits):
    bits = sorted(bits)
    out = []
    start = prev = bits[0]
    for b in bits[1:]:
        if b == prev + 1:
            prev = b
            continue
        out.append("%d" % start if start == prev else "%d-%d" % (start, prev))
        start = prev = b
    out.append("%d" % start if start == prev else "%d-%d" % (start, prev))
    return ",".join(out)


# ---------------------------------------------------------------------
# the Verilog the bench includes
# ---------------------------------------------------------------------
def emit_vh(flops, path):
    n = len(flops)
    lines = []
    lines.append("// GENERATED by hw/soc/fi/gl_netlist.py -- do not edit.")
    lines.append("// %d flip-flops, in netlist file order." % n)
    lines.append("")
    lines.append("`define FI_GL_COUNT %d" % n)
    lines.append("")
    # Bit i of the vector is flop i, so the concatenation runs from the
    # last flop down to the first.
    lines.append("`define FI_GL_QVEC { \\")
    for f in reversed(flops):
        lines.append("  %s%s \\" % (verilog_ref(f.q), "," if f.idx else ""))
    lines.append("}")
    lines.append("")
    # The force lands on the cell's own output node, `int_fwire_IQ` --
    # the wire between the flip-flop primitive and the output buffer in
    # sg13g2_dfrbpq_*'s model -- and not on the Q net.  The Q net is a
    # bit of a vector for most flops, and vvp cannot force a bit select
    # of a net; forcing the whole vector would hold every sibling bit
    # for the window as well.  The inner node is a scalar, it is what
    # drives Q, and releasing it hands Q back to the primitive exactly
    # as releasing the net would.
    lines.append("`define FI_GL_FORCE_CASES \\")
    for f in flops:
        lines.append("  %d: force dut.%s.int_fwire_IQ = fi_val; \\"
                     % (f.idx, f.inst))
    lines.append("")
    lines.append("`define FI_GL_RELEASE_CASES \\")
    for f in flops:
        lines.append("  %d: release dut.%s.int_fwire_IQ; \\" % (f.idx, f.inst))
    lines.append("")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------
# fan-in cones, for structures whose flip-flops lost their names
# ---------------------------------------------------------------------
_OUTPINS = ("Q", "Y", "X", "L_HI", "L_LO")


def graph(path):
    """net -> driving instance, and instance -> (cell, pins)."""
    text = open(path).read()
    inst_re = re.compile(r"^\s*(sg13g2_\w+|RM_\w+) (\S+) \((.*?)\);", re.M | re.S)
    driver, cells = {}, {}
    for m in inst_re.finditer(text):
        cell, inst, body = m.groups()
        pins = {k: v.strip() for k, v in _PIN.findall(body)}
        cells[inst] = (cell, pins)
        for k, v in pins.items():
            if k in _OUTPINS:
                driver[v] = inst
    return driver, cells


def cone_flops(driver, cells, net, _seen=None):
    """The flip-flop instances in the fan-in cone of `net`, stopping at
    every flip-flop and every macro or port."""
    if _seen is None:
        _seen = set()
    if net in _seen:
        return set()
    _seen.add(net)
    inst = driver.get(net)
    if inst is None:
        return set()
    cell, pins = cells[inst]
    if cell in DFF_CELLS:
        return {inst}
    if cell.startswith("RM_"):
        return set()
    out = set()
    for k, v in pins.items():
        if k not in _OUTPINS:
            out |= cone_flops(driver, cells, v, _seen)
    return out


WDOG = "u_timer0.u_wdog.g_prot_tmr."


def wdog_replicas(flops, driver, cells, width=29):
    """The three replica banks of the watchdog's protected word: A by
    name (POL_A = 0, MIX = 0, so its flip-flops ARE the voter's input
    qa), B and C by the fan-in cone of the voter's qb and qc nets --
    half of each bank stores an inverted image (POL_B = 0x5555...,
    POL_C = 0xAAAA...), dfflibmap legalises a reset-to-one flip-flop as
    a reset-to-zero one behind an inverter, and the flip-flop that
    results carries no name.  A census by name would report 29 + 14 +
    15 and conclude that half of B and C had been merged away; the
    cone census reports 29 + 29 + 29 (docs/74 section 6)."""
    by_inst = {f.inst: f for f in flops}
    a = [f for f in flops if plain(f.q)[0] == WDOG + "u_prot_a.bits"]
    b, c = set(), set()
    for k in range(width):
        b |= cone_flops(driver, cells, "\\%sqb [%d]" % (WDOG, k))
        c |= cone_flops(driver, cells, "\\%sqc [%d]" % (WDOG, k))
    return (sorted(a, key=lambda f: f.idx),
            sorted((by_inst[i] for i in b), key=lambda f: f.idx),
            sorted((by_inst[i] for i in c), key=lambda f: f.idx))


def emit_wdog_vh(path, width=29):
    """The bench's shadow of the watchdog's voter, over the nets the
    netlist names: replica A's bits (= qa) and the qb/qc nets."""
    lines = ["// GENERATED by hw/soc/fi/gl_netlist.py --emit-wdog -- do not edit.",
             "  wire [%d:0] wd_qa, wd_qb, wd_qc, wd_vote;" % (width - 1)]
    for k in range(width):
        lines.append("  assign wd_qa[%d] = dut.\\%su_prot_a.bits [%d];" % (k, WDOG, k))
        lines.append("  assign wd_qb[%d] = dut.\\%sqb [%d];" % (k, WDOG, k))
        lines.append("  assign wd_qc[%d] = dut.\\%sqc [%d];" % (k, WDOG, k))
    lines += ["  assign wd_vote = (wd_qa & wd_qb) | (wd_qa & wd_qc) | (wd_qb & wd_qc);",
              "  reg [31:0] wd_mm = 32'h0;",
              "  always @(posedge clk) if (rst_n && ((wd_qa != wd_vote) || "
              "(wd_qb != wd_vote) || (wd_qc != wd_vote))) wd_mm <= wd_mm + 32'd1;",
              "  assign wd_mismatch_cycles = wd_mm;",
              "  // soc_wdog.v: P_TMRERR = 4, P_TMRCNT = 5, TMC_W = 4",
              "  assign wd_tmr_err = wd_vote[4];",
              "  assign wd_tmr_count = wd_vote[8:5];"]
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def write_list(flops, path):
    with open(path, "w") as fh:
        fh.write("idx\tcell\tinst\tq\td\tclk\trst\n")
        for f in flops:
            fh.write("%d\t%s\t%s\t%s\t%s\t%s\t%s\n" % f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--emit", default=None)
    ap.add_argument("--list", default=None)
    ap.add_argument("--emit-wdog", default=None)
    ap.add_argument("--wdog-census", action="store_true")
    args = ap.parse_args()
    if args.emit_wdog:
        emit_wdog_vh(args.emit_wdog)
        if not (args.census or args.emit or args.list or args.wdog_census):
            return
    if args.wdog_census:
        flops, _ = parse(args.netlist)
        d, c = graph(args.netlist)
        a, b, cc = wdog_replicas(flops, d, c)
        named = lambda fs: sum(1 for f in fs if not re.match(r"^_\d+_$", plain(f.q)[0]))
        print("watchdog protected word, replica flip-flops by cone: A %d (%d named), "
              "B %d (%d named), C %d (%d named)" % (len(a), named(a), len(b), named(b),
                                                    len(cc), named(cc)))
    flops, cells = parse(args.netlist)
    if args.census:
        sys.path.insert(0, __file__.rsplit("/", 1)[0])
        census(flops, cells)
    if args.emit:
        emit_vh(flops, args.emit)
    if args.list:
        write_list(flops, args.list)
    if not (args.census or args.emit or args.list):
        print("%d flip-flops" % len(flops))


if __name__ == "__main__":
    main()
