"""Command-line interface for simulating one dynamic scenario."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from uav_routing.alns import SearchInvariantError
from uav_routing.cli import _route_to_dict, _write_json_atomic
from uav_routing.config import ALNSConfig
from uav_routing.contextual.config import ContextualBanditConfig
from uav_routing.initial import InitialSolutionError

from .config import POLICIES, TRIGGERS, RollingHorizonConfig
from .horizon import effective_epoch_length, run_rolling_horizon
from .models import (
    CustomerArrival,
    DeadlineUpdate,
    EpochRecord,
    RiskUpdate,
    Scenario,
    SimulationResult,
)
from .scenario import load_scenario

EVENT_NAMES = {
    CustomerArrival: "customer_arrival",
    RiskUpdate: "risk_update",
    DeadlineUpdate: "deadline_update",
}


def simulation_to_dict(
    result: SimulationResult,
    scenario: Scenario,
    config: RollingHorizonConfig,
    alns: ALNSConfig,
    bandit: ContextualBanditConfig | None = None,
) -> dict[str, object]:
    evaluation = result.evaluation
    routes = [
        _route_to_dict(index, route, route_evaluation)
        for index, (route, route_evaluation) in enumerate(
            zip(result.realized.routes, evaluation.routes, strict=True), start=1
        )
    ]

    return {
        "scenario": scenario.name,
        "instance": scenario.instance_path.name,
        "static_customers": scenario.static_customers,
        "dynamic_customers": sum(
            isinstance(event, CustomerArrival) for event in scenario.events
        ),
        "events": len(scenario.events),
        "risks": scenario.risk_limit,
        "horizon": float(scenario.horizon),
        "policy": result.policy,
        "trigger": config.trigger,
        "epoch_length": effective_epoch_length(config, scenario.horizon),
        "epoch_fraction": config.epoch_fraction,
        "seed": result.seed,
        "iterations_epoch0": config.iterations_epoch0,
        "iterations_per_epoch": config.iterations_per_epoch,
        "total_iterations": result.total_iterations,
        "alpha": float(alns.alpha),
        "beta": float(alns.beta),
        "contextual_bandit": asdict(bandit) if bandit is not None else None,
        "d_ref": float(result.d_ref),
        "vehicles": evaluation.vehicle_count,
        "distance": float(evaluation.distance),
        "risk_delay": float(evaluation.risk_delay),
        "objective": float(evaluation.objective),
        "feasible": bool(evaluation.feasible),
        "unserved": list(result.unserved),
        "unserved_priority": float(result.unserved_priority),
        "runtime_seconds": float(result.runtime_seconds),
        "epochs": [_epoch_to_dict(record) for record in result.epochs],
        "routes": routes,
    }


def _epoch_to_dict(record: EpochRecord) -> dict[str, object]:
    revealed = {name: 0 for name in EVENT_NAMES.values()}

    for event in record.revealed:
        revealed[EVENT_NAMES[type(event)]] += 1

    return {
        "index": record.index,
        "time": float(record.time),
        "revealed": revealed,
        "locked_customers": record.locked_customers,
        "rejected": list(record.rejected),
        "vehicles": record.evaluation.vehicle_count,
        "distance": float(record.evaluation.distance),
        "risk_delay": float(record.evaluation.risk_delay),
        "objective": float(record.evaluation.objective),
        "iterations": record.iterations,
        "runtime_seconds": float(record.runtime_seconds),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    print("Simulation Started", file=sys.stderr)

    try:
        payload = _simulate(args)
    except (
        FileNotFoundError,
        OSError,
        ValueError,
        InitialSolutionError,
        SearchInvariantError,
    ) as exc:
        parser.error(str(exc))

    print("Simulation Completed", file=sys.stderr)
    print(json.dumps(payload, ensure_ascii=False))

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uav-routing-dynamic")
    subparsers = parser.add_subparsers(dest="command", required=True)
    simulate = subparsers.add_parser("simulate", help="simulate one dynamic scenario")

    simulate.add_argument("--scenario", type=Path, required=True)
    simulate.add_argument("--policy", choices=POLICIES, default="warm_alns")
    simulate.add_argument("--trigger", choices=TRIGGERS, default="periodic")
    simulate.add_argument("--epoch-length", type=float, default=60.0)
    simulate.add_argument("--epoch-fraction", type=float)
    simulate.add_argument("--iterations-epoch0", type=int, default=2_000)
    simulate.add_argument("--iterations-per-epoch", type=int, default=500)
    simulate.add_argument("--seed", type=int, default=42)
    simulate.add_argument("--alpha", type=float, default=0.5)
    simulate.add_argument("--beta", type=float, default=0.5)
    simulate.add_argument("--context-window", type=int, default=100)
    simulate.add_argument("--linucb-exploration", type=float, default=0.5)
    simulate.add_argument("--linucb-regularization", type=float, default=1.0)

    simulate.add_argument("--exclude-temperature", action="store_true")
    simulate.add_argument("--short-route-warm-start", action="store_true")
    simulate.add_argument("--output", type=Path)

    return parser


def _simulate(args: argparse.Namespace) -> dict[str, object]:
    alns = ALNSConfig(alpha=args.alpha, beta=args.beta, seed=args.seed)
    config = RollingHorizonConfig(
        policy=args.policy,
        trigger=args.trigger,
        epoch_length=args.epoch_length,
        epoch_fraction=args.epoch_fraction,
        iterations_epoch0=args.iterations_epoch0,
        iterations_per_epoch=args.iterations_per_epoch,
        seed=args.seed,
    )
    bandit = None

    if args.policy == "contextual_warm_alns":
        bandit = ContextualBanditConfig(
            context_window=args.context_window,
            linucb_exploration=args.linucb_exploration,
            linucb_regularization=args.linucb_regularization,
            include_temperature=not args.exclude_temperature,
            short_route_warm_start=args.short_route_warm_start,
        )

    alns.validate()
    config.validate()

    scenario = load_scenario(args.scenario)
    result = run_rolling_horizon(scenario, alns, config, bandit=bandit)
    payload = simulation_to_dict(result, scenario, config, alns, bandit)

    if args.output is not None:
        _write_json_atomic(args.output, payload)

    return payload


if __name__ == "__main__":
    raise SystemExit(main())
