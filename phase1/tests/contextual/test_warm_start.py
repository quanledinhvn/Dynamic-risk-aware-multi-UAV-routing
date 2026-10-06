"""Focused checks for short-route warm start."""

from dataclasses import replace
from pathlib import Path

from uav_routing.config import ALNSConfig
from uav_routing.contextual import ContextualBanditConfig, run_contextual_alns
from uav_routing.contextual.warm_start import compress_short_routes
from uav_routing.evaluator import Evaluator
from uav_routing.initial import build_initial_solution
from uav_routing.parser import parse_instance

DATASET = Path(__file__).parents[3] / "dataset/solomon_risk"


def test_short_route_compression_reduces_c101_and_preserves_feasibility():
    instance = parse_instance(DATASET / "c101.txt", 100, 5)
    initial, d_ref = build_initial_solution(instance, 0.5, 0.5)

    compressed = compress_short_routes(instance, initial, d_ref, 0.5, 0.5)
    evaluation = Evaluator(instance, d_ref, 0.5, 0.5).solution(compressed)

    assert len(initial.routes) == 12
    assert evaluation.feasible
    assert evaluation.vehicle_count == 11


def test_short_route_compression_skips_instance_without_small_routes():
    instance = parse_instance(DATASET / "c102.txt", 100, 5)
    initial, d_ref = build_initial_solution(instance, 0.5, 0.5)

    compressed = compress_short_routes(instance, initial, d_ref, 0.5, 0.5)

    assert compressed == initial


def test_contextual_solver_uses_opt_in_warm_start():
    instance = parse_instance(DATASET / "c101.txt", 100, 5)
    config = replace(ALNSConfig(), iterations=1, seed=0)
    bandit = ContextualBanditConfig(short_route_warm_start=True)

    result = run_contextual_alns(instance, config, bandit)

    assert len(result.initial_solution.routes) == 11
    assert result.evaluation.feasible
