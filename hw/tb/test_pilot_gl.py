# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Gate-level rerun of the pilot bring-up suite, on the hardened netlist.

This module contains no tests of its own. It re-exports the tests in
`test_pilot_top` that drive the design *only* through the Tiny Tapeout
port list, and withholds the ones that reach into the RTL hierarchy,
because the submission netlist is elaborated with
`SYNTH_HIERARCHY_MODE: deferred_flatten` and has exactly one module in
it: there is no `dut.u_pilot` to deposit into, and no `u_lif.state` to
upset. cocotb discovers tests by scanning `vars(module)` for `Test`
objects, so an imported test is a real test and runs unmodified against
whatever `COCOTB_TOPLEVEL` names.

**The partition is derived, not hand-written.** A hand-maintained skip
list is exactly the failure this run exists to catch: it goes stale
silently, and a gate-level suite that quietly stops covering half the
design is worth less than no gate-level suite at all, because it reads
as evidence. So the split is computed here by parsing
`test_pilot_top.py` and asking, for every test and transitively for
every module-level helper it calls, whether any `dut.<attr>` access
names something that is not a port of the Tiny Tapeout wrapper. A test
that grows a hierarchical reference tomorrow leaves the gate-level set
tomorrow, and the count in the log changes with it.

Nothing in `test_pilot_top.py` is modified or monkey-patched. The two
suites run the same code; only the sources under the simulator differ.

Run: cd hw/tb && make -f Makefile.gl
"""

import ast
import inspect
import os
import sys
from pathlib import Path

import cocotb  # noqa: F401  (imported first: see below)
import cocotb.handle  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_pilot_top as rtl_suite  # noqa: E402

# `cocotb.regression` re-exports `Test` but pulls in `cocotb.handle`, and
# importing it as the very first cocotb submodule trips a circular
# import in cocotb 2.0.1 outside a running simulator. Importing
# `cocotb.handle` first makes this module importable by a plain
# interpreter as well as by the simulator, which is what lets the
# partition below be inspected without starting a run.
from cocotb.regression import Test  # noqa: E402

# The Tiny Tapeout wrapper's entire port list (hw/rtl/
# tt_um_melihakbulut_nssoc.v), plus cocotb's own logger handle. Anything
# else reached off `dut` is below the top level and therefore does not
# survive the flatten.
TT_PORTS = frozenset(
    {
        "clk",
        "rst_n",
        "ena",
        "ui_in",
        "uio_in",
        "uo_out",
        "uio_out",
        "uio_oe",
        "_log",
    }
)

_SUITE_PATH = Path(inspect.getsourcefile(rtl_suite)).resolve()
_TREE = ast.parse(_SUITE_PATH.read_text(), filename=str(_SUITE_PATH))
_TOP_LEVEL_FUNCS = {
    node.name: node
    for node in _TREE.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}


def _chain(node):
    """`dut.u_pilot.u_lif.state` -> ["dut", "u_pilot", "u_lif", "state"].

    Returns None for anything not rooted in a bare name.
    """
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return list(reversed(parts))


def _direct_hierarchy_refs(node):
    """Every `dut.<attr>...` in this function that is not a wrapper port.

    Reported as the longest dotted path written in the source, so the
    log says *what* the test reaches for -- `dut.u_pilot.u_lif.state`,
    not merely "u_pilot" -- and a reader can check the claim that the
    thing named does not survive the flatten.
    """
    chains = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute):
            c = _chain(sub)
            if c and c[0] == "dut" and len(c) > 1 and c[1] not in TT_PORTS:
                chains.append(c)
    found = set()
    for c in chains:
        # keep only the maximal chains; `.value` is cocotb's accessor and
        # is not part of the hierarchical path
        if any(other[: len(c)] == c and len(other) > len(c) for other in chains):
            continue
        if c[-1] == "value":
            c = c[:-1]
        found.add(f"{node.name}: {'.'.join(c)}")
    return found


def _called_names(node):
    """Module-level helper functions this function calls, by name.

    Only bare `f(...)` and `await f(...)` forms are resolved; that is
    every helper in `test_pilot_top.py`, and a name that does not
    resolve to a module-level function here is simply not followed.
    """
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            if sub.func.id in _TOP_LEVEL_FUNCS:
                names.add(sub.func.id)
    return names


def _hierarchy_reach(func_name, _seen=None):
    """Transitive closure of `_direct_hierarchy_refs` over the callees.

    `_fill_output_queue` polls `dut.u_pilot.fo_full`, and three tests
    reach the hierarchy only through it. Following calls is what keeps
    those three out of the gate-level set instead of letting them fail
    for a reason the log would not explain.
    """
    if _seen is None:
        _seen = set()
    if func_name in _seen or func_name not in _TOP_LEVEL_FUNCS:
        return set()
    _seen.add(func_name)
    node = _TOP_LEVEL_FUNCS[func_name]
    refs = _direct_hierarchy_refs(node)
    for callee in _called_names(node):
        refs |= _hierarchy_reach(callee, _seen)
    return refs


# ---------------------------------------------------------------------
# Optional preamble: write the weight memory before anything else
# ---------------------------------------------------------------------
# Off by default, and the default is the honest one.
#
# `lif_core`'s 256-entry synapse memory `wmem` has no reset -- resetting
# it would cost 256 flip-flops' worth of reset routing for no functional
# gain -- so before the first weight write it holds x in ANY simulation.
# RTL Verilog hides that: `if (x)` takes the else branch, so an unknown
# never reaches a register through a conditional. A gate netlist has no
# such rule; the synthesised mux and comparator trees carry the x
# through, and in `test_axon_out_of_range_is_dropped_and_counted` -- the
# one test in the port-driven set that enables the core without writing
# any weights first -- it reaches `fo_wr_en`, then the EVQ_OUT pointer
# bank, and STATUS.OUT_EMPTY reads 0 forever.
#
# That is X-pessimism against X-optimism, not a netlist defect: docs/24
# section 6 shows the same test agreeing to the nanosecond on both sides
# as soon as the weight memory is written first. Setting GL_PRELOAD=1
# writes it, at the cost of one extra test in the count and of a
# gate-level run that no longer reproduces the finding.
if os.environ.get("GL_PRELOAD", "0") == "1":

    @cocotb.test()
    async def test_gl_preload_weight_memory(dut):
        """Write wmem through the serial port, so no later test reads x.

        Purely a precondition. It asserts nothing about the design; if it
        fails, the serial port or the weight loader is broken and every
        later result is meaningless anyway.
        """
        p = await rtl_suite.reset(dut)
        n_neurons, n_axons = await rtl_suite.geometry(p)
        zeros = [[0] * n_neurons for _ in range(n_axons)]
        await rtl_suite.load_weights(p, zeros, n_neurons)
        dut._log.info(
            f"GL_PRELOAD: wrote {n_axons}x{n_neurons} zero weights; "
            "wmem is now defined for every test that follows"
        )


GATE_LEVEL = {}   # test name -> Test object, exported into this module
RTL_ONLY = {}     # test name -> sorted list of the references that excluded it

for _obj in list(vars(rtl_suite).values()):
    if not isinstance(_obj, Test):
        continue
    _name = _obj.func.__name__
    _refs = _hierarchy_reach(_name)
    if _refs:
        RTL_ONLY[_name] = sorted(_refs)
    else:
        GATE_LEVEL[_name] = _obj
        globals()[_name] = _obj

# cocotb discovers tests with `vars(module)`, so ANY module-level name
# bound to a Test is a test. The loop variable is one: leaving `_obj`
# bound leaks whichever test happened to be last out of
# `vars(test_pilot_top)` back into the regression, RTL-only or not. The
# first run of this file did exactly that and executed 21 tests instead
# of 20, the extra one being an RTL-only test that then failed on a
# hierarchical reference. Delete the bindings.
for _leak in ("_obj", "_name", "_refs"):
    globals().pop(_leak, None)
del _leak

# Fail loudly rather than run an empty regression: cocotb would raise on
# an empty module anyway, but the message would not say why.
if not GATE_LEVEL:
    raise RuntimeError(
        "no port-driven tests were found in test_pilot_top; the gate-level "
        "partition is broken, not the design"
    )

_lines = [
    "",
    "gate-level partition of test_pilot_top (derived by AST, not hand-listed)",
    f"  netlist         : {os.environ.get('GL_NETLIST', '<unset>')}",
    f"  cell models     : {os.environ.get('GL_CELLS', '<unset>')}",
    f"  run at gate level: {len(GATE_LEVEL)}",
    f"  RTL-only        : {len(RTL_ONLY)}",
    f"  GL_PRELOAD      : {os.environ.get('GL_PRELOAD', '0')}",
]
for _n in sorted(RTL_ONLY):
    _lines.append(f"    {_n}")
    for _r in RTL_ONLY[_n]:
        _lines.append(f"        reaches {_r}")
_lines.append("")
print("\n".join(_lines), flush=True)
