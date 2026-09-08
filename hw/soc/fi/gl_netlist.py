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

# Every flip-flop this file may be asked to walk past. DFF_CELLS above
# is the sg13g2 list the campaign's parse insists on; this predicate is
# wider on purpose, because the cone census below also runs on a yosys
# result that has not been through `dfflibmap` (no liberty on the
# machine) and on `synth_ecp5`, and a cone that walked THROUGH a
# flip-flop it did not recognise would report the flops behind it and
# silently overcount.
_YOSYS_FF = ("$_DFF", "$_SDFF", "$_ALDFF", "$_DFFE", "$_SDFFE", "$_DFFSR")


def is_flop(cell):
    if cell in DFF_CELLS or cell == "TRELLIS_FF":
        return True
    if cell.startswith(_YOSYS_FF):
        return True
    return bool(re.match(r"^sg13g2_s?df", cell))


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
    if is_flop(cell):
        return {inst}
    if cell.startswith("RM_") or cell.startswith("$mem"):
        return set()
    out = set()
    for k, v in pins.items():
        if k in _OUTPINS:
            continue
        # A structural netlist connects a pin to one net; a yosys JSON
        # connects it to a list of bits. One walker, both shapes.
        for one in (v if isinstance(v, list) else (v,)):
            out |= cone_flops(driver, cells, one, _seen)
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


# ---------------------------------------------------------------------
# the general replica census: three instruments over one structure
# ---------------------------------------------------------------------
#
# docs/75. `wdog_replicas` above is this, specialised to one structure
# and one width, and it is kept because docs/74 quotes it. Everything
# that counts replicas now goes through `tmr_census`, including
# sw/tests/test_soc_synthesis_guards.py, so that there is ONE cone
# implementation in the tree and not one per caller --
# `test_the_verdict_rule_is_one_file_and_not_two_copies_of_one` is the
# same rule applied to the STA verdict.
#
# THREE INSTRUMENTS, because they do not agree and the disagreement is
# the point:
#
#   by_q_net    the flip-flops whose Q net is called `<bank>.bits`.
#               This is what gl_netlist.py --census does against the
#               RTL site table and what docs/74 section 6.6 reports as
#               29 / 14 / 15. It UNDERCOUNTS a mixed replica in a
#               netlist that has been through dfflibmap: the flop that
#               stores an inverted bit is a different cell from the one
#               that carried the name, and it carries none.
#
#   by_instance the flip-flops whose INSTANCE PATH lies under the bank.
#               This is what every guard in sw/tests has always used.
#               It is exact wherever the instance path survives -- a
#               yosys `flatten` prefixes `$flatten\<path>.` onto every
#               cell it lifts, including cells dfflibmap created inside
#               the module -- and it is BLIND wherever the path does
#               not survive, which is the netlist LibreLane writes.
#
#   cone        the flip-flops in the fan-in cone of the net the voter
#               reads. It depends on no name at all and is the only one
#               of the three that works on the shipped netlist.
#
# The cone is the measurement; the other two are reported beside it so
# that a disagreement is visible rather than inferred.

# Each entry is (prefix, bank instances, the wires the bank drives, the
# voter instance). The VOTER is named because the cone must start at the
# voter's own input pin and not at the bank's output wire wherever both
# survive: those two nets are the same net in a correct design and are
# NOT the same net in a design whose voter reads one replica twice,
# which is a failure no flip-flop count can see
# (test_a_voter_wired_to_one_replica_twice_is_caught_only_by_the_cone).
TMR_STRUCTURES = {
    # name          prefix                          banks              bank outputs  voter
    "wdog":  (WDOG,                     ("u_prot_a", "u_prot_b", "u_prot_c"),
              ("qa", "qb", "qc"), "u_prot_vote"),
    "boot":  ("u_boot.g_prot_tmr.",     ("u_prot_a", "u_prot_b", "u_prot_c"),
              ("qa", "qb", "qc"), "u_prot_vote"),
    "npu":   ("u_npu.g_cfg_tmr.",       ("u_cfg_a", "u_cfg_b", "u_cfg_c"),
              ("qa", "qb", "qc"), "u_cfg_vote"),
    # the same three structures synthesised on their own, which is what
    # the guards in sw/tests do: no path above the generate block.
    "wdog_block": ("g_prot_tmr.",       ("u_prot_a", "u_prot_b", "u_prot_c"),
                   ("qa", "qb", "qc"), "u_prot_vote"),
    "boot_block": ("g_prot_tmr.",       ("u_prot_a", "u_prot_b", "u_prot_c"),
                   ("qa", "qb", "qc"), "u_prot_vote"),
    "npu_block":  ("g_cfg_tmr.",        ("u_cfg_a", "u_cfg_b", "u_cfg_c"),
                   ("qa", "qb", "qc"), "u_cfg_vote"),
}


class StructuralNetlist:
    """A netlist as LibreLane and `write_verilog` write it: a flat
    module of sg13g2 instances, nets addressed by their escaped names."""

    kind = "structural"

    def __init__(self, path):
        self.text = open(path).read()
        self.driver, self.cells = graph(path)
        self._flops = list(parse(path)[0])
        self._q = {f.inst: plain(f.q)[0] for f in self._flops}

    def net(self, name):
        """The per-bit keys of vector net `name`, taken from its USES
        rather than its declaration, because a declaration is
        `wire [28:0] \\x ;` and a use is `\\x [3]`."""
        bits = sorted({int(k) for k in re.findall(
            r"\\%s \[(\d+)\]" % re.escape(name), self.text)})
        return ["\\%s [%d]" % (name, k) for k in bits]

    def flop_instances(self):
        return [f.inst for f in self._flops]

    def q_name(self, inst):
        return self._q.get(inst)

    def q_names(self):
        return list(self._q.values())


class JsonNetlist:
    """The same netlist as yosys `write_json` writes it, which is what
    the guards in sw/tests already have in hand.

    It exists so that there is ONE cone implementation in the tree:
    `cone_flops` is generic over the key type, so a bit index serves
    where a net name serves above. It is NOT a second census -- the two
    front ends are checked against each other on the same design by
    `test_the_cone_census_reads_the_same_answer_out_of_both_front_ends`.
    """

    kind = "json"

    def __init__(self, path):
        import json
        design = json.load(open(path))
        self.driver, self.cells, self._nets = {}, {}, {}
        self._flops, self._bit_name = [], {}
        for mod in design["modules"].values():
            for name, net in mod.get("netnames", {}).items():
                self._nets.setdefault(name, net["bits"])
                if not net.get("hide_name", 0):
                    for i, b in enumerate(net["bits"]):
                        self._bit_name.setdefault(b, (name, i))
            for inst, cell in mod["cells"].items():
                pins = cell["connections"]
                self.cells[inst] = (cell["type"], pins)
                if is_flop(cell["type"]):
                    self._flops.append(inst)
                for k, v in pins.items():
                    if k in _OUTPINS:
                        for b in v:
                            self.driver[b] = inst

    def net(self, name):
        return list(self._nets.get(name, []))

    def flop_instances(self):
        return list(self._flops)

    def q_name(self, inst):
        for k in _OUTPINS:
            bits = self.cells[inst][1].get(k)
            if bits:
                got = self._bit_name.get(bits[0])
                return got[0] if got else None
        return None

    def q_names(self):
        return [self.q_name(i) for i in self._flops]


def open_netlist(path):
    return JsonNetlist(path) if str(path).endswith(".json") \
        else StructuralNetlist(path)


def replica_output(nl, prefix, bank, qname, voter=None, pin=None):
    """The net the voter reads for one replica, and its per-bit keys.

    THE ORDER MATTERS AND IT IS NOT ARBITRARY. The first candidate is
    the VOTER'S OWN INPUT, because that is the question -- what the
    voter reads -- and it is the only candidate that differs from the
    others in a design whose voter has been wired to one replica twice.
    Everything after it is a fall-back for a netlist in which that name
    did not survive: LibreLane's `soc_top.nl.v` has no
    `u_prot_vote.in_b`, and there `qb` IS the voter's input because the
    two are one net.

    `qa` normally does not exist as a net of its own either: POL_A is
    zero and MIX is off, so `q_o = bits` and opt_clean keeps one name
    for the three aliases. The candidate that hit is REPORTED, never
    assumed -- a census that silently fell back to the bank's own
    storage net would count replica A correctly and tell a reader
    nothing about it.

    A candidate whose bits exist but are UNDRIVEN is refused. abc leaves
    the name of a wire it dissolved behind, pointing at bits no cell
    drives any more, and a cone anchored there is empty for a reason
    that has nothing to do with the design."""
    cands = []
    if voter and pin:
        cands.append(prefix + voter + "." + pin)
    cands += [prefix + qname, prefix + bank + ".q_o",
              prefix + bank + ".bits"]
    for cand in cands:
        bits = nl.net(cand)
        if bits and all(b in nl.driver for b in bits):
            return cand, bits
    return None, []


def tmr_census(path, prefix, banks, qnames, nl=None, voter=None):
    """Every replica of one TMR structure, counted three ways.

    Returns one dict per bank with `cone`, `by_q_net`, `by_instance`,
    the net the cone started from and the width that net turned out to
    have -- so a caller can assert the width it expected rather than
    trusting the census to have found the whole word. A bank whose
    output net is not in the netlist at all comes back with width 0 and
    cone 0, which is a failure a caller must not read as "merged"."""
    nl = nl or open_netlist(path)
    q_of = {}
    for inst in nl.flop_instances():
        q_of[inst] = nl.q_name(inst)
    rows = []
    for bank, qname, pin in zip(banks, qnames, ("in_a", "in_b", "in_c")):
        net, bits = replica_output(nl, prefix, bank, qname, voter, pin)
        cone = set()
        for b in bits:
            cone |= cone_flops(nl.driver, nl.cells, b)
        rows.append({
            "bank": bank,
            "net": net,
            "width": len(bits),
            "cone": len(cone),
            "cone_insts": sorted(cone, key=str),
            "by_q_net": sum(1 for n in q_of.values()
                            if n == prefix + bank + ".bits"),
            "by_instance": sum(1 for i in q_of
                               if (prefix + bank + ".") in str(i)),
            "anonymous": sum(1 for i in cone
                             if q_of.get(i) is None
                             or re.match(r"^[_$]", str(q_of[i]))),
        })
    return rows


# ---------------------------------------------------------------------
# what feeds an asynchronous reset
# ---------------------------------------------------------------------
def reset_cones(path, nl=None):
    """Group every flip-flop's RESET_B net by the SET of flip-flops that
    feeds it combinationally.

    docs/75 section 6. An asynchronous reset has no setup or hold check
    and no static timing analysis in this repository asks how wide a
    glitch on one is, so what matters about it is how many flip-flops'
    outputs have to settle before it is stable. One flip-flop is safe:
    a flop output does not glitch. Two flip-flops ANDed is safe for the
    same reason a two-input AND of two registered values is. A decode of
    thirteen flip-flops spread over three TMR replicas is what docs/74
    section 10.2 measured resetting the SoC on every corrected upset.

    Returns a list of (sources, reset nets, flip-flops reset), sorted by
    the number of flip-flops reset, where `sources` is the sorted set of
    Q-net names driving the reset."""
    nl = nl or open_netlist(path)
    flops, _ = parse(path) if getattr(nl, "kind", "") != "json" else ([], None)
    q_of = {f.inst: plain(f.q)[0] for f in flops}
    groups = {}
    for f in flops:
        cone = cone_flops(nl.driver, nl.cells, f.rst)
        key = tuple(sorted(q_of.get(i, str(i)) for i in cone))
        g = groups.setdefault(key, {"sources": key, "nets": set(), "flops": 0})
        g["nets"].add(f.rst.strip())
        g["flops"] += 1
    return sorted(groups.values(), key=lambda g: -g["flops"])


def tmr_census_named(path, which, nl=None):
    prefix, banks, qnames, voter = TMR_STRUCTURES[which]
    return tmr_census(path, prefix, banks, qnames, nl=nl, voter=voter)


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
    ap.add_argument("--reset-cones", action="store_true",
                    help="every asynchronous reset, grouped by what "
                         "feeds it (docs/75 section 6)")
    ap.add_argument("--tmr-census", default=None,
                    help="one of " + ", ".join(sorted(TMR_STRUCTURES))
                         + ", or PREFIX:a,b,c")
    args = ap.parse_args()
    if args.tmr_census:
        if args.tmr_census in TMR_STRUCTURES:
            prefix, banks, qnames, voter = TMR_STRUCTURES[args.tmr_census]
        else:
            prefix, spec = args.tmr_census.rsplit(":", 1)
            banks = tuple(spec.split(","))
            qnames, voter = ("qa", "qb", "qc"), None
        for row in tmr_census(args.netlist, prefix, banks, qnames,
                              voter=voter):
            print("%-10s cone %3d  by_q_net %3d  by_instance %3d  "
                  "(width %d from %s, %d anonymous)"
                  % (row["bank"], row["cone"], row["by_q_net"],
                     row["by_instance"], row["width"], row["net"],
                     row["anonymous"]))
        if not (args.census or args.emit or args.list or args.wdog_census):
            return
    if args.emit_wdog:
        emit_wdog_vh(args.emit_wdog)
        if not (args.census or args.emit or args.list or args.wdog_census):
            return
    if args.reset_cones:
        groups = reset_cones(args.netlist)
        print("%d distinct asynchronous-reset fan-in source sets" % len(groups))
        for g in groups:
            print("  %d source flip-flop(s) -> %d reset net(s) -> %d "
                  "flip-flops reset" % (len(g["sources"]), len(g["nets"]),
                                        g["flops"]))
            for n in g["sources"]:
                print("      <- %s" % n)
        if not (args.census or args.emit or args.list or args.wdog_census
                or args.tmr_census):
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
