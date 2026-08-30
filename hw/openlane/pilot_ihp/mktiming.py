#!/usr/bin/env python3
"""Derive the docs/28 timing-recovery variants from the 6x2 submission config.

The docs/27 re-harden left the slow-corner setup margin at +0.3229 ns,
1.61 % of a 20 ns cycle. docs/28 attributes that loss and then measures
what each recovery option is worth. Every option is one or two keys
changed against `config.6x2.json` and nothing else, so a difference in
any other sign-off number is itself a finding -- the same discipline
`mkconfig.py` applies to the shape and corner variants.

The variants are DERIVED here rather than hand-written for the reason
`mkconfig.py` gives: `config.6x2.json` is itself generated from
`tt/src/config_merged.json`, so a hand-edited variant would drift from
the submission's own geometry the moment the submission moved.

Every variant also carries SETUP_VIOLATION_CORNERS = ["*"]. That is not
a timing experiment, it is a sign-off hole. LibreLane resolves the setup
checker's corners as `SETUP_VIOLATION_CORNERS or TIMING_VIOLATION_CORNERS`
(librelane/steps/checker.py, `get_corner_wildcards`), the IHP PDK ships
TIMING_VIOLATION_CORNERS = ["*typ*"], and SETUP_VIOLATION_CORNERS is
unset -- so `Checker.SetupViolations` has only ever checked the TYPICAL
corner, while HOLD_VIOLATION_CORNERS is already ["*"]. The slow corner
this document is about is not gated by any checker in the baseline.
docs/23 records the mirror-image of exactly this: a hold violation that
`design__violations` did not aggregate. Raising it costs nothing when
the corner passes and fails the run when it does not, which is the
point.

Usage:
    ./mktiming.py            # write the five variants
    ./mktiming.py --check    # re-derive and diff against disk
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "config.6x2.json")

# The two ihp-sg13g2 corners that matter to setup. nom_typ_1p20V_25C is
# DEFAULT_CORNER and is kept first so the baseline behaviour is a subset,
# exactly as config.pnrcorners.json does it.
PNR_CORNERS = ["nom_typ_1p20V_25C", "nom_slow_1p08V_125C"]

VARIANTS = {
    # The control. One key against the submission config, and that key is
    # a checker rather than an optimisation, so this run must reproduce
    # docs/27 section 3 exactly. It is here for two reasons: to confirm
    # the setup checker passes at the slow corner once it is actually
    # looking at it, and to confirm docs/20 section 5.6's determinism
    # claim still holds for this RTL and this shape -- without which no
    # delta measured below is attributable to the key that was changed.
    "tr-control": (
        {},
        "docs/28 control: config.6x2.json plus the SETUP_VIOLATION_CORNERS "
        "sign-off fix and nothing else. Must reproduce docs/27 section 3.",
    ),
    # Trade area for delay at technology mapping. This is the option the
    # design's own budget argues for: docs/27 section 6 measures 32.53 %
    # spare core area against a 70 % criterion, and 0.3229 ns of setup
    # margin. AREA 0 is the LibreLane default and has never been varied
    # in this repository.
    "tr-delay0": (
        {"SYNTH_STRATEGY": "DELAY 0"},
        "docs/28: ABC mapped for delay rather than area. The design has "
        "32.53 % spare core and 1.61 % spare cycle, so this spends the "
        "abundant resource on the scarce one.",
    ),
    "tr-delay2": (
        {"SYNTH_STRATEGY": "DELAY 2"},
        "docs/28: a second point on the DELAY curve, because LibreLane's "
        "own SYNTH_STRATEGY documentation says there is no way to know "
        "which strategy is best without trying them.",
    ),
    # docs/18 section 3.3b named this and docs/20 section 6 ran it on
    # sky130, where it cut total negative slack 42 % and moved the worst
    # path 0.17 ns. It has never been run on IHP.
    "tr-postgrt": (
        {
            "PNR_CORNERS": PNR_CORNERS,
            "RUN_POST_GRT_DESIGN_REPAIR": 1,
            "RUN_POST_GRT_RESIZER_TIMING": 1,
        },
        "docs/28: the two post-global-routing repair steps, off by default "
        "and skipped in every run in this repository. PNR_CORNERS is set "
        "so the mid-PnR STA reports the slow corner, which is the "
        "observability docs/20 section 7 found to be its only real effect.",
    ),
    # docs/20 section 5.3(b) is the reason this is worth a run: it
    # established that PNR_CORNERS reaches placement but that placement
    # ignores it, because gpl.tcl gates -timing_driven on PL_TIMING_DRIVEN
    # and that is False. This turns the gate on.
    "tr-tdp": (
        {"PL_TIMING_DRIVEN": 1, "PNR_CORNERS": PNR_CORNERS},
        "docs/28: timing-driven global placement. docs/20 section 5.3(b) "
        "measured that PNR_CORNERS cannot help while PL_TIMING_DRIVEN is "
        "False, because gpl.tcl gates -timing_driven on it; this is the "
        "untested other half of that finding.",
    ),
    # The two levers above address different halves of the same problem
    # and are expected to compose. Measured on the critical cone at the
    # synthesised netlist: DELAY 0 takes it from 36 logic levels to 33,
    # but leaves every cell on it at minimum drive strength, because
    # SYNTH_SIZING and SYNTH_ABC_BUFFERING are both False. Nothing sizes
    # those cells until a resizer does, and the post-CTS resizer reports
    # RSZ-0098 "No setup violations found" because at that point, on
    # pre-route parasitics, there are none. The post-GRT resizer is the
    # first step in the flow that sees the corner and the congestion at
    # the same time.
    "tr-best": (
        {
            "SYNTH_STRATEGY": "DELAY 0",
            "PNR_CORNERS": PNR_CORNERS,
            "RUN_POST_GRT_DESIGN_REPAIR": 1,
            "RUN_POST_GRT_RESIZER_TIMING": 1,
        },
        "docs/28: fewer logic levels (DELAY 0) AND the sizing that only "
        "the post-global-routing resizer performs. The two address "
        "different halves of the path -- depth and drive strength -- so "
        "they are run together as well as separately. NOT RUN: tr-delay0 "
        "measured DELAY 0 at -4.0356 ns on the slow corner, 4.36 ns WORSE "
        "than the baseline, because it grows routed wirelength 44.8 %. "
        "Composing a lever worth -4.36 ns with one worth +0.85 ns has a "
        "predictable answer and the machine time was spent on tr-margin "
        "instead. Kept here so the variant that was considered is on "
        "record with the reason it was dropped.",
    ),
    # The decision-relevant follow-on to tr-postgrt. That run left the
    # post-GRT resizer at its default GRT_RESIZER_SETUP_SLACK_MARGIN of
    # 0.025 ns, and it stopped at +0.170 ns on its own internal estimate
    # with 9 gates resized and +0.1 % area -- i.e. it stopped because it
    # had met the margin it was asked for, not because it ran out of
    # moves. Asking for 0.5 ns instead measures how much more targeted
    # sizing is available and what it costs, which is exactly the number
    # the next hardening wave needs in order to be costed.
    "tr-margin": (
        {
            "PNR_CORNERS": PNR_CORNERS,
            "RUN_POST_GRT_DESIGN_REPAIR": 1,
            "RUN_POST_GRT_RESIZER_TIMING": 1,
            "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.5,
        },
        "docs/28: tr-postgrt with the post-GRT setup slack margin raised "
        "from the 0.025 ns default to 0.5 ns. Measures the headroom still "
        "in targeted sizing, and its area price.",
    ),
}

# ---------------------------------------------------------------------
# The sign-off configuration, derived from config.json rather than from
# config.6x2.json
# ---------------------------------------------------------------------
# The seven variants above are all derived from `config.6x2.json`, which
# was generated by `mkconfig.py` BEFORE two flow defects were fixed in
# `config.json`:
#
#   * `TIME_DERATING_CONSTRAINT: 5.0`. The PDK ships the integer 5 and
#     LibreLane's base.sdc consumes it with Tcl integer division, so
#     `expr 5 / 100` is 0 and the flow applied NO derate while logging
#     "5%". docs/28 section 4.4b. Written as a float, the division is
#     real and the late factor is 1.05.
#   * `SETUP_VIOLATION_CORNERS: ["*"]`. Both PDKs ship
#     `TIMING_VIOLATION_CORNERS: ["*typ*"]`, so with the key unset
#     `Checker.SetupViolations` gated the typical corner and nothing
#     else. docs/28 section 4.4a.
#
# `config.6x2.json` carries NEITHER, so a variant derived from it would
# harden without the derate and would gate setup at the typical corner
# only -- i.e. it would reproduce exactly the two defects docs/28
# reported. The sign-off variant is therefore derived from `config.json`,
# which carries both, and the four adopted timing keys are added on top.
#
# The four keys are docs/28 section 6.2's adopted set, verbatim. Nothing
# is added to buy margin: `PL_TIMING_DRIVEN` is worth +0.5856 ns on its
# own (docs/28 section 5.5) and is deliberately NOT here, because
# composing it with the post-GRT repair has never been hardened and
# docs/28 section 10 item 9 names that as the untested experiment. This
# document does not adopt a knob it has not measured either.
#
# Two decks are switched on that the submission config leaves off:
# RUN_KLAYOUT_DRC and RUN_KLAYOUT_XOR. Neither changes a layout bit --
# they are read-only decks over the streamed GDS -- and both are run by
# the Tiny Tapeout precheck, where a failure costs a resubmission round
# rather than half an hour of local machine time. docs/20 section 11 is
# the precedent for the DRC deck; the XOR has never been run in this
# repository at all, which is why it is here.
SIGNOFF_BASE = os.path.join(HERE, "config.json")
SIGNOFF = (
    "signoff-6x2",
    {
        "PNR_CORNERS": PNR_CORNERS,
        "RUN_POST_GRT_DESIGN_REPAIR": 1,
        "RUN_POST_GRT_RESIZER_TIMING": 1,
        "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.5,
        "RUN_KLAYOUT_DRC": 1,
        "RUN_KLAYOUT_XOR": 1,
    },
    "docs/31: the geometric sign-off of the docs/28 section 6.2 adopted "
    "timing configuration, on the RTL as of the run's pin commit. Derived "
    "from config.json and NOT from config.6x2.json, because only "
    "config.json carries TIME_DERATING_CONSTRAINT as a float and "
    "SETUP_VIOLATION_CORNERS = [\"*\"] -- the two defects docs/28 section "
    "4.4 reported. The four timing keys are docs/28 section 6.2 verbatim; "
    "PL_TIMING_DRIVEN is deliberately absent (docs/28 section 10 item 9). "
    "RUN_KLAYOUT_DRC and RUN_KLAYOUT_XOR are raised so the run produces "
    "the whole sign-off set, including the two decks the Tiny Tapeout "
    "precheck runs, in one pass.",
)


def derive(name):
    pairs = json.load(open(BASE), object_pairs_hook=list)
    keys, note = VARIANTS[name]
    out = [(k, v) for k, v in pairs if k != "//variant"]
    # The sign-off fix goes into every variant, including the control.
    out.append(("SETUP_VIOLATION_CORNERS", ["*"]))
    for k, v in keys.items():
        out.append((k, v))
    out.append(("//variant", note))
    return dict(out)


def derive_signoff():
    name, keys, note = SIGNOFF
    pairs = json.load(open(SIGNOFF_BASE), object_pairs_hook=list)
    out = [(k, v) for k, v in pairs if k != "//variant"]
    for k, v in keys.items():
        out.append((k, v))
    out.append(("//variant", note))
    cfg = dict(out)
    # Assert the two fixes really did come through the base, rather than
    # trusting that config.json still carries them. If mkconfig.py is ever
    # re-run it regenerates config.json from tt/src/config_merged.json,
    # which carries neither key, and this variant would silently go back
    # to hardening with no derate and a typical-corner-only setup gate --
    # the exact pair of defects it exists to close.
    if not isinstance(cfg.get("TIME_DERATING_CONSTRAINT"), float):
        raise SystemExit(
            f"{SIGNOFF_BASE} does not carry TIME_DERATING_CONSTRAINT as a "
            "float; the derate would be integer-divided to zero. See "
            "docs/28 section 4.4b.")
    if cfg.get("SETUP_VIOLATION_CORNERS") != ["*"]:
        raise SystemExit(
            f"{SIGNOFF_BASE} does not carry SETUP_VIOLATION_CORNERS = "
            '["*"]; setup would be gated at the typical corner only. See '
            "docs/28 section 4.4a.")
    return name, cfg


def main():
    check = "--check" in sys.argv
    bad = 0
    targets = {
        os.path.join(HERE, f"config.{n}.json"): derive(n) for n in VARIANTS
    }
    signoff_name, signoff_cfg = derive_signoff()
    targets[os.path.join(HERE, f"config.{signoff_name}.json")] = signoff_cfg
    for path, cfg in sorted(targets.items()):
        text = json.dumps(cfg, indent=2) + "\n"
        if check:
            have = open(path).read() if os.path.exists(path) else None
            if have != text:
                print(f"DRIFT: {path}")
                bad += 1
        else:
            with open(path, "w") as f:
                f.write(text)
            print(f"wrote {path}")
    if check:
        print(
            f"all {len(targets)} variants match" if not bad else f"{bad} drifted"
        )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
