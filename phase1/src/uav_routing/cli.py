"""Command-line interface for solving one Solomon-RISK instance."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from .alns import SearchInvariantError, SearchResult, run_alns
from .config import ALNSConfig
from .contextual.alns import ContextualSearchResult, run_contextual_alns
from .contextual.config import ContextualBanditConfig
from .initial import InitialSolutionError
from .models import Instance, Route, RouteEvaluation
from .parser import InstanceFormatError, parse_instance


def result_to_dict(
    result: SearchResult | ContextualSearchResult,
    instance: Instance,
    config: ALNSConfig,
    bandit_config: ContextualBanditConfig | None = None,
) -> dict[str, object]:
    evaluation = result.evaluation

    routes = [
        _route_to_dict(route_index, route, route_evaluation)
        for route_index, (route, route_evaluation) in enumerate(
            zip(result.best_solution.routes, evaluation.routes, strict=True), start=1
        )
    ]

    if isinstance(result, ContextualSearchResult):
        if bandit_config is None:
            raise ValueError("bandit_config is required for contextual results")

        algorithm = "contextual"
        contextual_bandit = asdict(bandit_config)

        operators = []
        pair_selection_stats = [asdict(stats) for stats in result.pair_selection_stats]
    else:
        algorithm = "baseline"
        contextual_bandit = None
        pair_selection_stats = []

        operators = [
            {
                "name": stats.name,
                "weight": float(stats.weight),
                "total_uses": stats.total_uses,
                "segment_uses": stats.segment_uses,
                "segment_score": float(stats.segment_score),
            }
            for stats in result.operator_stats
        ]

    return {
        "algorithm": algorithm,
        "instance": instance.name,
        "customers": len(instance.customers),
        "risks": len(instance.risk_zones),
        "seed": result.seed,
        "iterations": result.iterations,
        "alpha": float(config.alpha),
        "beta": float(config.beta),
        "score_policy": config.score_policy,
        "risk_threshold": float(config.risk_threshold),
        "vehicles": evaluation.vehicle_count,
        "distance": float(evaluation.distance),
        "risk_delay": float(evaluation.risk_delay),
        "objective": float(evaluation.objective),
        "runtime_seconds": float(result.runtime_seconds),
        "feasible": bool(evaluation.feasible),
        "contextual_bandit": contextual_bandit,
        "operators": operators,
        "pair_selection_stats": pair_selection_stats,
        "routes": routes,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    print("ALNS Started", file=sys.stderr)

    try:
        payload = _solve(args)
    except (
        FileNotFoundError,
        OSError,
        ValueError,
        InstanceFormatError,
        InitialSolutionError,
        SearchInvariantError,
    ) as exc:
        parser.error(str(exc))

    print("ALNS Completed", file=sys.stderr)
    print(json.dumps(payload, ensure_ascii=False))

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uav-routing")
    subparsers = parser.add_subparsers(dest="command", required=True)
    solve = subparsers.add_parser("solve", help="solve one Solomon-RISK instance")

    solve.add_argument("--instance", type=Path, required=True)
    solve.add_argument("--customers", type=int, default=25)
    solve.add_argument("--risks", type=int, choices=range(6), default=5)
    solve.add_argument("--iterations", type=int, default=10_000)
    solve.add_argument("--seed", type=int, default=42)
    solve.add_argument("--alpha", type=float, default=0.5)
    solve.add_argument("--beta", type=float, default=0.5)
    solve.add_argument(
        "--score-policy",
        choices=("lexicographic", "emergency_gate"),
        default="lexicographic",
    )
    solve.add_argument("--risk-threshold", type=float, default=0.2)
    solve.add_argument(
        "--algorithm", choices=("baseline", "contextual"), default="baseline"
    )
    solve.add_argument("--short-route-warm-start", action="store_true")
    solve.add_argument("--output", type=Path)

    return parser


def _solve(args: argparse.Namespace) -> dict[str, object]:
    config = ALNSConfig(
        iterations=args.iterations,
        seed=args.seed,
        alpha=args.alpha,
        beta=args.beta,
        score_policy=args.score_policy,
        risk_threshold=args.risk_threshold,
    )
    config.validate()

    instance = parse_instance(args.instance, args.customers, args.risks)

    if args.algorithm == "contextual":
        bandit_config = ContextualBanditConfig(
            short_route_warm_start=args.short_route_warm_start
        )
        result = run_contextual_alns(instance, config, bandit_config)
        payload = result_to_dict(result, instance, config, bandit_config)
    else:
        if args.short_route_warm_start:
            raise ValueError("--short-route-warm-start requires --algorithm contextual")

        result = run_alns(instance, config)
        payload = result_to_dict(result, instance, config)

    if args.output is not None:
        _write_json_atomic(args.output, payload)

    return payload


def _route_to_dict(
    route_index: int,
    route: Route,
    route_evaluation: RouteEvaluation,
) -> dict[str, object]:
    return {
        "route_index": route_index,
        "customers": list(route),
        "distance": float(route_evaluation.distance),
        "load": float(route_evaluation.load),
        "depot_return": float(route_evaluation.depot_return),
        "schedule": [
            {
                "customer_id": stop.customer_id,
                "arrival": float(stop.arrival),
                "service_start": float(stop.service_start),
                "departure": float(stop.departure),
            }
            for stop in route_evaluation.schedule
        ],
    }


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
