from dataclasses import replace
from pathlib import Path

from uav_routing.alns import ALNSSolver, run_alns
from uav_routing.config import ALNSConfig
from uav_routing.destroy import RandomRemoval
from uav_routing.evaluator import Evaluator
from uav_routing.parser import parse_instance
from uav_routing.repair import RepairResult


def c101_25():
    path = Path(__file__).parents[2] / "dataset/solomon_risk/c101.txt"
    return parse_instance(path, 25)


def comparable(result):
    return result.best_solution, result.evaluation, result.operator_stats


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
