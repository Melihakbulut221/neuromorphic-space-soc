# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Where the TMR replicas sit on the die, and the fact that nothing put
them anywhere in particular.

`test_synthesis_guards.py` asserts three banks of 55 flip-flops in the
mapped netlist. That is a statement about the netlist. This file is the
statement about the die, and it does not say what a reader might expect.

**The replicas are not placement-separated, and these tests record that
rather than demand it.** A test asserting a minimum separation would
fail on the frozen design, which cannot change before the shuttle; a
test asserting nothing would leave the corpus's strongest published
claim resting on a measurement nobody re-runs. So these pin the measured
values. If a future layout separates the banks, these fail and the
document that reports them has to be rewritten -- which is the correct
outcome, because the claim would have changed.

`docs/79` is the finding. `hw/openlane/replica_placement.py` is the
instrument.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hw" / "openlane"))

RUN = ROOT / "hw" / "openlane" / "pilot_ihp" / "runs" / "signoff-6x2"
REPLICAS = ["u_pilot.u_cfg_a", "u_pilot.u_cfg_b", "u_pilot.u_cfg_c"]

pytestmark = pytest.mark.skipif(
    not (RUN / "final" / "def").is_dir(),
    reason="the sign-off run tree is gitignored build output; this measures a "
           "layout, and without the layout there is nothing to measure")


@pytest.fixture(scope="module")
def measured():
    import replica_placement
    return replica_placement.measure(RUN, REPLICAS)


def test_the_attribution_reproduces_the_synthesis_guard(measured):
    """The placement measurement must be counting the same flip-flops the
    netlist census counts, or it is measuring something else.

    This is the join between the two instruments. `docs/33`'s census
    reads 55/55/55 on this netlist; if this reads anything else, the DEF
    and the netlist have come apart and no number below means anything.
    """
    assert measured["flops_per_replica"] == {r: 55 for r in REPLICAS}, (
        "placement attribution disagrees with the synthesis census: "
        + repr(measured["flops_per_replica"]))


def test_the_replicas_are_not_separated_on_the_die(measured):
    """Measured 2026-09-09 on `signoff-6x2`, the frozen sign-off layout.

    Cell bounding boxes touch. Nothing in the flow asked for separation
    and none was requested, so this is what the placer does when left to
    minimise wirelength to a shared voter: it pulls the three copies of
    each bit together.
    """
    assert measured["min_c2c_um"] == pytest.approx(3.78, abs=0.01), (
        "minimum cross-replica centre-to-centre distance moved from "
        "3.78 um; docs/79 reports 3.78 and must be re-read")
    assert measured["min_edge_um"] == pytest.approx(0.0, abs=1e-6), (
        "cross-replica cells no longer abut; docs/79's central measurement "
        "has changed")
    assert measured["abutting_pairs"] == 49, (
        "the number of abutting cross-replica pairs moved from 49 to "
        f"{measured['abutting_pairs']}")


def test_the_banks_are_not_segregated(measured):
    """103 of 165 nearest neighbours are in another replica -- AND THAT
    NUMBER MEANS NOTHING WITHOUT ITS BASELINE.

    REWRITTEN 2026-09-09. This test was called
    `test_most_flops_neighbour_a_different_replica` and its docstring
    called 103 "the sharpest single number, because it needs no
    threshold". It needs a baseline, which is not the same as a
    threshold, and it did not have one.

    Shuffling only the replica LABELS over the same 165 placed positions,
    preserving the 55/55/55 partition, gives 110.73 +/- 8.26 over 200
    permutations, against an analytic expectation of 110.67. The observed
    103 is **0.94 standard deviations BELOW chance**.

    So the statistic does not say the placer drew replicas together. It
    says the three banks are interleaved to the point of being
    indistinguishable from an arbitrary assignment of replica labels to
    these positions. Three separated banks would give a value near zero,
    many standard deviations away, and that is what this test would
    catch.
    """
    assert measured["nearest_is_another_replica"] == 103
    assert measured["nearest_is_own_replica"] == 62
    assert measured["nearest_other_null_analytic"] == pytest.approx(110.67,
                                                                    abs=0.01)
    assert abs(measured["nearest_other_sigma_from_chance"]) < 2.0, (
        "the observed value has moved more than two standard deviations "
        "from chance; docs/79 reports it as indistinguishable and would "
        "have to be rewritten")


def test_corresponding_bits_are_concentrated(measured):
    """This is the measurement of the mechanism, and it is a ratio.

    A shared voter ties the three copies of one bit together, so if
    wirelength minimisation is what co-locates them the effect should
    appear on CORRESPONDING bits and not on cross-replica pairs at
    large. It does: the median over all 9,075 cross-replica pairs is
    113.47 um and over corresponding-bit pairs 27.52 um, 4.1 times
    closer.

    The tool has printed both since it was written. The document quoted
    the mechanism in bold and omitted the ratio that evidences it.
    """
    ratio = measured["median_c2c_um"] / measured["same_bit_median_c2c_um"]
    assert ratio == pytest.approx(4.12, abs=0.05), (
        "the corresponding-bit concentration moved from 4.12x; docs/79 "
        "section 1.3 rests on it")


def test_the_corresponding_bit_figures_are_declared_a_lower_bound(measured):
    """15 of replica C's flip-flops cannot be attributed to a bit.

    C is instantiated with `MIX = 1` so that it stores a transform of the
    value rather than the value, which is what stops the synthesiser
    merging it with A and B (`docs/33`). The same transform means its
    `bits[]` nets may be optimised away, so the corresponding-bit
    statistics undercount. The tool says so; this asserts it keeps
    saying so, because a lower bound quoted as a measurement is exactly
    the failure this project keeps finding in itself.
    """
    assert measured["unindexed_per_replica"], (
        "the tool now attributes every flip-flop to a bit. If that is real, "
        "the lower-bound caveat in docs/79 and in the tool must be removed "
        "rather than left standing")
    assert sum(measured["unindexed_per_replica"].values()) == 15
