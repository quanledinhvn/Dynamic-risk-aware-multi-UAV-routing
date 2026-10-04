"""Reproduce exploratory acceptance-score and route-selection ablations."""

import argparse
import csv
from dataclasses import replace
from pathlib import Path

import numpy as np

from uav_routing.alns import _operators as original_operators
from uav_routing.alns import accept_score as lex_accept_score
from uav_routing.config import ALNSConfig
from uav_routing.contextual import ContextualBanditConfig
from uav_routing.contextual import alns as contextual_alns
from uav_routing.destroy import RouteRemoval, remove_customers
from uav_routing.evaluator import Evaluator
from uav_routing.initial import build_initial_solution as original_build_initial
from uav_routing.parser import parse_instance
from uav_routing.repair import (
    GreedyRepair,
    Regret2Repair,
    RepairContext,
    RiskPriorityRepair,
)

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_ROUTE_APPLY = RouteRemoval.apply
ORIGINAL_CONTEXTUAL_OPERATORS = contextual_alns._operators

ORIGINAL_CONTEXTUAL_BUILD_INITIAL = contextual_alns.build_initial_solution
POLICIES = (
    "lex",
    "soft_0.1",
    "soft_0.25",
    "soft_0.5",
    "shortest",
    "inverse",
    "route_only",
    "route_only_shortest",
    "route_random",
    "warm_route_4",
    "warm_route_8",
    "warm_route_small",
)


def soft_acceptance(penalty: float):
    def accept(candidate, current, temperature, rng):
        candidate_merit = penalty * candidate[0] + candidate[1]
        current_merit = penalty * current[0] + current[1]

        return lex_accept_score(
            (0, candidate_merit), (0, current_merit), temperature, rng
        )

    return accept


def route_selection(policy: str):
    def apply(self, solution, instance, evaluator, rng, q):
        if policy not in ("shortest", "inverse", "route_only_shortest"):
            return ORIGINAL_ROUTE_APPLY(self, solution, instance, evaluator, rng, q)

        lengths = np.asarray([len(route) for route in solution.routes], dtype=float)

        if policy in ("shortest", "route_only_shortest"):
            choices = np.flatnonzero(lengths == lengths.min())
            index = int(rng.choice(choices))
        else:
            weights = 1.0 / lengths
            index = int(rng.choice(len(lengths), p=weights / weights.sum()))

        return remove_customers(solution, solution.routes[index])

    return apply


def operator_portfolio(policy: str):
    def operators(config, destroy_override, repair_override):
        destroy, repair = original_operators(config, destroy_override, repair_override)

        if policy in ("route_only", "route_only_shortest"):
            destroy = tuple(op for op in destroy if op.name == "route")
        elif policy == "route_random":
            destroy = tuple(op for op in destroy if op.name in ("route", "random"))

        return destroy, repair

    return operators


def warm_route_start(instance, alpha: float, beta: float, route_limit: int):
    solution, d_ref = original_build_initial(instance, alpha, beta)
    evaluator = Evaluator(instance, d_ref, alpha, beta)
    context = RepairContext(instance, evaluator, d_ref, alpha, beta)

    repair_operators = (GreedyRepair(), Regret2Repair(), RiskPriorityRepair())

    for _ in range(3):
        improved = False
        indices = sorted(
            range(len(solution.routes)), key=lambda i: len(solution.routes[i])
        )

        for route_index in indices[:route_limit]:
            route = solution.routes[route_index]
            destroyed = remove_customers(solution, route)
            candidates = []

            for repair in repair_operators:
                result = repair.apply(destroyed.partial, destroyed.removed, context)

                if result.success and len(result.solution.routes) < len(
                    solution.routes
                ):
                    candidates.append(result.solution)

            if candidates:
                solution = min(candidates, key=lambda s: evaluator.solution(s).score)
                improved = True
                break

        if not improved:
            break

    return solution, d_ref


def run_policy(instance, config, bandit_config, policy: str):
    penalty = float(policy.split("_")[1]) if policy.startswith("soft_") else None
    contextual_alns.accept_score = (
        lex_accept_score if penalty is None else soft_acceptance(penalty)
    )

    RouteRemoval.apply = route_selection(policy)
    contextual_alns._operators = operator_portfolio(policy)

    if policy == "warm_route_small":
        bandit_config = replace(bandit_config, short_route_warm_start=True)
    elif policy.startswith("warm_route_"):
        route_limit = int(policy.rsplit("_", 1)[1])
        contextual_alns.build_initial_solution = lambda instance, alpha, beta: (
            warm_route_start(instance, alpha, beta, route_limit)
        )

    try:
        return contextual_alns.run_contextual_alns(instance, config, bandit_config)
    finally:
        contextual_alns.accept_score = lex_accept_score
        RouteRemoval.apply = ORIGINAL_ROUTE_APPLY
        contextual_alns._operators = ORIGINAL_CONTEXTUAL_OPERATORS
        contextual_alns.build_initial_solution = ORIGINAL_CONTEXTUAL_BUILD_INITIAL


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", nargs="+", default=["c101", "c102", "r101"])
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--q-min", type=int, default=2)
    parser.add_argument("--q-max", type=int, default=5)
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=["lex"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.seeds <= 0:
        parser.error("--seeds must be positive")

    if args.iterations <= 0:
        parser.error("--iterations must be positive")

    if not 0 < args.q_min <= args.q_max:
        parser.error("require 0 < --q-min <= --q-max")

    config = ALNSConfig(iterations=args.iterations, q_min=args.q_min, q_max=args.q_max)
    bandit_config = ContextualBanditConfig(
        context_window=10,
        linucb_exploration=1.0,
        linucb_regularization=0.25,
    )
    rows = []

    for instance_name in args.instances:
        path = ROOT / "dataset/solomon_risk" / f"{instance_name}.txt"
        instance = parse_instance(path, 100, 5)

        for seed in range(args.seeds):
            seeded_config = replace(config, seed=seed)

            for policy in args.policies:
                result = run_policy(instance, seeded_config, bandit_config, policy)
                evaluation = result.evaluation

                rows.append(
                    (
                        instance_name,
                        seed,
                        args.iterations,
                        args.q_min,
                        args.q_max,
                        policy,
                        evaluation.vehicle_count,
                        evaluation.objective,
                        evaluation.distance,
                        evaluation.risk_delay,
                        result.runtime_seconds,
                    )
                )

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "instance",
                "seed",
                "iterations",
                "q_min",
                "q_max",
                "policy",
                "vehicles",
                "objective",
                "distance",
                "risk_delay",
                "runtime",
            )
        )
        writer.writerows(rows)


if __name__ == "__main__":
    main()
