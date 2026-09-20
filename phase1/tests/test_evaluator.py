import math

import pytest

from uav_routing.evaluator import Evaluator, lexicographically_better
from uav_routing.models import Customer, Solution

from helpers import make_instance, with_depot_due


def schedule_instance():
    return make_instance(
        (
            Customer(1, 3, 4, 2, 10, 30, 2),
            Customer(2, 0, 4, 3, 0, 30, 2),
        ),
        priorities=(1.0, 0.5),
    )


def test_route_schedule_includes_wait_service_and_return():
    result = Evaluator(schedule_instance(), 12, 0.5, 0.5).route((1, 2))
    assert [(s.arrival, s.service_start, s.departure) for s in result.schedule] == [
        pytest.approx((5.0, 10.0, 12.0)),
        pytest.approx((15.0, 15.0, 17.0)),
    ]
    assert result.depot_return == pytest.approx(21.0)
    assert result.distance == pytest.approx(12.0)
    assert result.load == 5
    assert result.feasible


def test_route_rejects_capacity_violation():
    instance = make_instance(
        (Customer(1, 1, 0, 6, 0, 50, 0), Customer(2, 2, 0, 6, 0, 50, 0)),
        capacity=10,
    )
    result = Evaluator(instance, 4, 0.5, 0.5).route((1, 2))
    assert not result.feasible
    assert "capacity" in result.violations


def test_route_rejects_customer_due_date_violation():
    instance = make_instance((Customer(3, 5, 0, 1, 0, 4, 0),))
    result = Evaluator(instance, 10, 0.5, 0.5).route((3,))
    assert not result.feasible
    assert "customer_due_date" in result.violations


def test_route_rejects_depot_due_date_violation():
    instance = with_depot_due(
        make_instance((Customer(4, 4, 0, 1, 0, 10, 3),)), 10
    )
    result = Evaluator(instance, 8, 0.5, 0.5).route((4,))
    assert not result.feasible
    assert "depot_due_date" in result.violations


@pytest.mark.parametrize(
    "routes, violation",
    [
        (((1,),), "missing_customers"),
        (((1, 2), (2, 3)), "duplicate_customers"),
        (((1,), (2,), (3,)), "vehicle_limit"),
    ],
)
def test_solution_checks_completeness_and_vehicle_limit(routes, violation):
    instance = make_instance(
        tuple(Customer(i, i, 0, 1, 0, 100, 0) for i in (1, 2, 3)),
        max_vehicles=2,
    )
    result = Evaluator(instance, 10, 0.5, 0.5).solution(Solution(routes))
    assert not result.feasible
    assert violation in result.violations


def test_zero_priority_has_zero_risk_delay():
    instance = make_instance((Customer(1, 1, 0, 1, 0, 10, 0),))
    result = Evaluator(instance, d_ref=10, alpha=0.5, beta=0.5).solution(
        Solution(((1,),))
    )
    assert result.risk_delay == 0.0
    assert math.isfinite(result.objective)


def test_objective_uses_normalized_distance_and_weighted_risk_delay():
    instance = make_instance(
        (
            Customer(1, 3, 4, 1, 0, 10, 0),
            Customer(2, 0, 4, 1, 0, 20, 0),
        ),
        priorities=(1.0, 3.0),
    )
    result = Evaluator(instance, d_ref=12, alpha=0.5, beta=0.5).solution(
        Solution(((1, 2),))
    )
    expected_risk = (1 * 0.5 + 3 * 0.4) / 4
    assert result.distance == pytest.approx(12)
    assert result.risk_delay == pytest.approx(expected_risk)
    assert result.objective == pytest.approx(0.5 + 0.5 * expected_risk)
    assert result.score == pytest.approx((1, result.objective))


def test_empty_route_and_unknown_customer_are_rejected():
    evaluator = Evaluator(schedule_instance(), 12, 0.5, 0.5)
    assert "empty_route" in evaluator.route(()).violations
    assert "unknown_customer" in evaluator.route((99,)).violations


def test_invalid_evaluator_parameters_are_rejected():
    with pytest.raises(ValueError, match="d_ref"):
        Evaluator(schedule_instance(), 0, 0.5, 0.5)
    with pytest.raises(ValueError, match="sum to 1"):
        Evaluator(schedule_instance(), 1, 0.4, 0.4)


def test_lexicographic_score_prefers_vehicle_count_before_objective():
    assert lexicographically_better((2, 100.0), (3, 0.0))
    assert lexicographically_better((2, 0.9), (2, 1.0))
    assert not lexicographically_better((2, 1.0), (2, 1.0))
