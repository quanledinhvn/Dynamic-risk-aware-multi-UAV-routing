"""Small reproducible benchmark runner for raw Pareto summaries."""

import argparse
import csv
import json
import shutil
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

from .nsga3 import NSGA3Config, run_nsga3
from .parser import parse_instance

OBJECTIVE_FIELDS = (
    "vehicles",
    "distance",
    "risk_delay",
    "max_load",
    "total_lateness",
)

AGGREGATE_FIELDS = (
    "instance",
    "risk_limit",
    "runs",
    "population_size",
    "generations",
    "divisions",
    "pareto_size_mean",
    "pareto_size_std",
    *(name for field in OBJECTIVE_FIELDS for name in (
        f"{field}_mean",
        f"{field}_std",
        f"{field}_best",
        f"{field}_worst",
    )),
    "runtime_mean",
    "runtime_std",
)


@dataclass(frozen=True)
class BenchmarkConfig:
    data_dir: Path
    names: tuple[str, ...]
    seeds: tuple[int, ...]
    customer_limit: int = 25
    risk_limits: tuple[int, ...] = (5,)
    population_size: int = 28
    generations: int = 100
    divisions: int = 4
    workers: int = 1
    output: Path = Path("results/nsga3_pareto_raw.csv")


def _create_run_directory(output: Path) -> Path:
    """Create the directory that stores per-case checkpoints."""
    temporary_root = output.parent / ".tmp"
    run_dir = temporary_root / f"run-{uuid4().hex}"

    run_dir.mkdir(parents=True, exist_ok=False)

    return run_dir


def _write_checkpoint(path: Path, rows: list[dict[str, object]]) -> None:
    """Atomically write one completed benchmark case."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(rows, indent=2)

    temporary.write_text(payload + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_checkpoint(path: Path) -> list[dict[str, object]]:
    """Read one completed benchmark case."""
    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, list):
        raise ValueError(f"invalid checkpoint payload: {path}")

    if any(not isinstance(row, dict) for row in payload):
        raise ValueError(f"invalid checkpoint row: {path}")

    return [dict(row) for row in payload]


def load_benchmark_config(path: Path) -> BenchmarkConfig:
    """Load a benchmark configuration from JSON."""
    values = json.loads(path.read_text(encoding="utf-8"))
    default_data_dir = path.parent.parent / "../dataset/solomon_risk"
    configured_data_dir = Path(values.get("data_dir", default_data_dir))

    if not configured_data_dir.is_absolute() and "data_dir" in values:
        configured_data_dir = path.parent / configured_data_dir

    generations = values.get("generations", values.get("iterations", 100))
    risk_limits = values.get("risk_limits", [values.get("risk_limit", 5)])
    config = BenchmarkConfig(
        data_dir=configured_data_dir.resolve(),
        names=tuple(str(value) for value in values["instances"]),
        seeds=tuple(int(value) for value in values["seeds"]),
        customer_limit=int(values.get("customer_limit", 25)),
        risk_limits=tuple(int(value) for value in risk_limits),
        population_size=int(values.get("population_size", 28)),
        generations=int(generations),
        divisions=int(values.get("divisions", 4)),
        workers=int(values.get("workers", 1)),
        output=Path(values.get("output", "results/nsga3_pareto_raw.csv")),
    )

    _validate_benchmark_config(config)

    return config


def _build_parser() -> argparse.ArgumentParser:
    """Build the benchmark command-line parser."""
    parser = argparse.ArgumentParser(prog="uav-routing-nsga-benchmark")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--generations", "--iterations", type=int)

    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--workers", type=int)
    output = parser.add_mutually_exclusive_group()

    output.add_argument("--output", type=Path)
    output.add_argument("--output-dir", type=Path)

    return parser


def _benchmark_config_from_args(args: argparse.Namespace) -> BenchmarkConfig:
    """Apply command-line overrides to a benchmark configuration."""
    config = load_benchmark_config(args.config)
    generations = (
        args.generations if args.generations is not None else config.generations
    )
    seeds = tuple(args.seeds) if args.seeds is not None else config.seeds

    output = config.output
    if args.output is not None:
        output = args.output

    if args.output_dir is not None:
        output = args.output_dir / "nsga3_pareto_raw.csv"

    workers = args.workers if args.workers is not None else config.workers
    config = replace(
        config,
        generations=generations,
        seeds=seeds,
        workers=workers,
        output=output,
    )
    _validate_benchmark_config(config)

    return config


def main(argv: list[str] | None = None) -> int:
    """Run the configured benchmark command."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config = _benchmark_config_from_args(args)
        run_benchmark(
            data_dir=config.data_dir,
            names=config.names,
            seeds=config.seeds,
            output=config.output,
            customer_limit=config.customer_limit,
            population_size=config.population_size,
            generations=config.generations,
            divisions=config.divisions,
            risk_limits=config.risk_limits,
            workers=config.workers,
        )
    except (KeyError, OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    run_count = len(config.names) * len(config.seeds) * len(config.risk_limits)
    aggregate = config.output.with_name("aggregate.csv")
    print(
        f"Benchmark completed: {run_count} runs; "
        f"raw={config.output}; aggregate={aggregate}"
    )

    return 0


def _validate_benchmark_config(config: BenchmarkConfig) -> None:
    if not config.names:
        raise ValueError("benchmark requires at least one instance")

    if not config.seeds:
        raise ValueError("benchmark requires at least one seed")

    if config.customer_limit <= 0:
        raise ValueError("customer_limit must be positive")

    if not config.risk_limits:
        raise ValueError("benchmark requires at least one risk limit")

    if any(value < 0 or value > 5 for value in config.risk_limits):
        raise ValueError("risk limits must be between 0 and 5")

    algorithm = NSGA3Config(
        population_size=config.population_size,
        generations=config.generations,
        divisions=config.divisions,
    )
    algorithm.validate()

    if config.workers <= 0:
        raise ValueError("workers must be positive")


def aggregate_results(
    rows: list[dict[str, object]],
    population_size: int,
    generations: int,
    divisions: int,
) -> list[dict[str, object]]:
    """Aggregate per-seed Pareto summaries by instance and risk limit."""
    grouped: dict[tuple[object, object], dict[object, list[dict[str, object]]]] = {}

    for row in rows:
        key = (row["instance"], row["risk_limit"])
        grouped.setdefault(key, {}).setdefault(row["seed"], []).append(row)

    aggregate = []
    for (instance, risk_limit), seed_groups in grouped.items():
        result: dict[str, object] = {
            "instance": instance,
            "risk_limit": risk_limit,
            "runs": len(seed_groups),
            "population_size": population_size,
            "generations": generations,
            "divisions": divisions,
        }
        pareto_sizes = [float(len(group)) for group in seed_groups.values()]

        result.update(_statistics("pareto_size", pareto_sizes, extremes=False))

        for field in OBJECTIVE_FIELDS:
            seed_best = [
                min(float(row[field]) for row in group)
                for group in seed_groups.values()
            ]
            result.update(_statistics(field, seed_best))

        runtimes = [
            float(group[0].get("runtime_seconds", 0.0))
            for group in seed_groups.values()
        ]
        result.update(_statistics("runtime", runtimes, extremes=False))
        aggregate.append(result)

    return aggregate


def _statistics(
    field: str,
    values: list[float],
    *,
    extremes: bool = True,
) -> dict[str, float]:
    result = {
        f"{field}_mean": statistics.fmean(values),
        f"{field}_std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }

    if extremes:
        result[f"{field}_best"] = min(values)
        result[f"{field}_worst"] = max(values)

    return result


def run_benchmark(
    data_dir: Path,
    names: tuple[str, ...],
    seeds: tuple[int, ...],
    output: Path,
    customer_limit: int = 25,
    risk_limit: int = 5,
    population_size: int = 28,
    generations: int = 100,
    divisions: int = 4,
    risk_limits: tuple[int, ...] | None = None,
    workers: int = 1,
) -> None:
    selected_risk_limits = risk_limits or (risk_limit,)
    case_arguments = [
        (
            data_dir,
            name,
            seed,
            customer_limit,
            risk_count,
            population_size,
            generations,
            divisions,
        )
        for risk_count in selected_risk_limits
        for name in names
        for seed in seeds
    ]
    run_dir = _create_run_directory(output)
    jobs = [
        (arguments, run_dir / f"{index:04d}.json")
        for index, arguments in enumerate(case_arguments)
    ]

    try:
        if workers == 1:
            for arguments, result_path in jobs:
                _write_checkpoint(result_path, _solve_case(arguments))
        else:
            _run_parallel_jobs(jobs, workers)

        groups = [_read_checkpoint(path) for _, path in jobs]
        rows = [row for group in groups for row in group]

        _write_benchmark_results(
            rows,
            output,
            population_size,
            generations,
            divisions,
        )
    except BaseException:
        raise
    else:
        shutil.rmtree(run_dir)

        try:
            run_dir.parent.rmdir()
        except OSError:
            pass


def _run_parallel_jobs(
    jobs: list[tuple[tuple, Path]],
    workers: int,
) -> None:
    futures = {}

    with ProcessPoolExecutor(max_workers=workers) as executor:
        for arguments, result_path in jobs:
            future = executor.submit(_solve_case, arguments)
            futures[future] = result_path

        try:
            for future in as_completed(futures):
                _write_checkpoint(futures[future], future.result())
        except BaseException:
            for future in futures:
                future.cancel()

            raise


def _write_benchmark_results(
    rows: list[dict[str, object]],
    output: Path,
    population_size: int,
    generations: int,
    divisions: int,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = (
            "instance",
            "risk_limit",
            "seed",
            "pareto_index",
            "vehicles",
            "distance",
            "risk_delay",
            "max_load",
            "total_lateness",
            "runtime_seconds",
        )
        writer = csv.DictWriter(handle, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(rows)

    aggregate = aggregate_results(
        rows,
        population_size,
        generations,
        divisions,
    )
    aggregate_path = output.with_name("aggregate.csv")

    with aggregate_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=AGGREGATE_FIELDS)

        writer.writeheader()
        writer.writerows(aggregate)


def _solve_case(job: tuple[Path, str, int, int, int, int, int, int]) -> list[dict]:
    (
        data_dir,
        name,
        seed,
        customer_limit,
        risk_limit,
        population_size,
        generations,
        divisions,
    ) = job
    instance = parse_instance(data_dir / f"{name}.txt", customer_limit, risk_limit)
    config = NSGA3Config(
        population_size=population_size,
        generations=generations,
        divisions=divisions,
        seed=seed,
    )

    result = run_nsga3(instance, config)

    return [
        {
            "instance": name,
            "risk_limit": risk_limit,
            "seed": seed,
            "pareto_index": index,
            "vehicles": item.evaluation.objectives[0],
            "distance": item.evaluation.objectives[1],
            "risk_delay": item.evaluation.objectives[2],
            "max_load": item.evaluation.objectives[3],
            "total_lateness": item.evaluation.objectives[4],
            "runtime_seconds": result.runtime_seconds,
        }
        for index, item in enumerate(result.pareto_front)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
