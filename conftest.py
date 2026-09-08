# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Repository-root pytest configuration.

Several directories in this repository hold files named ``test_*.py``, and
only one of them is a pytest suite:

  * ``sw/tests/``  the golden-model suite. Plain pytest, runs anywhere the
    root virtualenv is available. THE one pytest tree.
  * ``hw/tb/``     cocotb test modules. They are loaded by the simulator
    process that ``hw/tb/Makefile`` and ``hw/tb/Makefile.<block>`` start;
    they import ``cocotb`` and talk to a live design handle, so pytest
    cannot execute them and must not try.
  * ``hw/soc/tb/`` the SoC fabric's cocotb modules, added with
    ``docs/39-soc-bus-and-memory-map.md``. Same situation as ``hw/tb/``:
    driven by ``hw/soc/tb/cocotb/Makefile.<block>`` inside the ``hw/.venv``
    environment, not by a bare pytest.
  * ``tt/``        a vendored third-party checkout with its own test suite
    and its own dependencies (klayout and friends), run by that project's
    tooling, not by ours.

The rule: everything except ``sw/tests/`` is driven by something other than
a bare ``pytest``, so it is listed in ``collect_ignore`` below. A tree added
later and not listed will abort collection loudly rather than fail
silently - that is the intended failure mode, and the fix is one line here.

``pytest.ini`` states the same rule from the other side, and the two are
complementary rather than redundant:

  * ``pytest.ini`` sets ``testpaths = sw/tests``. That is the positive,
    future-proof form - a sibling tree added later is out of scope on the
    day it is created, with no edit anywhere - but pytest consults
    ``testpaths`` only when it is invoked from the rootdir with no path
    arguments.
  * ``collect_ignore`` here is the negative form, and it is what covers
    the invocations ``testpaths`` does not see: an explicit ``pytest .``
    at the root, or ``pytest`` from a directory above ``sw/tests/`` that
    still contains ``hw/tb``. It costs one line per new tree, which is the
    price of covering those cases.

Neither replaces the other; drop either and one real invocation breaks.

Without this file a bare ``pytest`` at the repository root walks into
``hw/tb/`` and aborts collection for the whole repository, taking
``sw/tests/`` down with it. Two independent reasons, both real:

  * ``hw/tb/test_secded.py`` and ``sw/tests/test_secded.py`` share a module
    basename and neither directory was a package, so pytest's rootdir
    import mode reports an "import file mismatch" error for whichever it
    collects second;
  * the root virtualenv deliberately has no cocotb (docs/11 section 3.2
    keeps the two environments separate), so every ``hw/tb`` module also
    fails to import there.

Ignoring ``hw/tb`` at the root fixes both. ``sw/tests/__init__.py`` closes
the basename collision as well, so an explicit
``pytest hw/tb/... sw/tests/...`` in the cocotb virtualenv stays collectable
too.

This file adds no fixtures and no options: it exists only to keep the test
trees apart.
"""

# Paths are relative to this file's directory (the repository root).
collect_ignore = [
    "hw/tb",      # cocotb modules: simulator-loaded, need a design handle
    "hw/soc/tb",  # the SoC fabric's cocotb modules, same reason
    "tt",         # vendored third-party checkout with its own suite and deps
]
