"""Acceptance policy and orchestration for adaptive large neighborhood search."""

from dataclasses import dataclass
import math

import numpy as np

from .adaptive import AdaptivePool
from .config import ALNSConfig
from .destroy import (
    RandomRemoval,
    RelatednessWeights,
    RelatedRemoval,
    RiskPriorityRemoval,
    RouteRemoval,
    WorstRemoval,
)
from .evaluator import Evaluator, lexicographically_better
from .initial import build_initial_solution
from .models import Instance, Solution, SolutionEvaluation
from .repair import GreedyRepair, Regret2Repair, RepairContext, RiskPriorityRepair


@dataclass(frozen=True)
class Acceptance:
    accepted: bool
    kind: str
    probability: float


@dataclass(frozen=True)
class SearchResult:
    best_solution: Solution
    evaluation: SolutionEvaluation


class SearchInvariantError(RuntimeError):
    """Raised when the search produces an invalid final result."""


def accept_score(
    candidate: tuple[int, float],
    current: tuple[int, float],
    temperature: float,
    rng: np.random.Generator,
) -> Acceptance:
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    if candidate[0] < current[0]:
        return Acceptance(True, "improve", 1.0)
    if candidate[0] > current[0]:
        return Acceptance(False, "reject", 0.0)
    delta = candidate[1] - current[1]
    if delta < 0:
        return Acceptance(True, "improve", 1.0)
    if delta == 0:
        return Acceptance(True, "equal", 1.0)
    probability = math.exp(-delta / temperature)
    accepted = float(rng.random()) < probability
    return Acceptance(
        accepted,
        "accepted_worse" if accepted else "reject",
        probability,
    )


def cool_temperature(temperature: float, cooling_rate: float, minimum: float) -> float:
    if temperature <= 0 or minimum <= 0:
        raise ValueError("temperatures must be positive")
    if not 0 < cooling_rate <= 1:
        raise ValueError("cooling_rate must be in (0, 1]")
    return max(minimum, temperature * cooling_rate)


def classify_reward(candidate, current, best, acceptance, config) -> float:
    if lexicographically_better(candidate, best):
        return config.reward_best
    if lexicographically_better(candidate, current):
        return config.reward_improve
    if acceptance.accepted and candidate != current:
        return config.reward_accepted
    return 0.0


def run_alns(instance: Instance, config: ALNSConfig) -> SearchResult:
    config.validate()
    rng = np.random.default_rng(config.seed)
    initial, d_ref = build_initial_solution(instance, config.alpha, config.beta)
    evaluator = Evaluator(instance, d_ref, config.alpha, config.beta)
    repair_context = RepairContext(
        instance, evaluator, d_ref, config.alpha, config.beta
    )
    related_weights = RelatednessWeights(
        config.related_distance_weight,
        config.related_time_weight,
        config.related_demand_weight,
        config.related_risk_weight,
    )
    destroy_operators = (
        RandomRemoval(),
        WorstRemoval(config.removal_determinism),
        RelatedRemoval(related_weights, config.removal_determinism),
        RouteRemoval(),
        RiskPriorityRemoval(config.removal_determinism),
    )
    repair_operators = (GreedyRepair(), Regret2Repair(), RiskPriorityRepair())
    destroy_by_name = {operator.name: operator for operator in destroy_operators}
    repair_by_name = {operator.name: operator for operator in repair_operators}
    destroy_pool = AdaptivePool(
        tuple(destroy_by_name), 1.0, config.reaction_factor, config.minimum_weight
    )
    repair_pool = AdaptivePool(
        tuple(repair_by_name), 1.0, config.reaction_factor, config.minimum_weight
    )

    current = initial
    current_evaluation = evaluator.solution(current)
    best = current
    best_evaluation = current_evaluation
    temperature = config.initial_temperature

    for iteration in range(config.iterations):
        q = int(rng.integers(config.q_min, config.q_max + 1))
        destroy_name = destroy_pool.select(rng)
        repair_name = repair_pool.select(rng)
        destroyed = destroy_by_name[destroy_name].apply(
            current, instance, evaluator, rng, q
        )
        repaired = repair_by_name[repair_name].apply(
            destroyed.partial, destroyed.removed, repair_context
        )
        reward = 0.0
        if repaired.success and repaired.solution is not None:
            candidate = repaired.solution
            candidate_evaluation = evaluator.solution(candidate)
            if candidate_evaluation.feasible:
                acceptance = accept_score(
                    candidate_evaluation.score,
                    current_evaluation.score,
                    temperature,
                    rng,
                )
                reward = classify_reward(
                    candidate_evaluation.score,
                    current_evaluation.score,
                    best_evaluation.score,
                    acceptance,
                    config,
                )
                if lexicographically_better(
                    candidate_evaluation.score, best_evaluation.score
                ):
                    best = candidate
                    best_evaluation = candidate_evaluation
                if acceptance.accepted:
                    current = candidate
                    current_evaluation = candidate_evaluation
        destroy_pool.record(destroy_name, reward)
        repair_pool.record(repair_name, reward)
        if (iteration + 1) % config.segment_length == 0:
            destroy_pool.update_segment()
            repair_pool.update_segment()
        temperature = cool_temperature(
            temperature, config.cooling_rate, config.minimum_temperature
        )

    final_evaluation = Evaluator(
        instance, d_ref, config.alpha, config.beta
    ).solution(best)
    if not final_evaluation.feasible:
        raise SearchInvariantError(
            "best solution failed final feasibility audit: "
            + ", ".join(final_evaluation.violations)
        )
    return SearchResult(best, final_evaluation)


def accept_candidate(
    current: SolutionEvaluation,
    candidate: SolutionEvaluation,
    temperature: float,
    rng: np.random.Generator,
) -> Acceptance:
    return accept_score(candidate.score, current.score, temperature, rng)
