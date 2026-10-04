"""Screen contextual macro-action policies against adaptive roulette."""

import argparse
import csv
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from uav_routing.adaptive import AdaptivePool
from uav_routing.alns import _operators, accept_score, classify_reward, cool_temperature
from uav_routing.config import ALNSConfig
from uav_routing.contextual.context import SearchHistory, build_context
from uav_routing.contextual.linucb import DisjointLinUCB
from uav_routing.evaluator import Evaluator
from uav_routing.experimental import (
    AbsorbableRouteRemoval,
    NoRemoval,
    RiskRegretRepair,
    RiskRelocateRepair,
)
from uav_routing.initial import build_initial_solution
from uav_routing.parser import parse_instance
from uav_routing.repair import RepairContext

ROOT = Path(__file__).resolve().parents[2]
POLICIES = (
    "roulette",
    "bandit_bias",
    "bandit_legacy",
    "bandit_structural",
    "shared_structural",
    "shared_dense",
)


@dataclass(frozen=True)
class MacroAction:
    name: str
    destroy: object
    repair: object
    q_min: int = 2
    q_max: int = 5


def macro_actions(
    config: ALNSConfig,
    include_large=False,
    include_risk_relocate=True,
) -> tuple[MacroAction, ...]:
    destroys, repairs = _operators(config, None, None)
    destroy = {operator.name: operator for operator in destroys}
    repair = {operator.name: operator for operator in repairs}

    actions = (
        MacroAction("guided_regret", AbsorbableRouteRemoval(), repair["regret2"]),
        MacroAction("guided_greedy", AbsorbableRouteRemoval(), repair["greedy"]),
        MacroAction("related_regret", destroy["related"], repair["regret2"]),
        MacroAction("worst_greedy", destroy["worst"], repair["greedy"]),
        MacroAction("risk_regret", destroy["risk_priority"], RiskRegretRepair()),
        MacroAction("random_regret", destroy["random"], repair["regret2"]),
    )

    if include_risk_relocate:
        actions += (
            MacroAction("risk_relocate", NoRemoval(), RiskRelocateRepair()),
        )

    if include_large:
        actions += (
            MacroAction(
                "related_large", destroy["related"], repair["regret2"], 6, 8
            ),
            MacroAction(
                "random_large", destroy["random"], repair["regret2"], 6, 8
            ),
        )

    return actions


class SharedLinUCB:
    def __init__(self, arms, exploration, regularization, rng, prior=None):
        self.arms = tuple(arms)
        self.exploration = exploration
        self.rng = rng
        self.dimension = len(self.features(self.arms[0], np.zeros(7)))
        self.inverse = np.eye(self.dimension) / regularization
        self.reward_vector = np.zeros(self.dimension)

        if prior is not None:
            self.inverse = prior[0].copy()
            self.reward_vector = prior[1].copy()

    @staticmethod
    def features(arm, context):
        route = float(arm.startswith("guided"))
        risk = float(arm.startswith("risk_"))
        related = float(arm == "related_regret")
        regret = float(arm.endswith("regret"))

        return np.concatenate((
            context,
            [route, risk, related, regret],
            [route * context[3], route * context[5]],
            [risk * context[6], related * context[2]],
        ))

    def select(self, context):
        scores = []

        for arm in self.arms:
            features = self.features(arm, context)
            mean = float(features @ self.inverse @ self.reward_vector)
            variance = max(0.0, float(features @ self.inverse @ features))
            scores.append(mean + self.exploration * math.sqrt(variance))

        best = np.flatnonzero(np.isclose(scores, max(scores)))

        return self.arms[int(self.rng.choice(best))]

    def update(self, arm, context, reward):
        features = self.features(arm, context)
        inverse_features = self.inverse @ features
        denominator = 1.0 + float(features @ inverse_features)

        self.inverse -= np.outer(inverse_features, inverse_features) / denominator
        self.inverse = (self.inverse + self.inverse.T) * 0.5
        self.reward_vector += reward * features

    def snapshot(self):
        return self.inverse.copy(), self.reward_vector.copy()


def structural_context(solution, evaluation, instance, iteration, history):
    routes = solution.routes
    lengths = np.asarray([len(route) for route in routes], dtype=float)
    short_fraction = float(np.mean(lengths <= 5)) if len(lengths) else 0.0
    min_length = min(1.0, float(np.min(lengths)) / 10.0) if len(lengths) else 0.0

    if len(routes) > 1:
        shortest_index = int(np.argmin(lengths))
        shortest = routes[shortest_index]
        spare_capacity = tuple(
            instance.capacity - route_result.load
            for index, route_result in enumerate(evaluation.routes)
            if index != shortest_index
        )
        customer_by_id = {customer.id: customer for customer in instance.customers}
        absorbable = sum(
            any(spare >= customer_by_id[customer_id].demand for spare in spare_capacity)
            for customer_id in shortest
        ) / len(shortest)
    else:
        absorbable = 0.0

    risk_by_route = []
    customers = {customer.id: customer for customer in instance.customers}
    indices = {
        customer.id: index
        for index, customer in enumerate(instance.customers, 1)
    }

    for route_result in evaluation.routes:
        route_risk = 0.0

        for stop in route_result.schedule:
            customer = customers[stop.customer_id]
            priority = float(instance.risk_priority[indices[stop.customer_id]])
            delay = (stop.service_start - customer.ready_time) / max(
                1.0, customer.due_date - customer.ready_time
            )
            route_risk += priority * delay

        risk_by_route.append(route_risk)

    risk_total = sum(risk_by_route)
    risk_concentration = max(risk_by_route) / risk_total if risk_total > 0 else 0.0

    return np.array((
        1.0,
        iteration,
        min(1.0, history.stagnation / history.window),
        short_fraction,
        min_length,
        absorbable,
        risk_concentration,
    ))


def _reward(candidate, current, best, accepted, config, dense):
    if dense:
        if candidate.vehicle_count < current.vehicle_count:
            return 1.0

        if candidate.vehicle_count == current.vehicle_count:
            gain = max(0.0, current.objective - candidate.objective)

            return 0.5 * (1.0 - math.exp(-gain / 0.05))

        return 0.0

    raw = classify_reward(
        candidate.score, current.score, best.score, accepted, config
    )

    return raw / 20.0


def run(
    instance,
    config,
    policy,
    snapshot_callback=None,
    shared_prior=None,
    include_large=False,
    include_risk_relocate=True,
):
    if include_large and policy.startswith("shared"):
        raise ValueError("large neighborhoods require a disjoint selector")

    started = time.perf_counter()
    rng = np.random.default_rng(config.seed)
    initial, d_ref = build_initial_solution(instance, config.alpha, config.beta)
    evaluator = Evaluator(instance, d_ref, config.alpha, config.beta)
    repair_context = RepairContext(
        instance, evaluator, d_ref, config.alpha, config.beta
    )
    actions = macro_actions(
        config,
        include_large=include_large,
        include_risk_relocate=include_risk_relocate,
    )
    by_name = {action.name: action for action in actions}
    names = tuple(by_name)

    if policy == "roulette":
        selector = AdaptivePool(
            names, 1.0, config.reaction_factor, config.minimum_weight
        )
    elif policy.startswith("shared"):
        selector = SharedLinUCB(names, 0.5, 1.0, rng, prior=shared_prior)
    else:
        dimension = {
            "bandit_bias": 1,
            "bandit_legacy": 9,
            "bandit_structural": 7,
        }[policy]
        selector = DisjointLinUCB(names, dimension, 0.5, 1.0, rng)

    current = initial
    current_eval = evaluator.solution(current)
    best_eval = current_eval
    temperature = config.initial_temperature
    history = SearchHistory(20)

    for iteration in range(config.iterations):
        if snapshot_callback is not None:
            snapshot_callback(iteration, current, current_eval)

        if policy == "bandit_bias":
            context = np.array([1.0])
        elif policy == "bandit_legacy":
            context = build_context(
                iteration=iteration,
                total_iterations=config.iterations,
                temperature=temperature,
                initial_temperature=config.initial_temperature,
                minimum_temperature=config.minimum_temperature,
                current=current_eval,
                best=best_eval,
                max_vehicles=instance.max_vehicles,
                history=history,
            )
        elif policy == "roulette":
            context = None
        else:
            context = structural_context(
                current, current_eval, instance,
                iteration / max(1, config.iterations - 1), history,
            )
        arm = selector.select(rng) if policy == "roulette" else selector.select(context)
        action = by_name[arm]
        q = int(rng.integers(action.q_min, action.q_max + 1))

        destroyed = action.destroy.apply(current, instance, evaluator, rng, q)
        repaired = action.repair.apply(
            destroyed.partial, destroyed.removed, repair_context
        )
        accepted = False
        improved = False
        new_best = False
        reward = 0.0

        if repaired.success and repaired.solution is not None:
            candidate = repaired.solution
            candidate_eval = evaluator.solution(candidate)

            if candidate_eval.feasible:
                acceptance = accept_score(
                    candidate_eval.score, current_eval.score, temperature, rng
                )
                accepted = acceptance.accepted
                improved = candidate_eval.score < current_eval.score
                new_best = candidate_eval.score < best_eval.score
                reward = _reward(
                    candidate_eval, current_eval, best_eval,
                    acceptance, config, policy == "shared_dense",
                )

                if new_best:
                    best_eval = candidate_eval

                if accepted:
                    current = candidate
                    current_eval = candidate_eval

        if policy == "roulette":
            selector.record(arm, reward * 20.0)

            if (iteration + 1) % config.segment_length == 0:
                selector.update_segment()
        else:
            selector.update(arm, context, reward)

        history.record(accepted=accepted, improved=improved, new_best=new_best)
        temperature = cool_temperature(
            temperature, config.cooling_rate, config.minimum_temperature
        )

    posterior = selector.snapshot() if isinstance(selector, SharedLinUCB) else None

    return best_eval, time.perf_counter() - started, posterior


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", nargs="+", default=["c101", "r101", "rc101"])
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=POLICIES)
    parser.add_argument("--large-neighborhoods", action="store_true")
    parser.add_argument("--without-risk-relocate", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = ALNSConfig(iterations=args.iterations, segment_length=20)
    rows = []

    for name in args.instances:
        path = ROOT / "dataset/solomon_risk" / f"{name}.txt"
        instance = parse_instance(path, 100, 5)

        for seed in range(args.seed_start, args.seed_start + args.seeds):
            for policy in args.policies:
                seeded = ALNSConfig(**{**vars(config), "seed": seed})
                evaluation, runtime, _ = run(
                    instance, seeded, policy,
                    include_large=args.large_neighborhoods,
                    include_risk_relocate=not args.without_risk_relocate,
                )
                rows.append((
                    name, seed, args.iterations, policy,
                    evaluation.vehicle_count, evaluation.objective,
                    evaluation.distance, evaluation.risk_delay, runtime,
                ))

                print(name, seed, policy, evaluation.score, flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow((
            "instance", "seed", "iterations", "policy", "vehicles",
            "objective", "distance", "risk_delay", "runtime",
        ))
        writer.writerows(rows)


if __name__ == "__main__":
    main()
