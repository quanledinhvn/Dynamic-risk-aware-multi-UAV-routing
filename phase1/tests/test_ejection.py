import pytest
from helpers import make_instance

from uav_routing.ejection import EjectionRepair
from uav_routing.evaluator import Evaluator
from uav_routing.experimental import RouteEliminationRepair
from uav_routing.models import Customer, Solution
from uav_routing.repair import RepairContext, RepairResult


@pytest.fixture
def context():
    customers = tuple(
        Customer(i, i, 0, demand, 0, 100, 0)
        for i, demand in enumerate((1, 1, 2, 2), start=1)
    )
    instance = make_instance(customers, capacity=3, max_vehicles=3)
    evaluator = Evaluator(instance, 20, 0.5, 0.5)

    return RepairContext(instance, evaluator, 20, 0.5, 0.5)


@pytest.mark.parametrize("risk_aware", [False, True])
def test_ejection_solves_capacity_conflict_that_direct_repair_cannot(
    context, risk_aware
):
    partial = Solution(((1, 2), (3,)))
    operator = EjectionRepair(risk_aware=risk_aware)

    assert not RouteEliminationRepair().apply(partial, (4,), context).success

    result = operator.apply(partial, (4,), context)

    assert result.success
    assert context.evaluator.solution(result.solution).feasible
    assert len(result.solution.routes) == 2

    assert operator.used_ejections >= 1
    assert partial == Solution(((1, 2), (3,)))


def test_zero_ejections_cannot_resolve_capacity_conflict(context):
    result = EjectionRepair(max_ejections=0).apply(
        Solution(((1, 2), (3,))), (4,), context
    )

    assert result == RepairResult(False, None)


def test_direct_insertion_and_no_new_routes(context):
    result = EjectionRepair().apply(Solution(((1, 4), (3,))), (2,), context)

    assert result.success
    assert len(result.solution.routes) == 2
    assert context.evaluator.solution(result.solution).feasible


def test_evaluation_budget_is_respected(context):
    operator = EjectionRepair(max_evaluations=1)
    result = operator.apply(Solution(((1, 2), (3,))), (4,), context)

    assert result == RepairResult(False, None)
    assert operator.evaluations <= 1


@pytest.mark.parametrize("removed", [(4, 4), (1, 4), (99,), ()])
def test_invalid_or_incomplete_input_is_rejected(context, removed):
    result = EjectionRepair().apply(Solution(((1, 2), (3,))), removed, context)

    assert result == RepairResult(False, None)


def test_time_windows_prevent_an_otherwise_capacity_feasible_merge():
    instance = make_instance(
        (
            Customer(1, -10, 0, 1, 0, 10, 0),
            Customer(2, 10, 0, 1, 0, 10, 0),
        ),
        capacity=10,
    )
    evaluator = Evaluator(instance, 40, 0.5, 0.5)
    context = RepairContext(instance, evaluator, 40, 0.5, 0.5)

    result = EjectionRepair().apply(Solution(((1,),)), (2,), context)

    assert result == RepairResult(False, None)


def test_risk_ranking_prefers_earlier_service_for_urgent_customer():
    instance = make_instance(
        (
            Customer(1, 9, 0, 1, 0, 100, 0),
            Customer(2, 1, 0, 1, 0, 100, 50),
        ),
        priorities=(1.0, 0.0),
    )
    evaluator = Evaluator(instance, 10, 0.5, 0.5)
    context = RepairContext(instance, evaluator, 10, 0.5, 0.5)
    partial = Solution(((1,),))

    distance_only = EjectionRepair(risk_aware=False).apply(partial, (2,), context)
    risk_aware = EjectionRepair(risk_aware=True).apply(partial, (2,), context)

    assert risk_aware.success and distance_only.success
    assert risk_aware.solution == Solution(((1, 2),))
    assert evaluator.solution(risk_aware.solution).feasible
    assert (
        evaluator.solution(risk_aware.solution).objective
        < evaluator.solution(distance_only.solution).objective
    )


def test_expired_deadline_returns_no_candidate(context):
    operator = EjectionRepair()
    operator.deadline = 0.0

    result = operator.apply(Solution(((1, 4), (3,))), (2,), context)

    assert result == RepairResult(False, None)
    assert operator.evaluations == 0
