"""Contextual search outcomes and orchestration contracts."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from uav_routing.config import ALNSConfig
from uav_routing.contextual import ContextualBanditConfig
from uav_routing.contextual.alns import (
    CandidateOutcome,
    _candidate_outcome,
    _SearchState,
    run_contextual_alns,
)
from uav_routing.contextual.context import SearchHistory
from uav_routing.destroy import DestroyResult
from uav_routing.evaluator import Evaluator
from uav_routing.models import Solution, SolutionEvaluation
from uav_routing.parser import parse_instance
from uav_routing.repair import RepairResult


def _instance():
    path = Path(__file__).parents[3] / "dataset/solomon_risk/c101.txt"
    return parse_instance(path, 25)


def _evaluation(score, *, feasible=True):
    return SolutionEvaluation(
        feasible=feasible,
        vehicle_count=score[0],
        distance=0.0,
        risk_delay=0.0,
        objective=score[1],
        score=score,
        routes=(),
        violations=() if feasible else ("invalid",),
    )


class _Evaluator:
    def __init__(self, evaluation):
        self.evaluation = evaluation

    def solution(self, candidate):
        return self.evaluation


class _Rng:
    def __init__(self, random_value):
        self.random_value = random_value

    def random(self):
        return self.random_value


def _state():
    current = Solution(((1,),))
    best = Solution(((2,),))

    return _SearchState(
        current=current,
        current_evaluation=_evaluation((2, 100.0)),
        best=best,
        best_evaluation=_evaluation((2, 90.0)),
        temperature=1.0,
    )


@pytest.mark.parametrize(
    ("score", "feasible", "random_value", "expected"),
    [
        ((2, 80.0), True, 0.5, CandidateOutcome(20.0, True, True, True)),
        ((2, 95.0), True, 0.5, CandidateOutcome(10.0, True, True, False)),
        ((2, 100.0), True, 0.5, CandidateOutcome(0.0, True, False, False)),
        ((2, 101.0), True, 0.0, CandidateOutcome(2.0, True, False, False)),
        ((2, 101.0), True, 1.0, CandidateOutcome(0.0, False, False, False)),
        ((2, 80.0), False, 0.5, CandidateOutcome(0.0, False, False, False)),
    ],
)
def test_candidate_outcome_updates_state_consistently(
    score, feasible, random_value, expected
):
    state = _state()
    original_current = state.current
    original_best = state.best

    candidate = Solution(((3,),))
    repaired = RepairResult(True, candidate)

    outcome = _candidate_outcome(
        repaired,
        state,
        _Evaluator(_evaluation(score, feasible=feasible)),
        ALNSConfig(),
        _Rng(random_value),
    )

    assert outcome == expected
    assert state.current == (candidate if expected.accepted else original_current)
    assert state.best == (candidate if expected.new_best else original_best)


def test_failed_repair_has_zero_outcome_and_preserves_state():
    state = _state()
    original = replace(state)

    outcome = _candidate_outcome(
        RepairResult(False, None), state, _Evaluator(None), ALNSConfig(), _Rng(0)
    )

    assert outcome == CandidateOutcome(0.0, False, False, False)
    assert state == original


@pytest.mark.parametrize(
    ("alns_config", "bandit_config", "message"),
    [
        (replace(ALNSConfig(), iterations=0), ContextualBanditConfig(), "iterations"),
        (ALNSConfig(), ContextualBanditConfig(context_window=0), "context_window"),
        (
            replace(
                ALNSConfig(),
                reward_best=0.0,
                reward_improve=0.0,
                reward_accepted=0.0,
            ),
            ContextualBanditConfig(),
            "reward",
        ),
    ],
)
def test_contextual_run_validates_both_configs_and_positive_reward(
    alns_config, bandit_config, message
):
    with pytest.raises(ValueError, match=message):
        run_contextual_alns(_instance(), alns_config, bandit_config)


@pytest.mark.parametrize(
    ("destroy_names", "repair_names", "message"),
    [
        (("same", "same"), ("r",), "unique names"),
        (("d",), ("same", "same"), "unique names"),
        ((), ("r",), "nonblank names"),
        (("d",), (), "nonblank names"),
        (("",), ("r",), "nonblank names"),
        (("d",), ("  ",), "nonblank names"),
    ],
)
def test_invalid_operator_names_are_rejected_before_iteration(
    monkeypatch, destroy_names, repair_names, message
):
    from uav_routing.contextual import alns as contextual_alns

    applied = []

    def destroy_apply(solution, instance, evaluator, rng, q):
        applied.append("destroy")
        return DestroyResult(solution, ())

    def repair_apply(partial, removed, context):
        applied.append("repair")
        return RepairResult(False, None)

    destroy = tuple(
        SimpleNamespace(name=name, apply=destroy_apply) for name in destroy_names
    )
    repair = tuple(
        SimpleNamespace(name=name, apply=repair_apply) for name in repair_names
    )

    monkeypatch.setattr(contextual_alns, "_operators", lambda *_: (destroy, repair))

    with pytest.raises(ValueError, match=message):
        run_contextual_alns(_instance(), replace(ALNSConfig(), iterations=1))

    assert applied == []


def test_complete_search_is_feasible_and_reproducible():
    instance = _instance()
    config = replace(ALNSConfig(), iterations=20, seed=7)

    first = run_contextual_alns(instance, config)
    second = run_contextual_alns(instance, config)
    initial = Evaluator(instance, first.d_ref, config.alpha, config.beta).solution(
        first.initial_solution
    )

    assert first.evaluation.feasible
    assert first.evaluation.score <= initial.score
    assert sorted(
        customer for route in first.best_solution.routes for customer in route
    ) == list(range(1, 26))

    assert len(first.pair_selection_stats) == 15
    assert sum(stats.total_uses for stats in first.pair_selection_stats) == 20
    assert first.iterations == 20

    assert first.seed == 7
    assert (
        first.initial_solution,
        first.final_current,
        first.best_solution,
        first.evaluation,
        first.pair_selection_stats,
    ) == (
        second.initial_solution,
        second.final_current,
        second.best_solution,
        second.evaluation,
        second.pair_selection_stats,
    )


def test_failed_repair_still_records_pair_and_history(monkeypatch):
    from uav_routing.contextual import alns as contextual_alns

    class Destroy:
        name = "destroy"

        def apply(self, solution, instance, evaluator, rng, q):
            return DestroyResult(solution, ())

    class Repair:
        name = "repair"

        def apply(self, partial, removed, context):
            return RepairResult(False, None)

    histories = []

    class TrackedHistory(SearchHistory):
        def __init__(self, window):
            super().__init__(window)
            histories.append(self)

    monkeypatch.setattr(
        contextual_alns, "_operators", lambda *_: ((Destroy(),), (Repair(),))
    )
    monkeypatch.setattr(contextual_alns, "SearchHistory", TrackedHistory)

    result = run_contextual_alns(_instance(), replace(ALNSConfig(), iterations=1))

    assert result.final_current == result.initial_solution
    assert result.pair_selection_stats[0].total_uses == 1
    assert result.pair_selection_stats[0].total_raw_reward == 0.0

    assert histories[0].total_iterations == 1
    assert histories[0].acceptance_rate == 0.0
    assert histories[0].improvement_rate == 0.0

    assert histories[0].stagnation == 1
