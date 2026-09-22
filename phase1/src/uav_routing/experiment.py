"""Reproducible multi-instance benchmark runner."""

import argparse
import csv
import json
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from .alns import run_alns
from .cli import result_to_dict
from .config import ALNSConfig
from .parser import parse_instance

RAW_FIELDS = (
    "instance",
    "customers",
    "risks",
    "seed",
    "iterations",
    "vehicles",
    "distance",
    "risk_delay",
    "objective",
    "runtime_seconds",
    "feasible",
)

AGGREGATE_FIELDS = (
    "instance",
    "customers",
    "risks",
    "iterations",
    "alpha",
    "beta",
    "runs",
    "vehicles_mean",
    "vehicles_std",
    "vehicles_best",
    "vehicles_worst",
    "distance_mean",
    "distance_std",
    "distance_best",
    "distance_worst",
    "risk_delay_mean",
    "risk_delay_std",
    "risk_delay_best",
    "risk_delay_worst",
    "objective_mean",
    "objective_std",
    "objective_best",
    "objective_worst",
    "runtime_mean",
    "runtime_std",
)


@dataclass(frozen=True)
class BenchmarkConfig:
    instance_paths: tuple[Path, ...]
    seeds: tuple[int, ...]
    alns: ALNSConfig
    customer_limit: int = 25
    risk_limit: int = 5
    checkpoint_dir: Path | None = None


def run_benchmark(
    config: BenchmarkConfig, solver: Callable | None = None
) -> list[dict[str, object]]:
    _validate_benchmark_config(config)

    solve = solver or _solve_one
    rows: list[dict[str, object]] = []

    for instance_path in config.instance_paths:
        for seed in config.seeds:
            alns = replace(config.alns, seed=seed)
            
            alns.validate()

            row = solve(
                instance_path,
                alns,
                config.customer_limit,
                config.risk_limit,
            )

            if not bool(row["feasible"]):
                raise RuntimeError(
                    f"infeasible benchmark run: {instance_path} seed={seed}"
                )

            rows.append(dict(row))

            if config.checkpoint_dir is not None:
                write_results(rows, config.checkpoint_dir)

    return rows


def write_results(rows: list[dict[str, object]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_path = output_dir / "raw.csv"
    aggregate_path = output_dir / "aggregate.csv"

    _write_csv_atomic(raw_path, RAW_FIELDS, rows)
    _write_csv_atomic(aggregate_path, AGGREGATE_FIELDS, _aggregate(rows))

    return raw_path, aggregate_path


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    print("Benchmark Started", file=sys.stderr)

    try:
        config = _benchmark_config_from_args(args)
        rows = run_benchmark(config)
        raw, aggregate = write_results(rows, args.output_dir)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        parser.error(str(exc))

    print("Benchmark Completed", file=sys.stderr)
    print(f"completed {len(rows)} runs; raw={raw}; aggregate={aggregate}")

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uav-routing-benchmark")

    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--output-dir", type=Path, default=Path("results"))

    return parser


def _benchmark_config_from_args(args: argparse.Namespace) -> BenchmarkConfig:
    config = _load_config(args.config)
    alns = config.alns

    if args.iterations is not None:
        alns = replace(alns, iterations=args.iterations)

    seeds = tuple(args.seeds) if args.seeds is not None else config.seeds

    return replace(
        config,
        seeds=seeds,
        alns=alns,
        checkpoint_dir=args.output_dir,
    )


def _solve_one(
    path: Path,
    config: ALNSConfig,
    customer_limit: int,
    risk_limit: int,
) -> dict[str, object]:
    instance = parse_instance(path, customer_limit, risk_limit)
    result = run_alns(instance, config)
    payload = result_to_dict(result, instance, config)

    return {key: payload[key] for key in (*RAW_FIELDS, "alpha", "beta")}


def _aggregate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}

    for row in rows:
        key = (
            row["instance"],
            row["customers"],
            row["risks"],
            row["iterations"],
            row["alpha"],
            row["beta"],
        )
        grouped.setdefault(key, []).append(row)

    aggregate: list[dict[str, object]] = []

    for key, group in grouped.items():
        aggregate.append(_aggregate_group(key, group))

    return aggregate


def _aggregate_group(
    key: tuple[object, ...], group: list[dict[str, object]]
) -> dict[str, object]:
    result: dict[str, object] = dict(zip(AGGREGATE_FIELDS[:6], key, strict=True))
    result["runs"] = len(group)

    for field in ("vehicles", "distance", "risk_delay", "objective"):
        result.update(_summary_statistics(field, group))

    runtimes = [float(row["runtime_seconds"]) for row in group]
    result["runtime_mean"] = statistics.fmean(runtimes)
    result["runtime_std"] = _sample_standard_deviation(runtimes)

    return result


def _summary_statistics(field: str, rows: list[dict[str, object]]) -> dict[str, float]:
    values = [float(row[field]) for row in rows]

    return {
        f"{field}_mean": statistics.fmean(values),
        f"{field}_std": _sample_standard_deviation(values),
        f"{field}_best": min(values),
        f"{field}_worst": max(values),
    }


def _sample_standard_deviation(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def _write_csv_atomic(
    path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]
) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")

        writer.writeheader()
        writer.writerows(rows)

    temporary.replace(path)


def _load_config(path: Path) -> BenchmarkConfig:
    values = json.loads(path.read_text(encoding="utf-8"))

    return BenchmarkConfig(
        instance_paths=tuple(Path(value) for value in values["instances"]),
        seeds=tuple(int(value) for value in values["seeds"]),
        alns=ALNSConfig.from_dict(values["alns"]),
        customer_limit=int(values.get("customers", 25)),
        risk_limit=int(values.get("risks", 5)),
    )


def _validate_benchmark_config(config: BenchmarkConfig) -> None:
    if not config.instance_paths:
        raise ValueError("benchmark requires at least one instance")

    if not config.seeds:
        raise ValueError("benchmark requires at least one seed")

    if config.customer_limit <= 0:
        raise ValueError("customer_limit must be positive")

    if not 0 <= config.risk_limit <= 5:
        raise ValueError("risk_limit must be between 0 and 5")


if __name__ == "__main__":
    raise SystemExit(main())
