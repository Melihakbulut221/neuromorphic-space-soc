#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Cross-check the any-state recovery theorem against the injections.

    scripts/formal_fi_crosscheck.py

`docs/09` target #5 is the FSM any-state recovery template, and its
acceptance criterion says the formal result and the force/release
campaign "must agree", with any disagreement a blocker at gate F3.
Nothing compared them. `docs/35` calls this the largest piece of
unclaimed ground reachable without new RTL, and it sits across `hw/tb/`
and `formal/`, which is why neither pass owned it.

WHAT THE THEOREM SAYS. `formal/lif_ctrl.sby`'s `bmc_safe` task starts a
trace from an ILLEGAL state encoding and proves the design reaches the
SAFE state. Its own header records why that task is not redundant with
`prove`: the inductive invariant "the encoding is always legal" makes
the recovery antecedent unreachable in the induction step, so `prove`
cannot check it, and a default arm that resumed in IDLE would pass
`prove` and fail here.

WHAT THE CAMPAIGN SAYS. Injecting into `u_lif.state` corrupts exactly
that encoding. So every `lif_fsm` record is an empirical instance of the
theorem's antecedent, and the theorem forbids one outcome: silent data
corruption. An injection that leaves the FSM producing wrong output
without reporting is a state the proof says cannot persist.

WHAT THIS DOES NOT DO, and it is half the item. It compares the
theorem's PREDICTION with the campaign's OUTCOMES. It does not re-run
the proof, and it does not check that the netlist the campaign injected
into is the one the proof elaborated -- the gate-level arm injects into
`u_pilot.u_lif.state[*]` of a placed netlist and the proof elaborates
RTL. Closing that half means an equivalence obligation between the two,
which `docs/09` gate F3 also asks for and which this script does not
supply.
"""
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARMS = [("gate-level", ROOT / "hw" / "tb" / "gl_fi_results_signoff-6x2.json"),
        ("register-transfer", ROOT / "hw" / "tb" / "fi_campaign_results.json")]

# The group whose records are injections into the FSM state encoding the
# theorem is about.
GROUP = "lif_fsm"

# The theorem forbids exactly one outcome class. MASKED, DETECTED and
# CORRECTED are all consistent with reaching SAFE; SDC is not, because a
# design that silently produces wrong output has not recovered.
FORBIDDEN = {"SDC"}


def main():
    bad, total, report = [], 0, []
    for tag, path in ARMS:
        if not path.is_file():
            report.append("  {:18s} MISSING {}".format(tag, path.name))
            continue
        data = json.loads(path.read_text())
        inj = [i for i in data.get("injections", [])
               if i.get("group") == GROUP]
        if not inj:
            report.append("  {:18s} no {} records -- the campaign no "
                          "longer covers the FSM this theorem is about"
                          .format(tag, GROUP))
            bad.append(tag)
            continue
        classes = collections.Counter(i.get("class") for i in inj)
        total += len(inj)
        viol = [i for i in inj if i.get("class") in FORBIDDEN]
        report.append("  {:18s} {:3d} injections  {}".format(
            tag, len(inj), dict(classes)))
        if viol:
            bad.append(tag)
            for v in viol[:5]:
                report.append("      DISAGREEMENT  net={} class={}".format(
                    v.get("net"), v.get("class")))

    print("formal/lif_ctrl.sby bmc_safe  vs  the {} injections".format(GROUP))
    print("the theorem: from an illegal state encoding, SAFE is reached")
    print("so the campaign must contain no {} in this group\n"
          .format("/".join(sorted(FORBIDDEN))))
    print("\n".join(report))
    print("\n{} injections compared across {} arms".format(total, len(ARMS)))

    if bad:
        print("\nDISAGREEMENT in: {}. docs/09 gate F3 calls this a "
              "blocker.".format(", ".join(bad)))
        return 1
    print("\nAGREE. Every injection into the FSM encoding ends in a class "
          "the theorem permits.")
    print("NOT CHECKED, and it is half of target #5: that the netlist the "
          "gate-level arm injected into is the one the proof elaborated. "
          "That is an equivalence obligation, not a comparison.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
