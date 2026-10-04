"""Acceptance policy and orchestration for adaptive large neighborhood search."""

import math
import time
from dataclasses import dataclass

import numpy as np

from .adaptive import AdaptivePool, OperatorStats
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
from .scoring import annealing_delta, is_better, preference_key


@dataclass(frozen=True)
class Acceptance:
    accepted: bool
    kind: str
    probability: float


@dataclass(frozen=True)
class SearchResult:
    initial_solution: Solution
    final_current: Solution
    best_solution: Solution
    d_ref: float
    evaluation: SolutionEvaluation
    iterations: int
    seed: int
    runtime_seconds: float
    operator_stats: tuple[OperatorStats, ...]


@dataclass
class _SearchState:
    current: Solution
    current_evaluation: SolutionEvaluation
    best: Solution
    best_evaluation: SolutionEvaluation
    temperature: float


@dataclass(frozen=True)
class _SearchResources:
    evaluator: Evaluator
    repair_context: RepairContext
    destroy_by_name: dict
    repair_by_name: dict
    destroy_pool: AdaptivePool
    repair_pool: AdaptivePool


class SearchInvariantError(RuntimeError):
    """Raised when the search produces an invalid final result."""


class ALNSSolver:
    def __init__(
        self,
        instance: Instance,
        config: ALNSConfig,
        *,
        destroy_operators=None,
        repair_operators=None,
    ):
        self.instance = instance
        self.config = config
        self.destroy_operators = destroy_operators
        self.repair_operators = repair_operators

    def run(self) -> SearchResult:
        return _run_alns(
            self.instance,
            self.config,
            destroy_operators_override=self.destroy_operators,
            repair_operators_override=self.repair_operators,
        )


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


def accept_evaluation(
    candidate: SolutionEvaluation,
    current: SolutionEvaluation,
    temperature: float,
    rng: np.random.Generator,
    config: ALNSConfig,
) -> Acceptance:
    """Apply the configured score policy to one candidate evaluation."""
    if temperature <= 0:
        raise ValueError("temperature must be positive")

    policy = config.score_policy
    threshold = config.risk_threshold

    if is_better(candidate, current, policy, threshold):
        return Acceptance(True, "improve", 1.0)

    if preference_key(candidate, policy, threshold) == preference_key(
        current, policy, threshold
    ):
        return Acceptance(True, "equal", 1.0)

    delta = annealing_delta(candidate, current, policy, threshold)

    if delta is None:
        return Acceptance(False, "reject", 0.0)

    probability = math.exp(-delta / temperature)
    accepted = float(rng.random()) < probability

    return Acceptance(
        accepted,
        "accepted_worse" if accepted else "reject",
        probability,
    )


def classify_evaluation_reward(
    candidate: SolutionEvaluation,
    current: SolutionEvaluation,
    best: SolutionEvaluation,
    acceptance: Acceptance,
    config: ALNSConfig,
) -> float:
    """Classify an operator reward using the configured score policy."""
    policy = config.score_policy
    threshold = config.risk_threshold

    if is_better(candidate, best, policy, threshold):
        return config.reward_best

    if is_better(candidate, current, policy, threshold):
        return config.reward_improve

    if acceptance.accepted and candidate != current:
        return config.reward_accepted

    return 0.0


def _run_alns(
    instance: Instance,
    config: ALNSConfig,
    *,
    destroy_operators_override=None,
    repair_operators_override=None,
) -> SearchResult:
    started = time.perf_counter()
    config.validate()

    rng = np.random.default_rng(config.seed)

    initial, d_ref = build_initial_solution(instance, config.alpha, config.beta)

    resources = _build_search_resources(
        instance,
        config,
        d_ref,
        destroy_operators_override,
        repair_operators_override,
    )

    initial_evaluation = resources.evaluator.solution(initial)
    state = _SearchState(
        current=initial,
        current_evaluation=initial_evaluation,
        best=initial,
        best_evaluation=initial_evaluation,
        temperature=config.initial_temperature,
    )

    _run_iterations(state, resources, instance, config, rng)

    final_evaluation = _audit_best_solution(
        instance,
        state.best,
        d_ref,
        config,
    )

    return SearchResult(
        initial_solution=initial,
        final_current=state.current,
        best_solution=state.best,
        d_ref=d_ref,
        evaluation=final_evaluation,
        iterations=config.iterations,
        seed=config.seed,
        runtime_seconds=time.perf_counter() - started,
        operator_stats=_operator_stats(
            resources.destroy_pool,
            resources.repair_pool,
        ),
    )


def _build_search_resources(
    instance: Instance,
    config: ALNSConfig,
    d_ref: float,
    destroy_override,
    repair_override,
) -> _SearchResources:
    evaluator = Evaluator(instance, d_ref, config.alpha, config.beta)
    repair_context = RepairContext(
        instance, evaluator, d_ref, config.alpha, config.beta
    )
    destroy_operators, repair_operators = _operators(
        config,
        destroy_override,
        repair_override,
    )

    destroy_by_name = {operator.name: operator for operator in destroy_operators}
    repair_by_name = {operator.name: operator for operator in repair_operators}

    destroy_pool = AdaptivePool(
        tuple(destroy_by_name), 1.0, config.reaction_factor, config.minimum_weight
    )
    repair_pool = AdaptivePool(
        tuple(repair_by_name), 1.0, config.reaction_factor, config.minimum_weight
    )

    return _SearchResources(
        evaluator=evaluator,
        repair_context=repair_context,
        destroy_by_name=destroy_by_name,
        repair_by_name=repair_by_name,
        destroy_pool=destroy_pool,
        repair_pool=repair_pool,
    )


def _run_iterations(
    state: _SearchState,
    resources: _SearchResources,
    instance: Instance,
    config: ALNSConfig,
    rng: np.random.Generator,
) -> None:
    for iteration in range(config.iterations):
        _search_step(state, resources, instance, config, rng)

        if (iteration + 1) % config.segment_length == 0:
            resources.destroy_pool.update_segment()
            resources.repair_pool.update_segment()

        state.temperature = cool_temperature(
            state.temperature, config.cooling_rate, config.minimum_temperature
        )


def _operators(config, destroy_override, repair_override):
    related_weights = RelatednessWeights(
        config.related_distance_weight,
        config.related_time_weight,
        config.related_demand_weight,
        config.related_risk_weight,
    )
    destroy_operators = destroy_override or (
        RandomRemoval(),
        WorstRemoval(config.removal_determinism),
        RelatedRemoval(related_weights, config.removal_determinism),
        RouteRemoval(),
        RiskPriorityRemoval(config.removal_determinism),
    )
    repair_operators = repair_override or (
        GreedyRepair(),
        Regret2Repair(),
        RiskPriorityRepair(),
    )

    return destroy_operators, repair_operators


def _search_step(
    state: _SearchState,
    resources: _SearchResources,
    instance: Instance,
    config: ALNSConfig,
    rng: np.random.Generator,
) -> None:
    q = int(rng.integers(config.q_min, config.q_max + 1))
    destroy_name = resources.destroy_pool.select(rng)
    repair_name = resources.repair_pool.select(rng)

    destroyed = resources.destroy_by_name[destroy_name].apply(
        state.current, instance, resources.evaluator, rng, q
    )
    repaired = resources.repair_by_name[repair_name].apply(
        destroyed.partial, destroyed.removed, resources.repair_context
    )
    reward = _candidate_reward(
        repaired,
        state,
        resources.evaluator,
        config,
        rng,
    )

    resources.destroy_pool.record(destroy_name, reward)
    resources.repair_pool.record(repair_name, reward)


def _candidate_reward(repaired, state, evaluator, config, rng) -> float:
    if not repaired.success or repaired.solution is None:
        return 0.0

    candidate = repaired.solution
    candidate_evaluation = evaluator.solution(candidate)

    if not candidate_evaluation.feasible:
        return 0.0

    acceptance = accept_evaluation(
        candidate_evaluation,
        state.current_evaluation,
        state.temperature,
        rng,
        config,
    )
    reward = classify_evaluation_reward(
        candidate_evaluation,
        state.current_evaluation,
        state.best_evaluation,
        acceptance,
        config,
    )

    if is_better(
        candidate_evaluation,
        state.best_evaluation,
        config.score_policy,
        config.risk_threshold,
    ):
        state.best = candidate
        state.best_evaluation = candidate_evaluation

    if acceptance.accepted:
        state.current = candidate
        state.current_evaluation = candidate_evaluation

    return reward


def _audit_best_solution(
    instance: Instance,
    best: Solution,
    d_ref: float,
    config: ALNSConfig,
) -> SolutionEvaluation:
    evaluation = Evaluator(instance, d_ref, config.alpha, config.beta).solution(best)

    if not evaluation.feasible:
        raise SearchInvariantError(
            "best solution failed final feasibility audit: "
            + ", ".join(evaluation.violations)
        )

    return evaluation


def _operator_stats(
    destroy_pool: AdaptivePool, repair_pool: AdaptivePool
) -> tuple[OperatorStats, ...]:
    return _prefixed_stats("destroy", destroy_pool) + _prefixed_stats(
        "repair", repair_pool
    )


def _prefixed_stats(prefix: str, pool: AdaptivePool) -> tuple[OperatorStats, ...]:
    return tuple(
        OperatorStats(
            f"{prefix}:{stats.name}",
            stats.weight,
            stats.total_uses,
            stats.segment_uses,
            stats.segment_score,
        )
        for stats in pool.snapshot()
    )


def run_alns(instance: Instance, config: ALNSConfig) -> SearchResult:
    return ALNSSolver(instance, config).run()


def accept_candidate(
    current: SolutionEvaluation,
    candidate: SolutionEvaluation,
    temperature: float,
    rng: np.random.Generator,
    config: ALNSConfig | None = None,
) -> Acceptance:
    return accept_evaluation(
        candidate,
        current,
        temperature,
        rng,
        config or ALNSConfig(),
    )
