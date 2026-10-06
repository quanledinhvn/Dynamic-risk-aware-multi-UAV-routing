import pytest
from helpers import make_instance

from uav_routing.evaluator import Evaluator
from uav_routing.models import Customer, SearchConstraints, Solution
from uav_routing.repair import (
    GreedyRepair,
    Regret2Repair,
    RepairContext,
    RiskPriorityRepair,
    feasible_insertions,
)

CUSTOMERS = (
    Customer(1, 3, 4, 1, 0, 200, 0),
    Customer(2, 6, 8, 1, 0, 200, 0),
    Customer(3, 0, 10, 1, 0, 200, 0),
    Customer(4, 3, 0, 1, 0, 50, 0),
    Customer(5, 10, 0, 1, 0, 200, 0),
    Customer(6, 12, 5, 1, 0, 200, 0),
)
INSTANCE = make_instance(
    CUSTOMERS,
    depot=Customer(0, 0, 0, 0, 0, 500, 0),
    max_vehicles=3,
    priorities=(1.0, 0.2, 0.3, 0.4, 0.5, 0.6),
)
REPAIRS = (GreedyRepair(), Regret2Repair(), RiskPriorityRepair())


def make_context(constraints: SearchConstraints | None = None) -> RepairContext:
    evaluator = Evaluator(INSTANCE, 100.0, 0.5, 0.5)

    if constraints is None:
        return RepairContext(INSTANCE, evaluator, 100.0, 0.5, 0.5)

    return RepairContext(INSTANCE, evaluator, 100.0, 0.5, 0.5, constraints)


def test_context_defaults_to_unconstrained():
    assert make_context().constraints == SearchConstraints()


def test_insertions_skip_positions_inside_locked_prefix():
    context = make_context(SearchConstraints(locked_prefixes=((1, 2),)))
    partial = Solution(((1, 2, 3),))

    positions = {
        (insertion.route_index, insertion.position)
        for insertion in feasible_insertions(partial, 5, context)
    }

    assert positions == {(0, 2), (0, 3), (1, 0)}


def test_new_route_uses_free_departure():
    context = make_context(SearchConstraints(free_departure=90.0))

    assert feasible_insertions(Solution(()), 4, context) == ()
    assert feasible_insertions(Solution(()), 4, make_context()) != ()


def test_existing_free_route_is_evaluated_with_free_departure():
    context = make_context(SearchConstraints(free_departure=90.0))

    assert feasible_insertions(Solution(((1,),)), 4, context) == ()


def test_locked_route_is_still_evaluated_from_zero():
    context = make_context(
        SearchConstraints(locked_prefixes=((1,),), free_departure=90.0)
    )

    insertions = feasible_insertions(Solution(((1,),)), 4, context)

    assert [insertion.route_index for insertion in insertions] == [0]


def test_partial_evaluation_uses_free_departure():
    context = make_context(SearchConstraints(free_departure=40.0))

    delayed = context.evaluate_partial(Solution(((1,),)))
    prompt = make_context().evaluate_partial(Solution(((1,),)))

    # service starts at 45 instead of 5, so the weighted delay is nine times larger
    assert prompt.risk_delay > 0
    assert delayed.risk_delay == pytest.approx(9 * prompt.risk_delay)
    assert delayed.distance == pytest.approx(prompt.distance)


@pytest.mark.parametrize("repair", REPAIRS, ids=lambda repair: repair.name)
def test_repair_result_keeps_locked_prefixes(repair):
    constraints = SearchConstraints(locked_prefixes=((1, 2), (5,)), free_departure=5.0)
    result = repair.apply(
        Solution(((1, 2), (5,))), (3, 4, 6), make_context(constraints)
    )

    assert result.success
    assert result.solution.routes[0][:2] == (1, 2)
    assert result.solution.routes[1][:1] == (5,)
    assert sorted(c for route in result.solution.routes for c in route) == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]


@pytest.mark.parametrize("repair", REPAIRS, ids=lambda repair: repair.name)
def test_repair_rejects_removed_set_containing_locked_customer(repair):
    constraints = SearchConstraints(locked_prefixes=((1,),))
    result = repair.apply(Solution(((2,),)), (1, 3), make_context(constraints))

    assert not result.success
    assert result.solution is None


@pytest.mark.parametrize("repair", REPAIRS, ids=lambda repair: repair.name)
def test_repair_without_constraints_is_unchanged(repair):
    partial = Solution(((1, 2), (5,)))

    left = repair.apply(partial, (3, 4, 6), make_context())
    right = repair.apply(partial, (3, 4, 6), make_context(SearchConstraints()))

    assert left == right
