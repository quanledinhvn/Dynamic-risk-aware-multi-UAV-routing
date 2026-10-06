import pytest
from helpers import make_instance, with_depot_due

from uav_routing.evaluator import Evaluator
from uav_routing.models import Customer, SearchConstraints, Solution

CUSTOMERS = (
    Customer(1, 3, 4, 1, 0, 100, 0),
    Customer(2, 6, 8, 1, 0, 100, 0),
    Customer(3, 0, 10, 1, 0, 100, 0),
)


def _evaluator(**kwargs) -> Evaluator:
    instance = make_instance(CUSTOMERS, max_vehicles=3, **kwargs)

    return Evaluator(instance, 1.0, 1.0, 0.0)


def test_free_route_departs_at_free_departure():
    late = _evaluator().route((1,), departure=40.0)

    assert late.schedule[0].arrival == pytest.approx(45.0)
    assert late.depot_return == pytest.approx(50.0)


def test_route_departure_defaults_to_zero():
    evaluator = _evaluator()

    assert evaluator.route((1,)) == evaluator.route((1,), departure=0.0)


def test_free_departure_can_make_route_infeasible_by_depot_deadline():
    instance = with_depot_due(make_instance(CUSTOMERS, max_vehicles=3), 20.0)
    evaluator = Evaluator(instance, 1.0, 1.0, 0.0)
    solution = Solution(((1,), (2,), (3,)))

    assert evaluator.solution(solution).feasible
    assert not evaluator.solution(
        solution, SearchConstraints(free_departure=15.0)
    ).feasible


def test_locked_route_still_departs_at_zero_while_free_routes_wait():
    evaluator = _evaluator()
    constraints = SearchConstraints(locked_prefixes=((1,),), free_departure=40.0)

    evaluation = evaluator.solution(Solution(((1, 2), (3,))), constraints)

    assert evaluation.feasible
    assert evaluation.routes[0].schedule[0].arrival == pytest.approx(5.0)
    assert evaluation.routes[1].schedule[0].arrival == pytest.approx(50.0)


@pytest.mark.parametrize(
    "routes",
    [
        ((2, 1, 3),),  # prefix reordered
        ((1,), (2, 3)),  # prefix split across routes
        ((3, 1, 2),),  # prefix not at the start
    ],
)
def test_changed_prefix_reports_locked_prefix_violation(routes):
    constraints = SearchConstraints(locked_prefixes=((1, 2),))
    evaluation = _evaluator().solution(Solution(routes), constraints)

    assert "locked_prefix" in evaluation.violations
    assert not evaluation.feasible


def test_missing_locked_route_reports_locked_prefix_violation():
    constraints = SearchConstraints(locked_prefixes=((1,), (2,)))
    evaluation = _evaluator().solution(Solution(((1, 2, 3),)), constraints)

    assert "locked_prefix" in evaluation.violations


def test_route_shorter_than_prefix_reports_locked_prefix_violation():
    constraints = SearchConstraints(locked_prefixes=((1, 2),))
    evaluation = _evaluator().solution(Solution(((1,), (2, 3))), constraints)

    assert "locked_prefix" in evaluation.violations


def test_matching_prefixes_add_no_violation():
    constraints = SearchConstraints(locked_prefixes=((1,), (2,)))
    evaluation = _evaluator().solution(Solution(((1, 3), (2,))), constraints)

    assert evaluation.feasible
    assert evaluation.violations == ()


def test_none_constraints_matches_default_evaluation():
    evaluator = _evaluator()
    solution = Solution(((1, 2), (3,)))

    assert evaluator.solution(solution) == evaluator.solution(solution, None)
    assert evaluator.solution(solution) == evaluator.solution(
        solution, SearchConstraints()
    )
