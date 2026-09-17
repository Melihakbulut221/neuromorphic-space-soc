# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Make this directory importable, so tests can share one helper.

`sw/tests/evidence.py` resolves a run's recorded evidence, and more
than one test file needs it. pytest adds a test file's directory to
sys.path under rootdir-based import modes but not reliably under all of
them, and the suite is run three ways here: from the repository root,
from scripts/ci_local.sh, and from the checks workflow. This removes
the question.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
