"""Behavioral checks for the independent LinUCB arm models."""

import numpy as np
import pytest

from uav_routing.contextual.linucb import DisjointLinUCB


def _bandit(**overrides):
    arguments = {
        "arms": ("first", "second"),
        "dimension": 2,
        "exploration": 0.5,
        "regularization": 2.0,
        "rng": np.random.default_rng(7),
    }
    arguments.update(overrides)

    return DisjointLinUCB(**arguments)


@pytest.mark.parametrize("arms", [(), ("same", "same")])
def test_constructor_rejects_empty_or_duplicate_arms(arms):
    with pytest.raises(ValueError, match="arms"):
        _bandit(arms=arms)


@pytest.mark.parametrize("dimension", [0, -1, True, False, 1.5, "2"])
def test_constructor_rejects_nonpositive_or_noninteger_dimension(dimension):
    with pytest.raises(ValueError, match="dimension"):
        _bandit(dimension=dimension)


@pytest.mark.parametrize("exploration", [-0.1, float("inf"), float("nan")])
def test_constructor_rejects_invalid_exploration(exploration):
    with pytest.raises(ValueError, match="exploration"):
        _bandit(exploration=exploration)


@pytest.mark.parametrize("regularization", [0.0, -1.0, float("inf"), float("nan")])
def test_constructor_rejects_invalid_regularization(regularization):
    with pytest.raises(ValueError, match="regularization"):
        _bandit(regularization=regularization)


def test_constructor_initializes_independent_regularized_arm_states():
    bandit = _bandit()

    for arm in ("first", "second"):
        state = bandit.state(arm)
        np.testing.assert_array_equal(state.matrix, [[2.0, 0.0], [0.0, 2.0]])
        np.testing.assert_array_equal(state.reward_vector, [0.0, 0.0])


def test_state_returns_copies_that_cannot_change_the_bandit():
    bandit = _bandit()
    snapshot = bandit.state("first")
    snapshot.matrix[0, 0] = 99.0
    snapshot.reward_vector[0] = 99.0

    current = bandit.state("first")
    np.testing.assert_array_equal(current.matrix, [[2.0, 0.0], [0.0, 2.0]])
    np.testing.assert_array_equal(current.reward_vector, [0.0, 0.0])


@pytest.mark.parametrize("method", ["state", "update"])
def test_unknown_arm_is_rejected(method):
    bandit = _bandit()

    with pytest.raises(ValueError, match="arm"):
        if method == "state":
            bandit.state("missing")
        else:
            bandit.update("missing", np.array([1.0, 0.0]), 1.0)


@pytest.mark.parametrize("context", [np.array([1.0]), np.array([[1.0, 0.0]])])
@pytest.mark.parametrize("method", ["select", "update"])
def test_context_must_be_one_dimensional_with_expected_length(context, method):
    bandit = _bandit()

    with pytest.raises(ValueError, match="context"):
        if method == "select":
            bandit.select(context)
        else:
            bandit.update("first", context, 1.0)


@pytest.mark.parametrize("method", ["select", "update"])
def test_context_must_be_finite(method):
    bandit = _bandit()
    context = np.array([1.0, float("nan")])

    with pytest.raises(ValueError, match="context"):
        if method == "select":
            bandit.select(context)
        else:
            bandit.update("first", context, 1.0)


@pytest.mark.parametrize("reward", [float("inf"), float("-inf"), float("nan")])
def test_reward_must_be_finite(reward):
    bandit = _bandit()

    with pytest.raises(ValueError, match="reward"):
        bandit.update("first", np.array([1.0, 0.0]), reward)


def test_selection_prefers_higher_estimated_reward_without_exploration():
    bandit = _bandit(dimension=1, exploration=0.0, regularization=1.0)
    bandit.update("second", np.array([1.0]), 2.0)

    assert bandit.select(np.array([1.0])) == "second"


def test_selection_prefers_uncertain_arm_when_estimated_rewards_tie():
    bandit = _bandit(dimension=1, exploration=1.0, regularization=1.0)
    bandit.update("first", np.array([1.0]), 0.0)

    assert bandit.select(np.array([1.0])) == "second"


def test_selection_uses_full_two_dimensional_linear_system():
    bandit = _bandit(exploration=1.0, regularization=1.0)
    bandit.update("first", np.array([1.0, 1.0]), 0.0)
    bandit.update("second", np.array([1.0, 0.0]), 0.0)

    # At x=(1, 0), A_first^-1 gives variance 2/3; A_second^-1 gives 1/2.
    assert bandit.select(np.array([1.0, 0.0])) == "first"

    # At x=(0, 1), the correlated first arm has variance 2/3 versus 1.
    assert bandit.select(np.array([0.0, 1.0])) == "second"


def test_update_changes_only_selected_arm_by_outer_product_and_reward():
    bandit = _bandit(regularization=1.0)
    bandit.update("first", np.array([2.0, 3.0]), 0.5)
    bandit.update("first", np.array([-1.0, 1.0]), -1.0)

    first = bandit.state("first")
    second = bandit.state("second")
    np.testing.assert_array_equal(first.matrix, [[6.0, 5.0], [5.0, 11.0]])
    np.testing.assert_array_equal(first.reward_vector, [2.0, 0.5])

    np.testing.assert_array_equal(second.matrix, [[1.0, 0.0], [0.0, 1.0]])
    np.testing.assert_array_equal(second.reward_vector, [0.0, 0.0])


def test_equal_scores_are_broken_by_injected_rng_reproducibly():
    arms = ("first", "second", "third")
    first = _bandit(arms=arms, dimension=1, rng=np.random.default_rng(11))
    replay = _bandit(arms=arms, dimension=1, rng=np.random.default_rng(11))
    context = np.array([1.0])

    choices = [first.select(context) for _ in range(12)]
    replayed = [replay.select(context) for _ in range(12)]

    assert choices == replayed
    assert set(choices) == set(arms)


def test_numerically_close_scores_are_treated_as_tied():
    bandit = _bandit(
        dimension=1,
        exploration=0.0,
        regularization=1.0,
        rng=np.random.default_rng(1),
    )
    context = np.array([1.0])
    bandit.update("first", context, 2.0)
    bandit.update("second", context, 2.0 + 1e-9)

    assert bandit.select(context) == "first"


def test_update_rejects_outer_product_overflow_without_mutating_state():
    bandit = _bandit(dimension=1, regularization=1.0)
    before = bandit.state("first")

    with pytest.raises(ValueError, match="context"):
        bandit.update("first", np.array([1e200]), 0.0)

    after = bandit.state("first")
    np.testing.assert_array_equal(after.matrix, before.matrix)
    np.testing.assert_array_equal(after.reward_vector, before.reward_vector)


def test_update_rejects_reward_product_overflow_without_mutating_state():
    bandit = _bandit(dimension=1, regularization=1.0)
    before = bandit.state("first")

    with pytest.raises(ValueError, match="reward"):
        bandit.update("first", np.array([2.0]), 1e308)

    after = bandit.state("first")
    np.testing.assert_array_equal(after.matrix, before.matrix)
    np.testing.assert_array_equal(after.reward_vector, before.reward_vector)


def test_update_rejects_accumulation_overflow_without_mutating_state():
    bandit = _bandit(dimension=1, regularization=1.0)
    bandit.update("first", np.array([1.0]), 1e308)
    before = bandit.state("first")

    with pytest.raises(ValueError, match="reward"):
        bandit.update("first", np.array([1.0]), 1e308)

    after = bandit.state("first")
    np.testing.assert_array_equal(after.matrix, before.matrix)
    np.testing.assert_array_equal(after.reward_vector, before.reward_vector)


def test_select_rejects_context_whose_score_overflows():
    bandit = _bandit(dimension=1, regularization=1.0)

    with pytest.raises(ValueError, match="context"):
        bandit.select(np.array([1e200]))


def test_update_promotes_large_integer_context_before_outer_product():
    bandit = _bandit(dimension=1, regularization=1.0)
    context = np.array([4_000_000_000], dtype=np.int64)

    bandit.update("first", context, 2.0)

    state = bandit.state("first")
    np.testing.assert_allclose(state.matrix, [[1.6e19]])
    np.testing.assert_allclose(state.reward_vector, [8e9])
    assert np.all(np.isfinite(state.matrix))
