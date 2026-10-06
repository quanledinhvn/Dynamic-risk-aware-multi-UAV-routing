import numpy as np
from helpers import make_instance

from uav_routing.evaluator import Evaluator
from uav_routing.experimental import (
    AbsorbableRouteRemoval,
    NoRemoval,
    RiskRegretRepair,
    RiskRelocateRepair,
    RouteEliminationRepair,
)
from uav_routing.models import Customer, Solution
from uav_routing.repair import RepairContext, RepairResult


def test_absorbable_removal_prefers_route_with_feasible_alternatives():
    instance = make_instance(
        (
            Customer(1, 1, 0, 1, 0, 100, 0),
            Customer(2, 2, 0, 1, 0, 100, 0),
            Customer(3, 30, 0, 2, 0, 31, 0),
        ),
        max_vehicles=3,
        capacity=2,
    )
    solution = Solution(((1,), (2,), (3,)))
    evaluator = Evaluator(instance, 100, 0.5, 0.5)

    result = AbsorbableRouteRemoval().apply(
        solution, instance, evaluator, np.random.default_rng(0), 2
    )

    assert result.removed in ((1,), (2,))
    remaining = [
        customer for route in result.partial.routes for customer in route
    ]

    assert sorted(remaining) == sorted({1, 2, 3} - set(result.removed))


def test_risk_regret_reconstructs_a_feasible_solution():
    instance = make_instance(
        tuple(Customer(i, i * 2, 0, 1, 0, 100, 0) for i in range(1, 5)),
        max_vehicles=3,
        priorities=(0.0, 1.0, 0.5, 0.0),
    )
    evaluator = Evaluator(instance, 20, 0.5, 0.5)
    context = RepairContext(instance, evaluator, 20, 0.5, 0.5)

    result = RiskRegretRepair().apply(Solution(((1, 4),)), (2, 3), context)

    assert result.success
    assert evaluator.solution(result.solution).feasible


def test_route_elimination_never_opens_a_route():
    instance = make_instance(
        tuple(Customer(i, i * 2, 0, 1, 0, 100, 0) for i in range(1, 4)),
        max_vehicles=3,
        priorities=(0.0, 1.0, 0.5),
    )
    evaluator = Evaluator(instance, 20, 0.5, 0.5)
    context = RepairContext(instance, evaluator, 20, 0.5, 0.5)

    result = RouteEliminationRepair().apply(Solution(((1,),)), (2, 3), context)

    assert result.success
    assert result.solution is not None
    assert len(result.solution.routes) == 1
    assert evaluator.solution(result.solution).feasible


def test_route_elimination_fails_atomically_when_absorption_impossible():
    instance = make_instance(
        (
            Customer(1, 1, 0, 1, 0, 100, 0),
            Customer(2, 2, 0, 1, 0, 100, 0),
        ),
        max_vehicles=2,
        capacity=1,
    )
    evaluator = Evaluator(instance, 10, 0.5, 0.5)
    context = RepairContext(instance, evaluator, 10, 0.5, 0.5)

    result = RouteEliminationRepair().apply(Solution(((1,),)), (2,), context)

    assert result == RepairResult(False, None)


def test_risk_relocate_uses_same_uavs_and_reduces_objective():
    instance = make_instance(
        (
            Customer(1, 9, 0, 1, 0, 100, 0),
            Customer(2, 1, 0, 1, 0, 100, 0),
        ),
        max_vehicles=1,
        priorities=(0.0, 1.0),
    )
    evaluator = Evaluator(instance, 18, 0.5, 0.5)
    context = RepairContext(instance, evaluator, 18, 0.5, 0.5)
    original = Solution(((1, 2),))

    destroyed = NoRemoval().apply(
        original, instance, evaluator, np.random.default_rng(0), 2
    )
    repaired = RiskRelocateRepair().apply(
        destroyed.partial, destroyed.removed, context
    )

    assert repaired.success
    assert repaired.solution == Solution(((2, 1),))
    assert (
        evaluator.solution(repaired.solution).score
        < evaluator.solution(original).score
    )
