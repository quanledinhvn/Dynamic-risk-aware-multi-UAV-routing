import numpy as np
import pytest

from uav_routing.destroy import (
    RandomRemoval,
    RelatednessWeights,
    RelatedRemoval,
    RiskPriorityRemoval,
    RouteRemoval,
    WorstRemoval,
    relatedness,
)
from uav_routing.evaluator import Evaluator
from uav_routing.models import Customer, Solution

from helpers import make_instance


def destroy_context(seed=0):
    instance = make_instance(
        (
            Customer(1, 1, 0, 1, 0, 20, 0),
            Customer(2, 2, 0, 2, 2, 22, 0),
            Customer(3, 8, 0, 4, 10, 30, 0),
            Customer(4, 9, 0, 5, 12, 32, 0),
        ),
        priorities=(0.9, 0.7, 0.2, 0.1),
    )
    solution = Solution(((1, 2), (3, 4)))
    evaluator = Evaluator(instance, d_ref=20, alpha=0.5, beta=0.5)
    return solution, instance, evaluator, np.random.default_rng(seed)


def all_destroy_operators():
    return (
        RandomRemoval(),
        WorstRemoval(),
        RelatedRemoval(),
        RouteRemoval(),
        RiskPriorityRemoval(),
    )


@pytest.mark.parametrize("operator", all_destroy_operators())
@pytest.mark.parametrize("seed", range(5))
def test_destroy_partitions_customer_set(operator, seed):
    solution, instance, evaluator, rng = destroy_context(seed)
    result = operator.apply(solution, instance, evaluator, rng, q=2)
    remaining = [customer for route in result.partial.routes for customer in route]
    original = [customer for route in solution.routes for customer in route]
    assert sorted(remaining + list(result.removed)) == sorted(original)
    assert len(remaining) == len(set(remaining))
    assert all(result.partial.routes)
    assert solution == Solution(((1, 2), (3, 4)))


def test_random_removal_is_seed_reproducible():
    solution, instance, evaluator, rng_a = destroy_context(7)
    *_, rng_b = destroy_context(7)
    a = RandomRemoval().apply(solution, instance, evaluator, rng_a, q=2)
    b = RandomRemoval().apply(solution, instance, evaluator, rng_b, q=2)
    assert a == b


def test_route_removal_ignores_q_and_removes_whole_route():
    solution, instance, evaluator, rng = destroy_context(1)
    result = RouteRemoval().apply(solution, instance, evaluator, rng, q=1)
    assert result.removed in solution.routes
    assert len(result.removed) == 2


def test_relatedness_combines_four_normalized_terms():
    _, instance, _, _ = destroy_context()
    weights = RelatednessWeights(distance=1, time_window=1, demand=1, risk=1)
    # Pair 1-2: distance 1/8, time-window difference 4/24,
    # demand difference 1/4, risk difference .2/.8.
    assert relatedness(instance, 1, 2, weights) == pytest.approx(
        1 / 8 + 4 / 24 + 1 / 4 + 0.2 / 0.8
    )


def test_normal_removal_clamps_q_to_served_count():
    solution, instance, evaluator, rng = destroy_context()
    result = RandomRemoval().apply(solution, instance, evaluator, rng, q=99)
    assert len(result.removed) == 4
    assert result.partial.routes == ()
