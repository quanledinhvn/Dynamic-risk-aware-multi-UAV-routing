from dataclasses import replace
from pathlib import Path

import pytest
from helpers import make_instance

from uav_routing.config import ALNSConfig
from uav_routing.dynamic.policies import (
    POLICIES,
    cold_restart,
    evaluate_only,
    greedy_insert,
    solve_clairvoyant,
    warm_alns,
)
from uav_routing.dynamic.scenario import load_scenario
from uav_routing.evaluator import Evaluator
from uav_routing.initial import InitialSolutionError, build_initial_solution
from uav_routing.models import Customer, SearchConstraints, Solution

TINY = Path(__file__).parent / "fixtures" / "tiny_scenario.json"
CUSTOMERS = (
    Customer(1, 3, 4, 1, 0, 200, 0),
    Customer(2, 6, 8, 1, 0, 200, 0),
    Customer(3, 0, 10, 1, 0, 200, 0),
    Customer(4, 3, 0, 1, 0, 200, 0),
    Customer(5, 10, 0, 1, 0, 200, 0),
    Customer(6, 12, 5, 1, 0, 200, 0),
)
INSTANCE = make_instance(
    CUSTOMERS,
    depot=Customer(0, 0, 0, 0, 0, 500, 0),
    max_vehicles=3,
    priorities=(1.0, 0.2, 0.3, 0.4, 0.5, 0.6),
)
ALNS = ALNSConfig(iterations=100, seed=0, q_min=1, q_max=3)
INITIAL, D_REF = build_initial_solution(INSTANCE, 0.5, 0.5)
LOCKS = SearchConstraints(locked_prefixes=(INITIAL.routes[0][:1],), free_departure=4.0)


def _served(solution: Solution) -> list[int]:
    return sorted(c for route in solution.routes for c in route)


def test_policy_table_exposes_all_epoch_solvers():
    assert set(POLICIES) == {
        "greedy_insert",
        "cold_restart",
        "warm_alns",
        "contextual_warm_alns",
    }


def test_evaluate_only_wraps_initial_without_search():
    result = evaluate_only(INSTANCE, INITIAL, LOCKS, D_REF, ALNS, 7)

    assert result.best_solution == INITIAL
    assert result.initial_solution == INITIAL
    assert result.iterations == 0
    assert result.seed == 7
    assert result.d_ref == D_REF
    assert result.evaluation.feasible
    assert result.operator_stats == ()


def test_evaluate_only_rejects_infeasible_initial():
    with pytest.raises(InitialSolutionError):
        evaluate_only(INSTANCE, Solution(((1, 1),)), LOCKS, D_REF, ALNS, 0)


def test_greedy_insert_returns_initial_regardless_of_budget():
    result = greedy_insert(INSTANCE, INITIAL, LOCKS, D_REF, ALNS, 500, 1)

    assert result.best_solution == INITIAL
    assert result.iterations == 0


def test_warm_alns_with_zero_budget_matches_evaluate_only():
    result = warm_alns(INSTANCE, INITIAL, LOCKS, D_REF, ALNS, 0, 1)

    assert result.best_solution == INITIAL
    assert result.iterations == 0


def test_warm_alns_starts_from_initial_and_keeps_locks():
    result = warm_alns(INSTANCE, INITIAL, LOCKS, D_REF, ALNS, 100, 3)

    assert result.initial_solution == INITIAL
    assert result.iterations == 100
    assert result.seed == 3
    assert result.best_solution.routes[0][:1] == LOCKS.locked_prefixes[0]
    assert _served(result.best_solution) == [1, 2, 3, 4, 5, 6]
    assert result.evaluation.feasible


def test_cold_restart_rebuilds_free_part_but_keeps_locked_prefixes():
    result = cold_restart(INSTANCE, INITIAL, LOCKS, D_REF, ALNS, 0, 3)

    assert result.best_solution.routes[0][:1] == LOCKS.locked_prefixes[0]
    assert _served(result.best_solution) == [1, 2, 3, 4, 5, 6]
    assert result.initial_solution.routes[0][:1] == LOCKS.locked_prefixes[0]
    assert (
        Evaluator(INSTANCE, D_REF, 0.5, 0.5)
        .solution(result.best_solution, LOCKS)
        .feasible
    )


def test_cold_restart_ignores_the_free_part_of_the_warm_solution():
    # a deliberately poor warm solution must not leak into the cold construction
    poor = Solution((INITIAL.routes[0][:1], (6,), (5, 4, 3, 2)))
    poor_routes = {route for route in poor.routes if len(route) > 1}

    result = cold_restart(INSTANCE, poor, LOCKS, D_REF, ALNS, 0, 3)

    assert not poor_routes & set(result.initial_solution.routes)


def test_solve_clairvoyant_serves_static_and_dynamic_customers_with_given_d_ref():
    scenario = load_scenario(TINY)

    result = solve_clairvoyant(
        scenario, replace(ALNS, iterations=20), total_iterations=20, seed=1, d_ref=50.0
    )

    assert result.d_ref == 50.0
    assert result.iterations == 20
    assert _served(result.best_solution) == [1, 2, 3]
    assert result.evaluation.feasible
