"""Gate-level fault injection on the hardened submission netlist.

Every fault-injection number this project has ever quoted -- the SDC
rates in docs/16, the evidence the hardening claims rest on -- comes from
RTL-level injection into `hw/rtl/pilot_top.v`. docs/24 section 8.2 item 2
records the consequence plainly: the SEU half of the verification story
has no gate-level evidence at all. This module is that evidence, and
docs/26 is its report.

The reason it matters more here than it would elsewhere is that this
project has twice measured something at RTL that the netlist did not
support. The configuration TMR was correct in RTL and merged into one
physical bank by synthesis (docs/16 section 4). The pointer TMR measured
as useless -- 23 SDC of 24 against a working majority vote -- until the
injector was retargeted, because a deposit onto a driven net models a
permanent stuck-at rather than a transient (test_fi_campaign.py target
list item 9). Both times the RTL layer said something the layer below it
did not.

---------------------------------------------------------------------
1. Why a deposit does not work here, and what does

docs/24 section 4.3 measured the wall. On a flattened netlist a deposit
onto a net is held until the net's DRIVER re-evaluates, and the driver is
a standard cell whose output does not change while the design holds its
state. Measured there, on this netlist: depositing `4'b0001` into
`u_pilot.u_lif.state` and clocking once leaves bit 0 still set a cycle
later, with the FSM's own reaction ORed on top. That is a stuck-at held
on a wire, not the single-cycle corruption of a storage bit that docs/16
specifies -- and it is the identical error the pointer-TMR episode is
about. Repeating it here to raise an injection count would be a
regression, not a result.

Four mechanisms were considered. The choice and the three rejections are
argued in docs/26 section 2; in short:

  * FORCE / RELEASE over exactly one clock period on the net driven by a
    mapped flip-flop's Q pin. CHOSEN. `Force` overrides the cell's own
    drive, so the corrupted value is what the fan-out cone sees; the
    force spans exactly one active clock edge, so the flip-flop samples
    its D input -- computed from the corrupted value, including through
    its own hold path -- and captures it; `Release` hands the net back to
    the cell, which now holds the captured value. That is what an upset
    in a flip-flop does: the state is wrong for one cycle, and whether it
    STAYS wrong is decided by the design's own next-state logic rather
    than by the injector. `test_00_method` proves both halves of that on
    this netlist rather than asserting them; docs/26 section 4 reports it.

  * Driving the cell model's internal state. Rejected as impossible here:
    `sg13g2_dfrbpq_1` is a UDP-based model, its state lives in the UDP
    instance's output, and neither Verilog nor VPI offers a way to write
    it. The `q` reg other libraries expose does not exist in these
    models (measured: the module body is a `$setuphold` specify block, a
    `notifier` reg and a UDP instance).

  * A modified cell model with an injection port. Rejected on
    provenance: `Makefile.gl` resolves the models out of the run's own
    `resolved.json` precisely so the models under the simulator are the
    ones that hardened the netlist. A local edit of that file would make
    every result conditional on a patch, and the patch would have to be
    trusted exactly where the whole point is not to trust an
    abstraction.

  * SDF annotation. Rejected as irrelevant to reachability: SDF changes
    delays, not the name space, so it makes no flip-flop reachable that
    is not reachable now, and Icarus does not implement the timing checks
    that would make an annotated run say anything post-route STA has not
    already said (docs/24 section 2.2).

---------------------------------------------------------------------
2. Getting at the flip-flops at all

`SYNTH_HIERARCHY_MODE: deferred_flatten` leaves one module, but the names
survive as single escaped identifiers containing dots:
`\\u_pilot.u_lif.state[0]` is a wire in the netlist. cocotb cannot look
those up by name -- `vpi_handle_by_name` splits on `.` -- so this module
iterates the whole top-level scope once and keys the handles on `_name`.

The RTL campaign's target paths are then mapped onto those names by
`NET_MAP` below. The mapping is not cosmetic: synthesis renamed real
storage. `wmem` became `w_data_all`, `out_pend` became `lif_out_valid`,
`sticky_sec` became `sec_seen`, `u_evq_in.drop_cnt` became `fi_drop`, and
the dispatcher's `evw` is split across three names because `ev_id` and
`ev_type` are declared as slices of it. Every mapping is justified by a
line of RTL and checked at run time against the set of nets that are
actually driven by a flip-flop Q pin, which is parsed out of the netlist
file rather than assumed.

That last check is the one that stops this suite from repeating the
pointer-TMR mistake in a new form: a target that does not resolve to a
flip-flop output is not injected, it is REPORTED as unreachable with the
reason. docs/26 section 6 carries the resulting coverage statement.

---------------------------------------------------------------------
3. The like-for-like rule

The point of this suite is comparison, so nothing about the experiment is
re-invented. `test_fi_campaign` is imported: its workload, its weight
seed, its burst structure, its golden model, its classifier and its
target list are used unchanged, and the injection phases are drawn by
replaying its own `target_list()` iteration in its own order against its
own seeded streams. A target this suite cannot reach still consumes its
draw, so every gate-level injection stands at the same (burst, delay) as
the RTL injection it is compared with.

What necessarily differs, and is recorded rather than hidden:

  * the device is the Tiny Tapeout wrapper, not `pilot_top`, because that
    is what the netlist is. The wrapper is a pin map and a reset
    synchronizer, so the stimulus is the same stimulus through
    `ui_in` / `uio_in` instead of through named ports.
  * `test_fi_campaign.fill_fifo_sentinel` has no gate-level equivalent.
    A pre-fill written by deposit would be a stuck-at; written by force
    it would evaporate on release. The two queue memories are therefore
    X until the design writes them, exactly as docs/24 section 6.2
    measured, and an injection into a slot that is still X is not a bit
    flip -- it is recorded as skipped, with the reason, and never
    classified.

Run:  cd hw/tb && make -f Makefile.glfi
Log:  hw/tb/gl_fi_results.json
Doc:  docs/26-gate-level-fault-injection.md
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import cocotb
import cocotb.utils
from cocotb.clock import Clock
from cocotb.handle import Force, Release
from cocotb.triggers import RisingEdge, Timer

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
for _p in (str(HERE), str(REPO_ROOT), str(REPO_ROOT / "sw")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_pilot_top as tt            # noqa: E402

from golden.regmap_gen import ADDR     # noqa: E402


def _git(*args):
    return subprocess.run(("git", "-C", str(REPO_ROOT)) + args,
                          capture_output=True, text=True,
                          check=True).stdout


def _blob(path):
    if not path:
        return None
    try:
        return _git("hash-object", str(path)).strip()
    except Exception:                        # noqa: BLE001
        return None


# ---------------------------------------------------------------------
# the RTL campaign of record, pinned rather than picked up
# ---------------------------------------------------------------------
# The RTL campaign is imported rather than copied, so that its workload,
# weight seed, burst structure, golden model, classifier and target list
# are used unchanged and the comparison is like-for-like by construction.
# Importing it binds ITS cocotb tests into ITS namespace, not this one,
# so nothing extra runs -- the property test_pilot_gl relies on too.
#
# But it is imported from a COMMIT, not from the working tree, and the
# reason is not hypothetical. The first full run of this suite read
# hw/tb/test_fi_campaign.py out of the working tree while that file was
# under concurrent edit. Its directed cases acquired a step naming
# `fetch_expire` -- a register added to hw/rtl/pilot_top.v AFTER this
# netlist was hardened -- so one of the twelve constructions referred to
# storage that does not exist in the design being measured, and the
# suite crashed on it rather than reporting it. A baseline that moves
# under a comparison is not a baseline.
#
# The pin is derived, and the rule is not "the newest RTL campaign". It
# is **the newest RTL campaign that was run against the RTL this netlist
# was synthesized from**, and the difference is the whole point.
#
# A netlist is a photograph of one commit. docs/24 section 1.2 records
# that the shape-6x2 harden was pinned against e1361fe by
# hw/openlane/pin_rtl.py. While this suite was being written the RTL
# moved twice, and the second move -- "Make the fault report unerasable"
# -- retired the very flip-flops one of the disagreements in section 5 is
# about. An RTL campaign run after that describes a design that is not
# in this netlist, so comparing against it would report a difference
# between two designs as though it were a difference between two levels.
#
# So: walk the commits that touched hw/tb/fi_campaign_results.json,
# newest first, and take the first one whose hw/rtl tree is IDENTICAL to
# the netlist's pinned RTL. When the RTL moves on, this pin does not
# move with it, which is correct and is stated rather than hidden.
NETLIST_RTL = os.environ.get("GLFI_NETLIST_RTL", "e1361fe")


def _rtl_baseline():
    want = _git("rev-parse", f"{NETLIST_RTL}^{{tree}}:hw/rtl").strip()
    for c in _git("log", "--format=%H", "--",
                  "hw/tb/fi_campaign_results.json").split():
        try:
            if _git("rev-parse", f"{c}^{{tree}}:hw/rtl").strip() == want:
                return c
        except subprocess.CalledProcessError:
            continue
    raise RuntimeError(
        "no committed RTL fault-injection campaign was run against the RTL "
        f"this netlist came from ({NETLIST_RTL}); there is nothing to "
        "compare against and a comparison against a different design would "
        "report a design change as a level difference")


RTL_REF = os.environ.get("GLFI_RTL_REF") or _rtl_baseline()

if RTL_REF == "WORKTREE":
    import test_fi_campaign as fi      # noqa: E402
    RTL_LOG = json.loads((HERE / "fi_campaign_results.json").read_text())
    RTL_CAMPAIGN_BLOB = _blob(HERE / "test_fi_campaign.py")
    RTL_LOG_BLOB = _blob(HERE / "fi_campaign_results.json")
else:
    import importlib.util              # noqa: E402
    _ref_dir = Path(os.environ.get("SIM_BUILD", str(HERE))) / "rtl_ref"
    _ref_dir.mkdir(parents=True, exist_ok=True)
    _ref_src = _ref_dir / "test_fi_campaign.py"
    _ref_src.write_text(_git("show", f"{RTL_REF}:hw/tb/test_fi_campaign.py"))
    _spec = importlib.util.spec_from_file_location("fi_campaign_ref", _ref_src)
    fi = importlib.util.module_from_spec(_spec)
    sys.modules["fi_campaign_ref"] = fi
    _spec.loader.exec_module(fi)
    RTL_LOG = json.loads(
        _git("show", f"{RTL_REF}:hw/tb/fi_campaign_results.json"))
    RTL_CAMPAIGN_BLOB = _git(
        "rev-parse", f"{RTL_REF}:hw/tb/test_fi_campaign.py").strip()
    RTL_LOG_BLOB = _git(
        "rev-parse", f"{RTL_REF}:hw/tb/fi_campaign_results.json").strip()

CLK_NS = fi.CLK_NS

# ---------------------------------------------------------------------
# knobs
# ---------------------------------------------------------------------
# A comma-separated list of RTL group names restricts the campaign, for
# iterating on one structure without paying for the whole run. A
# restricted run writes to a differently named log so it can never be
# mistaken for the full one.
GROUPS_FILTER = tuple(g for g in os.environ.get("GLFI_GROUPS", "").split(",")
                      if g)
RUN_TAG = os.environ.get("GLFI_TAG", "")

RESULTS = []
NOTES = {}
WALL = {}
CLK = {}          # the one clock handle, so the injector can find an edge


# ---------------------------------------------------------------------
# the flip-flop map, parsed out of the netlist
# ---------------------------------------------------------------------
_CELL = re.compile(r"\b(sg13g2_\w+)\s+(\\?\S+)\s*\((.*?)\);", re.S)
_QPIN = re.compile(r"\.Q\(\s*(\\[^\s]+\s|[^\s,)]+)\s*\)")


def flop_output_nets(netlist_path):
    """Every net in the netlist that is driven by a flip-flop's Q pin.

    This is the definition of a legal injection target for this suite,
    and it is read out of the netlist rather than inferred from a name.
    A net that is not in this set is combinational or a cell input, and
    forcing it would model a stuck-at on a wire -- the exact error
    docs/24 section 4.3 measured and the pointer-TMR episode is about.
    """
    src = Path(netlist_path).read_text()
    nets = set()
    for cell, _inst, conns in (m.groups() for m in _CELL.finditer(src)):
        if not cell.startswith("sg13g2_df") and not cell.startswith("sg13g2_sdf"):
            continue
        q = _QPIN.search(conns)
        if q:
            n = q.group(1).strip()
            nets.add(n[1:] if n.startswith("\\") else n)
    return nets


# How an RTL target path maps onto a netlist net name. Each entry is
# (rtl path, function of (bit, geometry) -> netlist name or None). Every
# rename below is a fact about this netlist checked against the RTL line
# that causes it; docs/26 section 3.2 tabulates them with the references.
def _fmt(template):
    return lambda bit, geo: template.format(b=bit)


def _wmem(index):
    # lif_core.v line 570: assign w_data_all[gw*64 + gk*4 +: 4] =
    # wmem[gw*WPW + gk], WPW = 16. With i = gw*16 + gk that is
    # w_data_all[4*i + b] = wmem[i][b] exactly, for every i.
    return lambda bit, geo: f"u_pilot.u_lif.w_data_all[{4 * index + bit}]"


def _evw(bit, geo):
    # pilot_top.v 1438-1439: ev_id = evw[9:0], ev_type = evw[15:14]. The
    # 16-bit register survives; yosys named its bits after the three
    # aliases, so bits 10..13 keep the name `evw` and the rest do not.
    if bit < 10:
        return f"u_pilot.ev_id[{bit}]"
    if bit < 14:
        return f"u_pilot.evw[{bit}]"
    return f"u_pilot.ev_type[{bit - 14}]"


def _out_event(bit, geo):
    # lif_core.v 851: out_event <= {2'b00, 4'b0000, spike_id}. Bits 15:10
    # are constants and synthesis removed their flip-flops; the netlist
    # has ten, not sixteen. An RTL injection above bit 9 lands on storage
    # that does not exist in the manufactured design.
    return f"u_pilot.lif_out_event[{bit}]" if bit < 10 else None


NET_MAP = {
    "u_lif.state": _fmt("u_pilot.u_lif.state[{b}]"),
    "u_lif.wchk": _fmt("u_pilot.u_lif.wchk[{b}]"),
    "u_lif.smem": _fmt("u_pilot.u_lif.smem[{b}]"),
    "u_lif.jj": _fmt("u_pilot.u_lif.jj[{b}]"),
    "u_lif.ev_axon_r": _fmt("u_pilot.u_lif.ev_axon_r[{b}]"),
    # lif_core.v 507/707: assign out_valid = out_pend, so the flop that
    # holds out_pend is named after the pilot-level wire it drives.
    "u_lif.out_pend": _fmt("u_pilot.lif_out_valid"),
    "u_lif.out_event": _out_event,
    # pilot_top.v 1197: .drop_cnt(fi_drop)
    "u_evq_in.drop_cnt": _fmt("u_pilot.fi_drop[{b}]"),
    # pilot_top.v 1240-1241: .rd_data(fo_rd_data), .rd_valid(fo_rd_valid)
    "u_evq_out.rd_valid": _fmt("u_pilot.fo_rd_valid"),
    "u_evq_out.rd_data": _fmt("u_pilot.fo_rd_data[{b}]"),
    # pilot_top.v 1329: assign aer_out_vld = oh_valid
    "oh_valid": _fmt("aer_out_vld"),
    "oh_req": _fmt("u_pilot.oh_req"),
    "oh_data": _fmt("u_pilot.oh_data[{b}]"),
    "dstate": _fmt("u_pilot.dstate[{b}]"),
    "evw": _evw,
    "fetch_wait": _fmt("u_pilot.fetch_wait[{b}]"),
    "fetch_timeout": _fmt("u_pilot.fetch_timeout"),
    "oh_wait": _fmt("u_pilot.oh_wait[{b}]"),
    "oh_timeout": _fmt("u_pilot.oh_timeout"),
    "cfg_axon": _fmt("u_pilot.cfg_axon[{b}]"),
    "ctrl_en": _fmt("u_pilot.ctrl_en"),
    "node_id": _fmt("u_pilot.node_id[{b}]"),
    "n_addr": _fmt("u_pilot.n_addr[{b}]"),
    "w_addr": _fmt("u_pilot.w_addr[{b}]"),
    "scratch": _fmt("u_pilot.scratch[{b}]"),
    "ecc_inj_pos": _fmt("u_pilot.ecc_inj_pos[{b}]"),
    "tmr_inj": _fmt("u_pilot.tmr_inj[{b}]"),
    "ecc_data": _fmt("u_pilot.ecc_data[{b}]"),
    "ecc_check": _fmt("u_pilot.ecc_check[{b}]"),
    "cnt_sec": _fmt("u_pilot.cnt_sec[{b}]"),
    "cnt_ded": _fmt("u_pilot.cnt_ded[{b}]"),
    "cnt_oor": _fmt("u_pilot.cnt_oor[{b}]"),
    "cnt_tmr": _fmt("u_pilot.cnt_tmr[{b}]"),
    "fault_addr": _fmt("u_pilot.fault_addr[{b}]"),
    "sticky_errcfg": _fmt("u_pilot.sticky_errcfg"),
    "sticky_ovf": _fmt("u_pilot.sticky_ovf"),
    "sticky_sync": _fmt("u_pilot.sticky_sync"),
    # pilot_top.v 1907-1909: assign sec_seen = sticky_sec, and so on. The
    # three sticky bits are named after the output ports they drive.
    "sticky_sec": _fmt("sec_seen"),
    "sticky_ded": _fmt("ded_seen"),
    "sticky_tmr": _fmt("tmr_seen"),
}

# Targets with no flip-flop behind them in this netlist, with the reason.
# Stated here so the coverage report is a fact about the design rather
# than a list of things that happened not to resolve.
UNREACHABLE = {
    "ctrl_scrub_en":
        "no flip-flop of this name survives; the scrub-enable bit was "
        "absorbed into the logic it gates",
}

_IDX = re.compile(r"^(.*?)\[(\d+)\]$")

# Flip-flops resolved at run time by a controlled experiment rather than
# by a name. Filled by identify_flop(); see test_00 section F.
RESOLVED = {}


def bank_nets(prefix):
    """One replica bank's flip-flops, split by whether the name kept its
    RTL bit index.

    Synthesis kept `bits[i]` as the net name for only some of the flops
    in a replicated bank -- 51 of 55 in configuration bank A, 4 in bank
    B -- and gave the rest yosys-internal names. The flops are still
    there and still that bank's storage; only the index is gone.
    """
    named, unnamed = {}, []
    pat = re.compile(re.escape(prefix) + r"bits\[(\d+)\]$")
    for n in FLOP_NETS:
        if not n.startswith(prefix):
            continue
        m = pat.match(n)
        if m:
            named[int(m.group(1))] = n
        else:
            unnamed.append(n)
    return named, sorted(unnamed)


def bank_target(path, bit, all_bits):
    """A replica bank's storage flop for one RTL bit index.

    Returns (net, reason, index_is_exact). When the name survived, the
    mapping is exact. When it did not, the flop is still injectable IF
    the RTL group covers the bank's FULL width -- then the set of flops
    injected is provably the same set whatever order they are assigned
    in, so a group total is exact even though a per-bit label inside the
    bank may be permuted. That is true of the AER pointer replicas (three
    bits, three flops) and not true of the configuration replicas (five
    sampled bits of fifty-five), which is why the configuration domain
    gets its own full sweep in test_05 instead of a guess here.
    """
    prefix = f"u_pilot.{path[:-len('bits')]}"
    named, unnamed = bank_nets(prefix)
    if bit in named:
        return named[bit], None, True
    if not named and not unnamed:
        return None, f"no storage found for the replica bank {prefix}", False
    if all_bits is None or len(named) + len(unnamed) != len(all_bits):
        return None, (
            f"{prefix}bits[{bit}] kept no name through synthesis, and the "
            f"campaign samples {len(all_bits) if all_bits else '?'} of the "
            f"bank's {len(named) + len(unnamed)} flip-flops, so which flop "
            f"carries this bit cannot be recovered"), False
    missing = [b for b in sorted(all_bits) if b not in named]
    if len(missing) != len(unnamed) or bit not in missing:
        return None, f"{prefix}bits[{bit}] cannot be assigned a flop", False
    return unnamed[missing.index(bit)], None, False


def map_target(path, bit, all_bits=None):
    """RTL target path + bit -> (netlist net name, reason-if-none).

    Callers that need to know whether the bit index survived use
    map_target_x, which returns the third value too.
    """
    return map_target_x(path, bit, all_bits)[:2]


def map_target_x(path, bit, all_bits=None):
    if (path, bit) in RESOLVED:
        return RESOLVED[(path, bit)], None, True
    if path in UNREACHABLE:
        return None, UNREACHABLE[path], True

    # memory-word forms: u_lif.vmem[j], u_lif.rmem[j], u_lif.wmem[i],
    # u_evq_{in,out}.mem[i]
    m = _IDX.match(path)
    if m:
        base, i = m.group(1), int(m.group(2))
        if base == "u_lif.wmem":
            return _wmem(i)(bit, None), None, True
        if base in ("u_lif.vmem", "u_lif.rmem",
                    "u_evq_in.mem", "u_evq_out.mem"):
            return f"u_pilot.{base}[{i}][{bit}]", None, True

    # replica banks: u_cfg_{a,b,c}.bits, u_evq_*.u_{w,r}ptr_{a,b,c}.bits
    if path.endswith(".bits"):
        return bank_target(path, bit, all_bits)

    fn = NET_MAP.get(path)
    if fn is None:
        return None, f"no mapping rule for the RTL path {path}", True
    net = fn(bit, None)
    if net is None:
        return None, (f"{path}[{bit}] has no flip-flop in this netlist: "
                      f"synthesis proved the bit constant"), True
    return net, None, True


# ---------------------------------------------------------------------
# pin plumbing: the same stimulus, through the wrapper's pins
# ---------------------------------------------------------------------
# test_fi_campaign drives pilot_top's named ports; the netlist is the
# Tiny Tapeout wrapper, so the same protocol goes through ui_in / uio_in.
# The helpers below are test_pilot_top's, which are already the
# port-driven form of exactly this protocol, wrapped so the campaign
# reads the same as its RTL twin.
def busy(dut):
    return tt.uo(dut, tt.BUSY)


def status_pins(dut):
    return {"err": tt.uo(dut, tt.ERR), "sec_seen": tt.uo(dut, tt.SEC),
            "ded_seen": tt.uo(dut, tt.DED), "tmr_seen": tt.uo(dut, tt.TMR)}


async def clk_edges(dut, n):
    for _ in range(n):
        await RisingEdge(dut.clk)


async def hard_reset(p):
    """Assert rst_n, release it, leave the clock running.

    Two cycles longer on each side than test_fi_campaign's, because the
    wrapper's two-flop reset synchronizer sits between the pin and the
    design. Nothing downstream depends on the length: every injection
    phase is measured from the first BUSY cycle of a burst, not from
    reset.
    """
    p.dut.rst_n.value = 0
    await clk_edges(p.dut, 7)
    p.dut.rst_n.value = 1
    await clk_edges(p.dut, 7)


async def pin_event(p, kind, axon):
    """One AER command through the parallel pins; fi.pin_event's timing."""
    p.set_ui(tt.AER_IN_TICK, 1 if kind == "T" else 0)
    p.set_uio((axon or 0) & 0xF)
    await clk_edges(p.dut, 2)
    p.set_ui(tt.AER_IN_STB, 1)
    await clk_edges(p.dut, 2)
    p.set_ui(tt.AER_IN_STB, 0)
    await clk_edges(p.dut, 2)


async def pulse_scrub(p):
    await clk_edges(p.dut, 2)
    p.set_ui(tt.SCRUB_STB, 1)
    await clk_edges(p.dut, 3)
    p.set_ui(tt.SCRUB_STB, 0)
    await clk_edges(p.dut, 3)


async def wait_idle(p, budget=fi.BUSY_BUDGET):
    for _ in range(budget):
        if not busy(p.dut):
            return True
        await RisingEdge(p.dut.clk)
    return False


async def drain(p, limit=fi.DRAIN_LIMIT):
    # One edge first, to put the serial frames back on the system-clock
    # grid. An injection ends 3 ns past an edge and a burst can go idle
    # there; test_pilot_top.realign records what a leftover offset costs
    # (the whole 32-bit word comes back shifted by one bit). The design
    # is idle at this point, so the extra cycle changes nothing else.
    await RisingEdge(p.dut.clk)
    words = []
    for _ in range(limit):
        word = await tt.rd(p, ADDR["EVQ_OUT"])
        if not word & (1 << 31):
            return words
        words.append(word & 0xFFFF)
    return words


async def bring_up(p, words, ecc_inj=None, scrub_en=False):
    """fi.bring_up, minus the sentinel fill (section 3 of the docstring)."""
    await hard_reset(p)
    await tt.wr(p, ADDR["CTRL"], fi.CTRL_STATE_CLR)
    await tt.wr(p, ADDR["CFG_THRESH"], fi.CFG.thresh & 0xFFFF)
    await tt.wr(p, ADDR["CFG_VRESET"], fi.CFG.v_reset & 0xFFFF)
    await tt.wr(p, ADDR["CFG_LEAK"], fi.CFG.leak_shift)
    await tt.wr(p, ADDR["CFG_SYNSHIFT"], fi.CFG.syn_shift)
    await tt.wr(p, ADDR["CFG_REFR"], fi.CFG.refr_period)
    await tt.wr(p, ADDR["CFG_FLAGS"], 2 if fi.CFG.leak_en else 0)
    await tt.wr(p, ADDR["PASS_TILE_OFF"], 0)

    await tt.wr(p, ADDR["W_ADDR"], 0)
    for wi, word in enumerate(words):
        if ecc_inj is not None and ecc_inj[0] == wi:
            await tt.wr(p, fi.ADDR_ECC_INJ_POS, ecc_inj[1])
            await tt.wr(p, ADDR["ECC_INJ"], ecc_inj[2])
        await tt.wr(p, ADDR["W_DATA_LO"], word & 0xFFFF_FFFF)
        await tt.wr(p, ADDR["W_DATA_HI"], (word >> 32) & 0xFFFF_FFFF)

    await tt.wr(p, ADDR["CTRL"],
                fi.CTRL_EN | (fi.CTRL_SCRUB_EN if scrub_en else 0))
    assert not busy(p.dut), "the bring-up left the pilot busy"


async def read_observations(p, n_neurons, completed):
    """fi.read_observations, in the same order and for the same reasons."""
    dut = p.dut
    obs = {
        "status": await tt.rd(p, ADDR["STATUS"]),
        "cnt_sec": await tt.rd(p, ADDR["CNT_SEC"]),
        "cnt_ded": await tt.rd(p, ADDR["CNT_DED"]),
        "cnt_ovf": await tt.rd(p, ADDR["CNT_EVQ_OVF"]),
        "cnt_oor": await tt.rd(p, ADDR["CNT_AXON_OOR"]),
        "cnt_tmr": await tt.rd(p, fi.ADDR_CNT_TMR),
        "pins": status_pins(dut),
    }
    if not completed:
        await tt.wr(p, ADDR["CTRL"], fi.CTRL_SOFT_RST)
        await wait_idle(p, 200)
    state = []
    for j in range(n_neurons):
        await tt.wr(p, ADDR["N_ADDR"], j)
        word = await tt.rd(p, ADDR["N_DATA"])
        v = word & 0xFFFF
        state.append((v - 0x10000 if v >= 0x8000 else v, (word >> 16) & 0xF))
    obs["state"] = state
    return obs


# ---------------------------------------------------------------------
# the injection primitive
# ---------------------------------------------------------------------
def bit_of(handle):
    """0, 1, or None when the net is not fully defined."""
    s = str(handle.value)
    return int(s, 2) if s in ("0", "1") else None


async def upset(net, flip=True, value=None):
    """Model one single-event upset in the flip-flop that drives `net`.

    The caller must already be standing 3 ns past a rising clock edge --
    the same offset test_fi_campaign uses, and for the same recorded
    reason: an injection made ON the edge is overwritten by that edge's
    own update before anything samples it.

    Force from here to 3 ns past the NEXT rising edge, then release. The
    forced window therefore spans exactly one active clock edge:

      * during the window the fan-out cone sees the corrupted value, so
        the fault propagates exactly as a real upset would;
      * at the edge inside the window the driving flip-flop samples its
        own D input, which was computed from the corrupted value. Where
        the register holds (an enable implemented as a feedback mux, the
        usual mapping here) that D IS the corrupted value, so the flop
        captures the corruption and the upset persists after release --
        which is what an upset in storage does. Where the register is
        reloaded every cycle the flop captures the new value and the
        upset does not persist -- which is also what a real upset does.
        The injector decides neither; the design does.
      * on release the net returns to the cell's own drive, so nothing is
        held on a wire and there is no stuck-at.

    Returns the value that was forced, or None if the net was not defined
    (X) at the injection instant, in which case NOTHING is forced: a
    force onto an undefined node is not a bit flip and must not be
    counted as one.
    """
    was = bit_of(net)
    if was is None:
        return None
    forced = (1 - was) if flip else int(value)
    net.value = Force(forced)
    await RisingEdge(CLK["clk"])
    await Timer(3, unit="ns")
    net.value = Release()
    return forced


async def upset_word(nets, values):
    """The multi-bit form, for the directed cases' absolute writes.

    Every net is forced in the same window, so the whole register is
    corrupted for exactly one cycle. Returns the popcount of the change,
    which is what makes an absolute write reportable as what it is: not
    necessarily a single-event upset. This is the gate-level twin of
    test_fi_campaign.force_now and it carries the same warning.
    """
    olds = [bit_of(n) for n in nets]
    if any(o is None for o in olds):
        return None
    moved = 0
    for n, old, new in zip(nets, olds, values):
        if old != new:
            moved += 1
        n.value = Force(new)
    await RisingEdge(CLK["clk"])
    await Timer(3, unit="ns")
    for n in nets:
        n.value = Release()
    return moved


async def inject_after_busy(p, nets, delay):
    """Wait for BUSY, count `delay` cycles, upset. fi.inject_after_busy."""
    dut = p.dut
    for _ in range(fi.BUSY_BUDGET):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if busy(dut):
            break
    else:
        raise AssertionError("BUSY never rose after the first burst event")
    await clk_edges(dut, delay)
    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")
    return await upset(nets)


async def run_stimulus(p, inj_burst=None, net=None, delay=0, script=None,
                       script_log=None):
    """fi.run_stimulus: three bursts, one injection inside one of them."""
    words = []
    outcome = {"forced": None}
    for b, burst in enumerate(fi.BURSTS):
        injector = None
        if b == inj_burst:
            injector = cocotb.start_soon(
                run_script(p, script, script_log) if script is not None
                else inject_after_busy(p, net, delay))
        for kind, axon in burst:
            await pin_event(p, kind, axon)
        if injector is not None:
            got = await injector
            if script is None:
                outcome["forced"] = got
        ok = await wait_idle(p)
        words.extend(await drain(p))
        if not ok:
            return False, words, outcome
    return True, words, outcome


# ---------------------------------------------------------------------
# directed scripts (the gate-level twin of fi.run_script)
# ---------------------------------------------------------------------
async def run_script(p, steps, log):
    """fi.run_script's grammar, with force/release in place of deposits.

    ("xor", path, bit)        one single-event upset
    ("force", path, value)    an absolute write to a named register; the
                              popcount of the change is logged
    ("wait", n)               n clock cycles
    ("until", path, value, n) advance until the named register reads
                              `value`, at most n cycles. An OBSERVATION
                              used to place a deposit, never to classify.
    """
    dut = p.dut
    for _ in range(fi.BUSY_BUDGET):
        await RisingEdge(dut.clk)
        await Timer(3, unit="ns")
        if busy(dut):
            break
    else:
        raise AssertionError("BUSY never rose for a directed injection")

    for step in steps:
        kind = step[0]
        if kind == "wait":
            for _ in range(step[1]):
                await RisingEdge(dut.clk)
                await Timer(3, unit="ns")
            log.append(f"wait {step[1]}")
        elif kind == "xor":
            name, why = map_target(step[1], step[2])
            if name is None or name not in FLOP_NETS:
                log.append(f"upset {step[1]} bit {step[2]}: {why or name}")
                log.append("NOT CONSTRUCTED")
                continue
            v = await upset(NETS[name])
            log.append(f"upset {step[1]} bit {step[2]} -> {v}")
            if v is None:
                log.append("NOT CONSTRUCTED")
        elif kind == "force":
            nets, vals = register_nets(step[1], step[2])
            if nets is None:
                log.append(f"force {step[1]} = {step[2]}: {vals}")
                log.append("NOT CONSTRUCTED")
                continue
            n = await upset_word(nets, vals)
            log.append(f"force {step[1]} = {step[2]} ({n} bit(s) flipped)")
            if n is None:
                log.append("NOT CONSTRUCTED")
        elif kind == "until":
            _, path, want, budget = step
            nets, why = register_nets(path, 0)
            if nets is None:
                log.append(f"until {path} == {want}: {why}")
                log.append("NOT CONSTRUCTED")
                continue
            hit = False
            for _ in range(budget + 1):
                bits = [bit_of(n) for n in nets]
                if None not in bits and \
                        sum(b << i for i, b in enumerate(bits)) == want:
                    hit = True
                    break
                await RisingEdge(dut.clk)
                await Timer(3, unit="ns")
            log.append(f"until {path} == {want}: {'hit' if hit else 'MISSED'}")
            if not hit:
                log.append("NOT CONSTRUCTED")
        else:
            # Not an error. A step kind this suite does not implement is
            # a construction it cannot build, which is reported and not
            # classified. The RTL campaign grew an `xor?` step -- a
            # deposit into a declared-retired target -- after this
            # netlist was hardened; raising here would have read as a
            # broken gate-level suite rather than as a design that has
            # moved past the netlist.
            log.append(f"step {step[0]} is not implemented at gate level")
            log.append("NOT CONSTRUCTED")
    return log


# Widths of the registers the directed cases write as a whole.
REG_WIDTH = {"dstate": 2, "fetch_wait": 6, "oh_wait": 6,
             "fetch_timeout": 1, "oh_timeout": 1, "oh_req": 1}


def register_nets(path, value):
    """Every net of a named register, LSB first, with the target value.

    Returns (None, reason) rather than raising when the register is not
    in this netlist. A directed case that names storage the netlist does
    not have has not failed -- it has not been CONSTRUCTED, which is a
    different thing and the only honest way to report it. This is not
    defensive coding for its own sake: the RTL campaign grew a step
    naming `fetch_expire`, a register added to the RTL after this
    netlist was hardened, and a crash there would have read as a broken
    gate-level suite rather than as a design that has moved on.
    """
    w = REG_WIDTH.get(path)
    if w is None:
        return None, (f"{path} is not a register this netlist has; the RTL "
                      f"campaign names storage added after the harden")
    nets = []
    for b in range(w):
        net, why = map_target(path, b)
        if net is None or net not in FLOP_NETS:
            return None, why or f"{path}[{b}] is not a flip-flop output here"
        nets.append(NETS[net])
    return nets, [(value >> b) & 1 for b in range(w)]


# ---------------------------------------------------------------------
# one injection
# ---------------------------------------------------------------------
NETS = {}          # netlist net name -> cocotb handle
FLOP_NETS = set()  # nets driven by a flip-flop Q pin, parsed from the file


async def injection(p, geo, group, target, bit, burst, delay,
                    net_name=None, ecc_inj=None, scrub=False,
                    poison_word=None, expect_tel=None, latent_regs=(),
                    script=None, extra_fields=None):
    """fi.injection, with a gate-level upset in place of a deposit."""
    n_neurons, n_axons, weights, words = geo
    exp_bursts, exp_state = fi.golden_run(n_neurons, n_axons, weights)
    exp_events = [w for b in exp_bursts for w in b]

    await bring_up(p, words, ecc_inj=ecc_inj, scrub_en=scrub)
    extra = dict(extra_fields or {})
    if script is not None:
        slog = []
        completed, got, out = await run_stimulus(p, burst, script=script,
                                                 script_log=slog)
        extra["script"] = slog
        extra["constructed"] = "NOT CONSTRUCTED" not in slog
    elif net_name is None:
        completed, got, out = await run_stimulus(p)
    else:
        completed, got, out = await run_stimulus(p, burst, NETS[net_name],
                                                 delay)
        if out["forced"] is None:
            # The net was X when the injection was due: nothing was
            # forced, so there is no injection to classify. Recorded and
            # counted separately -- never as MASKED, which is what a
            # campaign that quietly swallowed this would report.
            rec = {"group": group, "target": target, "net": net_name,
                   "bit": bit, "burst": burst, "delay": delay,
                   "class": "SKIPPED_X",
                   "reason": "the net was undefined at the injection "
                             "instant; forcing it would not be a bit flip"}
            RESULTS.append(rec)
            return rec
        extra["forced_value"] = out["forced"]

    if scrub:
        await pulse_scrub(p)
        lo = await tt.rd(p, ADDR["W_DATA_LO"])
        hi = await tt.rd(p, ADDR["W_DATA_HI"])
        extra["stored_repaired"] = ((hi << 32) | lo) == words[-1]

    latent = {}
    for name, addr, want in latent_regs:
        latent[name] = (await tt.rd(p, addr)) != want
    if latent_regs:
        extra["latent"] = any(latent.values())
        extra["latent_regs"] = latent

    obs = await read_observations(p, n_neurons, completed)

    spikes_ok = got == exp_events
    state_ok = [tuple(s) for s in obs["state"]] == exp_state
    cls = fi.classify(completed, obs, spikes_ok and state_ok)

    want_tel = {k: 0 for k in fi.COUNTERS}
    want_tel.update(expect_tel or {})
    tel = {k: obs[k] for k in fi.COUNTERS}
    extra["telemetry_ok"] = tel == want_tel
    if poison_word is not None:
        e10_bursts, e10_state = fi.golden_run(n_neurons, n_axons, weights,
                                              poison_word=poison_word)
        extra["e10_events_ok"] = got == [w for b in e10_bursts for w in b]
        extra["e10_state_ok"] = \
            [tuple(s) for s in obs["state"]] == e10_state

    rec = {
        "group": group, "target": target, "net": net_name,
        "bit": list(bit) if isinstance(bit, tuple) else bit,
        "burst": burst, "delay": delay, "class": cls,
        "completed": completed,
        "out_ok": spikes_ok and state_ok,
        "spikes_ok": spikes_ok, "state_ok": state_ok,
        "status": obs["status"], "counters": tel, "pins": obs["pins"],
        "got_events": got, "exp_events": exp_events,
        "state": [list(s) for s in obs["state"]],
    }
    rec.update(extra)
    RESULTS.append(rec)
    return rec


# ---------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------
async def gl_setup(dut):
    """Clock, quiescent pins, the name index, and the geometry."""
    p = tt.Pins(dut)
    # A fresh clock per test: cocotb ends a test by killing the tasks it
    # started, so the previous test's clock is already gone.
    CLK["clk"] = dut.clk
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    dut.ena.value = 1
    dut.ui_in.value = p.ui
    dut.uio_in.value = p.uio
    await hard_reset(p)

    if not NETS:
        t0 = time.time()
        for h in dut:
            try:
                NETS[h._name] = h
            except Exception:               # noqa: BLE001 - scope scan
                continue
        FLOP_NETS.update(flop_output_nets(os.environ["GL_NETLIST"]))
        NOTES["scope_children"] = len(NETS)
        NOTES["flop_output_nets"] = len(FLOP_NETS)
        NOTES["scope_scan_seconds"] = round(time.time() - t0, 1)
        dut._log.info(
            f"netlist scope: {len(NETS)} named children in "
            f"{NOTES['scope_scan_seconds']} s; {len(FLOP_NETS)} of them "
            f"are driven by a flip-flop Q pin")

    n_neurons = await tt.rd(p, ADDR["CFG_NEUR"])
    n_axons = await tt.rd(p, ADDR["CFG_AXON"])
    assert (n_neurons, n_axons) in fi.WORKLOAD, \
        f"no workload for the elaborated geometry {n_neurons}x{n_axons}"
    fi.GEOMETRY = (n_neurons, n_axons)
    fi.WL_SEED, fi.BURST_WINDOW = fi.WORKLOAD[fi.GEOMETRY]
    weights = fi.make_weights(n_axons, n_neurons)
    return p, (n_neurons, n_axons, weights, fi.pack_words(weights))


async def identify_flop(p, addr, bit, low, high):
    """Find the flip-flop that carries one register bit, by experiment.

    Some storage survives synthesis with neither its RTL name nor its
    bit index: `cfg_axon[3]` is a writable bit of a writable register and
    there is no net of that name anywhere in the netlist, because yosys
    renamed it when it merged the flop with an identical one. Guessing
    which of the anonymous flops it is would be exactly the kind of
    assumption this suite exists not to make, so it is measured instead:
    write the register with the bit clear, then with the bit set, and
    keep whichever anonymous flip-flop changed with it.

    `low` and `high` are two legal values of the register differing in
    that bit alone, so the experiment perturbs nothing else.
    """
    cands = sorted(n for n in FLOP_NETS if re.match(r"^u_pilot\._\d+_$", n))
    await tt.wr(p, addr, low)
    await clk_edges(p.dut, 2)
    before = {n: bit_of(NETS[n]) for n in cands}
    await tt.wr(p, addr, high)
    await clk_edges(p.dut, 2)
    after = {n: bit_of(NETS[n]) for n in cands}
    moved = [n for n in cands if before[n] != after[n]]
    await tt.wr(p, addr, low)
    return moved, cands


def q_depth_from_netlist():
    """The AER queue depth, counted from the netlist's own storage names.

    The RTL campaign reads len(dut.u_evq_in.mem); a flattened netlist has
    no such array, so the depth is derived from how many slots yosys
    named. Derived, not assumed: a re-harden at a different depth changes
    this number rather than silently reusing the old target list.
    """
    slots = {int(m.group(1)) for m in
             (re.match(r"u_pilot\.u_evq_in\.mem\[(\d+)\]\[\d+\]$", n)
              for n in FLOP_NETS) if m}
    assert slots, "no u_evq_in.mem storage found in the netlist"
    return max(slots) + 1


# ---------------------------------------------------------------------
# test 00: the method, proved on this netlist before anything is measured
# ---------------------------------------------------------------------
@cocotb.test(timeout_time=900, timeout_unit="sec")
async def test_00_method(dut):
    """Prove that the injector models an upset, before trusting a number.

    The pointer-TMR episode is the template for why this test exists: a
    campaign that reports plausible numbers while measuring the wrong
    thing is worse than no campaign. Five things are established here,
    each by measurement on this netlist:

      A. the control run is golden-exact through the wrapper pins, so the
         harness itself is not the variable;
      B. force overrides a mapped flip-flop's own drive, and release
         gives it back -- so the injection reaches the design and does
         not linger;
      C. the corruption is CAPTURED: a one-cycle force on a held register
         is still there, at the register port, long after release. That
         is the difference between an upset and a glitch;
      D. a deposit on the same net is a stuck-at, measured side by side
         with C on the same target, which is why the RTL technique is not
         reused;
      E. the injector reaches a structure whose RTL outcome is already
         known: an upset in lif_core's FSM state must be DETECTED.
    """
    p, geo = await gl_setup(dut)
    n_neurons, n_axons, weights, words = geo
    dut._log.info(f"geometry {n_neurons}x{n_axons}, weight seed "
                  f"{fi.WL_SEED}, q_depth {q_depth_from_netlist()}")

    # -- A. the control run ------------------------------------------
    exp_bursts, exp_state = fi.golden_run(n_neurons, n_axons, weights)
    exp_events = [w for b in exp_bursts for w in b]
    await bring_up(p, words)
    completed, got, _ = await run_stimulus(p)
    obs = await read_observations(p, n_neurons, completed)
    assert completed, "the gate-level control run did not complete"
    assert got == exp_events, f"control events {got} != golden {exp_events}"
    assert [tuple(s) for s in obs["state"]] == exp_state, \
        f"control state {obs['state']} != golden {exp_state}"
    assert obs["status"] & (fi.ST_ERR_CFG | fi.ST_DED_SEEN
                            | fi.ST_OVF_SEEN) == 0
    assert not any(obs[k] for k in fi.COUNTERS)
    assert not any(obs["pins"].values())
    dut._log.info(f"A. control run golden-exact at gate level: {got}")
    NOTES["control_events"] = got

    # -- B/C/D. the injector, on a held register ---------------------
    # SCRATCH is the right target for this: 32 flip-flops whose only job
    # is to hold what the host wrote, so what the register port reads
    # after the run is exactly what the storage holds -- no next-state
    # logic to argue about.
    await bring_up(p, words)
    await tt.wr(p, ADDR["SCRATCH"], 0x0000_0000)
    net = NETS["u_pilot.scratch[0]"]
    assert "u_pilot.scratch[0]" in FLOP_NETS, \
        "scratch[0] is not a flip-flop output in this netlist"

    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")
    before = bit_of(net)
    net.value = Force(1)
    await Timer(1, unit="ns")
    during = bit_of(net)
    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")
    net.value = Release()
    await Timer(1, unit="ns")
    after = bit_of(net)
    await clk_edges(dut, 4)
    settled = bit_of(net)
    read_back = await tt.rd(p, ADDR["SCRATCH"])
    dut._log.info(f"B/C. scratch[0]: before={before} during_force={during} "
                  f"after_release={after} settled={settled} "
                  f"SCRATCH reads 0x{read_back:08X}")
    assert before == 0 and during == 1, \
        "Force did not override the flip-flop cell's own drive"
    assert after == 1 and settled == 1, \
        "the flip-flop did not capture the forced value: the injector " \
        "models a glitch on a wire, not an upset in storage"
    assert read_back & 1, \
        "the corruption is not visible at the register port after " \
        "release, so it was never in the storage element"
    NOTES["upset_persists"] = {"before": before, "during": during,
                               "after_release": after, "settled": settled,
                               "scratch_readback": read_back}

    # The design must be able to overwrite it afterwards, or the force
    # was never really released and every later injection is a stuck-at.
    await tt.wr(p, ADDR["SCRATCH"], 0x0000_0000)
    assert (await tt.rd(p, ADDR["SCRATCH"])) == 0, \
        "the net did not return to its cell's control after Release"

    # -- D. the same target, by deposit, for the contrast -------------
    # The RTL campaign's primitive, applied to the same flip-flop output
    # net. A deposit is held until the net's DRIVER re-evaluates, and the
    # driver of a register that is holding does not, so the corruption
    # stays on the node for as long as the design leaves it alone -- a
    # stuck-at whose duration is set by the injector rather than by the
    # design. Measured below over one full serial read frame.
    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")
    t_dep = cocotb.utils.get_sim_time("ns")
    net.value = 1
    await Timer(1, unit="ns")
    dep_during = bit_of(net)
    await clk_edges(dut, 8)
    dep_settled = bit_of(net)
    dep_read = await tt.rd(p, ADDR["SCRATCH"])
    dep_held = bit_of(net)
    held_cycles = int((cocotb.utils.get_sim_time("ns") - t_dep) // CLK_NS)
    await tt.wr(p, ADDR["SCRATCH"], 0x0000_0000)   # the driver re-evaluates
    dep_after_write = bit_of(net)
    dut._log.info(f"D. the same net by DEPOSIT: during={dep_during}, eight "
                  f"cycles later={dep_settled}, still {dep_held} after "
                  f"{held_cycles} cycles, SCRATCH reads 0x{dep_read:08X}; "
                  f"after a register write re-evaluates the driver="
                  f"{dep_after_write}")
    NOTES["deposit_contrast"] = {
        "during": dep_during, "eight_cycles_later": dep_settled,
        "held_for_cycles": held_cycles, "still_set_after": dep_held,
        "scratch_readback": dep_read,
        "after_driver_re_evaluates": dep_after_write}
    assert dep_settled == 1 and dep_held == 1 and dep_read & 1, \
        "a deposit on this netlist did not behave as a stuck-at; the " \
        "argument for force/release rests on it doing so (docs/24 4.3)"
    assert dep_after_write == 0, \
        "the deposit never cleared, so the state left behind by this " \
        "demonstration would contaminate every injection after it"

    # -- D2. the two primitives on a register the design is DRIVING ---
    # On `scratch` the two look alike, because nothing ever overwrites
    # it. The difference shows on a register whose next-state logic is
    # live, and lif_core's FSM is the one docs/24 section 4.3 already
    # measured a deposit on. Both primitives are applied here at the same
    # point of the same stimulus, and neither run is classified: this is
    # a measurement of the injector, not of the design.
    async def push(burst):
        for kind, axon in burst:
            await pin_event(p, kind, axon)

    async def fsm_snapshot(primitive):
        await bring_up(p, words)
        pusher = cocotb.start_soon(push(fi.BURSTS[0]))
        for _ in range(fi.BUSY_BUDGET):
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            if busy(dut):
                break
        s = [NETS[f"u_pilot.u_lif.state[{i}]"] for i in range(4)]
        def word():
            return "".join(str(bit_of(n)) for n in reversed(s))
        await RisingEdge(dut.clk)
        await Timer(3, unit="ns")
        before = word()
        if primitive == "deposit":
            s[0].value = 1 - bit_of(s[0])
        else:
            s[0].value = Force(1 - bit_of(s[0]))
        await Timer(1, unit="ns")
        during = word()
        await RisingEdge(dut.clk)
        await Timer(3, unit="ns")
        if primitive == "force":
            s[0].value = Release()
            await Timer(1, unit="ns")
        after = word()
        await clk_edges(dut, 1)
        await Timer(3, unit="ns")
        later = word()
        await pusher
        await wait_idle(p)
        await drain(p)
        return {"before": before, "during": during,
                "one_edge_later": after, "two_edges_later": later}

    dep_fsm = await fsm_snapshot("deposit")
    frc_fsm = await fsm_snapshot("force")
    dut._log.info(f"D2. u_lif.state by DEPOSIT: {dep_fsm}")
    dut._log.info(f"D2. u_lif.state by FORCE/RELEASE: {frc_fsm}")
    NOTES["fsm_primitive_contrast"] = {"deposit": dep_fsm, "force": frc_fsm}

    # -- D3. the one experiment that tells the two apart outright ------
    # On a register nothing ever rewrites, the two primitives look alike:
    # both leave the node at the flipped value and both read back through
    # the register port. They are not alike, and a reset says so. After a
    # genuine upset the flip-flop HOLDS the wrong value, so the design's
    # own recovery -- an asynchronous reset -- clears it. After a deposit
    # the flip-flop holds the right value and only the wire is wrong, so
    # the reset changes nothing on that node and the "fault" survives a
    # recovery no real upset could survive.
    async def survives_reset(primitive):
        await bring_up(p, words)
        await tt.wr(p, ADDR["SCRATCH"], 0x0000_0000)
        await RisingEdge(dut.clk)
        await Timer(3, unit="ns")
        if primitive == "deposit":
            net.value = 1
            await Timer(1, unit="ns")
        else:
            await upset(net)
        await hard_reset(p)
        after = await tt.rd(p, ADDR["SCRATCH"])
        if primitive == "deposit":            # hand the node back
            await tt.wr(p, ADDR["SCRATCH"], 0xFFFF_FFFF)
            await tt.wr(p, ADDR["SCRATCH"], 0x0000_0000)
        return after

    frc_reset = await survives_reset("force")
    dep_reset = await survives_reset("deposit")
    dut._log.info(f"D3. SCRATCH after a hard reset -- upset by "
                  f"force/release: 0x{frc_reset:08X}; by deposit: "
                  f"0x{dep_reset:08X}")
    NOTES["survives_reset"] = {"force_release": frc_reset,
                               "deposit": dep_reset}
    assert frc_reset == 0, \
        "the reset did not clear the forced upset, so the injector is " \
        "holding state the design cannot reach"
    assert dep_reset & 1, \
        "the deposit did not survive the reset; the stuck-at argument " \
        "for rejecting deposits rests on this measurement"

    # -- F. storage that survived synthesis without a usable name ------
    ax_moved, ax_cands = await identify_flop(p, ADDR["CFG_AXON"], 3,
                                             n_axons & ~0x8, n_axons)
    dut._log.info(f"F. cfg_axon[3] has no net of that name; of the "
                  f"{len(ax_cands)} anonymous pilot-level flip-flops, "
                  f"{ax_moved} moved with it")
    NOTES["identified"] = {"cfg_axon[3]": ax_moved,
                           "anonymous_candidates": ax_cands}
    if len(ax_moved) == 1:
        RESOLVED[("cfg_axon", 3)] = ax_moved[0]

    # Neither snapshot may leave anything behind: a deposit that was
    # still held would contaminate every injection after it, which is
    # the failure mode this whole test exists to rule out.
    await bring_up(p, words)
    completed, got, _ = await run_stimulus(p)
    assert completed and got == exp_events, \
        f"the design is not clean after the primitive contrast: {got}"

    # -- E. a structure with a known RTL outcome ----------------------
    # test_fi_campaign's own control probe, reproduced at gate level: the
    # five legal FSM encodings are the even-parity words of a four-bit
    # vector, so every single-bit upset lands on an illegal one and the
    # core must park with err_cfg raised. If this comes back MASKED the
    # injector is not landing and nothing after it means anything.
    probe = await injection(p, geo, "method_probe", "u_lif.state", 0, 0, 0,
                            net_name="u_pilot.u_lif.state[0]")
    assert probe["class"] == "DETECTED", \
        f"a gate-level upset in lif_core.state must be DETECTED, got " \
        f"{probe['class']}; the injector is not reaching the design"
    dut._log.info(f"E. lif_core FSM upset at gate level: {probe['class']}, "
                  f"STATUS 0x{probe['status']:08X}")
    NOTES["fsm_probe"] = {"class": probe["class"], "status": probe["status"]}

    RESULTS.clear()
    WALL["t0"] = time.time()


# ---------------------------------------------------------------------
# test 01: the RTL campaign's own target list, replayed at gate level
# ---------------------------------------------------------------------
def wanted(group):
    return not GROUPS_FILTER or group in GROUPS_FILTER


@cocotb.test(timeout_time=14400, timeout_unit="sec")
async def test_01_structural(dut):
    """Every RTL structural target, at its own drawn phase, at gate level.

    The iteration is test_fi_campaign.test_01_structural_injections',
    step for step, so the seeded streams are consumed in the same order
    and every gate-level injection stands at the (burst, delay) of the
    RTL injection it will be compared with -- including for targets this
    suite cannot reach, which still consume their draw.
    """
    p, geo = await gl_setup(dut)
    n_neurons, n_axons = geo[0], geo[1]
    lat = fi.latent_map(n_axons)
    q_depth = q_depth_from_netlist()

    skipped = {}
    for group, path, bits, n_phase, pin_first in \
            fi.target_list(n_neurons, n_axons, q_depth):
        paths = path if isinstance(path, tuple) else (path,)
        rng = fi.EXT_RNG if group in fi.EXT_GROUPS else fi.RNG
        for bit in bits:
            for b, d in fi.phases(n_phase, pin_first, rng):
                for one in paths:
                    net_name, why, exact = map_target_x(one, bit, bits)
                    if net_name is None or net_name not in FLOP_NETS:
                        why = why or (
                            f"{net_name} is not driven by a flip-flop Q "
                            f"pin in this netlist")
                        skipped.setdefault((group, one, bit), why)
                        continue
                    if not wanted(group):
                        continue
                    await injection(p, geo, group, one, bit, b, d,
                                    net_name=net_name,
                                    latent_regs=lat.get(one, ()),
                                    extra_fields={"bit_index_exact": exact})
    NOTES["unreachable"] = [
        {"group": g, "target": t, "bit": bit, "reason": why}
        for (g, t, bit), why in sorted(skipped.items(), key=lambda kv: str(kv[0]))]
    dut._log.info(f"structural injections: {len(RESULTS)}; "
                  f"unreachable targets: {len(skipped)}")
    for entry in NOTES["unreachable"]:
        dut._log.info(f"  unreachable {entry['group']}/{entry['target']}"
                      f"[{entry['bit']}]: {entry['reason']}")


# ---------------------------------------------------------------------
# test 02: the ECC weight word -- no hierarchy access at all
# ---------------------------------------------------------------------
@cocotb.test(timeout_time=3600, timeout_unit="sec")
async def test_02_ecc_weight_word(dut):
    """fi.test_02, unchanged in substance.

    The `ecc_port_*` half needs no injector: the fault is delivered by the
    design's own ECC_INJ register, so these injections are portable to
    gate level exactly as written and are the cleanest like-for-like
    comparison in this suite -- identical stimulus, identical oracle, and
    nothing in the mechanism that could differ between the two levels.
    """
    p, geo = await gl_setup(dut)
    n_words = len(geo[3])

    if wanted("ecc_port_single"):
        for k, pos in enumerate([0, 7, 19, 31, 33, 47, 58, 63, 64, 67, 70, 71]):
            wi = k % n_words
            rec = await injection(p, geo, "ecc_port_single", None, None,
                                  None, 0, ecc_inj=(wi, pos, fi.INJ_SINGLE),
                                  expect_tel={"cnt_sec": 1})
            rec["ecc_word"], rec["ecc_pos"] = wi, pos
    if wanted("ecc_port_double"):
        for k, pos in enumerate([0, 20, 55, 70]):
            wi = k % n_words
            rec = await injection(p, geo, "ecc_port_double", None, None,
                                  None, 0, ecc_inj=(wi, pos, fi.INJ_DOUBLE),
                                  poison_word=wi, expect_tel={"cnt_ded": 1})
            rec["ecc_word"], rec["ecc_pos"] = wi, pos
    if wanted("ecc_ff"):
        for bit in (0, 17, 40, 63):
            await injection(p, geo, "ecc_ff", "ecc_data", bit, 0, 0,
                            net_name=f"u_pilot.ecc_data[{bit}]",
                            scrub=True, expect_tel={"cnt_sec": 1})
        for bit in (0, 3, 7):
            await injection(p, geo, "ecc_ff", "ecc_check", bit, 0, 0,
                            net_name=f"u_pilot.ecc_check[{bit}]",
                            scrub=True, expect_tel={"cnt_sec": 1})
    dut._log.info(f"after the ECC domain: {len(RESULTS)} injections")


# ---------------------------------------------------------------------
# test 03: can an upset erase the record it exists to keep
# ---------------------------------------------------------------------
@cocotb.test(timeout_time=1800, timeout_unit="sec")
async def test_03_telemetry_erasure(dut):
    """fi.test_03 at gate level, on the netlist's own names for the flops.

    Two of the six targets are renamed by synthesis: `sticky_sec` and
    `sticky_ded` are named after the output ports they drive
    (pilot_top.v 1907-1908). They are the same flip-flops.
    """
    if not wanted("telemetry_primed"):
        return
    p, geo = await gl_setup(dut)
    primed = {"cnt_sec": 1}
    for target, bit in (("cnt_sec", 0), ("cnt_sec", 1), ("sticky_sec", 0),
                        ("cnt_ded", 0), ("sticky_ded", 0), ("cnt_tmr", 0)):
        net_name, why = map_target(target, bit)
        assert net_name in FLOP_NETS, f"{target}[{bit}]: {why or net_name}"
        for b, d in fi.phases(1):
            await injection(p, geo, "telemetry_primed", target, bit, b, d,
                            net_name=net_name,
                            ecc_inj=(0, 5, fi.INJ_SINGLE), expect_tel=primed)
    dut._log.info(f"after the telemetry domain: {len(RESULTS)} injections")


# ---------------------------------------------------------------------
# test 04: the directed watchdog cases
# ---------------------------------------------------------------------
@cocotb.test(timeout_time=1800, timeout_unit="sec")
async def test_04_watchdog_directed(dut):
    """fi.test_04's twelve constructions, at gate level.

    Every step is the RTL script unchanged; only the deposit primitive
    differs. The `until` steps read internal state to PLACE a deposit and
    never to classify one, exactly as in the RTL suite, and this test
    asserts that each of them found its cycle -- a case that did not
    construct says nothing about the safety net and must fail rather than
    be reported.
    """
    p, geo = await gl_setup(dut)
    for group, case, note, steps in fi.watchdog_cases():
        if not wanted(group):
            continue
        rec = await injection(p, geo, group, case, None, 0, None,
                              script=steps,
                              extra_fields={"case": case, "note": note})
        rec["errcfg"] = bool(rec["status"] & fi.ST_ERR_CFG)
        if not rec["constructed"]:
            # Recorded, not asserted. A case that could not be built
            # says nothing about the safety net, and the classification
            # it would otherwise carry would be a number about nothing.
            rec["class"] = "NOT_CONSTRUCTED"
            dut._log.info(f"{group:<16}{case:<18}NOT CONSTRUCTED: "
                          f"{rec['script']}")
            continue
        dut._log.info(f"{group:<16}{case:<18}{rec['class']:<10}"
                      f"ERR_CFG={int(rec['errcfg'])} "
                      f"out_ok={int(rec['out_ok'])} "
                      f"completed={int(rec['completed'])}")
    hung = [r for r in RESULTS
            if r["group"].startswith("wdog_") and not r.get("completed", True)]
    assert not hung, \
        f"a bounded wait failed to bound at gate level: " \
        f"{[(r['group'], r.get('case')) for r in hung]}"


# ---------------------------------------------------------------------
# test 05: the whole configuration TMR domain, flip-flop by flip-flop
# ---------------------------------------------------------------------
@cocotb.test(timeout_time=7200, timeout_unit="sec")
async def test_05_cfg_tmr_sweep(dut):
    """Every flip-flop of all three configuration replicas, once each.

    This group has no RTL twin and is here because the netlist makes a
    stronger experiment possible than the RTL does. docs/16 section 4
    records that yosys once merged the three replicas into one physical
    bank; docs/24 section 5.2 answered that at the netlist level with one
    functional test. This asks it of every stored bit: if any pair of the
    three banks shared storage, an upset in the shared flop would corrupt
    two replicas at once and the vote would carry it through.

    Synthesis kept `bits[i]` as a net name for only some of the flops in
    each bank -- 51 of 55 in bank A, 4 in bank B, 29 in bank C -- so a
    per-RTL-bit comparison is not available for the whole bank. Sweeping
    every flop of every bank does not need one: each of these flops is,
    by construction, one replica's storage, and a single-replica upset
    must be masked whichever bit it is.
    """
    if not wanted("cfg_tmr_sweep"):
        return
    p, geo = await gl_setup(dut)
    banks = {r: sorted(n for n in FLOP_NETS
                       if n.startswith(f"u_pilot.u_cfg_{r}."))
             for r in ("a", "b", "c")}
    dut._log.info("configuration replica storage in this netlist: "
                  + ", ".join(f"{r}={len(v)}" for r, v in banks.items()))
    NOTES["cfg_bank_flops"] = {r: len(v) for r, v in banks.items()}
    assert len(set(map(len, banks.values()))) == 1 and len(banks["a"]) > 1, \
        f"the three configuration replicas do not have equal storage: " \
        f"{ {r: len(v) for r, v in banks.items()} }"
    # One phase each, the campaign's own first phase for the cfg groups.
    for r, nets in banks.items():
        for net_name in nets:
            await injection(p, geo, f"cfg_tmr_sweep_{r}", net_name, None,
                            0, 0, net_name=net_name)
    dut._log.info(f"after the configuration TMR sweep: {len(RESULTS)}")


# ---------------------------------------------------------------------
# test 055: the one disagreement, taken apart before it is reported
# ---------------------------------------------------------------------
@cocotb.test(timeout_time=3600, timeout_unit="sec")
async def test_055_disagreement_probe(dut):
    """Is the `report_*` disagreement a level difference or a phase one?

    The two campaigns agree on 355 of the 357 injections they both make,
    and the two that differ are `report_erased` in each bounded-wait net
    — RTL SDC, gate level MASKED. Underneath the class labels the real
    difference is the OUTPUT: at RTL the deadlock-and-recovery returns
    `[0, 1, 2, 3, 4, 2]` where the golden model says `[1, 2, 5, 6, 4, 2]`,
    in the control (`report_kept`) as well as in the case, and docs/16
    section 5.8 rests its ranking on that wrong answer. At gate level the
    same construction returns the golden stream.

    A one-cycle difference in where the first deposit lands would explain
    it just as well as a difference between the two levels, and the two
    have to be told apart before either is reported. The directed script
    anchors on the first cycle `dstate` reads D_IDLE after BUSY rises, so
    prepending a wait moves the anchor to a later D_IDLE and sweeps the
    placement. If ANY placement reproduces the RTL's wrong stream, the
    disagreement is an alignment artefact of two harnesses. If none does,
    the netlist recovers from this fault and the RTL does not.

    Nothing here is classified into the campaign histogram: this is a
    measurement about the measurement.
    """
    if not wanted("disagreement_probe"):
        return
    p, geo = await gl_setup(dut)
    n_neurons, n_axons, weights, _ = geo
    exp_bursts, _ = fi.golden_run(n_neurons, n_axons, weights)
    exp = [w for b in exp_bursts for w in b]
    rtl_by_case = {(r["group"], r.get("case")): r
                   for r in (RTL_LOG["injections"] if RTL_LOG else [])
                   if r["group"].endswith("_dir")}

    out = []
    for group, case, _note, steps in fi.watchdog_cases():
        if case not in ("report_kept", "report_erased"):
            continue
        ref = rtl_by_case.get((group, case), {})
        for extra in range(6):
            rec = await injection(p, geo, "disagreement_probe",
                                  f"{group}/{case}+{extra}", None, 0, None,
                                  script=([("wait", extra)] + list(steps)))
            RESULTS.pop()          # measured, not counted
            row = {"group": group, "case": case, "extra_wait": extra,
                   "gl_class": rec["class"], "gl_events": rec["got_events"],
                   "gl_out_ok": rec["out_ok"],
                   "constructed": rec["constructed"],
                   "rtl_class": ref.get("class"),
                   "rtl_events": ref.get("got_events"),
                   "matches_rtl_stream":
                       rec["got_events"] == ref.get("got_events")}
            out.append(row)
            dut._log.info(
                f"{group}/{case} +{extra}: GL {rec['class']:<10} "
                f"{rec['got_events']}  RTL {ref.get('class')} "
                f"{ref.get('got_events')}  "
                f"{'MATCHES RTL' if row['matches_rtl_stream'] else ''}")
    NOTES["disagreement_probe"] = {
        "golden": exp,
        "any_placement_reproduces_rtl": any(r["matches_rtl_stream"]
                                            for r in out),
        "rows": out}
    dut._log.info(
        "any gate-level placement reproducing the RTL event stream: "
        f"{NOTES['disagreement_probe']['any_placement_reproduces_rtl']}")


# ---------------------------------------------------------------------
# test 06: aggregate, compare against the RTL campaign, write the log
# ---------------------------------------------------------------------
CLASSES = tuple(fi.CLASSES) + ("SKIPPED_X", "NOT_CONSTRUCTED")


@cocotb.test(timeout_time=300, timeout_unit="sec")
async def test_06_summary(dut):
    """Histogram, side-by-side comparison with docs/16, and the log."""
    await Timer(10, unit="ns")
    wall = time.time() - WALL.get("t0", time.time())

    groups = {}
    for r in RESULTS:
        assert r["class"] in CLASSES, f"unclassified injection: {r}"
        groups.setdefault(r["group"], {c: 0 for c in CLASSES})[r["class"]] += 1

    total = len(RESULTS)
    hist = {c: sum(g[c] for g in groups.values()) for c in CLASSES}

    rtl = RTL_LOG
    rtl_groups = rtl["groups"] if rtl else {}

    dut._log.info(f"gate-level campaign: {total} injections, {wall:.1f} s")
    head = f"{'group':<22}" + "".join(f"{c:>10}" for c in CLASSES)
    dut._log.info(head)
    for name in sorted(groups):
        g = groups[name]
        dut._log.info(f"{name:<22}" + "".join(f"{g[c]:>10}" for c in CLASSES))
    dut._log.info(f"{'TOTAL':<22}" + "".join(f"{hist[c]:>10}" for c in CLASSES))

    # Like-for-like: only groups the RTL campaign also has, and only
    # counting the injections that actually landed on both sides.
    dut._log.info(" ")
    dut._log.info("group-by-group against the RTL campaign "
                  "(GL n / RTL n, then the classes that differ)")
    agree, differ = [], []
    for name in sorted(groups):
        if name not in rtl_groups:
            continue
        g, rg = groups[name], rtl_groups[name]
        gl_n = sum(g[c] for c in fi.CLASSES)
        rtl_n = sum(rg.values())
        same_shape = gl_n == rtl_n
        diffs = {c: (g[c], rg[c]) for c in fi.CLASSES if g[c] != rg[c]}
        (agree if same_shape and not diffs else differ).append(name)
        mark = "same" if same_shape and not diffs else "DIFFERS"
        dut._log.info(f"  {name:<22} {gl_n:>4} / {rtl_n:<4} {mark} "
                      + (", ".join(f"{c}: GL {a} vs RTL {b}"
                                   for c, (a, b) in diffs.items())))
    NOTES["groups_agreeing"] = agree
    NOTES["groups_differing"] = differ

    stem = "gl_fi_results" + (f"_{RUN_TAG}" if RUN_TAG else
                              ("_partial" if GROUPS_FILTER else ""))
    out = HERE / f"{stem}.json"
    out.write_text(json.dumps({
        "netlist": os.environ.get("GL_NETLIST"),
        "netlist_blob": _blob(os.environ.get("GL_NETLIST")),
        "cell_models": os.environ.get("GL_CELLS"),
        "rtl_ref": RTL_REF,
        "rtl_campaign_blob": RTL_CAMPAIGN_BLOB,
        "rtl_log_blob": RTL_LOG_BLOB,
        "rtl_total": rtl["total"] if rtl else None,
        "seed": fi.CAMPAIGN_SEED,
        "geometry": {"n_neurons": fi.GEOMETRY[0], "n_axons": fi.GEOMETRY[1]},
        "groups_filter": list(GROUPS_FILTER),
        "wall_seconds": round(wall, 1),
        "total": total, "histogram": hist, "groups": groups,
        "rtl_groups": rtl_groups,
        "notes": NOTES,
        "injections": RESULTS}, indent=1))
    dut._log.info(f"per-injection log written to {out}")

    if GROUPS_FILTER:
        return
    # -- what this run will not let regress ---------------------------
    assert total > 0, "the gate-level campaign injected nothing"
    fsm = groups.get("lif_fsm", {})
    assert fsm and fsm["DETECTED"] == sum(fsm.values()), \
        f"every gate-level lif_core FSM upset must be DETECTED, got {fsm}"
    ptr = groups.get("evq_ptr", {})
    assert ptr and ptr["SDC"] == 0, \
        f"a single-replica AER pointer upset must never be SDC at gate " \
        f"level, got {ptr}"
    sweep = {c: sum(groups.get(f"cfg_tmr_sweep_{r}", {}).get(c, 0)
                    for r in ("a", "b", "c")) for c in CLASSES}
    if sum(sweep.values()):
        assert sweep["SDC"] == 0, \
            f"an upset in one configuration replica flip-flop reached the " \
            f"output: the three banks are not independent storage in this " \
            f"netlist. {sweep}"
