"""Equal-time pilot of bounded route-elimination search; no bandit involved."""

import argparse
import csv
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from uav_routing.alns import (
    _audit_best_solution,
    _build_search_resources,
    _candidate_reward,
    _SearchState,
    cool_temperature,
)
from uav_routing.config import ALNSConfig
from uav_routing.ejection import EjectionRepair
from uav_routing.experimental import AbsorbableRouteRemoval
from uav_routing.initial import build_initial_solution
from uav_routing.parser import parse_instance

ROOT = Path(__file__).resolve().parents[2]
POLICIES = ("original", "guided", "beam", "ejection", "risk_ejection")


def run(instance, seed, policy, seconds, max_evaluations, beam_width):
    started = time.perf_counter()
    deadline = started + seconds
    config = ALNSConfig(seed=seed, segment_length=20)

    rng = np.random.default_rng(seed)
    initial, d_ref = build_initial_solution(instance, config.alpha, config.beta)
    resources = _build_search_resources(instance, config, d_ref, None, None)

    if policy != "original":
        resources.destroy_by_name["route"] = AbsorbableRouteRemoval()

    evaluation = resources.evaluator.solution(initial)
    state = _SearchState(
        initial, evaluation, initial, evaluation, config.initial_temperature
    )
    operator = EjectionRepair(
        max_ejections=0 if policy == "beam" else 2,
        risk_aware=policy == "risk_ejection",
        beam_width=beam_width,
        max_evaluations=max_evaluations,
    )
    operator.deadline = deadline

    counts = dict(
        iterations=0,
        unchanged=0,
        attempts=0,
        repair_success=0,
        chain_success=0,
        reduced_k=0,
        route_evaluations=0,
        late_candidates=0,
    )

    while time.perf_counter() < deadline:
        q = int(rng.integers(config.q_min, config.q_max + 1))
        destroy_name = resources.destroy_pool.select(rng)
        repair_name = resources.repair_pool.select(rng)

        destroyed = resources.destroy_by_name[destroy_name].apply(
            state.current, instance, resources.evaluator, rng, q
        )
        repaired = None

        if destroy_name == "route" and policy in ("beam", "ejection", "risk_ejection"):
            counts["attempts"] += 1
            repaired = operator.apply(
                destroyed.partial, destroyed.removed, resources.repair_context
            )
            counts["route_evaluations"] += operator.evaluations

            if repaired.success:
                counts["repair_success"] += 1
                counts["chain_success"] += int(operator.used_ejections > 0)

        if time.perf_counter() >= deadline:
            counts["late_candidates"] += 1
            break

        if repaired is None or not repaired.success:
            repaired = resources.repair_by_name[repair_name].apply(
                destroyed.partial, destroyed.removed, resources.repair_context
            )

        # Never credit candidates completed after the common deadline.
        if time.perf_counter() >= deadline:
            counts["late_candidates"] += 1
            break

        if repaired.success and repaired.solution is not None:
            counts["unchanged"] += int(repaired.solution == state.current)
            counts["reduced_k"] += int(
                len(repaired.solution.routes) < len(state.current.routes)
            )

        previous = replace(state)
        reward = _candidate_reward(repaired, state, resources.evaluator, config, rng)

        if time.perf_counter() >= deadline:
            state = previous
            counts["late_candidates"] += 1
            break

        resources.destroy_pool.record(destroy_name, reward)
        resources.repair_pool.record(repair_name, reward)

        counts["iterations"] += 1

        if counts["iterations"] % config.segment_length == 0:
            resources.destroy_pool.update_segment()
            resources.repair_pool.update_segment()

        state.temperature = cool_temperature(
            state.temperature, config.cooling_rate, config.minimum_temperature
        )

    result = _audit_best_solution(instance, state.best, d_ref, config)

    return dict(
        instance=instance.name,
        seed=seed,
        policy=policy,
        budget_seconds=seconds,
        max_evaluations=max_evaluations,
        beam_width=beam_width,
        vehicles=result.vehicle_count,
        objective=result.objective,
        distance=result.distance,
        risk_delay=result.risk_delay,
        feasible=result.feasible,
        runtime=time.perf_counter() - started,
        **counts,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", nargs="+", default=["c101", "r101", "rc101"])
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--seconds", type=float, default=2.0)

    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=POLICIES)
    parser.add_argument("--max-evaluations", type=int, default=2000)
    parser.add_argument("--beam-width", type=int, default=4)

    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if min(args.seeds, args.seconds, args.max_evaluations, args.beam_width) <= 0:
        parser.error("budgets, seeds, and beam width must be positive")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = None

        for name in args.instances:
            instance = parse_instance(
                ROOT / "dataset/solomon_risk" / f"{name}.txt", 100, 5
            )

            for seed in range(args.seeds):
                # Rotate order to avoid assigning one policy a fixed run position.
                policies = (
                    args.policies[seed % len(args.policies) :]
                    + args.policies[: seed % len(args.policies)]
                )

                for policy in policies:
                    row = run(
                        instance,
                        seed,
                        policy,
                        args.seconds,
                        args.max_evaluations,
                        args.beam_width,
                    )

                    if writer is None:
                        writer = csv.DictWriter(handle, fieldnames=row)
                        writer.writeheader()

                    writer.writerow(row)
                    handle.flush()

                    print(
                        name,
                        seed,
                        policy,
                        row["vehicles"],
                        round(row["objective"], 5),
                        row["chain_success"],
                        flush=True,
                    )


if __name__ == "__main__":
    main()
