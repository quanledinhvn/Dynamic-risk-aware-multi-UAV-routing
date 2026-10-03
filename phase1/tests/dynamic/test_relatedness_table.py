import numpy as np
import pytest
from helpers import make_instance

from uav_routing.destroy import (
    RelatednessWeights,
    RelatedRemoval,
    relatedness,
    relatedness_table,
)
from uav_routing.evaluator import Evaluator
from uav_routing.models import Customer, Solution

CUSTOMERS = tuple(
    Customer(index, 3 * index, (4 * index) % 17, index, 10 * index, 50 + 20 * index, 1)
    for index in range(1, 13)
)
INSTANCE = make_instance(
    CUSTOMERS,
    depot=Customer(0, 0, 0, 0, 0, 1000, 0),
    max_vehicles=4,
    priorities=tuple((index % 5) / 5 for index in range(1, 13)),
)
WEIGHTS = RelatednessWeights(1.0, 0.5, 0.25, 2.0)


def test_table_gives_identical_relatedness_values():
    table = relatedness_table(INSTANCE)

    for left in range(1, 13):
        for right in range(1, 13):
            assert relatedness(INSTANCE, left, right, WEIGHTS, table) == relatedness(
                INSTANCE, left, right, WEIGHTS
            )


def test_table_rejects_unknown_customers():
    table = relatedness_table(INSTANCE)

    with pytest.raises(ValueError):
        relatedness(INSTANCE, 1, 99, WEIGHTS, table)


def test_related_removal_reuses_table_for_same_instance():
    operator = RelatedRemoval(WEIGHTS)
    solution = Solution(((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)))
    evaluator = Evaluator(INSTANCE, 1.0, 1.0, 0.0)

    operator.apply(solution, INSTANCE, evaluator, np.random.default_rng(0), 3)
    first = operator.table_for(INSTANCE)
    operator.apply(solution, INSTANCE, evaluator, np.random.default_rng(1), 3)

    assert operator.table_for(INSTANCE) is first

    other = make_instance(CUSTOMERS[:6], max_vehicles=2)

    assert operator.table_for(other) is not first
    assert operator.table_for(other).maxima != first.maxima


def test_related_removal_results_unchanged_by_caching():
    solution = Solution(((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)))
    evaluator = Evaluator(INSTANCE, 1.0, 1.0, 0.0)
    removed = [
        RelatedRemoval(WEIGHTS)
        .apply(solution, INSTANCE, evaluator, np.random.default_rng(seed), 4)
        .removed
        for seed in range(5)
    ]

    # fresh operator each time: identical selections regardless of cache state
    cached = RelatedRemoval(WEIGHTS)
    again = [
        cached.apply(
            solution, INSTANCE, evaluator, np.random.default_rng(seed), 4
        ).removed
        for seed in range(5)
    ]

    assert removed == again
