"""Train shared contextual prior on C101/R101/RC101, evaluate transfer."""

import argparse
import csv
from pathlib import Path

import numpy as np
from contextual_policy_ablation import ROOT, run

from uav_routing.config import ALNSConfig
from uav_routing.parser import parse_instance

TRAIN_INSTANCES = ("c101", "r101", "rc101")
TEST_INSTANCES = ("c103", "r103", "rc103")


def train_prior():
    prior = None

    for name in TRAIN_INSTANCES:
        instance = parse_instance(
            ROOT / "dataset/solomon_risk" / f"{name}.txt", 100, 5
        )

        for seed in range(3):
            config = ALNSConfig(iterations=100, segment_length=20, seed=seed)
            _, _, prior = run(instance, config, "shared_dense", shared_prior=prior)
            print("train", name, seed, flush=True)

    return prior


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.prior.exists():
        saved = np.load(args.prior)
        prior = saved["inverse"], saved["reward_vector"]
    else:
        prior = train_prior()
        args.prior.parent.mkdir(parents=True, exist_ok=True)
        np.savez(args.prior, inverse=prior[0], reward_vector=prior[1])

    rows = []

    for name in TEST_INSTANCES:
        instance = parse_instance(
            ROOT / "dataset/solomon_risk" / f"{name}.txt", 100, 5
        )

        for seed in range(args.seed_start, args.seed_start + args.seeds):
            config = ALNSConfig(iterations=100, segment_length=20, seed=seed)
            evaluation, runtime, _ = run(
                instance, config, "shared_dense", shared_prior=prior
            )
            rows.append((
                name, seed, evaluation.vehicle_count, evaluation.objective,
                evaluation.distance, evaluation.risk_delay, runtime,
            ))
            print("test", name, seed, evaluation.score, flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow((
            "instance", "seed", "vehicles", "objective",
            "distance", "risk_delay", "runtime",
        ))
        writer.writerows(rows)


if __name__ == "__main__":
    main()
