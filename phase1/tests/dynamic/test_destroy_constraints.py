import numpy as np
import pytest
from helpers import make_instance

from uav_routing.destroy import (
    RandomRemoval,
    RelatedRemoval,
    RiskPriorityRemoval,
    RouteRemoval,
    WorstRemoval,
    remove_customers,
)
from uav_routing.evaluator import Evaluator
from uav_routing.models import Customer, SearchConstraints, Solution

CUSTOMERS = tuple(
    Customer(index, 3 * index, 4 * index, 1, 0, 1000, 1) for index in range(1, 10)
)
INSTANCE = make_instance(
    CUSTOMERS,
    depot=Customer(0, 0, 0, 0, 0, 1000, 0),
    max_vehicles=4,
    priorities=tuple(index / 10 for index in range(1, 10)),
)
EVALUATOR = Evaluator(INSTANCE, 100.0, 0.5, 0.5)
OPERATORS = (
    RandomRemoval(),
    WorstRemoval(),
    RelatedRemoval(),
    RouteRemoval(),
    RiskPriorityRemoval(),
)
SOLUTION = Solution(((1, 2, 3), (4, 5), (6, 7, 8, 9)))
LOCKS = SearchConstraints(locked_prefixes=((1, 2), (4,)), free_departure=10.0)


@pytest.mark.parametrize("operator", OPERATORS, ids=lambda operator: operator.name)
@pytest.mark.parametrize("seed", range(12))
def test_destroy_never_removes_locked_customers(operator, seed):
    result = operator.apply(
        SOLUTION, INSTANCE, EVALUATOR, np.random.default_rng(seed), 3, LOCKS
    )

    assert set(result.removed).isdisjoint({1, 2, 4})
    assert result.partial.routes[0][:2] == (1, 2)
    assert result.partial.routes[1][:1] == (4,)
    assert len(result.removed) > 0


@pytest.mark.parametrize("operator", OPERATORS, ids=lambda operator: operator.name)
def test_destroy_with_only_locked_customers_removes_nothing(operator):
    solution = Solution(((1, 2), (4,)))
    result = operator.apply(
        solution, INSTANCE, EVALUATOR, np.random.default_rng(0), 3, LOCKS
    )

    assert result.removed == ()
    assert result.partial == solution


def test_route_removal_keeps_locked_prefix_and_route_index():
    fully_locked = SearchConstraints(locked_prefixes=((1, 2), (4, 5)))
    solution = Solution(((1, 2), (4, 5), (6, 7, 8, 9)))

    for seed in range(5):
        result = RouteRemoval().apply(
            solution, INSTANCE, EVALUATOR, np.random.default_rng(seed), 3, fully_locked
        )

        assert result.removed == (6, 7, 8, 9)
        assert result.partial.routes == ((1, 2), (4, 5))


def test_route_removal_strips_only_free_suffix():
    seen = set()

    for seed in range(20):
        result = RouteRemoval().apply(
            SOLUTION, INSTANCE, EVALUATOR, np.random.default_rng(seed), 3, LOCKS
        )
        seen.add(result.removed)

    assert seen == {(3,), (5,), (6, 7, 8, 9)}


def test_empty_free_route_is_dropped_but_locked_routes_keep_indices():
    solution = Solution(((1,), (7, 8), (9,)))
    constraints = SearchConstraints(locked_prefixes=((1,),))

    result = remove_customers(solution, (7, 8), constraints)

    assert result.partial.routes == ((1,), (9,))


def test_locked_route_with_empty_free_part_is_kept():
    solution = Solution(((1, 3), (7,)))
    constraints = SearchConstraints(locked_prefixes=((1,),))

    result = remove_customers(solution, (3, 7), constraints)

    assert result.partial.routes == ((1,),)


@pytest.mark.parametrize("operator", OPERATORS, ids=lambda operator: operator.name)
def test_empty_constraints_match_unconstrained_behaviour(operator):
    left = operator.apply(SOLUTION, INSTANCE, EVALUATOR, np.random.default_rng(5), 3)
    right = operator.apply(
        SOLUTION, INSTANCE, EVALUATOR, np.random.default_rng(5), 3, SearchConstraints()
    )

    assert left == right
