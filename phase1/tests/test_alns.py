import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from uav_routing.alns import (
    Acceptance,
    accept_score,
    classify_reward,
    cool_temperature,
    run_alns,
)
from uav_routing.config import ALNSConfig
from uav_routing.evaluator import Evaluator
from uav_routing.initial import build_initial_solution
from uav_routing.parser import parse_instance


class StubRng:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


def test_fewer_vehicles_is_always_accepted():
    result = accept_score((2, 99), (3, 0), 0.01, np.random.default_rng(1))
    assert result.accepted
    assert result.kind == "improve"


def test_more_vehicles_is_always_rejected():
    result = accept_score((3, 0), (2, 99), 100, np.random.default_rng(1))
    assert not result.accepted
    assert result.probability == 0


def test_equal_vehicle_improvement_and_equal_score_are_accepted():
    rng = np.random.default_rng(1)
    assert accept_score((2, 0.9), (2, 1.0), 0.01, rng).kind == "improve"
    assert accept_score((2, 1.0), (2, 1.0), 0.01, rng).kind == "equal"


def test_worse_equal_vehicle_candidate_uses_sa_probability():
    result = accept_score((2, 1.1), (2, 1.0), 0.5, StubRng(0.1))
    assert result.probability == pytest.approx(math.exp(-0.1 / 0.5))
    assert result.accepted
    assert result.kind == "accepted_worse"


def test_temperature_respects_floor():
    assert cool_temperature(0.01, 0.5, 0.008) == 0.008


@pytest.mark.parametrize(
    "candidate,current,best,acceptance,expected",
    [
        ((1, 2.0), (2, 1.0), (2, 0.5), Acceptance(True, "improve", 1), 20),
        ((2, 0.8), (2, 1.0), (2, 0.7), Acceptance(True, "improve", 1), 10),
        (
            (2, 1.1),
            (2, 1.0),
            (2, 0.7),
            Acceptance(True, "accepted_worse", 0.5),
            2,
        ),
        ((2, 1.0), (2, 1.0), (2, 0.7), Acceptance(True, "equal", 1), 0),
    ],
)
def test_reward_precedence(candidate, current, best, acceptance, expected):
    config = ALNSConfig()
    assert classify_reward(candidate, current, best, acceptance, config) == expected


def test_twenty_iteration_search_returns_feasible_best_not_worse_than_initial():
    path = Path(__file__).parents[2] / "dataset/solomon_risk/c101.txt"
    instance = parse_instance(path, 25)
    config = replace(ALNSConfig(), iterations=20, seed=7, segment_length=5)
    initial, d_ref = build_initial_solution(instance, config.alpha, config.beta)
    initial_eval = Evaluator(instance, d_ref, config.alpha, config.beta).solution(initial)
    result = run_alns(instance, config)
    assert result.evaluation.feasible
    assert result.evaluation.score <= initial_eval.score
    assert sorted(customer for route in result.best_solution.routes for customer in route) == list(
        range(1, 26)
    )
