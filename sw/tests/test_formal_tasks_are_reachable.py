# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Every SymbiYosys task is reachable from the formal Makefile.

WHY THIS GUARD EXISTS, AND IT IS THE SECOND TIME. A property set that
no target runs is worse than one that does not exist: a sweep of the
directory reports the design proved, and the proof it did not run is
the one somebody added because they were unsure. It has happened twice
in two days. `clkgate_wake_gnt.sby` was committed and passing on
2026-09-15 with no target at all, so `make -C hw/soc/formal` would
never have elaborated the parameter it exists for. `soc_bus.sby` gained
three `_rr` tasks on 2026-09-16 carrying `REQ_REG = 1`, and the `bus`
target ran the three original ones, so the fabric's contract was being
proved at one setting of a parameter the same commit offered at two.

THE PROPERTY, not the name: every task named in every `.sby` file's
`[tasks]` section appears somewhere in the Makefile, either as a bare
word in a task list or in the target that runs that job. A job may opt
out DELIBERATELY, and `regfile_scrub.sby` does -- every engine stalls
on the codec's parity network and a target that never returns is not a
regression test -- so the opt-out is declared here, in one place, with
its reason, rather than being the silent default for anything anyone
forgets.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
FORMAL = ROOT / "hw" / "soc" / "formal"

# Jobs deliberately outside the sweep, with the reason they are out.
OPTED_OUT = {
    "regfile_scrub.sby":
        "docs/63 section 23: every engine stalls at step 4 on the real "
        "codec's parity network, two of them TIMEOUT at 10,800 s. The "
        "abstracted job regfile_scrub_abs.sby is the one in the sweep.",
}

# Individual tasks outside the sweep, with the reason each is out. A
# task belongs here when it is kept for the record rather than for the
# gate -- a measurement of what an engine could not do is worth keeping
# in the .sby and is not worth failing a sweep over.
TASK_OPTED_OUT = {
    ("regfile_scrub_abs.sby", "prove12"):
        "docs/63 section 23: k-induction at depth 12 returned "
        "DONE (UNKNOWN, rc=4) -- it neither proved nor refuted. The "
        "unbounded proof is prove_pdr, which closes in 44 s and is what "
        "the sweep runs.",
}


def _tasks(sby_text):
    """Task names from a [tasks] section. A line may carry groups after
    the name -- 'bmc          sound' is task bmc in group sound -- so the
    task is the first token and the rest is not one."""
    m = re.search(r"(?m)^\[tasks\]\s*$(.*?)(?=^\[|\Z)", sby_text, re.S)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line.split()[0])
    return out


def test_every_formal_task_is_reachable_from_the_makefile():
    mk = (FORMAL / "Makefile").read_text()
    unreachable = []
    for sby in sorted(FORMAL.glob("*.sby")):
        if sby.name in OPTED_OUT:
            assert "-f %s " % sby.name not in mk, (
                "{} is listed as deliberately out of the sweep but the "
                "Makefile runs it; remove it from OPTED_OUT or from the "
                "Makefile".format(sby.name))
            continue
        if "-f %s " % sby.name not in mk:
            unreachable.append("%s: no target runs this job" % sby.name)
            continue
        for task in _tasks(sby.read_text()):
            if (sby.name, task) in TASK_OPTED_OUT:
                continue
            if not re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(task), mk):
                unreachable.append("%s: task %s is in no task list"
                                   % (sby.name, task))
    assert not unreachable, (
        "these SymbiYosys tasks cannot be reached from "
        "hw/soc/formal/Makefile, so a sweep reports the design proved "
        "without running them: {}".format(unreachable))


def test_the_default_target_runs_every_reachable_job():
    """`all` is what a sweep means; a target outside it is a target
    nobody runs by accident."""
    mk = (FORMAL / "Makefile").read_text()
    m = re.search(r"(?m)^all:(.*)$", mk)
    assert m, "the formal Makefile has no all target"
    in_all = set(m.group(1).split())
    targets = set(re.findall(r"(?m)^([a-z][a-z0-9_]*):", mk))
    # Targets that are machinery rather than jobs.
    machinery = {"all", "clean", "wdog_tmr_params", "boot_tmr_params"}
    missing = sorted(t for t in targets - machinery - in_all)
    assert not missing, (
        "these formal targets exist but are not in `all`: {}".format(missing))
