"""Reproducible benchmark over scenarios, seeds and policies.

Each (scenario, seed, policy) job runs one rolling-horizon simulation. One
clairvoyant job per (scenario, seed) solves the fully revealed instance with the
same iteration budget and provides the reference objective for the gap.
"""

import argparse
import glob
import json
import math
import shutil
import statistics
import sys
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path

from uav_routing.alns import SearchInvariantError
from uav_routing.config import ALNSConfig
from uav_routing.experiment import (
    _create_run_directory,
    _read_result,
    _sample_standard_deviation,
    _write_csv_atomic,
    _write_json_atomic,
)
from uav_routing.initial import InitialSolutionError, build_initial_solution

from .config import POLICIES, RollingHorizonConfig
from .horizon import decision_times, effective_epoch_length, run_rolling_horizon
from .models import CustomerArrival
from .policies import solve_clairvoyant
from .scenario import base_instance, load_scenario

RAW_FIELDS = (
    "scenario",
    "instance",
    "static_customers",
    "dynamic_customers",
    "degree_of_dynamism",
    "policy",
    "trigger",
    "epoch_length",
    "seed",
    "epochs",
    "total_iterations",
    "budget",
    "vehicles",
    "distance",
    "risk_delay",
    "objective",
    "unserved",
    "unserved_ids",
    "unserved_priority",
    "clairvoyant_objective",
    "clairvoyant_vehicles",
    "gap",
    "runtime_seconds",
    "runtime_per_epoch_mean",
    "feasible",
    "routes",
)

SUMMARY_METRICS = (
    "vehicles",
    "distance",
    "risk_delay",
    "objective",
    "unserved",
    "gap",
    "runtime_seconds",
)

AGGREGATE_FIELDS = (
    "scenario",
    "policy",
    "trigger",
    "epoch_length",
    "runs",
    *(
        f"{metric}_{statistic}"
        for metric in SUMMARY_METRICS
        for statistic in ("mean", "std", "best", "worst")
    ),
)


@dataclass(frozen=True)
class DynamicBenchmarkConfig:
    scenario_paths: tuple[Path, ...]
    seeds: tuple[int, ...]
    policies: tuple[str, ...]
    alns: ALNSConfig
    rolling: RollingHorizonConfig
    checkpoint_dir: Path | None = None
    workers: int = 1


def run_dynamic_benchmark(
    config: DynamicBenchmarkConfig, runner: Callable | None = None
) -> list[dict[str, object]]:
    _validate_config(config)

    run_policy = runner or _run_policy
    jobs = _jobs(config)

    if config.workers == 1:
        outputs = {key: _execute(key, config, run_policy) for key in jobs}
    else:
        outputs = _run_parallel(jobs, config, run_policy)

    rows = _assemble_rows(jobs, outputs)

    if config.checkpoint_dir is not None:
        write_dynamic_results(rows, config.checkpoint_dir)

    return rows


def write_dynamic_results(
    rows: list[dict[str, object]], output_dir: Path
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_path = output_dir / "raw.csv"
    aggregate_path = output_dir / "aggregate.csv"

    _write_csv_atomic(raw_path, RAW_FIELDS, [_csv_row(row) for row in rows])
    _write_csv_atomic(aggregate_path, AGGREGATE_FIELDS, _aggregate(rows))

    return raw_path, aggregate_path


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    print("Dynamic Benchmark Started", file=sys.stderr)

    try:
        config = _config_from_args(args)
        rows = run_dynamic_benchmark(config)
        raw, aggregate = write_dynamic_results(rows, args.output_dir)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        parser.error(str(exc))

    print("Dynamic Benchmark Completed", file=sys.stderr)
    print(f"completed {len(rows)} runs; raw={raw}; aggregate={aggregate}")

    return 0


# --- jobs -------------------------------------------------------------------

JobKey = tuple[str, Path, int, str]


def _jobs(config: DynamicBenchmarkConfig) -> list[JobKey]:
    jobs: list[JobKey] = []

    for scenario_path in config.scenario_paths:
        for seed in config.seeds:
            jobs.append(("clairvoyant", scenario_path, seed, ""))

            for policy in config.policies:
                jobs.append(("policy", scenario_path, seed, policy))

    return jobs


def _execute(
    key: JobKey, config: DynamicBenchmarkConfig, run_policy: Callable
) -> dict[str, object]:
    kind, scenario_path, seed, policy = key
    budget = _budget(scenario_path, config.rolling)

    if kind == "clairvoyant":
        return _run_clairvoyant(scenario_path, seed, config.alns, budget)

    row = run_policy(scenario_path, seed, policy, config.alns, config.rolling, budget)

    if not bool(row.get("feasible")):
        raise RuntimeError(
            f"infeasible realized solution: {scenario_path} seed={seed} policy={policy}"
        )

    return dict(row)


def _run_parallel(
    jobs: list[JobKey], config: DynamicBenchmarkConfig, run_policy: Callable
) -> dict[JobKey, dict[str, object]]:
    run_dir = _create_run_directory(config.checkpoint_dir)
    paths = {key: run_dir / f"{index:04d}.json" for index, key in enumerate(jobs)}

    try:
        with ProcessPoolExecutor(max_workers=config.workers) as executor:
            futures = {
                executor.submit(_execute, key, config, run_policy): key for key in jobs
            }

            try:
                for future in as_completed(futures):
                    _write_json_atomic(paths[futures[future]], future.result())
            except BaseException:
                for future in futures:
                    future.cancel()

                raise

        outputs = {key: _read_result(paths[key]) for key in jobs}
    except BaseException:
        raise
    else:
        shutil.rmtree(run_dir)

        try:
            run_dir.parent.rmdir()
        except OSError:
            pass

    return outputs


def _assemble_rows(
    jobs: list[JobKey], outputs: dict[JobKey, dict[str, object]]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for key in jobs:
        kind, scenario_path, seed, _ = key

        if kind != "policy":
            continue

        clairvoyant = outputs[("clairvoyant", scenario_path, seed, "")]
        row = dict(outputs[key])
        reference = float(clairvoyant["objective"])

        row["clairvoyant_objective"] = reference
        row["clairvoyant_vehicles"] = clairvoyant["vehicles"]
        row["gap"] = (
            (float(row["objective"]) - reference) / reference
            if math.isfinite(reference) and reference > 0
            else math.nan
        )

        rows.append(row)

    return rows


def _budget(scenario_path: Path, rolling: RollingHorizonConfig) -> int:
    scenario = load_scenario(scenario_path)
    epochs = len(decision_times(scenario, rolling))

    return rolling.iterations_epoch0 + epochs * rolling.iterations_per_epoch


def _run_policy(
    scenario_path: Path,
    seed: int,
    policy: str,
    alns: ALNSConfig,
    rolling: RollingHorizonConfig,
    budget: int,
) -> dict[str, object]:
    scenario = load_scenario(scenario_path)
    config = replace(rolling, policy=policy, seed=seed)
    result = run_rolling_horizon(scenario, alns, config)
    evaluation = result.evaluation

    dynamic = sum(isinstance(event, CustomerArrival) for event in scenario.events)
    epoch_runtimes = [record.runtime_seconds for record in result.epochs]

    return {
        "scenario": scenario.name,
        "instance": scenario.instance_path.name,
        "static_customers": scenario.static_customers,
        "dynamic_customers": dynamic,
        "degree_of_dynamism": dynamic / (scenario.static_customers + dynamic),
        "policy": policy,
        "trigger": config.trigger,
        "epoch_length": effective_epoch_length(config, scenario.horizon),
        "seed": seed,
        "epochs": len(result.epochs),
        "total_iterations": result.total_iterations,
        "budget": budget,
        "vehicles": evaluation.vehicle_count,
        "distance": float(evaluation.distance),
        "risk_delay": float(evaluation.risk_delay),
        "objective": float(evaluation.objective),
        "unserved": len(result.unserved),
        "unserved_ids": list(result.unserved),
        "unserved_priority": float(result.unserved_priority),
        "runtime_seconds": float(result.runtime_seconds),
        "runtime_per_epoch_mean": statistics.fmean(epoch_runtimes),
        "feasible": bool(evaluation.feasible),
        "routes": [list(route) for route in result.realized.routes],
    }


def _run_clairvoyant(
    scenario_path: Path, seed: int, alns: ALNSConfig, budget: int
) -> dict[str, object]:
    scenario = load_scenario(scenario_path)
    _, d_ref = build_initial_solution(base_instance(scenario), alns.alpha, alns.beta)

    try:
        result = solve_clairvoyant(scenario, alns, max(1, budget), seed, d_ref)
    except (InitialSolutionError, SearchInvariantError):
        return {"objective": math.nan, "vehicles": math.nan, "feasible": False}

    return {
        "objective": float(result.evaluation.objective),
        "vehicles": result.evaluation.vehicle_count,
        "feasible": bool(result.evaluation.feasible),
    }


# --- output -----------------------------------------------------------------


def _csv_row(row: dict[str, object]) -> dict[str, object]:
    csv_row = dict(row)
    csv_row["unserved_ids"] = json.dumps(row["unserved_ids"], separators=(",", ":"))

    return csv_row


def _aggregate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}

    for row in rows:
        key = (row["scenario"], row["policy"], row["trigger"], row["epoch_length"])
        grouped.setdefault(key, []).append(row)

    aggregate: list[dict[str, object]] = []

    for key, group in grouped.items():
        result: dict[str, object] = dict(zip(AGGREGATE_FIELDS[:4], key, strict=True))
        result["runs"] = len(group)

        for metric in SUMMARY_METRICS:
            result.update(_summary(metric, group))

        aggregate.append(result)

    return aggregate


def _summary(metric: str, rows: list[dict[str, object]]) -> dict[str, float]:
    values = [float(row[metric]) for row in rows]
    finite = [value for value in values if math.isfinite(value)]

    if not finite:
        return {
            f"{metric}_{statistic}": math.nan
            for statistic in ("mean", "std", "best", "worst")
        }

    return {
        f"{metric}_mean": statistics.fmean(finite),
        f"{metric}_std": _sample_standard_deviation(finite),
        f"{metric}_best": min(finite),
        f"{metric}_worst": max(finite),
    }


# --- configuration ----------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uav-routing-dynamic-benchmark")

    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--policies", nargs="+", choices=POLICIES)
    parser.add_argument("--iterations-epoch0", type=int)
    parser.add_argument("--iterations-per-epoch", type=int)
    parser.add_argument("--epoch-length", type=float)
    parser.add_argument("--epoch-fraction", type=float)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=Path("results/dynamic"))

    return parser


def _config_from_args(args: argparse.Namespace) -> DynamicBenchmarkConfig:
    config = _load_config(args.config)
    rolling = config.rolling

    if args.iterations_epoch0 is not None:
        rolling = replace(rolling, iterations_epoch0=args.iterations_epoch0)

    if args.iterations_per_epoch is not None:
        rolling = replace(rolling, iterations_per_epoch=args.iterations_per_epoch)

    if args.epoch_length is not None:
        rolling = replace(rolling, epoch_length=args.epoch_length, epoch_fraction=None)

    if args.epoch_fraction is not None:
        rolling = replace(rolling, epoch_fraction=args.epoch_fraction)

    return replace(
        config,
        seeds=tuple(args.seeds) if args.seeds is not None else config.seeds,
        policies=(
            tuple(args.policies) if args.policies is not None else config.policies
        ),
        rolling=rolling,
        checkpoint_dir=args.output_dir,
        workers=args.workers,
    )


def _load_config(path: Path) -> DynamicBenchmarkConfig:
    values = json.loads(path.read_text(encoding="utf-8"))
    base_dir = path.resolve().parent

    return DynamicBenchmarkConfig(
        scenario_paths=_expand_scenarios(values["scenarios"], base_dir),
        seeds=tuple(int(value) for value in values["seeds"]),
        policies=tuple(str(value) for value in values.get("policies", POLICIES)),
        alns=ALNSConfig.from_dict(values.get("alns", {})),
        rolling=RollingHorizonConfig.from_dict(values.get("rolling", {})),
    )


def _expand_scenarios(patterns: list[str], base_dir: Path) -> tuple[Path, ...]:
    paths: list[Path] = []

    for pattern in patterns:
        candidate = Path(pattern)

        if not candidate.is_absolute():
            candidate = base_dir / candidate

        matches = sorted(Path(match) for match in glob.glob(str(candidate)))
        paths.extend(matches or [candidate])

    return tuple(paths)


def _validate_config(config: DynamicBenchmarkConfig) -> None:
    if not config.scenario_paths:
        raise ValueError("benchmark requires at least one scenario")

    if not config.seeds:
        raise ValueError("benchmark requires at least one seed")

    if not config.policies:
        raise ValueError("benchmark requires at least one policy")

    unknown = [policy for policy in config.policies if policy not in POLICIES]

    if unknown:
        raise ValueError(f"unknown policies: {unknown}")

    if config.workers <= 0:
        raise ValueError("workers must be positive")

    config.alns.validate()
    config.rolling.validate()


if __name__ == "__main__":
    raise SystemExit(main())
