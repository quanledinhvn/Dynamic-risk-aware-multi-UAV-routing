"""Behavioral checks for destroy--repair pair selection and statistics."""

import numpy as np
import pytest

from uav_routing.contextual import ContextualBanditConfig
from uav_routing.contextual.selector import OperatorPairSelector, PairSelectionStats


def _selector(**overrides):
    arguments = {
        "destroy_names": ("random", "worst"),
        "repair_names": ("greedy", "regret2"),
        "config": ContextualBanditConfig(linucb_exploration=0.0),
        "maximum_raw_reward": 8.0,
        "rng": np.random.default_rng(7),
    }
    arguments.update(overrides)

    return OperatorPairSelector(**arguments)


def _context():
    return np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])


def test_arms_have_destroy_major_cartesian_order_and_pair_identity():
    selector = _selector()

    assert selector.arms == (
        ("random", "greedy"),
        ("random", "regret2"),
        ("worst", "greedy"),
        ("worst", "regret2"),
    )
    assert ["+".join(arm) for arm in selector.arms] == [
        "random+greedy",
        "random+regret2",
        "worst+greedy",
        "worst+regret2",
    ]


@pytest.mark.parametrize(
    ("field", "names"),
    [
        ("destroy_names", ()),
        ("repair_names", ()),
        ("destroy_names", ("same", "same")),
        ("repair_names", ("same", "same")),
        ("destroy_names", ("",)),
        ("repair_names", ("  ",)),
    ],
)
def test_constructor_rejects_empty_duplicate_or_blank_names(field, names):
    with pytest.raises(ValueError, match=field):
        _selector(**{field: names})


@pytest.mark.parametrize("maximum", [0.0, -1.0, float("inf"), float("nan")])
def test_constructor_rejects_invalid_maximum_raw_reward(maximum):
    with pytest.raises(ValueError, match="maximum_raw_reward"):
        _selector(maximum_raw_reward=maximum)


def test_selection_delegates_to_bandit_and_learns_pair_preference():
    selector = _selector(repair_names=("greedy",))
    context = _context()
    selector.record(("worst", "greedy"), context, 8.0)

    assert selector.select(context) == ("worst", "greedy")


def test_record_normalizes_bandit_reward_and_updates_only_selected_arm():
    selector = _selector()
    context = _context()
    selector.record(("random", "regret2"), context, 4.0)

    selected = selector._bandit.state(("random", "regret2"))
    untouched = selector._bandit.state(("random", "greedy"))
    np.testing.assert_array_equal(selected.reward_vector, [0.5] + [0.0] * 8)
    np.testing.assert_array_equal(untouched.reward_vector, [0.0] * 9)
    np.testing.assert_array_equal(untouched.matrix, np.eye(9))


def test_snapshot_tracks_raw_total_average_and_zero_use_arms_in_order():
    selector = _selector()
    context = _context()
    initial = selector.snapshot()
    selector.record(("random", "regret2"), context, 4.0)
    selector.record(("random", "regret2"), context, 8.0)

    assert selector.snapshot() == (
        PairSelectionStats("random", "greedy", 0, 0.0, 0.0),
        PairSelectionStats("random", "regret2", 2, 12.0, 6.0),
        PairSelectionStats("worst", "greedy", 0, 0.0, 0.0),
        PairSelectionStats("worst", "regret2", 0, 0.0, 0.0),
    )
    assert initial == tuple(
        PairSelectionStats(*arm, 0, 0.0, 0.0) for arm in selector.arms
    )


@pytest.mark.parametrize("reward", [-1.0, float("inf"), float("nan")])
def test_record_rejects_negative_or_nonfinite_raw_reward_without_changes(reward):
    selector = _selector()
    before = selector._bandit.state(("random", "greedy"))

    with pytest.raises(ValueError, match="raw_reward"):
        selector.record(("random", "greedy"), _context(), reward)

    np.testing.assert_array_equal(
        selector._bandit.state(("random", "greedy")).matrix, before.matrix
    )
    assert selector.snapshot()[0].total_uses == 0


def test_record_rejects_unknown_arm_without_changes():
    selector = _selector()

    with pytest.raises(ValueError, match="arm"):
        selector.record(("missing", "greedy"), _context(), 1.0)

    assert all(stats.total_uses == 0 for stats in selector.snapshot())


@pytest.mark.parametrize("method", ["select", "record"])
def test_invalid_context_is_rejected_at_bandit_boundary(method):
    selector = _selector()
    bad_context = np.full(9, float("nan"))

    with pytest.raises(ValueError, match="context"):
        if method == "select":
            selector.select(bad_context)
        else:
            selector.record(("random", "greedy"), bad_context, 1.0)

    assert all(stats.total_uses == 0 for stats in selector.snapshot())


def test_five_destroy_and_three_repair_names_make_fifteen_arms():
    selector = _selector(
        destroy_names=("random", "worst", "related", "route", "risk_priority"),
        repair_names=("greedy", "regret2", "risk_priority"),
    )

    assert len(selector.arms) == 15
    assert selector.arms[0] == ("random", "greedy")
    assert selector.arms[-1] == ("risk_priority", "risk_priority")
