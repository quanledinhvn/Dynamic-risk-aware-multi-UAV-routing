"""Epoch solvers: greedy insertion, cold restart, warm ALNS and clairvoyant."""

from dataclasses import replace
from typing import Protocol

from uav_routing.alns import SearchResult, run_alns
from uav_routing.config import ALNSConfig
from uav_routing.contextual.alns import run_contextual_alns
from uav_routing.contextual.config import ContextualBanditConfig
from uav_routing.evaluator import Evaluator
from uav_routing.initial import InitialSolutionError
from uav_routing.models import Instance, SearchConstraints, Solution
from uav_routing.repair import RepairContext, best_insertion

from .events import apply_events
from .models import Scenario
from .scenario import base_instance


class EpochSolver(Protocol):
    def __call__(
        self,
        instance: Instance,
        initial: Solution,
        constraints: SearchConstraints,
        d_ref: float,
        alns: ALNSConfig,
        iterations: int,
        seed: int,
    ) -> SearchResult: ...


def evaluate_only(
    instance: Instance,
    initial: Solution,
    constraints: SearchConstraints,
    d_ref: float,
    alns: ALNSConfig,
    seed: int,
) -> SearchResult:
    evaluation = Evaluator(instance, d_ref, alns.alpha, alns.beta).solution(
        initial, constraints
    )

    if not evaluation.feasible:
        raise InitialSolutionError(
            "epoch initial solution is infeasible: " + ", ".join(evaluation.violations)
        )

    return SearchResult(
        initial_solution=initial,
        final_current=initial,
        best_solution=initial,
        d_ref=float(d_ref),
        evaluation=evaluation,
        iterations=0,
        seed=seed,
        runtime_seconds=0.0,
        operator_stats=(),
    )


def greedy_insert(
    instance, initial, constraints, d_ref, alns, iterations, seed
) -> SearchResult:
    return evaluate_only(instance, initial, constraints, d_ref, alns, seed)


def warm_alns(
    instance, initial, constraints, d_ref, alns, iterations, seed
) -> SearchResult:
    if iterations <= 0:
        return evaluate_only(instance, initial, constraints, d_ref, alns, seed)

    return run_alns(
        instance,
        replace(alns, iterations=iterations, seed=seed),
        initial_solution=initial,
        constraints=constraints,
        d_ref=d_ref,
    )


def contextual_warm_alns(
    instance: Instance,
    initial: Solution,
    constraints: SearchConstraints,
    d_ref: float,
    alns: ALNSConfig,
    iterations: int,
    seed: int,
    bandit: ContextualBanditConfig | None = None,
) -> SearchResult:
    """Run contextual ALNS from the feasible plan projected into an epoch."""
    if iterations <= 0:
        return evaluate_only(instance, initial, constraints, d_ref, alns, seed)

    result = run_contextual_alns(
        instance,
        replace(alns, iterations=iterations, seed=seed),
        bandit,
        initial_solution=initial,
        constraints=constraints,
        d_ref=d_ref,
    )

    return SearchResult(
        initial_solution=result.initial_solution,
        final_current=result.final_current,
        best_solution=result.best_solution,
        d_ref=result.d_ref,
        evaluation=result.evaluation,
        iterations=result.iterations,
        seed=result.seed,
        runtime_seconds=result.runtime_seconds,
        operator_stats=(),
    )


def cold_restart(
    instance, initial, constraints, d_ref, alns, iterations, seed
) -> SearchResult:
    rebuilt = _cold_construction(instance, initial, constraints, d_ref, alns)

    return warm_alns(instance, rebuilt, constraints, d_ref, alns, iterations, seed)


def solve_clairvoyant(
    scenario: Scenario,
    alns: ALNSConfig,
    total_iterations: int,
    seed: int,
    d_ref: float,
) -> SearchResult:
    instance = apply_events(base_instance(scenario), scenario.events, {})

    return run_alns(
        instance, replace(alns, iterations=total_iterations, seed=seed), d_ref=d_ref
    )


def _cold_construction(
    instance: Instance,
    initial: Solution,
    constraints: SearchConstraints,
    d_ref: float,
    alns: ALNSConfig,
) -> Solution:
    """Rebuild the free part from scratch; fall back to ``initial`` if it fails."""
    evaluator = Evaluator(instance, d_ref, alns.alpha, alns.beta)
    context = RepairContext(
        instance, evaluator, d_ref, alns.alpha, alns.beta, constraints
    )
    locked = constraints.locked_customers()
    current = Solution(tuple(constraints.locked_prefixes))

    priorities = {
        customer.id: float(instance.risk_priority[index])
        for index, customer in enumerate(instance.customers, start=1)
    }
    pool = sorted(
        (customer for customer in instance.customers if customer.id not in locked),
        key=lambda customer: (customer.due_date, -priorities[customer.id], customer.id),
    )

    for customer in pool:
        choice = best_insertion(current, customer.id, context)

        if choice is None:
            return initial

        current = choice.solution

    return current


POLICIES: dict[str, EpochSolver] = {
    "greedy_insert": greedy_insert,
    "cold_restart": cold_restart,
    "warm_alns": warm_alns,
    "contextual_warm_alns": contextual_warm_alns,
}
