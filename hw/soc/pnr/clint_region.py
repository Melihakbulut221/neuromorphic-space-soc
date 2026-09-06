#!/usr/bin/env python3
"""The CLINT placement region of docs/73: derive the cell set, write the
constraint into a saved OpenDB database, and read the result back.

docs/72 section 6.4 found both layouts of docs/70 splitting the CLINT's
32-bit response register across the upper ROM macro, and section 15 item 1
asked for one placement probe: the CLINT's read mux and its response
register on one side of that macro, with the crossing count on the worst
path as the metric. This file is that probe's whole mechanism, in four
subcommands so that every number docs/73 quotes has a command behind it.

  members  <netlist.v> [--write members.json]
      The cell set. The design is flattened before abc (flow/syn_soc_top.sh
      runs `synth -flatten` and then `abc`), so no module boundary survives
      in the netlist; what survives are NET NAMES. The set is therefore
      derived, not read:
        seeds  = every cell whose output drives a net named `u_clint.*` or
                 `s_rdata_clint[*]` -- the CLINT's own registers (mtimecmp,
                 the mtime codeword, its check bits, rvalid_o, err_o), the
                 fabric's 32 registered response bits, and the combinational
                 drivers of the named CLINT nets;
        cone   = fixpoint over "a cell belongs if EVERY load of EVERY one of
                 its outputs already belongs, and no output touches a port
                 or a macro pin" -- the logic that feeds nothing but the
                 CLINT. This is the read mux and the SECDED decode/encode of
                 mtime; it stops at the first net a second block also
                 reads, which is where the address decode becomes the
                 fabric's rather than the CLINT's.
      A plain backward cone from the response flops does NOT work on this
      netlist: it runs through the fabric's address mux, the Ibex ALU and
      the register file's read multiplexer and returns 4,036 cells, because
      after `abc` that is one combinational cloud. The exclusive rule is
      what makes "the CLINT" a well-defined set of cells here, and docs/73
      section 3 states what it leaves out.

  apply    --odb-in <odb> --members members.json --box x0 y0 x1 y1
           --odb-out <odb> --def-out <def> [--state-in s.json --state-out s.json]
      Runs under `openroad -python`. Creates one dbRegion with the box as
      its boundary, one dbGroup inside it, and adds every member instance to
      the group. The installed OpenROAD (26Q1-2938-g0e2d771c5e) honours
      exactly this in both placers: gpl builds a separate placement problem
      per group whose bounding box is the region and BLOCKS the region's
      sites for every other cell (src/gpl/src/placerBase.cpp, "Initialize
      Region" and the siteGrid marking); dpl legalises group cells inside
      their region and keeps the rest out (src/dpl/src/Opendp.cpp,
      groupAssignCellRegions). Nothing else in the database is touched, and
      the DEF written beside the ODB is the step's own DEF plus a REGIONS
      and a GROUPS section, which is how the edit is checked. The box must
      lie on the site grid (0.48 um from the core's left edge, 3.78 um from
      its bottom) so that dpl does not invalidate a half-covered pixel row;
      the script asserts it. With --state-in the LibreLane state file of the
      step whose ODB was edited is copied with its `odb` and `def` entries
      pointed at the new files, which is what the resume form consumes.

  census   <soc_top.def> [--members members.json]
      Standard cells by die zone, docs/72 section 6.4's convention: the
      channel between the macro rows; the pocket above the upper ROM and
      the one above the lower ROM (each including the 60.48 um strip beside
      it at that height); the strip beside the ROMs themselves; elsewhere.
      Reproduces docs/72's 45,619 / 2,222 / 3,568 / 441 / 436 on s71boot's
      step-26 DEF.

  path     <max.rpt> <soc_top.def> [--members members.json] [--nth N]
      The N-th path of an OpenSTA report, one row per driver stage: cell,
      load, delay, placement, zone, CLINT membership, and whether the net
      from the previous driver crosses a ROM macro (one end in a pocket, the
      other not in that pocket or the strip beside it). Stops at the data
      arrival line, so the capture clock's buffers are not counted as
      stages. Reproduces docs/72 section 6.4's "2" on s71boot's step-37
      report.

The geometry -- macro origins, sizes, the channel bounds -- is the one
docs/59 section 4.2 extracted and config-ecc.json states; it is written
here as numbers rather than parsed so that the script has no dependency on
a run directory being present. Standard library only, except `apply`.

Nothing here writes into any existing run directory or into the
configuration; the probe's constraint is a database edit between two
steps of the flow, and docs/73 section 4 says why that form was chosen.
"""
import argparse
import collections
import json
import os
import re
import sys

LEF = os.path.join(
    os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel")),
    "ihp-sg13g2/libs.ref/sg13g2_stdcell/lef/sg13g2_stdcell.lef",
)

# ---- die geometry: config-ecc.json macro origins + LEF SIZE (docs/59 4.2)
RAM_W, RAM_H = 784.48, 626.70
ROM_W, ROM_H = 416.64, 336.46
ROM_X0 = 1769.28
ROM_X1 = ROM_X0 + ROM_W            # 2185.92
LROM_Y0, UROM_Y0 = 60.48, 1387.26
LROM_TOP = LROM_Y0 + ROM_H         # 396.94
UROM_TOP = UROM_Y0 + ROM_H         # 1723.72
CH_LO = LROM_Y0 + RAM_H            # 687.18, the lower RAM row's top
CH_HI = UROM_Y0                    # 1387.26, the upper row's bottom
CORE = (60.0, 45.36, 2246.4, 2029.86)
SITE_W, ROW_H = 0.48, 3.78


def zone(x, y):
    """docs/72 section 6.4's five zones, decided by height first."""
    if CH_LO <= y < CH_HI:
        return "channel"
    if y >= UROM_TOP and x >= ROM_X0:
        return "upper pocket"
    if LROM_TOP <= y < CH_LO and x >= ROM_X0:
        return "lower pocket"
    if x >= ROM_X1:
        return "strip"
    return "elsewhere"


def crosses_macro(z1, z2):
    """A net with one end in a pocket and the other anywhere but that pocket
    or the strip beside it passes the ROM macro."""
    if z1 == z2:
        return False
    pockets = {"upper pocket", "lower pocket"}
    for a, b in ((z1, z2), (z2, z1)):
        if a in pockets and b not in pockets and b != "strip":
            return True
    return z1 in pockets and z2 in pockets


# ---- parsing --------------------------------------------------------------

def lef_cells():
    txt = open(LEF).read()
    outpins, size = {}, {}
    # anchored: the LEF's PROPERTYDEFINITIONS block also contains the word
    # MACRO, and an unanchored match from there swallowed the first five
    # macros of the file (docs/73 section 3.4)
    for m in re.finditer(r"^MACRO (\S+)\s*$(.*?)^END \1\s*$", txt, re.S | re.M):
        name, body = m.group(1), m.group(2)
        pins = re.findall(r"PIN (\S+)\s+DIRECTION (\S+)", body)
        outpins[name] = {p for p, d in pins if d == "OUTPUT"}
        s = re.search(r"SIZE ([\d.]+) BY ([\d.]+)", body)
        size[name] = (float(s.group(1)), float(s.group(2)))
    return outpins, size


def norm(name):
    name = name.strip()
    if name.startswith("\\"):
        name = name[1:]
    return re.sub(r"\s+", "", name)


def anonymous(net):
    return re.fullmatch(r"_\d+_", net) is not None


def is_seq(master):
    return master.startswith(("sg13g2_df", "sg13g2_dl", "sg13g2_sdf"))


def is_stdcell(master):
    return not master.startswith(("RM_IHPSG13", "sg13g2_fill", "sg13g2_decap"))


class Netlist:
    def __init__(self, path):
        self.outpins, self.size = lef_cells()
        txt = open(path).read()
        inst_re = re.compile(r"^\s+(\S+)\s+(\S+)\s+\(\s*(.*?)\);", re.S | re.M)
        pin_re = re.compile(r"\.(\w+)\(([^()]*)\)")
        self.cells = {}
        self.driver = {}
        self.loads = collections.defaultdict(list)
        for m in inst_re.finditer(txt):
            master, name, body = m.group(1), m.group(2), m.group(3)
            if master in ("module", "wire", "input", "output", "assign", "reg"):
                continue
            pins = {pm.group(1): norm(pm.group(2)) for pm in pin_re.finditer(body)}
            self.cells[norm(name)] = (master, pins)
        for name, (master, pins) in self.cells.items():
            outs = self.outpins.get(master)
            for p, n in pins.items():
                if outs is None:               # a macro: every pin is a boundary
                    self.loads[n].append((name, p))
                elif p in outs:
                    self.driver[n] = (name, p)
                else:
                    self.loads[n].append((name, p))
        ports = set()
        for m in re.finditer(r"^\s*(input|output)\s+(?:\[[^\]]*\]\s*)?(.*?);", txt, re.S | re.M):
            for n in m.group(2).split(","):
                ports.add(norm(n))
        self.port_nets = {n for n in list(self.driver) + list(self.loads)
                          if re.sub(r"\[\d+\]$", "", n) in ports}

    def area(self, cell):
        w, h = self.size[self.cells[cell][0]]
        return w * h

    def clint_seeds(self):
        return {c for n, (c, p) in self.driver.items()
                if n.startswith("u_clint.") or n.startswith("s_rdata_clint")}

    def exclusive_fanin(self, seeds):
        members = set(seeds)
        changed = True
        while changed:
            changed = False
            cand = set()
            for c in members:
                master, pins = self.cells[c]
                for p, n in pins.items():
                    if p in self.outpins.get(master, set()):
                        continue
                    d = self.driver.get(n)
                    if d and d[0] not in members:
                        cand.add(d[0])
            for c in cand:
                master, pins = self.cells[c]
                if master not in self.outpins:
                    continue
                ok = True
                for p, n in pins.items():
                    if p not in self.outpins[master]:
                        continue
                    if n in self.port_nets or any(lc not in members for lc, _ in self.loads.get(n, [])):
                        ok = False
                        break
                if ok:
                    members.add(c)
                    changed = True
        return members


def read_def(path):
    pos = {}
    with open(path) as f:
        inside = False
        for line in f:
            if line.startswith("COMPONENTS"):
                inside = True
                continue
            if line.startswith("END COMPONENTS"):
                break
            if inside:
                m = re.match(r"\s*- (\S+) (\S+) .*?\+ (PLACED|FIXED) \( (-?\d+) (-?\d+) \)", line)
                if m:
                    pos[norm(m.group(1))] = (m.group(2), int(m.group(4)) / 1000, int(m.group(5)) / 1000)
    return pos


# ---- subcommands ----------------------------------------------------------

def cmd_members(a):
    nl = Netlist(a.netlist)
    seeds = nl.clint_seeds()
    members = nl.exclusive_fanin(seeds)
    seq = [c for c in members if is_seq(nl.cells[c][0])]
    area = sum(nl.area(c) for c in members)
    print(f"cells parsed: {len(nl.cells)}")
    print(f"seeds: {len(seeds)} cells drive a u_clint.* or s_rdata_clint net")
    print(f"members: {len(members)} = {len(seq)} sequential + {len(members) - len(seq)} combinational, LEF area {area:.4f} um2")
    print("  seeds by named Q net:", dict(collections.Counter(
        re.sub(r"\[\d+\]$", "", nl.cells[c][1].get("Q", "<combinational>")) for c in seeds)))
    print("  members by master:", dict(collections.Counter(nl.cells[c][0] for c in members).most_common(10)))
    ext_in = collections.Counter()
    for c in members:
        master, pins = nl.cells[c]
        for p, n in pins.items():
            if p in nl.outpins.get(master, set()):
                continue
            d = nl.driver.get(n)
            if d is None or d[0] not in members:
                ext_in[re.sub(r"\[\d+\]$", "", n) if not anonymous(n) else "<anonymous>"] += 1
    print("  input pins driven from outside the set:", dict(ext_in.most_common(6)))
    if a.write:
        json.dump(sorted(members), open(a.write, "w"), indent=0)
        print(f"wrote {a.write}")


def cmd_apply(a):
    import odb  # only under `openroad -python`
    x0, y0, x1, y1 = a.box
    for v, o, p, what in ((x0, CORE[0], SITE_W, "x0"), (x1, CORE[0], SITE_W, "x1"),
                          (y0, CORE[1], ROW_H, "y0"), (y1, CORE[1], ROW_H, "y1")):
        k = (v - o) / p
        assert abs(k - round(k)) < 1e-6, f"{what}={v} is not on the site grid ({o} + n*{p})"
    members = json.load(open(a.members))
    db = odb.dbDatabase.create()
    odb.read_db(db, a.odb_in)
    block = db.getChip().getBlock()
    assert not block.getRegions() and not block.getGroups(), "database already carries regions"
    dbu = block.getDbUnitsPerMicron()
    region = odb.dbRegion_create(block, a.name)
    odb.dbBox_create(region, int(round(x0 * dbu)), int(round(y0 * dbu)), int(round(x1 * dbu)), int(round(y1 * dbu)))
    group = odb.dbGroup_create(region, a.name)
    missing = []
    area = 0.0
    for name in members:
        inst = block.findInst(name)
        if inst is None:
            missing.append(name)
            continue
        group.addInst(inst)
        bb = inst.getMaster()
        area += bb.getWidth() * bb.getHeight() / dbu / dbu
    assert not missing, f"{len(missing)} members not in the database: {missing[:5]}"
    n = len(group.getInsts())
    util = area / ((x1 - x0) * (y1 - y0))
    print(f"region {a.name}: box ({x0}, {y0})-({x1}, {y1}) um, {(x1 - x0):.2f} x {(y1 - y0):.2f} = {(x1 - x0) * (y1 - y0):.2f} um2")
    print(f"group {a.name}: {n} instances, {area:.4f} um2 of cells, utilisation {util:.4f}")
    odb.write_db(db, a.odb_out)
    odb.write_def(block, a.def_out)
    print(f"wrote {a.odb_out}\nwrote {a.def_out}")
    if a.state_in:
        st = json.load(open(a.state_in))
        st["odb"] = os.path.abspath(a.odb_out)
        st["def"] = os.path.abspath(a.def_out)
        json.dump(st, open(a.state_out, "w"), indent=4)
        print(f"wrote {a.state_out} (odb and def re-pointed; every other view and metric kept)")


def cmd_placement(a):
    """Read the members' placed coordinates and orientations out of a DEF
    into a MANUAL_GLOBAL_PLACEMENTS-shaped JSON file."""
    members = json.load(open(a.members))
    want = set(members)
    out = {}
    with open(a.def_file) as f:
        for line in f:
            m = re.match(r"\s*- (\S+) (\S+) .*?\+ (PLACED|FIXED) \( (-?\d+) (-?\d+) \) (\w+)", line)
            if m and norm(m.group(1)) in want:
                out[norm(m.group(1))] = {"location": [int(m.group(4)) / 1000, int(m.group(5)) / 1000],
                                         "orientation": m.group(6)}
    missing = want - set(out)
    assert not missing, f"{len(missing)} members not placed in {a.def_file}"
    json.dump(out, open(a.write, "w"), indent=0)
    xs = [v["location"][0] for v in out.values()]
    ys = [v["location"][1] for v in out.values()]
    print(f"{len(out)} placements from {a.def_file}: x {min(xs):.2f}..{max(xs):.2f}, y {min(ys):.2f}..{max(ys):.2f}; wrote {a.write}")


def cmd_config(a):
    """config-ecc.json plus MANUAL_GLOBAL_PLACEMENTS, and an assertion that
    that is the only key added -- flow/pnr_soc_top.sh's own shape of guard."""
    base = json.load(open(a.base))
    placements = json.load(open(a.placements))
    assert "MANUAL_GLOBAL_PLACEMENTS" not in base
    out = dict(base)
    out["MANUAL_GLOBAL_PLACEMENTS"] = placements
    out["//clint"] = ("GENERATED BY hw/soc/pnr/clint_region.py config. docs/73: this file is "
                      "config-ecc.json plus MANUAL_GLOBAL_PLACEMENTS for the CLINT cell set of "
                      "clint_region.py members, at the coordinates in " + os.path.basename(a.placements)
                      + ". Every other key is carried byte for byte and asserted.")
    added = set(out) - set(base)
    changed = {k for k in base if base[k] != out[k]}
    assert added == {"MANUAL_GLOBAL_PLACEMENTS", "//clint"}, added
    assert not changed, changed
    json.dump(out, open(a.write, "w"), indent=4)
    print(f"wrote {a.write}: {len(placements)} manual placements added to {a.base}; no other key differs")


def cmd_census(a):
    pos = read_def(a.def_file)
    members = set(json.load(open(a.members))) if a.members else set()
    tot, ff, mem, rd = (collections.Counter() for _ in range(4))
    for c, (master, x, y) in pos.items():
        if not is_stdcell(master):
            continue
        z = zone(x, y)
        tot[z] += 1
        if is_seq(master):
            ff[z] += 1
        if c in members:
            mem[z] += 1
    order = ["channel", "upper pocket", "lower pocket", "strip", "elsewhere"]
    print(f"{a.def_file}")
    print(f"  {'zone':<14}{'std cells':>10}{'flip-flops':>12}{'CLINT set':>11}")
    for z in order:
        print(f"  {z:<14}{tot[z]:>10}{ff[z]:>12}{mem[z]:>11}")
    print(f"  {'total':<14}{sum(tot.values()):>10}{sum(ff.values()):>12}{sum(mem.values()):>11}")
    if members:
        xs = sorted(x for c, (m, x, y) in pos.items() if c in members)
        ys = sorted(y for c, (m, x, y) in pos.items() if c in members)
        if xs:
            n = len(xs)
            print(f"  CLINT set bbox x {xs[0]:.2f}..{xs[-1]:.2f} (p10 {xs[n // 10]:.2f}, p90 {xs[9 * n // 10]:.2f}); "
                  f"y {ys[0]:.2f}..{ys[-1]:.2f} (p10 {ys[n // 10]:.2f}, p90 {ys[9 * n // 10]:.2f})")


def cmd_path(a):
    pos = read_def(a.def_file)
    members = set(json.load(open(a.members))) if a.members else set()
    lines = open(a.report).read().split("\n")
    starts = [i for i, l in enumerate(lines) if l.startswith("Startpoint")]
    assert 1 <= a.nth <= len(starts), f"report has {len(starts)} paths"
    end = starts[a.nth] if a.nth < len(starts) else len(lines)
    blk = lines[starts[a.nth - 1]:end]
    rows, hdr, in_data = [], [], True
    for l in blk:
        if l.startswith(("Startpoint", "Endpoint", "Corner")):
            hdr.append(l.strip())
        if "data arrival time" in l:
            in_data = False
            hdr.append(l.strip())
        if "data required time" in l or l.strip().startswith("slack"):
            hdr.append(l.strip())
        m = re.match(r"\s*(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+) ([v^]) (\S+)/(\S+) \((\S+)\)", l)
        if m and in_data:
            rows.append(dict(cap=float(m.group(2)), delay=float(m.group(4)), inst=norm(m.group(7)),
                             pin=m.group(8), master=m.group(9)))
    for h in hdr:
        print(h)
    print(f"{'#':>3} {'driver':<16} {'cell':<20} {'load fF':>8} {'delay ns':>9} {'x':>9} {'y':>9} {'zone':<13} {'CLINT':<6} crossing")
    prev, ncross = None, 0
    for i, r in enumerate(rows):
        p = pos.get(r["inst"])
        z = zone(p[1], p[2]) if p else "?"
        x = crosses_macro(prev, z) if prev else False
        ncross += x
        prev = z
        print(f"{i + 1:>3} {r['inst']:<16} {r['master']:<20} {r['cap'] * 1000:8.1f} {r['delay']:9.3f} "
              f"{p[1] if p else 0:9.2f} {p[2] if p else 0:9.2f} {z:<13} {'member' if r['inst'] in members else '':<6} {'CROSSES' if x else ''}")
    heavy = sorted(rows, key=lambda r: -r["delay"])[:4]
    print(f"driver stages {len(rows)}, macro crossings {ncross}, "
          f"stages >= 100 fF {sum(r['cap'] >= 0.1 for r in rows)} ({sum(r['delay'] for r in rows if r['cap'] >= 0.1):.3f} ns), "
          f">= 50 fF {sum(r['cap'] >= 0.05 for r in rows)} ({sum(r['delay'] for r in rows if r['cap'] >= 0.05):.3f} ns), "
          f"CLINT-member stages {sum(r['inst'] in members for r in rows)}")
    print("heaviest:", ", ".join(f"{r['inst']} {r['master']} {r['cap'] * 1000:.0f} fF {r['delay']:.3f} ns" for r in heavy))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("members"); p.add_argument("netlist"); p.add_argument("--write")
    p.set_defaults(fn=cmd_members)
    p = sub.add_parser("apply")
    p.add_argument("--odb-in", required=True); p.add_argument("--members", required=True)
    p.add_argument("--box", nargs=4, type=float, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    p.add_argument("--odb-out", required=True); p.add_argument("--def-out", required=True)
    p.add_argument("--state-in"); p.add_argument("--state-out"); p.add_argument("--name", default="clint")
    p.set_defaults(fn=cmd_apply)
    p = sub.add_parser("placement"); p.add_argument("def_file"); p.add_argument("--members", required=True)
    p.add_argument("--write", required=True)
    p.set_defaults(fn=cmd_placement)
    p = sub.add_parser("config"); p.add_argument("--base", required=True); p.add_argument("--placements", required=True)
    p.add_argument("--write", required=True)
    p.set_defaults(fn=cmd_config)
    p = sub.add_parser("census"); p.add_argument("def_file"); p.add_argument("--members")
    p.set_defaults(fn=cmd_census)
    p = sub.add_parser("path"); p.add_argument("report"); p.add_argument("def_file")
    p.add_argument("--members"); p.add_argument("--nth", type=int, default=1)
    p.set_defaults(fn=cmd_path)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
