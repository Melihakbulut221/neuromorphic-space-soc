# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""NPU register bank suite.

The register list is walked PROGRAMMATICALLY from sw/golden/regmap_gen.py --
the generated Python view of regmap/regmap.yaml -- so the testbench cannot
drift from the single source: adding, moving or re-typing a register in the
YAML immediately changes what these tests check. Nothing here re-types an
address, a reset value or a field position.

Two facts about the register map are not exported by regmap_gen.py and are
therefore stated here, both cross-checked against the generated tables so a
YAML rename fails loudly rather than silently skipping coverage:

  * per-FIELD access codes (the generator exports ACCESS per register, plus
    FIELDS/FIELD_WIDTHS per field, but not the per-field access column), so
    the self-clearing field names are listed in SELF_CLEARING and looked up
    in FIELDS -- a rename raises KeyError;
  * the hardware event that drives each read-only / sticky / counter
    register, which is a property of the RTL interface, not of the YAML.

Coverage: reset value of every register, RW write/readback with field
masking, RO write-ignored, WO/W1C read-as-zero, W1C set-by-hardware and
clear-by-write-1, counter increment and clear, the hardware-event versus
software-clear race (hardware wins, RTL header convention C1), the
configuration lock over all 17 locked and all 6 unlocked registers
including the rising edge of hw_busy, cfg_valid start gating and the
ERR_CFG diagnostic, the CFG_NEUR / CFG_AXON reset from the build
parameters, the weight load port with W_ADDR auto-increment and the
commit index it exports, ECC_INJ arm/consume across the commit strobe,
the AER software ports including back-to-back EVQ_OUT reads against a
show-ahead queue model, the neuron state staging port, back-to-back bus
traffic, the EVQ_OUT wait state, the APB bridge adaptation the RTL header
prescribes, unmapped and misaligned access, and a randomized scoreboard
over the whole map.

Not covered here (documented, not skipped): fault-counter saturation. The
counters are 32 bits wide in silicon, so saturation is unreachable in
simulation; it is proven for all widths by formal/npu_regbank_props.v (P6)
and shown reachable by the CNT_W=2 cover task in formal/npu_regbank.sby.
"""

import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

# sw/golden/regmap_gen.py is the generated Python view of regmap/regmap.yaml.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sw" / "golden"))
import regmap_gen  # noqa: E402

ADDR = regmap_gen.ADDR
ACCESS = regmap_gen.ACCESS
RESET = regmap_gen.RESET
FIELDS = regmap_gen.FIELDS
FIELD_WIDTHS = regmap_gen.FIELD_WIDTHS

WORD = 4
ADDR_SPACE = 1 << 12          # regmap.yaml meta.addr_bits
ALL_ONES = 0xFFFFFFFF

# Self-clearing fields (regmap.yaml access code SC). Not exported per field
# by the generator; the names are resolved through FIELDS below, so a rename
# in the YAML raises KeyError instead of silently dropping coverage.
SELF_CLEARING = {
    "CTRL": ("STATE_CLR", "SOFT_RST"),
    "ECC_INJ": ("SINGLE", "DOUBLE"),
}

# Registers whose write or read has a side effect beyond storing/returning a
# value; excluded from the generic RW/scoreboard walks and covered by their
# own directed tests instead.
SIDE_EFFECT = ("CTRL", "STATUS_CLR", "W_DATA_LO", "W_DATA_HI", "ECC_INJ",
               "FAULT_CLR", "EVQ_IN", "EVQ_OUT", "N_DATA")

# STATUS sticky bit -> the RTL input that sets it (docs/10 section 10).
STICKY_EVENT = {
    "SYNC_DONE": "hw_sync_done",
    "ERR_CFG": "hw_err_cfg",
    "DED_SEEN": "hw_ded",
    "OVF_SEEN": "hw_evq_ovf",
}

# Fault counter -> the RTL input that increments it. The FAULT_CLR bit
# positions come from the generated field table (regmap.yaml declares them,
# RTL header convention C2); test_regmap_walk_is_complete cross-checks that
# they are still in fault-block offset order, which is what the packed
# counter vector in the RTL assumes.
COUNTER_EVENT = {
    "CNT_SEC": "hw_sec",
    "CNT_DED": "hw_ded",
    "CNT_EVQ_OVF": "hw_evq_ovf",
    "CNT_AXON_OOR": "hw_axon_oor",
}
COUNTERS = sorted(COUNTER_EVENT, key=lambda n: ADDR[n])
FCLR_BIT = {name: FIELDS["FAULT_CLR"][name] for name in COUNTERS}
FCLR_BIT_FAULT_ADDR = FIELDS["FAULT_CLR"]["FAULT_ADDR"]

# Configuration lock (docs/10 section 6, RTL header convention C4). Listed
# by register name from the specification side, never derived from the
# design's own decode wire, so a locked set that grows or shrinks in the
# RTL is caught rather than mirrored. LOCKED is every register whose value
# enters the per-pass configuration or the memory load port; UNLOCKED is
# the three names docs/10 gives plus the three the RTL header adds.
# test_regmap_walk_is_complete checks that the two lists partition the
# writable half of the map exactly.
LOCKED = ("CFG_NEUR", "CFG_AXON", "CFG_THRESH", "CFG_VRESET", "CFG_LEAK",
          "CFG_SYNSHIFT", "CFG_REFR", "CFG_FLAGS",
          "PASS_TILE_OFF", "W_BASE", "PASS_ID",
          "W_ADDR", "W_DATA_LO", "W_DATA_HI", "N_ADDR", "N_DATA",
          "NODE_ID")
UNLOCKED = ("CTRL", "STATUS_CLR", "FAULT_CLR", "SCRATCH", "ECC_INJ", "EVQ_IN")
WRITABLE_ACCESS = ("RW", "WO", "W1C")

# Hardware inputs at their idle values: core not busy, both queues empty,
# no faults, nothing pending on the state or output-event ports.
IDLE_INPUTS = {
    "hw_busy": 0,
    "hw_evq_in_empty": 1,
    "hw_evq_out_empty": 1,
    "hw_sync_done": 0,
    "hw_err_cfg": 0,
    "hw_sec": 0,
    "hw_ded": 0,
    "hw_evq_ovf": 0,
    "hw_axon_oor": 0,
    "hw_fault_addr": 0,
    "n_data_ld": 0,
    "n_data_hw": 0,
    "hw_evq_out_valid": 0,
    "hw_evq_out_data": 0,
    "hw_evq_in_fill": 0,
    "hw_evq_out_fill": 0,
}


# ----------------------------------------------------------------------
# Derived register facts (all computed from the generated tables)
# ----------------------------------------------------------------------

def field_mask(name, field):
    return ((1 << FIELD_WIDTHS[name][field]) - 1) << FIELDS[name][field]


def writable_mask(name):
    """Bits a software write can change: the union of the declared fields,
    or the whole word for a register the YAML declares without fields."""
    if name not in FIELDS:
        return ALL_ONES
    mask = 0
    for field in FIELDS[name]:
        mask |= field_mask(name, field)
    return mask


def sc_mask(name):
    """Bits that self-clear on the cycle after the write."""
    mask = 0
    for field in SELF_CLEARING.get(name, ()):
        mask |= field_mask(name, field)
    return mask


def sticky_mask(name):
    """Bits a write changes and that stay changed."""
    return writable_mask(name) & ~sc_mask(name) & ALL_ONES


def unmapped_offsets():
    used = set(ADDR.values())
    return [a for a in range(0, ADDR_SPACE, WORD) if a not in used]


def reset_values(dut):
    """The reset value of every register for THIS instantiation.

    CFG_NEUR and CFG_AXON reset from the N_NEURONS / N_AXONS parameters:
    docs/10 section 6 gives those two reset values symbolically, while
    regmap.yaml can only carry the 512 default (RTL header convention C8).
    Every other register resets to the literal in the generated table."""
    values = dict(RESET)
    values["CFG_NEUR"] = int(dut.N_NEURONS.value)
    values["CFG_AXON"] = int(dut.N_AXONS.value)
    return values


# ----------------------------------------------------------------------
# Bus driver: single-beat valid/ready, response one cycle after acceptance
#
# The driver honours bus_req_ready: the block inserts one wait state after
# an accepted EVQ_OUT read (RTL header section 1 / C9), and a bridge that
# pulsed the request for a fixed single cycle would silently lose that
# transaction. The request is therefore held until it is accepted and
# dropped as soon as it is -- the same one-shot rule the RTL header
# prescribes for the APB and SPI bridges.
#
# Holding the request is bounded, not open-ended. An unbounded wait turns
# any ready-side regression -- a ready that never reasserts, a decode that
# drops the accept -- into a suite that hangs until something outside kills
# it, which is strictly worse than a failure: no message, no failing test
# name, and in CI a wasted timeout budget instead of a diagnosis.
# ----------------------------------------------------------------------

# The block's longest documented stall is a single wait state (C9), so any
# real transaction is accepted within two edges. 64 is ~32x that: wide
# enough that no legitimate change to the accept policy trips it, small
# enough to fail in microseconds of simulated time.
BUS_ACCEPT_TIMEOUT = 64

async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.bus_req_valid.value = 0
    dut.bus_req_write.value = 0
    dut.bus_req_addr.value = 0
    dut.bus_req_wdata.value = 0
    for name, value in IDLE_INPUTS.items():
        getattr(dut, name).value = value
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


async def bus_xact(dut, addr, write, data=0):
    """One accepted transaction; returns (rdata, error) in the response
    cycle. Waits for bus_req_ready, but only for BUS_ACCEPT_TIMEOUT
    edges: a ready that never comes back fails here with the address and
    the direction, instead of hanging the suite."""
    dut.bus_req_valid.value = 1
    dut.bus_req_write.value = 1 if write else 0
    dut.bus_req_addr.value = addr
    dut.bus_req_wdata.value = data
    for _ in range(BUS_ACCEPT_TIMEOUT):
        await Timer(1, unit="ns")            # let the registered ready settle
        accepted = int(dut.bus_req_ready.value)
        await RisingEdge(dut.clk)
        if accepted:
            break
    else:
        dut.bus_req_valid.value = 0
        dut.bus_req_write.value = 0
        raise AssertionError(
            f"bus_req_ready stayed low for {BUS_ACCEPT_TIMEOUT} clock edges "
            f"on a {'write' if write else 'read'} to 0x{addr:03X}; the block "
            f"accepts within two edges even after the one EVQ_OUT wait state "
            f"(RTL header C9), so this is a ready-side regression")
    dut.bus_req_valid.value = 0
    dut.bus_req_write.value = 0
    await Timer(1, unit="ns")
    assert dut.bus_rsp_valid.value == 1, (
        "no response beat for an accepted transaction")
    return int(dut.bus_rsp_rdata.value), int(dut.bus_rsp_error.value)


async def bus_write(dut, addr, data):
    """One accepted write; returns bus_rsp_error."""
    _, err = await bus_xact(dut, addr, True, data)
    return err


async def bus_read(dut, addr):
    """One accepted read; returns (rdata, error)."""
    return await bus_xact(dut, addr, False)


async def rd(dut, name):
    value, err = await bus_read(dut, ADDR[name])
    assert err == 0, f"mapped read of {name} flagged as unmapped"
    return value


async def hw_pulse(dut, signal, cycles=1, **extra):
    """Assert a hardware event input for `cycles` clock edges."""
    for key, value in extra.items():
        getattr(dut, key).value = value
    getattr(dut, signal).value = 1
    for _ in range(cycles):
        await RisingEdge(dut.clk)
    getattr(dut, signal).value = 0
    await Timer(1, unit="ns")


async def snapshot(dut):
    return {name: await rd(dut, name) for name in ADDR}


async def show_ahead_queue(dut, pending, popped):
    """Drive hw_evq_out_valid / hw_evq_out_data as the show-ahead source
    the block requires (RTL header convention C9): the head word is
    presented until evq_out_pop is asserted, and the queue advances on the
    edge that ends the pop cycle. `pending` is consumed in place and every
    word the block pops is appended to `popped`, so a destroyed event shows
    up as a word that was popped but never read.

    hw/rtl/aer_fifo.v does NOT behave this way -- it is a registered-output
    queue -- which is why the contract is stated in the RTL header and
    modelled here rather than instantiated."""
    def present():
        if pending:
            dut.hw_evq_out_valid.value = 1
            dut.hw_evq_out_data.value = pending[0]
        else:
            dut.hw_evq_out_valid.value = 0
            dut.hw_evq_out_data.value = 0

    present()
    take = 0
    while True:
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if take and pending:
            popped.append(pending.pop(0))
        present()
        take = int(dut.evq_out_pop.value)


# ----------------------------------------------------------------------
# Structural checks on the generated map itself
# ----------------------------------------------------------------------

@cocotb.test()
async def test_regmap_walk_is_complete(dut):
    """Every register in the generated map is claimed by exactly one access
    class this suite knows how to drive, and every self-clearing field name
    resolves in the generated field table. A new access code or a renamed
    field fails here instead of silently skipping coverage."""
    known = {"RO", "RW", "WO", "W1C"}
    unknown = {n: a for n, a in ACCESS.items() if a not in known}
    assert not unknown, f"unhandled access codes in regmap.yaml: {unknown}"
    assert set(ACCESS) == set(ADDR) == set(RESET), "generated tables disagree"
    for name, fields in SELF_CLEARING.items():
        for field in fields:
            assert field in FIELDS[name], f"{name}.{field} vanished from regmap"
    for name in list(STICKY_EVENT):
        assert name in FIELDS["STATUS"], f"STATUS.{name} vanished from regmap"
    for name in COUNTERS:
        assert ACCESS[name] == "RO", f"{name} is no longer a read-only counter"
    assert len(ADDR) == len(set(ADDR.values())), "duplicate offsets"
    # FAULT_CLR carries its bit assignment in the YAML (convention C2), and
    # the RTL packs the four counters in fault-block offset order, so the
    # declared bits must follow that order with FAULT_ADDR last.
    for index, name in enumerate(COUNTERS):
        assert FIELDS["FAULT_CLR"][name] == index, (
            f"FAULT_CLR.{name} is at bit {FIELDS['FAULT_CLR'][name]}, "
            f"but the fault-block offset order puts it at bit {index}")
    assert FCLR_BIT_FAULT_ADDR == len(COUNTERS), "FAULT_CLR.FAULT_ADDR moved"
    assert set(FIELDS["FAULT_CLR"]) == set(COUNTERS) | {"FAULT_ADDR"}, (
        "FAULT_CLR fields no longer cover exactly the fault block")
    # The configuration lock lists must partition the writable half of the
    # map: nothing writable is unclassified, nothing is in both lists.
    writable = {n for n, a in ACCESS.items() if a in WRITABLE_ACCESS}
    assert set(LOCKED) | set(UNLOCKED) == writable, (
        "configuration lock lists do not cover the writable registers: "
        f"missing {sorted(writable - set(LOCKED) - set(UNLOCKED))}, "
        f"unknown {sorted(set(LOCKED) | set(UNLOCKED) - writable)}")
    assert not set(LOCKED) & set(UNLOCKED), "a register is locked and unlocked"
    assert len(LOCKED) == 17, f"the locked set is {len(LOCKED)} registers, not 17"


# ----------------------------------------------------------------------
# Reset values
# ----------------------------------------------------------------------

@cocotb.test()
async def test_reset_values(dut):
    """Every register reads its documented reset value out of reset: the
    regmap.yaml literal, except CFG_NEUR / CFG_AXON, which docs/10 section
    6 resets symbolically to N_NEURONS / N_AXONS (convention C8)."""
    await reset(dut)
    want = reset_values(dut)
    for name in ADDR:
        got = await rd(dut, name)
        assert got == want[name], (
            f"{name} reset value: got 0x{got:08X}, "
            f"expected 0x{want[name]:08X}")


@cocotb.test()
async def test_cfg_neur_axon_reset_from_parameters(dut):
    """CFG_NEUR and CFG_AXON reset to the N_NEURONS / N_AXONS parameters,
    not to the 512 literal regmap.yaml has to carry, so a smaller
    instantiation comes out of reset with a valid configuration and can be
    started (docs/10 sections 1 and 6, RTL header convention C8). The same
    parameters, not the literal, are the upper bound cfg_valid checks."""
    await reset(dut)
    err_bit = FIELDS["STATUS"]["ERR_CFG"]
    n_neurons = int(dut.N_NEURONS.value)
    n_axons = int(dut.N_AXONS.value)
    got_neur = await rd(dut, "CFG_NEUR")
    got_axon = await rd(dut, "CFG_AXON")
    assert got_neur == n_neurons, (
        f"CFG_NEUR reset {got_neur} != N_NEURONS {n_neurons}: a build "
        "smaller than the regmap default comes out of reset invalid")
    assert got_axon == n_axons, f"CFG_AXON reset {got_axon} != N_AXONS {n_axons}"
    assert int(dut.cfg_valid.value) == 1, "reset configuration must be valid"
    await bus_write(dut, ADDR["CTRL"], 1)
    assert int(dut.en.value) == 1, "the core must be startable out of reset"
    assert await rd(dut, "STATUS") >> err_bit & 1 == 0, (
        "a freshly reset core must not be reporting a configuration error")
    for reg, bound in (("CFG_NEUR", n_neurons), ("CFG_AXON", n_axons)):
        await bus_write(dut, ADDR[reg], bound + 1)
        assert int(dut.cfg_valid.value) == 0, (
            f"{reg} = {bound + 1} accepted above the build parameter")
        await bus_write(dut, ADDR[reg], bound)
        assert int(dut.cfg_valid.value) == 1, f"{reg} = {bound} rejected"


@cocotb.test()
async def test_status_reset_value_is_literal(dut):
    """STATUS reads its literal reset value (0x6: not busy, both queues
    empty) in the first cycle out of reset even when the datapath drives the
    opposite polarity, because the live bits are a registered snapshot
    (RTL header convention C3). One cycle later it tracks the inputs."""
    await reset(dut)
    dut.rst_n.value = 0
    dut.hw_busy.value = 1
    dut.hw_evq_in_empty.value = 0
    dut.hw_evq_out_empty.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst_n.value = 1
    got, _ = await bus_read(dut, ADDR["STATUS"])   # accepted on the first
    assert got == RESET["STATUS"], (               # post-reset edge
        f"STATUS out of reset: got 0x{got:08X}, "
        f"expected 0x{RESET['STATUS']:08X}")
    live = await rd(dut, "STATUS")
    assert live & 0x7 == 0x1, "STATUS live bits did not follow the datapath"


# ----------------------------------------------------------------------
# Access classes
# ----------------------------------------------------------------------

@cocotb.test()
async def test_rw_write_readback(dut):
    """Every RW register accepts writes on exactly its declared field bits
    and rejects the rest: an all-ones write reads back as the field mask,
    and a random pattern reads back masked."""
    await reset(dut)
    random.seed(20260825)
    want = reset_values(dut)
    for name, access in ACCESS.items():
        if access != "RW":
            continue
        mask = sticky_mask(name)
        assert mask, f"{name} is RW but has no writable bits"
        await bus_write(dut, ADDR[name], ALL_ONES)
        await bus_read(dut, ADDR[name])            # settle past any SC bit
        got = await rd(dut, name)
        assert got == mask, (
            f"{name} all-ones write: got 0x{got:08X}, expected 0x{mask:08X} "
            "(bits outside the declared fields must be unwritable)")
        pattern = random.getrandbits(32)
        await bus_write(dut, ADDR[name], pattern)
        await bus_read(dut, ADDR[name])
        got = await rd(dut, name)
        assert got == pattern & mask, (
            f"{name} pattern 0x{pattern:08X}: got 0x{got:08X}, "
            f"expected 0x{pattern & mask:08X}")
        await bus_write(dut, ADDR[name], want[name])    # leave it clean


@cocotb.test()
async def test_ro_write_ignored(dut):
    """A write to a read-only register changes nothing and is not an error
    (GRLIB convention: no effect). Covers every architecturally read-only
    register in the map, including the identity constants."""
    await reset(dut)
    for name, access in ACCESS.items():
        if access != "RO":
            continue
        before = await rd(dut, name)
        err = await bus_write(dut, ADDR[name], ~before & ALL_ONES)
        assert err == 0, f"write to mapped RO register {name} flagged as error"
        err = await bus_write(dut, ADDR[name], ALL_ONES)
        assert err == 0
        after = await rd(dut, name)
        assert after == before, (
            f"read-only {name} moved: 0x{before:08X} -> 0x{after:08X}")


@cocotb.test()
async def test_wo_and_w1c_read_as_zero(dut):
    """Write-only registers never expose their contents and the W1C ports
    hold no state: both read 0x00000000 whatever was written."""
    await reset(dut)
    for name, access in ACCESS.items():
        if access not in ("WO", "W1C"):
            continue
        await bus_write(dut, ADDR[name], ALL_ONES)
        got = await rd(dut, name)
        assert got == 0, f"{name} ({access}) read back 0x{got:08X}, expected 0"


@cocotb.test()
async def test_identity_and_version_constants(dut):
    """ID and VERSION are hardwired discovery words (docs/08 GRLIB
    identification convention): constant, and unaffected by any write."""
    await reset(dut)
    for name in ("ID", "VERSION"):
        assert await rd(dut, name) == RESET[name]
        await bus_write(dut, ADDR[name], ALL_ONES)
        assert await rd(dut, name) == RESET[name], f"{name} is not constant"
    assert RESET["ID"] == 0x4E505531, "identity word changed in regmap.yaml"


# ----------------------------------------------------------------------
# W1C sticky bits
# ----------------------------------------------------------------------

@cocotb.test()
async def test_w1c_sticky_set_by_hardware_clear_by_write_one(dut):
    """Each STATUS sticky bit is set only by its hardware event, stays set,
    is cleared only by a STATUS_CLR write-1 to its own position, and a
    write-0 leaves it alone."""
    await reset(dut)
    for field, signal in STICKY_EVENT.items():
        bit = FIELDS["STATUS"][field]
        assert await rd(dut, "STATUS") >> bit & 1 == 0
        await hw_pulse(dut, signal, hw_fault_addr=0)
        assert await rd(dut, "STATUS") >> bit & 1 == 1, f"{field} did not set"
        for _ in range(3):                      # sticky across idle cycles
            await RisingEdge(dut.clk)
        assert await rd(dut, "STATUS") >> bit & 1 == 1, f"{field} is not sticky"
        await bus_write(dut, ADDR["STATUS_CLR"], ALL_ONES & ~(1 << bit))
        assert await rd(dut, "STATUS") >> bit & 1 == 1, (
            f"{field} cleared by a write-1 aimed at other bits")
        await bus_write(dut, ADDR["STATUS_CLR"], 1 << bit)
        assert await rd(dut, "STATUS") >> bit & 1 == 0, f"{field} did not clear"


@cocotb.test()
async def test_w1c_race_hardware_wins(dut):
    """Hardware event coincident with the software clear: the event wins and
    the bit stays set (RTL header convention C1 -- an observed fault is
    never lost to a clear that raced it)."""
    await reset(dut)
    bit = FIELDS["STATUS"]["DED_SEEN"]
    dut.hw_ded.value = 1                        # event on the same edge as
    dut.hw_fault_addr.value = 0x0000ABCD        # the clear write
    await bus_write(dut, ADDR["STATUS_CLR"], 1 << bit)
    dut.hw_ded.value = 0
    await Timer(1, unit="ns")
    assert await rd(dut, "STATUS") >> bit & 1 == 1, (
        "software clear erased a coincident hardware event")
    await bus_write(dut, ADDR["STATUS_CLR"], 1 << bit)   # lone clear works
    assert await rd(dut, "STATUS") >> bit & 1 == 0


# ----------------------------------------------------------------------
# Fault counters
# ----------------------------------------------------------------------

@cocotb.test()
async def test_counter_increment_and_clear(dut):
    """Each fault counter counts exactly its own event, ignores the other
    events, and clears on exactly its own FAULT_CLR bit (RTL header
    convention C2) without disturbing the rest of the fault block."""
    await reset(dut)
    for k, name in enumerate(COUNTERS, start=1):
        await hw_pulse(dut, COUNTER_EVENT[name], cycles=k, hw_fault_addr=0)
        got = await rd(dut, name)
        assert got == k, f"{name}: got {got} after {k} of its own events"
    for k, name in enumerate(COUNTERS, start=1):
        got = await rd(dut, name)
        assert got == k, f"{name} counted an event belonging to another counter"
    for name in COUNTERS:
        before = {n: await rd(dut, n) for n in COUNTERS}
        assert before[name] != 0
        await bus_write(dut, ADDR["FAULT_CLR"], 1 << FCLR_BIT[name])
        after = {n: await rd(dut, n) for n in COUNTERS}
        assert after[name] == 0, f"{name} did not clear on its own bit"
        for other in COUNTERS:
            if other != name:
                assert after[other] == before[other], (
                    f"clearing {name} disturbed {other}")
        await hw_pulse(dut, COUNTER_EVENT[name])   # re-arm for the next round
        assert await rd(dut, name) == 1


@cocotb.test()
async def test_counter_clear_race_restarts_at_one(dut):
    """A counted event coincident with its clear restarts the counter at 1,
    so the event is not lost (convention C1, same as the aer_fifo drop
    counter)."""
    await reset(dut)
    name = "CNT_SEC"
    await hw_pulse(dut, COUNTER_EVENT[name], cycles=4)
    assert await rd(dut, name) == 4
    dut.hw_sec.value = 1
    await bus_write(dut, ADDR["FAULT_CLR"], 1 << FCLR_BIT[name])
    dut.hw_sec.value = 0
    await Timer(1, unit="ns")
    assert await rd(dut, name) == 1, "coincident event lost by the clear"


@cocotb.test()
async def test_fault_addr_latch(dut):
    """FAULT_ADDR latches the word index of the last double-bit detection,
    clears on its own FAULT_CLR bit, and keeps a newly latched address that
    races the clear."""
    await reset(dut)
    await hw_pulse(dut, "hw_ded", hw_fault_addr=0x00001234)
    assert await rd(dut, "FAULT_ADDR") == 0x00001234
    await hw_pulse(dut, "hw_ded", hw_fault_addr=0x0000BEEF)
    assert await rd(dut, "FAULT_ADDR") == 0x0000BEEF, "latch did not update"
    dut.hw_ded.value = 1
    dut.hw_fault_addr.value = 0x00005A5A
    await bus_write(dut, ADDR["FAULT_CLR"], 1 << FCLR_BIT_FAULT_ADDR)
    dut.hw_ded.value = 0
    await Timer(1, unit="ns")
    assert await rd(dut, "FAULT_ADDR") == 0x00005A5A, "racing latch lost"
    await bus_write(dut, ADDR["FAULT_CLR"], 1 << FCLR_BIT_FAULT_ADDR)
    assert await rd(dut, "FAULT_ADDR") == 0


@cocotb.test()
async def test_fault_clr_mask_is_re_exported(dut):
    """The FAULT_CLR mask reappears on the fault_clr output one cycle later
    so the SoC can clear distributed copies of the same record (convention
    C2); it is a one-cycle strobe.

    The mask used here is 0b10101, which is a palindrome. That is fine for
    what this test claims -- export and strobe length -- but it says
    nothing about bit ORDER, so the direction of the export is checked
    separately below."""
    await reset(dut)
    mask = 0b10101
    await bus_write(dut, ADDR["FAULT_CLR"], mask)
    assert int(dut.fault_clr.value) == mask, "FAULT_CLR mask not exported"
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.fault_clr.value) == 0, "fault_clr is not a one-cycle strobe"


@cocotb.test()
async def test_fault_clr_export_preserves_bit_order(dut):
    """fault_clr[i] carries FAULT_CLR bit i, for every i, in that order.

    A positive-direction obligation on the port, which the palindromic
    mask above cannot give: 0b10101 reversed is still 0b10101, so a
    bit-reversed re-export (`fault_clr <= {fclr[0], fclr[1], ...}`) or any
    permutation of the five bits would satisfy that test unchanged. The
    one-hot walk below pins every bit individually, so a reversal fails on
    CNT_SEC and a swap of any two bits fails on both of them. The
    asymmetric multi-bit masks then confirm the same order when several
    bits move at once, since a one-hot walk alone cannot see a decode that
    is order-correct singly and wrong in combination.

    Bit positions come from the generated field table, never from a
    literal here: a YAML edit that moves a bit moves this test with it,
    and sw/tests/test_regmap.py separately holds the table itself to the
    offset order the RTL's packed counter vector assumes."""
    await reset(dut)

    width = len(dut.fault_clr.value)
    assert width == len(FIELDS["FAULT_CLR"]), (
        f"fault_clr is {width} bits wide, regmap.yaml declares "
        f"{len(FIELDS['FAULT_CLR'])} FAULT_CLR fields")

    async def export_of(mask):
        """The fault_clr word a FAULT_CLR write of `mask` produces, with
        the strobe checked back to zero afterwards."""
        await bus_write(dut, ADDR["FAULT_CLR"], mask)
        exported = int(dut.fault_clr.value)
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.fault_clr.value) == 0, (
            f"fault_clr did not return to 0 after a write of 0x{mask:X}")
        return exported

    def reversed_of(mask):
        return int(f"{mask:0{width}b}"[::-1], 2)

    # One-hot walk: catches a reversal and any permutation.
    for field, bit in sorted(FIELDS["FAULT_CLR"].items(), key=lambda kv: kv[1]):
        exported = await export_of(1 << bit)
        assert exported == 1 << bit, (
            f"FAULT_CLR.{field} is bit {bit}: wrote 0b{1 << bit:0{width}b}, "
            f"fault_clr exported 0b{exported:0{width}b}. A bit-reversed "
            f"export would show 0b{reversed_of(1 << bit):0{width}b}")

    # Asymmetric multi-bit masks, each listed together with its own
    # reversal: a reversed export turns one of a pair into the other, and
    # both are legal masks, so only checking them by name catches it.
    # These literals are 5 bits wide by the width assertion above; a
    # FAULT_CLR that grows a sixth field fails there first, which is the
    # right place to be told to revisit them.
    for mask in (0b00011, 0b11000, 0b01101, 0b10110, 0b00111, 0b11100):
        exported = await export_of(mask)
        assert exported == mask, (
            f"wrote 0b{mask:0{width}b}, fault_clr exported "
            f"0b{exported:0{width}b} (reversal of the write would be "
            f"0b{reversed_of(mask):0{width}b})")

    # Bits above the declared fields are ignored by the register, so they
    # must not appear on the port either: a widened or mis-sliced export
    # shows up here rather than in silicon.
    all_declared = sum(1 << bit for bit in FIELDS["FAULT_CLR"].values())
    exported = await export_of(ALL_ONES)
    assert exported == all_declared, (
        f"writing all ones exported 0b{exported:0{width}b}, the declared "
        f"fields cover 0b{all_declared:0{width}b}")

    # ... and the unassigned bits on their own must reach nothing at all.
    # Checked separately from the all-ones write above, which cannot see a
    # leak: there every declared bit is set anyway, so an unassigned bit
    # wired into one of them is indistinguishable from correct behaviour.
    unassigned = ALL_ONES & ~all_declared
    assert unassigned, "FAULT_CLR has no unassigned bits left to check"
    for mask in (1 << width, 1 << 31, unassigned):
        exported = await export_of(mask)
        assert exported == 0, (
            f"wrote 0x{mask:08X}, which selects no declared FAULT_CLR "
            f"field, but fault_clr exported 0b{exported:0{width}b}; bits "
            f"[31:{width}] are ignored by the register and must not reach "
            f"the port")


# ----------------------------------------------------------------------
# CTRL, configuration lock and start gating
# ----------------------------------------------------------------------

@cocotb.test()
async def test_ctrl_self_clearing_bits(dut):
    """CTRL.STATE_CLR and CTRL.SOFT_RST pulse their outputs for exactly one
    cycle, read back as 1 only in that cycle, and never fire without a
    write-1."""
    await reset(dut)
    bits = sc_mask("CTRL")
    assert int(dut.state_clr.value) == 0 and int(dut.soft_rst.value) == 0
    await bus_write(dut, ADDR["CTRL"], bits)
    assert int(dut.state_clr.value) == 1, "STATE_CLR did not pulse"
    assert int(dut.soft_rst.value) == 1, "SOFT_RST did not pulse"
    got = await rd(dut, "CTRL")             # read accepted in the pulse cycle
    assert got & bits == bits, "self-clearing bits do not read back while set"
    assert int(dut.state_clr.value) == 0, "STATE_CLR wider than one cycle"
    assert int(dut.soft_rst.value) == 0, "SOFT_RST wider than one cycle"
    got = await rd(dut, "CTRL")
    assert got & bits == 0, "self-clearing bits did not clear"
    await bus_write(dut, ADDR["CTRL"], 0)   # write-0 must not pulse
    assert int(dut.state_clr.value) == 0 and int(dut.soft_rst.value) == 0


@cocotb.test()
async def test_config_lock_while_busy(dut):
    """docs/10 section 6: configuration writes while STATUS.BUSY are ignored
    and latch ERR_CFG, while CTRL, STATUS_CLR and FAULT_CLR stay writable
    (RTL header convention C4)."""
    await reset(dut)
    err_bit = FIELDS["STATUS"]["ERR_CFG"]
    before = await rd(dut, "CFG_THRESH")
    dut.hw_busy.value = 1
    await RisingEdge(dut.clk)               # BUSY snapshot reaches STATUS
    await Timer(1, unit="ns")
    assert await rd(dut, "STATUS") & 1 == 1, "BUSY did not reach STATUS"
    err = await bus_write(dut, ADDR["CFG_THRESH"], 0x0000007F)
    assert err == 0, "a blocked write is ignored, not a bus error"
    assert await rd(dut, "CFG_THRESH") == before, "config write ignored the lock"
    assert await rd(dut, "STATUS") >> err_bit & 1 == 1, "ERR_CFG not latched"
    await bus_write(dut, ADDR["STATUS_CLR"], 1 << err_bit)   # still writable
    assert await rd(dut, "STATUS") >> err_bit & 1 == 0
    await bus_write(dut, ADDR["CTRL"], 1)                    # still writable
    assert await rd(dut, "CTRL") & 1 == 1
    await bus_write(dut, ADDR["SCRATCH"], 0xC0FFEE00)        # not in the set
    assert await rd(dut, "SCRATCH") == 0xC0FFEE00
    dut.hw_busy.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    await bus_write(dut, ADDR["CFG_THRESH"], 0x0000007F)
    assert await rd(dut, "CFG_THRESH") == 0x0000007F, "lock stuck after BUSY"


@cocotb.test()
async def test_config_lock_has_no_rising_edge_hole(dut):
    """A configuration write accepted on the very edge hw_busy rises is
    still refused and still latches ERR_CFG. STATUS.BUSY is a registered
    snapshot one cycle behind hw_busy (convention C3), so a lock keyed only
    off that snapshot would let this one write through -- neither ignored
    nor flagged -- while the datapath is already running (C4)."""
    await reset(dut)
    err_bit = FIELDS["STATUS"]["ERR_CFG"]
    before = await rd(dut, "CFG_THRESH")
    assert await rd(dut, "STATUS") & 1 == 0, "the core must start not busy"
    dut.hw_busy.value = 1                    # rises on the same edge that
    err = await bus_write(dut, ADDR["CFG_THRESH"], 0x00000055)  # accepts
    assert err == 0, "a blocked write is ignored, not a bus error"
    assert await rd(dut, "STATUS") & 1 == 1, "hw_busy did not reach STATUS"
    assert await rd(dut, "CFG_THRESH") == before, (
        "a configuration write accepted on the rising edge of hw_busy got "
        "through: STATUS.BUSY lags hw_busy by one cycle and the lock must "
        "not lag with it")
    assert await rd(dut, "STATUS") >> err_bit & 1 == 1, "ERR_CFG not latched"


@cocotb.test()
async def test_config_lock_covers_every_locked_register(dut):
    """All 17 locked registers refuse their write while BUSY and latch
    ERR_CFG, and all 6 unlocked registers still take theirs without
    flagging (docs/10 section 6, convention C4). Driving one register would
    not distinguish the specified locked set from any larger or smaller
    one, so every member of both lists is exercised."""
    await reset(dut)
    err_bit = FIELDS["STATUS"]["ERR_CFG"]
    dut.hw_busy.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert await rd(dut, "STATUS") & 1 == 1, "BUSY did not reach STATUS"

    for name in LOCKED:
        await bus_write(dut, ADDR["STATUS_CLR"], 1 << err_bit)
        assert await rd(dut, "STATUS") >> err_bit & 1 == 0, "clean slate"
        # The probe is the complement of what the register holds, so every
        # writable bit would flip if the lock let the write through; a
        # fixed pattern could coincide with the current value and pass
        # vacuously.
        if name in ("W_DATA_LO", "W_DATA_HI"):
            shift = 0 if name == "W_DATA_LO" else 32
            before = (int(dut.w_data.value) >> shift) & ALL_ONES
            probe = ~before & ALL_ONES
            err = await bus_write(dut, ADDR[name], probe)
            after = (int(dut.w_data.value) >> shift) & ALL_ONES
            assert int(dut.w_commit.value) == 0, (
                f"a {name} write while BUSY committed a weight word")
        else:
            before = await rd(dut, name)
            probe = ~before & ALL_ONES
            err = await bus_write(dut, ADDR[name], probe)
            after = await rd(dut, name)
        assert probe & writable_mask(name) != before & writable_mask(name), (
            f"the {name} probe would not have changed anything")
        assert err == 0, f"a blocked write to {name} raised a bus error"
        assert after == before, (
            f"locked register {name} took a write while BUSY: "
            f"0x{before:08X} -> 0x{after:08X}")
        assert await rd(dut, "STATUS") >> err_bit & 1 == 1, (
            f"a blocked write to {name} did not latch ERR_CFG")

    await bus_write(dut, ADDR["STATUS_CLR"], 1 << err_bit)
    for name in UNLOCKED:
        await unlocked_probe(dut, name)
        assert await rd(dut, "STATUS") >> err_bit & 1 == 0, (
            f"a write to {name} while BUSY was flagged; it is not locked")


async def unlocked_probe(dut, name):
    """Write the one register `name` while BUSY and check the write took
    effect. Each of the six is observed through its own side effect,
    because three of them hold no readable state."""
    if name == "SCRATCH":
        await bus_write(dut, ADDR[name], 0xC0FFEE00)
        assert await rd(dut, name) == 0xC0FFEE00, "SCRATCH write lost"
    elif name == "CTRL":
        await bus_write(dut, ADDR[name], 1)
        assert await rd(dut, name) & 1 == 1, "CTRL.EN write lost"
        await bus_write(dut, ADDR[name], 0)
    elif name == "STATUS_CLR":
        bit = FIELDS["STATUS"]["SYNC_DONE"]
        await hw_pulse(dut, "hw_sync_done")
        assert await rd(dut, "STATUS") >> bit & 1 == 1
        await bus_write(dut, ADDR[name], 1 << bit)
        assert await rd(dut, "STATUS") >> bit & 1 == 0, "STATUS_CLR write lost"
    elif name == "FAULT_CLR":
        await hw_pulse(dut, COUNTER_EVENT["CNT_SEC"])
        assert await rd(dut, "CNT_SEC") == 1
        await bus_write(dut, ADDR[name], 1 << FCLR_BIT["CNT_SEC"])
        assert await rd(dut, "CNT_SEC") == 0, "FAULT_CLR write lost"
    elif name == "ECC_INJ":
        await bus_write(dut, ADDR[name], 1 << FIELDS["ECC_INJ"]["SINGLE"])
        assert int(dut.ecc_inj_single.value) == 1, "ECC_INJ write lost"
        await bus_write(dut, ADDR[name], 0)
    elif name == "EVQ_IN":
        await bus_write(dut, ADDR[name], 0x0000BEEF)
        assert int(dut.evq_in_wr.value) == 1, "EVQ_IN write lost"
        assert int(dut.evq_in_data.value) == 0xBEEF
    else:                                        # pragma: no cover
        raise AssertionError(f"no probe for unlocked register {name}")


@cocotb.test()
async def test_cfg_valid_gates_enable(dut):
    """cfg_valid follows the docs/10 section 6 ranges; the core refuses to
    start on an out-of-range configuration (en stays low) and enabling it
    anyway latches ERR_CFG, while CTRL.EN still reads back what was written
    (RTL header convention C5)."""
    await reset(dut)
    err_bit = FIELDS["STATUS"]["ERR_CFG"]
    want = reset_values(dut)
    assert int(dut.cfg_valid.value) == 1, "reset configuration must be valid"
    await bus_write(dut, ADDR["CTRL"], 1)
    assert int(dut.en.value) == 1, "en did not follow CTRL.EN on a valid config"
    for reg, bad in (("CFG_THRESH", 0x00000000),   # THETA must be positive
                     ("CFG_THRESH", 0x00008000),   # THETA must not be negative
                     ("CFG_NEUR", 0x00000000),     # CNT must be >= 1
                     ("CFG_NEUR", 0x000007FF),     # CNT must be <= N_NEURONS
                     ("CFG_AXON", 0x00000000)):
        await bus_write(dut, ADDR[reg], bad)
        assert int(dut.cfg_valid.value) == 0, f"{reg}=0x{bad:X} accepted"
        assert int(dut.en.value) == 0, "en asserted on an invalid configuration"
        await bus_write(dut, ADDR[reg], want[reg])
        assert int(dut.cfg_valid.value) == 1
    # V_RESET must be below THETA (signed compare)
    await bus_write(dut, ADDR["CFG_VRESET"], RESET["CFG_THRESH"])
    assert int(dut.cfg_valid.value) == 0, "V_RESET == THETA accepted"
    await bus_write(dut, ADDR["CFG_VRESET"], 0x0000FFFF)      # -1, valid
    assert int(dut.cfg_valid.value) == 1
    # enabling with a bad configuration: EN reads back, en stays low, ERR_CFG
    await bus_write(dut, ADDR["CTRL"], 0)
    await bus_write(dut, ADDR["CFG_THRESH"], 0)
    await bus_write(dut, ADDR["STATUS_CLR"], 1 << err_bit)
    await bus_write(dut, ADDR["CTRL"], 1)
    assert await rd(dut, "CTRL") & 1 == 1, "CTRL.EN must read back as written"
    assert int(dut.en.value) == 0, "core started on an invalid configuration"
    assert await rd(dut, "STATUS") >> err_bit & 1 == 1, "ERR_CFG not latched"


@cocotb.test()
async def test_err_cfg_latches_on_a_write_that_invalidates_a_running_config(dut):
    """An out-of-range configuration write made while CTRL.EN reads 1 must
    latch ERR_CFG. Otherwise STATUS reports EN = 1, the core is silently
    gated off and no error bit says why, which contradicts the single
    register description of ERR_CFG ("out-of-range configuration or config
    write while BUSY"). Loading an out-of-range value with the core
    disabled is not an error (convention C5)."""
    await reset(dut)
    err_bit = FIELDS["STATUS"]["ERR_CFG"]
    want = reset_values(dut)
    await bus_write(dut, ADDR["CTRL"], 1)
    assert int(dut.en.value) == 1
    assert await rd(dut, "STATUS") >> err_bit & 1 == 0, "clean start"

    await bus_write(dut, ADDR["CFG_NEUR"], 0)          # takes it out of range
    assert int(dut.cfg_valid.value) == 0
    assert int(dut.en.value) == 0, "en must be gated off"
    assert await rd(dut, "CTRL") & 1 == 1, "CTRL.EN still reads 1"
    assert await rd(dut, "STATUS") >> err_bit & 1 == 1, (
        "an enabled core whose configuration was just made invalid must "
        "latch ERR_CFG")
    # the condition is a level, so the bit cannot be cleared while it holds
    await bus_write(dut, ADDR["STATUS_CLR"], 1 << err_bit)
    assert await rd(dut, "STATUS") >> err_bit & 1 == 1, (
        "ERR_CFG cleared while the configuration was still out of range")
    await bus_write(dut, ADDR["CFG_NEUR"], want["CFG_NEUR"])
    await bus_write(dut, ADDR["STATUS_CLR"], 1 << err_bit)
    assert await rd(dut, "STATUS") >> err_bit & 1 == 0, "ERR_CFG stuck"
    assert int(dut.en.value) == 1, "the core must run again once repaired"

    await bus_write(dut, ADDR["CTRL"], 0)              # disabled: not an error
    await bus_write(dut, ADDR["CFG_NEUR"], 0)
    assert int(dut.cfg_valid.value) == 0
    assert await rd(dut, "STATUS") >> err_bit & 1 == 0, (
        "loading a configuration with the core disabled must not flag")


# ----------------------------------------------------------------------
# Side-effect ports
# ----------------------------------------------------------------------

@cocotb.test()
async def test_weight_load_port(dut):
    """W_DATA_LO stages, W_DATA_HI commits the 64-bit word on w_commit, the
    handshake presents the index of the word it carries, and W_ADDR
    auto-increments on the commit (convention C6)."""
    await reset(dut)
    base = 0x00000100
    await bus_write(dut, ADDR["W_ADDR"], base)
    for i, (lo, hi) in enumerate(((0xAAAA5555, 0x12345678),
                                  (0x0F0F0F0F, 0xF0F0F0F0))):
        await bus_write(dut, ADDR["W_DATA_LO"], lo)
        assert int(dut.w_commit.value) == 0, "LO write must not commit"
        assert await rd(dut, "W_ADDR") == base + i, "W_ADDR moved on a LO write"
        await bus_write(dut, ADDR["W_DATA_HI"], hi)
        assert int(dut.w_commit.value) == 1, "HI write did not commit"
        assert int(dut.w_data.value) == (hi << 32) | lo, "wrong committed word"
        assert int(dut.w_addr.value) == base + i, (
            "the commit handshake must address the word it carries: "
            f"w_addr = 0x{int(dut.w_addr.value):08X}, expected "
            f"0x{base + i:08X} (the auto-increment belongs to the register "
            "software reads back, not to the port)")
        assert await rd(dut, "W_ADDR") == base + i + 1, "W_ADDR did not increment"
        assert int(dut.w_commit.value) == 0, "w_commit wider than one cycle"


@cocotb.test()
async def test_weight_load_back_to_back_commits(dut):
    """W_DATA_HI written on consecutive cycles commits consecutive words:
    the index the handshake presents advances by exactly one per commit,
    with no repeat and no gap (convention C6)."""
    await reset(dut)
    base = 0x00000200
    words = 4
    await bus_write(dut, ADDR["W_ADDR"], base)
    dut.bus_req_valid.value = 1
    dut.bus_req_write.value = 1
    dut.bus_req_addr.value = ADDR["W_DATA_HI"]
    seen = []
    for i in range(words):
        dut.bus_req_wdata.value = i
        await Timer(1, unit="ns")
        assert int(dut.bus_req_ready.value) == 1, "a weight write must not stall"
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")              # the commit of this accept
        assert int(dut.w_commit.value) == 1, f"commit {i} did not fire"
        seen.append(int(dut.w_addr.value))
    dut.bus_req_valid.value = 0
    dut.bus_req_write.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.w_commit.value) == 0, "w_commit outlived the write stream"
    assert seen == [base + i for i in range(words)], (
        f"commit indices {[hex(a) for a in seen]}, expected "
        f"{[hex(base + i) for i in range(words)]}")
    assert await rd(dut, "W_ADDR") == base + words, "W_ADDR lost a commit"


@cocotb.test()
async def test_ecc_inj_arm_and_consume(dut):
    """ECC_INJ arms the injection hooks; the arm is still asserted during
    the w_commit strobe that is supposed to corrupt the word, and drops on
    the edge that ends it (convention C7). Clearing the arm at the
    accepting edge instead would leave no cycle in which an armed hook and
    the commit are visible together, which makes the docs/10 section 11.2
    hook unusable. The register itself reads 0."""
    await reset(dut)
    single = 1 << FIELDS["ECC_INJ"]["SINGLE"]
    double = 1 << FIELDS["ECC_INJ"]["DOUBLE"]
    assert int(dut.ecc_inj_single.value) == 0
    assert int(dut.ecc_inj_double.value) == 0
    await bus_write(dut, ADDR["ECC_INJ"], single | double)
    assert int(dut.ecc_inj_single.value) == 1
    assert int(dut.ecc_inj_double.value) == 1
    assert await rd(dut, "ECC_INJ") == 0, "write-only register exposed state"
    await bus_write(dut, ADDR["W_DATA_LO"], 0)     # no commit, still armed
    assert int(dut.ecc_inj_single.value) == 1

    await bus_write(dut, ADDR["W_DATA_HI"], 0)     # the commit cycle
    assert int(dut.w_commit.value) == 1, "HI write did not commit"
    assert int(dut.ecc_inj_single.value) == 1, (
        "SINGLE was already disarmed in the w_commit cycle: no cycle shows "
        "an armed hook together with the commit it is supposed to corrupt")
    assert int(dut.ecc_inj_double.value) == 1, "DOUBLE gone in the commit cycle"
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.w_commit.value) == 0, "w_commit wider than one cycle"
    assert int(dut.ecc_inj_single.value) == 0, "SINGLE not consumed"
    assert int(dut.ecc_inj_double.value) == 0, "DOUBLE not consumed"

    await bus_write(dut, ADDR["W_DATA_HI"], 0)     # one arm, one commit
    assert int(dut.w_commit.value) == 1
    assert int(dut.ecc_inj_single.value) == 0, "the arm survived its commit"


@cocotb.test()
async def test_aer_software_ports(dut):
    """EVQ_IN pushes a 16-bit event word, EVQ_OUT pops one and reports
    VALID, a read of an empty output queue reads 0 and pops nothing, and
    EVQ_STAT mirrors the queue fill levels."""
    await reset(dut)
    event = 0x0000BEEF
    await bus_write(dut, ADDR["EVQ_IN"], 0xDEAD0000 | event)
    assert int(dut.evq_in_wr.value) == 1, "EVQ_IN did not push"
    assert int(dut.evq_in_data.value) == event & 0xFFFF, "wrong event word"
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.evq_in_wr.value) == 0, "evq_in_wr wider than one cycle"

    got = await rd(dut, "EVQ_OUT")            # empty queue
    assert got == 0, f"empty EVQ_OUT read 0x{got:08X}"
    assert int(dut.evq_out_pop.value) == 0, "popped an empty queue"

    dut.hw_evq_out_valid.value = 1
    dut.hw_evq_out_data.value = 0x1234
    await RisingEdge(dut.clk)
    got = await rd(dut, "EVQ_OUT")
    assert got == (1 << FIELDS["EVQ_OUT"]["VALID"]) | 0x1234, (
        f"EVQ_OUT read 0x{got:08X}")
    assert int(dut.evq_out_pop.value) == 1, "read did not pop"
    dut.hw_evq_out_valid.value = 0

    dut.hw_evq_in_fill.value = 0x21
    dut.hw_evq_out_fill.value = 0x07
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert await rd(dut, "EVQ_STAT") == 0x0721, "EVQ_STAT fill levels wrong"


@cocotb.test()
async def test_evq_out_back_to_back_reads_never_repeat(dut):
    """Reads of EVQ_OUT issued as fast as the bus allows return every
    queued event exactly once.

    The read returns the queue head at the accepting edge and the pop that
    consumes it lands one cycle later, so a slave that accepted the next
    request on that edge would hand the same head to two reads while
    issuing two pops -- one event returned twice and one destroyed, against
    docs/10 section 7.2 ("spikes are never dropped"). The queue here is the
    show-ahead source the RTL header (C9) requires."""
    await reset(dut)
    events = [0x1111, 0x2222, 0x3333, 0x4444]
    pending = list(events)
    popped = []
    cocotb.start_soon(show_ahead_queue(dut, pending, popped))
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    valid_bit = 1 << FIELDS["EVQ_OUT"]["VALID"]
    event_mask = (1 << FIELD_WIDTHS["EVQ_OUT"]["EVENT"]) - 1
    got = []
    for _ in events:
        word, err = await bus_read(dut, ADDR["EVQ_OUT"])
        assert err == 0, "mapped read of EVQ_OUT flagged as unmapped"
        assert word & valid_bit, "the queue had a word but the read said empty"
        got.append(word & event_mask)
    assert got == events, (
        f"back-to-back EVQ_OUT reads returned {[hex(w) for w in got]}, "
        f"expected {[hex(w) for w in events]}: a repeated word means one "
        "event was delivered twice and another was destroyed")

    # The pop belonging to the last read lands in its response cycle, so
    # the queue has consumed it by the time the next read is accepted.
    word, _ = await bus_read(dut, ADDR["EVQ_OUT"])   # drained
    assert word == 0, f"empty EVQ_OUT read 0x{word:08X} on a drained queue"
    assert popped == events, (
        f"the queue popped {[hex(w) for w in popped]} for those reads, "
        f"expected {[hex(w) for w in events]}")
    assert not pending, "events left in the queue"
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert popped == events, "a read of an empty queue popped something"


@cocotb.test()
async def test_evq_out_read_inserts_exactly_one_wait_state(dut):
    """bus_req_ready is low for exactly the cycle after an accepted EVQ_OUT
    read and high everywhere else, whatever the queue holds. The wait state
    keys off the address alone, so the bus timing of every offset is
    deterministic (RTL header section 1)."""
    await reset(dut)
    for valid in (0, 1):
        dut.hw_evq_out_valid.value = valid
        dut.hw_evq_out_data.value = 0x0777
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        dut.bus_req_valid.value = 1
        dut.bus_req_write.value = 0
        dut.bus_req_addr.value = ADDR["EVQ_OUT"]
        pattern = []
        for _ in range(6):
            pattern.append(int(dut.bus_req_ready.value))
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
        dut.bus_req_valid.value = 0
        assert pattern == [1, 0, 1, 0, 1, 0], (
            f"ready pattern {pattern} on a stream of EVQ_OUT reads "
            f"(hw_evq_out_valid={valid}); expected one wait state each")

    dut.bus_req_valid.value = 1
    dut.bus_req_addr.value = ADDR["SCRATCH"]
    for _ in range(4):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.bus_req_ready.value) == 1, "a non-EVQ_OUT read stalled"
    dut.bus_req_valid.value = 0


@cocotb.test()
async def test_apb_bridge_adaptation_commits_once(dut):
    """The APB adaptation prescribed in the RTL header section 1 delivers
    exactly one transaction per APB transfer.

    PSEL && PENABLE alone would not: the access phase lasts until PREADY,
    which is the registered response beat, so it spans at least two cycles
    and the slave would accept the request twice -- committing a weight
    word twice and stepping W_ADDR twice. The one-shot below is the
    prescription; this test drives it against the real slave."""
    await reset(dut)
    base = 0x00000300
    await bus_write(dut, ADDR["W_ADDR"], base)

    async def apb_transfer(addr, write, data=0):
        """One APB transfer: setup phase (PENABLE = 0), then access phase
        held until PREADY. bus_req_valid is PSEL && PENABLE && !apb_taken,
        the one-shot the header prescribes; drop the !apb_taken term and
        the access phase presents a second accepted request."""
        taken = 0
        rdata = 0
        dut.bus_req_addr.value = addr
        dut.bus_req_write.value = 1 if write else 0
        dut.bus_req_wdata.value = data
        dut.bus_req_valid.value = 0                  # PENABLE = 0: setup
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        # Bounded like bus_xact: a ready- or response-side regression must
        # fail the test, not hang the suite.
        for _ in range(BUS_ACCEPT_TIMEOUT):     # PENABLE = 1: access
            dut.bus_req_valid.value = 0 if taken else 1
            await Timer(1, unit="ns")
            accept = (not taken) and int(dut.bus_req_ready.value)
            pready = int(dut.bus_rsp_valid.value)    # PREADY
            if pready:
                rdata = int(dut.bus_rsp_rdata.value)
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            if accept:
                taken = 1
            if pready:
                break
        else:
            raise AssertionError(
                f"APB transfer to 0x{addr:02x} did not complete within "
                f"{BUS_ACCEPT_TIMEOUT} cycles "
                f"(taken={taken}); ready or response side is stuck"
            )
        dut.bus_req_valid.value = 0
        dut.bus_req_write.value = 0
        return rdata

    commits = []
    stop = []
    cocotb.start_soon(commit_monitor(dut, commits, stop))
    for i in range(3):
        await apb_transfer(ADDR["W_DATA_LO"], True, 0xA0000000 | i)
        await apb_transfer(ADDR["W_DATA_HI"], True, 0xB0000000 | i)
    read_back = await apb_transfer(ADDR["W_ADDR"], False)
    stop.append(True)
    assert commits == [base, base + 1, base + 2], (
        "one APB transfer per weight word must commit exactly once at "
        f"consecutive indices; saw commits at {[hex(a) for a in commits]}")
    assert read_back == base + 3, (
        f"W_ADDR read back 0x{read_back:08X} after three committed words, "
        f"expected 0x{base + 3:08X}: it must step once per APB transfer")


async def commit_monitor(dut, commits, stop):
    """Record the index of every weight commit the block issues."""
    while not stop:
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if int(dut.w_commit.value):
            commits.append(int(dut.w_addr.value))


@cocotb.test()
async def test_neuron_state_port(dut):
    """N_DATA is the state staging register: software writes strobe
    n_data_wr, reads strobe n_data_rd, the datapath can load it, and a bus
    write wins a coincident load (the documented exception to C1)."""
    await reset(dut)
    mask = writable_mask("N_DATA")
    await bus_write(dut, ADDR["N_ADDR"], 0x00000042)
    await bus_write(dut, ADDR["N_DATA"], 0xFFF31234)
    assert int(dut.n_data_wr.value) == 1, "n_data_wr did not strobe"
    assert int(dut.n_data.value) == 0xFFF31234 & mask, "wrong staged state"
    assert await rd(dut, "N_DATA") == 0xFFF31234 & mask
    assert int(dut.n_data_rd.value) == 1, "n_data_rd did not strobe on a read"

    dut.n_data_hw.value = 0x5ABCD
    await hw_pulse(dut, "n_data_ld")
    assert await rd(dut, "N_DATA") == 0x5ABCD, "hardware load did not land"

    dut.n_data_ld.value = 1                     # load racing a bus write
    dut.n_data_hw.value = 0x11111
    await bus_write(dut, ADDR["N_DATA"], 0x22222)
    dut.n_data_ld.value = 0
    await Timer(1, unit="ns")
    assert await rd(dut, "N_DATA") == 0x22222, "bus write lost the race"


# ----------------------------------------------------------------------
# Bus behavior
# ----------------------------------------------------------------------

@cocotb.test()
async def test_unmapped_and_misaligned_access(dut):
    """An unmapped offset reads 0x00000000 with bus_rsp_error; an unmapped
    write is flagged and changes no register. Misaligned addresses decode as
    unmapped because every mapped offset is word-aligned."""
    await reset(dut)
    gaps = unmapped_offsets()
    assert gaps, "the map now covers the whole window; pick new probes"
    probes = [gaps[0], gaps[len(gaps) // 2], gaps[-1]]
    probes += [ADDR["SCRATCH"] + 1, ADDR["SCRATCH"] + 2, ADDR["STATUS"] + 3]
    before = await snapshot(dut)
    for addr in probes:
        data, err = await bus_read(dut, addr)
        assert err == 1, f"unmapped read of 0x{addr:03X} not flagged"
        assert data == 0, f"unmapped read of 0x{addr:03X} returned 0x{data:08X}"
        err = await bus_write(dut, addr, ALL_ONES)
        assert err == 1, f"unmapped write to 0x{addr:03X} not flagged"
    after = await snapshot(dut)
    assert after == before, "an unmapped access disturbed the register file"


@cocotb.test()
async def test_response_beat_per_transaction(dut):
    """bus_rsp_valid is exactly one cycle per accepted transaction and never
    fires while the request channel is idle; back-to-back transactions
    stream one response per cycle with the right data."""
    await reset(dut)
    for _ in range(4):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert dut.bus_rsp_valid.value == 0, "response beat without a request"

    words = [(ADDR["SCRATCH"], 0x0BADC0DE), (ADDR["W_BASE"], 0x1000),
             (ADDR["PASS_ID"], 0x5A), (ADDR["NODE_ID"], 0x9)]
    dut.bus_req_valid.value = 1
    dut.bus_req_write.value = 1
    for addr, data in words:                     # back-to-back writes
        dut.bus_req_addr.value = addr
        dut.bus_req_wdata.value = data
        assert int(dut.bus_req_ready.value) == 1, "these offsets never stall"
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert dut.bus_rsp_valid.value == 1, "dropped a response beat"
    dut.bus_req_write.value = 0
    got = []
    for addr, _ in words:                        # back-to-back reads
        dut.bus_req_addr.value = addr
        assert int(dut.bus_req_ready.value) == 1, "these offsets never stall"
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert dut.bus_rsp_valid.value == 1, "dropped a response beat"
        got.append(int(dut.bus_rsp_rdata.value))
    dut.bus_req_valid.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert dut.bus_rsp_valid.value == 0, "response outlived the request stream"
    names = ("SCRATCH", "W_BASE", "PASS_ID", "NODE_ID")
    for beat, (name, (_, data)) in enumerate(zip(names, words)):
        want = data & writable_mask(name)
        assert got[beat] == want, (
            f"read beat {beat} ({name}): got 0x{got[beat]:08X}, "
            f"expected 0x{want:08X}")


@cocotb.test()
async def test_reset_mid_traffic(dut):
    """An asynchronous reset in the middle of bus traffic returns every
    register to its documented reset value and leaves the block working."""
    await reset(dut)
    for name, access in ACCESS.items():
        if access == "RW":
            await bus_write(dut, ADDR[name], ALL_ONES)
    await hw_pulse(dut, "hw_ded", hw_fault_addr=0x0000FACE)
    dut.bus_req_valid.value = 1
    dut.bus_req_write.value = 1
    dut.bus_req_addr.value = ADDR["SCRATCH"]
    dut.bus_req_wdata.value = ALL_ONES
    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")
    dut.rst_n.value = 0
    dut.bus_req_valid.value = 0
    dut.bus_req_write.value = 0
    await Timer(2, unit="ns")
    assert dut.bus_rsp_valid.value == 0, "reset must silence the response"
    for _ in range(2):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    want = reset_values(dut)
    for name in ADDR:
        got = await rd(dut, name)
        assert got == want[name], (
            f"{name} after reset: got 0x{got:08X}, expected 0x{want[name]:08X}")
    await bus_write(dut, ADDR["SCRATCH"], 0x5A5AA5A5)
    assert await rd(dut, "SCRATCH") == 0x5A5AA5A5, "block dead after reset"


@cocotb.test()
async def test_random_traffic_scoreboard(dut):
    """Randomized reads and writes across the whole 12-bit window against a
    Python model of the map built from regmap_gen: RW registers track their
    field-masked value, RO registers hold their reset value, WO and W1C
    ports read zero, unmapped offsets read zero and flag an error.

    Side-effect registers (CTRL's self-clearing bits, the weight commit
    port, the AER ports, the W1C ports and N_DATA's hardware load) are
    excluded from the write stream and covered by their own directed tests;
    they are still read and checked here."""
    await reset(dut)
    random.seed(20260825)
    plain_rw = [n for n, a in ACCESS.items()
                if a == "RW" and n not in SIDE_EFFECT]
    assert plain_rw, "no plain RW registers left to randomize"
    model = reset_values(dut)
    gaps = unmapped_offsets()

    for _ in range(1200):
        roll = random.random()
        if roll < 0.40:                                   # write a RW register
            name = random.choice(plain_rw)
            data = random.getrandbits(32)
            err = await bus_write(dut, ADDR[name], data)
            assert err == 0, f"mapped write to {name} flagged as unmapped"
            model[name] = data & writable_mask(name)
        elif roll < 0.90:                                 # read anything mapped
            name = random.choice(list(ADDR))
            got, err = await bus_read(dut, ADDR[name])
            assert err == 0, f"mapped read of {name} flagged as unmapped"
            assert got == model[name], (
                f"{name}: got 0x{got:08X}, expected 0x{model[name]:08X}")
        else:                                             # probe a gap
            addr = random.choice(gaps)
            got, err = await bus_read(dut, addr)
            assert err == 1 and got == 0, f"gap 0x{addr:03X} answered wrongly"
