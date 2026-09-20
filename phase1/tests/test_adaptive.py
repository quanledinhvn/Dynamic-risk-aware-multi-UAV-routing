import numpy as np
import pytest

from uav_routing.adaptive import AdaptivePool


def test_roulette_uses_normalized_positive_weights():
    pool = AdaptivePool(
        ("a", "b"), initial_weight=1.0, reaction_factor=0.2, minimum_weight=0.1
    )
    assert pool.probabilities() == pytest.approx((0.5, 0.5))


def test_seeded_selection_sequence_is_stable():
    pool = AdaptivePool(("a", "b"), 1.0, 0.2, 0.1)
    rng = np.random.default_rng(42)
    assert [pool.select(rng) for _ in range(6)] == ["b", "a", "b", "b", "a", "b"]


def test_segment_update_uses_average_reward_and_resets_counters():
    pool = AdaptivePool(("a",), 1.0, 0.2, 0.1)
    pool.record("a", 20)
    pool.record("a", 0)
    pool.update_segment()
    assert pool.weight("a") == pytest.approx(0.8 * 1 + 0.2 * 10)
    assert pool.segment_count("a") == 0
    assert pool.segment_score("a") == 0


def test_unused_operator_keeps_weight_and_floor_is_enforced():
    pool = AdaptivePool(("a", "b"), 1.0, 1.0, 0.1)
    pool.record("a", 0)
    pool.update_segment()
    assert pool.weight("a") == 0.1
    assert pool.weight("b") == 1.0


def test_snapshot_preserves_input_order_and_tracks_total_uses():
    pool = AdaptivePool(("b", "a"), 1.0, 0.2, 0.1)
    pool.record("a", 2)
    snapshot = pool.snapshot()
    assert tuple(item.name for item in snapshot) == ("b", "a")
    assert snapshot[1].total_uses == 1
    assert snapshot[1].segment_uses == 1
    assert snapshot[1].segment_score == 2


@pytest.mark.parametrize(
    "names, initial, reaction, minimum",
    [
        ((), 1, 0.2, 0.1),
        (("a", "a"), 1, 0.2, 0.1),
        (("a",), 0, 0.2, 0.1),
        (("a",), 1, -0.1, 0.1),
        (("a",), 1, 1.1, 0.1),
        (("a",), 1, 0.2, 0),
    ],
)
def test_invalid_pool_configuration_is_rejected(names, initial, reaction, minimum):
    with pytest.raises(ValueError):
        AdaptivePool(names, initial, reaction, minimum)


def test_unknown_name_and_negative_reward_are_rejected():
    pool = AdaptivePool(("a",), 1, 0.2, 0.1)
    with pytest.raises(KeyError):
        pool.record("missing", 1)
    with pytest.raises(ValueError, match="reward"):
        pool.record("a", -1)
