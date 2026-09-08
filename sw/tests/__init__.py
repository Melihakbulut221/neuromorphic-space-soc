# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Package marker for the golden-model pytest suite.

This file is not here for imports - every module in this directory is
collected by pytest, not imported by name. It is here so that the modules
of this directory are imported as ``tests.<module>`` rather than as bare
top-level modules.

Reason: ``hw/tb/`` holds cocotb test modules with the same basenames
(``test_secded.py`` is in both trees). Without a package marker pytest maps
both files to the single top-level module name ``test_secded`` and aborts
the whole collection with "import file mismatch" as soon as it sees the
second one. ``hw/tb/`` cannot take the same treatment: cocotb loads those
files by bare module name (``MODULE=test_secded``), so that directory has
to stay a plain directory.

The repository-root ``conftest.py`` keeps a bare ``pytest`` out of
``hw/tb/`` in the first place; this marker makes the two trees coexist even
when both are named explicitly on one command line.
"""
