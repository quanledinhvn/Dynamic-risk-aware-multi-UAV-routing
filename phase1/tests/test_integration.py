from dataclasses import replace
from pathlib import Path

import pytest

from uav_routing.alns import ALNSSolver, run_alns
from uav_routing.config import ALNSConfig
from uav_routing.contextual import (
    ContextualALNSSolver,
    ContextualBanditConfig,
    ContextualSearchResult,
    run_contextual_alns,
)
from uav_routing.destroy import RandomRemoval
from uav_routing.evaluator import Evaluator
from uav_routing.parser import parse_instance
from uav_routing.repair import RepairResult


def c101_25():
    path = Path(__file__).parents[2] / "dataset/solomon_risk/c101.txt"
    return parse_instance(path, 25)


def comparable(result):
    return result.best_solution, result.evaluation, result.operator_stats


@pytest.fixture
def short_search():
    return c101_25(), replace(ALNSConfig(), iterations=10, seed=42)


@pytest.fixture
def contextual_result(short_search):
    instance, config = short_search
    return run_contextual_alns(instance, config, ContextualBanditConfig())


def test_baseline_public_api_preserves_fixed_seed_result(short_search):
    instance, config = short_search
    result = run_alns(instance, config)

    assert result.best_solution.routes == (
        (5, 3, 7, 8, 10, 11, 9, 6, 4, 2, 1),
        (20, 24, 25, 15, 23, 22, 21),
        (13, 17, 18, 19, 16, 14, 12),
    )
    assert result.evaluation.score == pytest.approx((3, 0.6417742578974153))


def test_contextual_public_api_reproduces_route_evaluation_and_stats(
    short_search, contextual_result
):
    instance, config = short_search
    repeated = ContextualALNSSolver(instance, config, ContextualBanditConfig()).run()

    assert isinstance(contextual_result, ContextualSearchResult)

    assert contextual_result.best_solution == repeated.best_solution
    assert contextual_result.evaluation == repeated.evaluation
    assert contextual_result.pair_selection_stats == repeated.pair_selection_stats


def test_contextual_pair_selection_accounts_for_every_iteration(
    short_search, contextual_result
):
    _, config = short_search
    stats = contextual_result.pair_selection_stats

    assert len(stats) == 15
    assert len({(stat.destroy_name, stat.repair_name) for stat in stats}) == 15
    assert sum(stat.total_uses for stat in stats) == config.iterations


def test_same_seed_produces_identical_search_result():
    instance = c101_25()
    config = replace(ALNSConfig(), iterations=50, seed=123, segment_length=10)

    first = run_alns(instance, config)
    second = run_alns(instance, config)

    assert comparable(first) == comparable(second)
    assert first.initial_solution == second.initial_solution
    assert first.final_current == second.final_current


def test_final_solution_is_complete_and_independently_feasible():
    instance = c101_25()
    config = replace(ALNSConfig(), iterations=50)

    result = run_alns(instance, config)
    checked = Evaluator(instance, result.d_ref, 0.5, 0.5).solution(result.best_solution)

    assert checked.feasible
    assert sorted(
        customer for route in result.best_solution.routes for customer in route
    ) == [customer.id for customer in instance.customers]


def test_different_seed_still_returns_valid_solution():
    instance = c101_25()

    first = run_alns(instance, replace(ALNSConfig(), iterations=10, seed=1))
    second = run_alns(instance, replace(ALNSConfig(), iterations=10, seed=2))

    assert first.evaluation.feasible
    assert second.evaluation.feasible


class FailingRepair:
    name = "always_fail"

    def apply(self, partial, removed, context):
        return RepairResult(False, None)


def test_failed_repair_does_not_change_current_solution():
    instance = c101_25()
    solver = ALNSSolver(
        instance,
        replace(ALNSConfig(), iterations=1),
        destroy_operators=(RandomRemoval(),),
        repair_operators=(FailingRepair(),),
    )

    result = solver.run()

    assert result.final_current == result.initial_solution
    assert result.operator_stats[0].total_uses == 1
    assert result.operator_stats[1].total_uses == 1
