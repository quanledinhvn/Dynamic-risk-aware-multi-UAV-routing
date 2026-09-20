import numpy as np
import pytest
from helpers import make_instance

from uav_routing.destroy import RandomRemoval
from uav_routing.evaluator import Evaluator
from uav_routing.models import Customer, Solution
from uav_routing.repair import (
    GreedyRepair,
    Regret2Repair,
    RepairContext,
    RepairResult,
    RiskPriorityRepair,
    best_insertion,
)


def broad_context():
    instance = make_instance(
        tuple(Customer(i, i * 2, 0, 1, 0, 100, 0) for i in range(1, 6)),
        max_vehicles=3,
        priorities=(0.1, 0.9, 0.5, 0.2, 0.3),
    )
    evaluator = Evaluator(instance, 20, 0.5, 0.5)

    return instance, evaluator, RepairContext(instance, evaluator, 20, 0.5, 0.5)


@pytest.mark.parametrize(
    "repair", [GreedyRepair(), Regret2Repair(), RiskPriorityRepair()]
)
def test_repair_restores_complete_feasible_solution(repair):
    instance, evaluator, context = broad_context()
    original = Solution(((1, 2, 3), (4, 5)))

    destroyed = RandomRemoval().apply(
        original, instance, evaluator, np.random.default_rng(4), q=2
    )
    result = repair.apply(destroyed.partial, destroyed.removed, context)

    assert result.success
    assert result.solution is not None
    assert evaluator.solution(result.solution).feasible


def test_regret2_prioritizes_customer_with_one_best_delta_k_position():
    instance = make_instance(
        (
            Customer(1, 10, 0, 1, 0, 100, 0),
            Customer(2, 5, 0, 1, 0, 100, 0),
            Customer(3, 1, 0, 1, 0, 1, 0),
        ),
        max_vehicles=1,
    )
    evaluator = Evaluator(instance, 20, 0.5, 0.5)
    context = RepairContext(instance, evaluator, 20, 0.5, 0.5)

    choice = Regret2Repair().choose_customer((2, 3), context, partial=Solution(((1,),)))

    assert choice is not None
    assert choice.customer_id == 3


def test_risk_priority_order_is_priority_due_id():
    instance, _, _ = broad_context()

    assert RiskPriorityRepair().ordered((3, 1, 2), instance) == (2, 3, 1)


def test_failed_repair_is_atomic():
    _, _, context = broad_context()
    partial = Solution(((1, 2),))
    before = partial

    result = GreedyRepair().apply(partial, (99,), context)

    assert result == RepairResult(False, None)
    assert partial == before


@pytest.mark.parametrize(
    "repair", [GreedyRepair(), Regret2Repair(), RiskPriorityRepair()]
)
def test_duplicate_removed_customer_fails_without_partial_result(repair):
    _, _, context = broad_context()

    result = repair.apply(Solution(((1,),)), (2, 2, 3, 4, 5), context)

    assert result == RepairResult(False, None)


@pytest.mark.parametrize(
    "repair", [GreedyRepair(), Regret2Repair(), RiskPriorityRepair()]
)
def test_failed_repair_discards_solution_after_a_successful_insertion(repair):
    instance = make_instance(
        (
            Customer(1, 1, 0, 1, 0, 100, 0),
            Customer(2, 2, 0, 1, 0, 100, 0),
            Customer(3, 3, 0, 1, 0, 100, 0),
        ),
        max_vehicles=1,
        capacity=2,
        priorities=(0.0, 1.0, 0.0),
    )
    evaluator = Evaluator(instance, 10, 0.5, 0.5)
    context = RepairContext(instance, evaluator, 10, 0.5, 0.5)
    partial = Solution(((1,),))

    first = best_insertion(partial, 2, context)

    assert first is not None
    assert best_insertion(first.solution, 3, context) is None

    result = repair.apply(partial, (2, 3), context)

    assert result == RepairResult(False, None)
    assert partial == Solution(((1,),))
