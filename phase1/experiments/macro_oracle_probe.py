"""Measure one-step selection headroom on shared search states."""

import argparse
import csv
from pathlib import Path

import numpy as np
from contextual_policy_ablation import ROOT, _reward, macro_actions, run

from uav_routing.config import ALNSConfig
from uav_routing.evaluator import Evaluator
from uav_routing.initial import build_initial_solution
from uav_routing.parser import parse_instance
from uav_routing.repair import RepairContext


def probe_instance(instance, seed, iterations, samples):
    config = ALNSConfig(iterations=iterations, segment_length=20, seed=seed)
    snapshots = []

    def collect(iteration, solution, evaluation):
        if iteration in samples:
            snapshots.append((iteration, solution, evaluation))

    run(
        instance,
        config,
        "roulette",
        snapshot_callback=collect,
        include_risk_relocate=False,
    )
    _, d_ref = build_initial_solution(instance, config.alpha, config.beta)
    evaluator = Evaluator(instance, d_ref, config.alpha, config.beta)
    context = RepairContext(instance, evaluator, d_ref, config.alpha, config.beta)
    actions = macro_actions(config, include_risk_relocate=False)
    rows = []

    for iteration, solution, evaluation in snapshots:
        for action in actions:
            outcomes = []

            for repetition in range(2):
                rng = np.random.default_rng(seed * 10000 + iteration * 100 + repetition)
                q = int(rng.integers(action.q_min, action.q_max + 1))
                destroyed = action.destroy.apply(solution, instance, evaluator, rng, q)
                repaired = action.repair.apply(
                    destroyed.partial, destroyed.removed, context
                )
                reward = 0.0

                if repaired.success and repaired.solution is not None:
                    candidate = evaluator.solution(repaired.solution)

                    if candidate.feasible:
                        reward = _reward(
                            candidate, evaluation, evaluation, None, config, True
                        )

                outcomes.append(reward)

            rows.append((iteration, action.name, sum(outcomes) / len(outcomes)))

    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", nargs="+", default=["c101", "r101", "rc101"])
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []

    for name in args.instances:
        instance = parse_instance(
            ROOT / "dataset/solomon_risk" / f"{name}.txt", 100, 5
        )

        for seed in range(args.seeds):
            outcomes = probe_instance(instance, seed, 50, (0, 20, 40))
            rows.extend((name, seed, *row) for row in outcomes)
            print(name, seed, flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("instance", "seed", "iteration", "action", "reward"))
        writer.writerows(rows)


if __name__ == "__main__":
    main()
