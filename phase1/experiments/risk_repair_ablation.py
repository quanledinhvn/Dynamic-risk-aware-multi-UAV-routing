"""Compare risk-aware neighborhoods on baseline and contextual ALNS."""

import argparse
import csv
from dataclasses import replace
from pathlib import Path

from uav_routing.alns import ALNSSolver, _operators
from uav_routing.config import ALNSConfig
from uav_routing.contextual.alns import run_contextual_alns
from uav_routing.contextual.config import ContextualBanditConfig
from uav_routing.experimental import (
    AbsorbableRouteRemoval,
    RiskRegretRepair,
    RouteEliminationRepair,
)
from uav_routing.parser import parse_instance

ROOT = Path(__file__).resolve().parents[2]
POLICIES = (
    "original",
    "risk_regret",
    "guided_destroy",
    "strict_repair",
    "route_elimination",
    "combined",
)


def portfolio(config: ALNSConfig, policy: str):
    destroys, repairs = _operators(config, None, None)

    if policy in ("guided_destroy", "route_elimination", "combined"):
        destroys = tuple(
            AbsorbableRouteRemoval() if op.name == "route" else op
            for op in destroys
        )

    if policy in ("risk_regret", "combined"):
        repairs = tuple(
            RiskRegretRepair() if op.name == "risk_priority" else op
            for op in repairs
        )

    if policy in ("strict_repair", "route_elimination", "combined"):
        repairs += (RouteEliminationRepair(),)

    return destroys, repairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", nargs="+", default=["c101", "r101", "rc101"])
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=POLICIES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.seeds <= 0 or args.iterations <= 0:
        parser.error("seeds and iterations must be positive")

    config = ALNSConfig(iterations=args.iterations, segment_length=20)
    bandit = ContextualBanditConfig(
        context_window=10,
        linucb_exploration=1.0,
        linucb_regularization=0.25,
    )
    rows = []

    for name in args.instances:
        instance = parse_instance(
            ROOT / "dataset/solomon_risk" / f"{name}.txt", 100, 5
        )

        for seed in range(args.seeds):
            seeded = replace(config, seed=seed)

            for policy in args.policies:
                destroys, repairs = portfolio(seeded, policy)

                for algorithm in ("baseline", "contextual"):
                    if algorithm == "baseline":
                        result = ALNSSolver(
                            instance,
                            seeded,
                            destroy_operators=destroys,
                            repair_operators=repairs,
                        ).run()
                    else:
                        result = run_contextual_alns(
                            instance,
                            seeded,
                            bandit,
                            destroy_operators=destroys,
                            repair_operators=repairs,
                        )

                    evaluation = result.evaluation
                    rows.append((
                        name, seed, args.iterations, algorithm, policy,
                        evaluation.vehicle_count, evaluation.objective,
                        evaluation.distance, evaluation.risk_delay,
                        result.runtime_seconds,
                    ))

                    print(name, seed, algorithm, policy, evaluation.score, flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow((
            "instance", "seed", "iterations", "algorithm", "policy",
            "vehicles", "objective", "distance", "risk_delay", "runtime",
        ))
        writer.writerows(rows)


if __name__ == "__main__":
    main()
