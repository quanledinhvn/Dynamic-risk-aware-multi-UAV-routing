"""Contextual ALNS search orchestration."""

import time
from dataclasses import dataclass

import numpy as np

from uav_routing.alns import (
    _audit_best_solution,
    _operators,
    _starting_point,
    accept_evaluation,
    classify_evaluation_reward,
    cool_temperature,
)
from uav_routing.config import ALNSConfig
from uav_routing.evaluator import Evaluator
from uav_routing.initial import InitialSolutionError
from uav_routing.models import (
    Instance,
    SearchConstraints,
    Solution,
    SolutionEvaluation,
)
from uav_routing.repair import RepairContext
from uav_routing.scoring import is_better

from .config import ContextualBanditConfig
from .context import SearchHistory, build_context
from .selector import OperatorPairSelector, PairSelectionStats
from .warm_start import compress_short_routes


@dataclass(frozen=True)
class ContextualSearchResult:
    initial_solution: Solution
    final_current: Solution
    best_solution: Solution
    d_ref: float
    evaluation: SolutionEvaluation
    iterations: int
    seed: int
    runtime_seconds: float
    pair_selection_stats: tuple[PairSelectionStats, ...]


@dataclass(frozen=True)
class CandidateOutcome:
    raw_reward: float
    accepted: bool
    improved: bool
    new_best: bool


@dataclass
class _SearchState:
    current: Solution
    current_evaluation: SolutionEvaluation
    best: Solution
    best_evaluation: SolutionEvaluation
    temperature: float


def _candidate_outcome(
    repaired, state, evaluator, config, rng, constraints=None
) -> CandidateOutcome:
    if not repaired.success or repaired.solution is None:
        return CandidateOutcome(0.0, False, False, False)

    candidate = repaired.solution
    candidate_evaluation = (
        evaluator.solution(candidate, constraints)
        if constraints is not None
        else evaluator.solution(candidate)
    )

    if not candidate_evaluation.feasible:
        return CandidateOutcome(0.0, False, False, False)

    acceptance = accept_evaluation(
        candidate_evaluation,
        state.current_evaluation,
        state.temperature,
        rng,
        config,
    )
    improved = is_better(
        candidate_evaluation,
        state.current_evaluation,
        config.score_policy,
        config.risk_threshold,
    )
    new_best = is_better(
        candidate_evaluation,
        state.best_evaluation,
        config.score_policy,
        config.risk_threshold,
    )

    reward = classify_evaluation_reward(
        candidate_evaluation,
        state.current_evaluation,
        state.best_evaluation,
        acceptance,
        config,
    )

    if new_best:
        state.best = candidate
        state.best_evaluation = candidate_evaluation

    if acceptance.accepted:
        state.current = candidate
        state.current_evaluation = candidate_evaluation

    return CandidateOutcome(reward, acceptance.accepted, improved, new_best)


class ContextualALNSSolver:
    def __init__(
        self,
        instance: Instance,
        alns_config: ALNSConfig,
        bandit_config: ContextualBanditConfig,
        *,
        destroy_operators=None,
        repair_operators=None,
        initial_solution: Solution | None = None,
        constraints: SearchConstraints | None = None,
        d_ref: float | None = None,
    ) -> None:
        self.instance = instance
        self.alns_config = alns_config
        self.bandit_config = bandit_config

        self.destroy_operators = destroy_operators
        self.repair_operators = repair_operators

        self.initial_solution = initial_solution
        self.constraints = constraints
        self.d_ref = d_ref

    def run(self) -> ContextualSearchResult:
        started = time.perf_counter()
        config = self.alns_config
        bandit_config = self.bandit_config

        config.validate()
        bandit_config.validate()
        maximum_reward = max(
            config.reward_best, config.reward_improve, config.reward_accepted
        )

        if maximum_reward <= 0:
            raise ValueError("at least one operator reward must be positive")

        rng = np.random.default_rng(config.seed)
        initial, d_ref = _starting_point(
            self.instance,
            config,
            self.initial_solution,
            self.d_ref,
        )

        has_locked_customers = (
            self.constraints is not None
            and bool(self.constraints.locked_customers())
        )

        if bandit_config.short_route_warm_start and not has_locked_customers:
            initial = compress_short_routes(
                self.instance, initial, d_ref, config.alpha, config.beta
            )

        evaluator = Evaluator(self.instance, d_ref, config.alpha, config.beta)
        repair_context = RepairContext(
            self.instance,
            evaluator,
            d_ref,
            config.alpha,
            config.beta,
            self.constraints or SearchConstraints(),
        )

        destroy_operators, repair_operators = _operators(
            config, self.destroy_operators, self.repair_operators
        )
        destroy_names = tuple(operator.name for operator in destroy_operators)
        repair_names = tuple(operator.name for operator in repair_operators)

        selector = OperatorPairSelector(
            destroy_names,
            repair_names,
            bandit_config,
            maximum_reward,
            rng,
        )
        destroy_by_name = {operator.name: operator for operator in destroy_operators}
        repair_by_name = {operator.name: operator for operator in repair_operators}

        history = SearchHistory(bandit_config.context_window)
        initial_evaluation = evaluator.solution(initial, self.constraints)

        if not initial_evaluation.feasible:
            raise InitialSolutionError(
                "initial solution is infeasible: "
                + ", ".join(initial_evaluation.violations)
            )

        state = _SearchState(
            current=initial,
            current_evaluation=initial_evaluation,
            best=initial,
            best_evaluation=initial_evaluation,
            temperature=config.initial_temperature,
        )

        for iteration in range(config.iterations):
            context = build_context(
                iteration=iteration,
                total_iterations=config.iterations,
                temperature=state.temperature,
                initial_temperature=config.initial_temperature,
                minimum_temperature=config.minimum_temperature,
                current=state.current_evaluation,
                best=state.best_evaluation,
                max_vehicles=self.instance.max_vehicles,
                history=history,
            )
            q = int(rng.integers(config.q_min, config.q_max + 1))
            destroy_name, repair_name = selector.select(context)

            if self.constraints is None:
                destroyed = destroy_by_name[destroy_name].apply(
                    state.current, self.instance, evaluator, rng, q
                )
            else:
                destroyed = destroy_by_name[destroy_name].apply(
                    state.current,
                    self.instance,
                    evaluator,
                    rng,
                    q,
                    self.constraints,
                )

            repaired = repair_by_name[repair_name].apply(
                destroyed.partial, destroyed.removed, repair_context
            )
            outcome = _candidate_outcome(
                repaired,
                state,
                evaluator,
                config,
                rng,
                self.constraints,
            )

            selector.record((destroy_name, repair_name), context, outcome.raw_reward)
            history.record(
                accepted=outcome.accepted,
                improved=outcome.improved,
                new_best=outcome.new_best,
            )
            state.temperature = cool_temperature(
                state.temperature, config.cooling_rate, config.minimum_temperature
            )

        final_evaluation = _audit_best_solution(
            self.instance,
            state.best,
            d_ref,
            config,
            self.constraints,
        )

        return ContextualSearchResult(
            initial_solution=initial,
            final_current=state.current,
            best_solution=state.best,
            d_ref=d_ref,
            evaluation=final_evaluation,
            iterations=config.iterations,
            seed=config.seed,
            runtime_seconds=time.perf_counter() - started,
            pair_selection_stats=selector.snapshot(),
        )


def run_contextual_alns(
    instance: Instance,
    alns_config: ALNSConfig,
    bandit_config: ContextualBanditConfig | None = None,
    *,
    destroy_operators=None,
    repair_operators=None,
    initial_solution: Solution | None = None,
    constraints: SearchConstraints | None = None,
    d_ref: float | None = None,
) -> ContextualSearchResult:
    return ContextualALNSSolver(
        instance,
        alns_config,
        bandit_config or ContextualBanditConfig(),
        destroy_operators=destroy_operators,
        repair_operators=repair_operators,
        initial_solution=initial_solution,
        constraints=constraints,
        d_ref=d_ref,
    ).run()
