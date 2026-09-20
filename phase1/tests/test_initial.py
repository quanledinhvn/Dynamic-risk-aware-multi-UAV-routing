from pathlib import Path

import pytest
from helpers import make_instance

from uav_routing.evaluator import Evaluator
from uav_routing.initial import (
    InitialSolutionError,
    build_initial_solution,
    ordered_customer_ids,
)
from uav_routing.models import Customer
from uav_routing.parser import parse_instance


def test_initial_customer_order_is_due_risk_id():
    instance = make_instance(
        (
            Customer(1, 1, 0, 1, 0, 20, 0),
            Customer(2, 2, 0, 1, 0, 10, 0),
            Customer(3, 3, 0, 1, 0, 10, 0),
        ),
        priorities=(0.1, 0.2, 0.1),
    )

    assert ordered_customer_ids(instance) == (2, 3, 1)


def test_initial_solution_is_deterministic_complete_and_feasible():
    path = Path(__file__).parents[2] / "dataset/solomon_risk/c101.txt"
    instance = parse_instance(path, 25)

    first, d_ref_1 = build_initial_solution(instance, 0.5, 0.5)
    second, d_ref_2 = build_initial_solution(instance, 0.5, 0.5)

    assert first == second
    assert d_ref_1 == d_ref_2
    assert sorted(customer for route in first.routes for customer in route) == list(
        range(1, 26)
    )
    assert Evaluator(instance, d_ref_1, 0.5, 0.5).solution(first).feasible


def test_initial_solution_raises_when_vehicle_limit_is_insufficient():
    instance = make_instance(
        (
            Customer(1, -10, 0, 1, 0, 10, 0),
            Customer(2, 10, 0, 1, 0, 10, 0),
        ),
        max_vehicles=1,
    )

    with pytest.raises(InitialSolutionError, match="customer 2"):
        build_initial_solution(instance, 0.5, 0.5)
