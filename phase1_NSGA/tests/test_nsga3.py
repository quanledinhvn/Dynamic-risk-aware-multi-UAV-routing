from pathlib import Path

from uav_routing_nsga.nsga3 import NSGA3Config, run_nsga3
from uav_routing_nsga.parser import parse_instance


ROOT = Path(__file__).parents[2]


def test_seeded_run_is_reproducible_and_feasible():
    instance = parse_instance(ROOT / "dataset/solomon_risk/c101.txt", 25)
    config = NSGA3Config(population_size=8, generations=2, divisions=2, seed=11)
    first = run_nsga3(instance, config)
    second = run_nsga3(instance, config)
    assert first.pareto_front
    assert all(item.evaluation.feasible for item in first.population)
    assert [item.evaluation.objectives for item in first.pareto_front] == [item.evaluation.objectives for item in second.pareto_front]
    assert [item.solution for item in first.pareto_front] == [item.solution for item in second.pareto_front]
