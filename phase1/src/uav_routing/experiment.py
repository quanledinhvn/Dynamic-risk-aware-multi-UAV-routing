"""Reproducible multi-instance benchmark runner."""

import argparse
import csv
import json
import pickle
import shutil
import statistics
import sys
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from .alns import run_alns
from .cli import result_to_dict
from .config import ALNSConfig
from .contextual.alns import run_contextual_alns
from .contextual.config import ContextualBanditConfig
from .parser import parse_instance

BANDIT_FIELDS = ("context_window", "linucb_exploration", "linucb_regularization")

RAW_FIELDS = (
    "instance",
    "customers",
    "risks",
    "algorithm",
    "seed",
    "iterations",
    "alpha",
    "beta",
    "context_window",
    "linucb_exploration",
    "linucb_regularization",
    "vehicles",
    "distance",
    "risk_delay",
    "objective",
    "runtime_seconds",
    "feasible",
    "routes",
)

AGGREGATE_FIELDS = (
    "instance",
    "customers",
    "risks",
    "algorithm",
    "iterations",
    "alpha",
    "beta",
    "context_window",
    "linucb_exploration",
    "linucb_regularization",
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
    workers: int = 1

    algorithm: str = "baseline"
    bandit: ContextualBanditConfig | None = None


def run_benchmark(
    config: BenchmarkConfig, solver: Callable | None = None
) -> list[dict[str, object]]:
    _validate_benchmark_config(config)

    solve = (
        solver
        if solver is not None
        else partial(_solve_one, algorithm=config.algorithm, bandit=config.bandit)
    )

    if config.workers == 1:
        return _run_sequential(config, solve)

    return _run_parallel(config, solve)


def _run_sequential(
    config: BenchmarkConfig, solve: Callable
) -> list[dict[str, object]]:
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

            _validate_feasible_row(row, instance_path, seed)

            rows.append(dict(row))

            if config.checkpoint_dir is not None:
                write_results(rows, config.checkpoint_dir)

    return rows


def _run_parallel(config: BenchmarkConfig, solve: Callable) -> list[dict[str, object]]:
    try:
        pickle.dumps(solve)
    except (AttributeError, pickle.PickleError, TypeError) as exc:
        raise ValueError("parallel benchmark solver must be picklable") from exc

    run_dir = _create_run_directory(config.checkpoint_dir)
    jobs: list[tuple[int, Path, int, Path]] = []

    index = 0

    for instance_path in config.instance_paths:
        for seed in config.seeds:
            result_path = run_dir / f"{index:04d}.json"
            jobs.append((index, instance_path, seed, result_path))

            index += 1

    futures = {}

    try:
        with ProcessPoolExecutor(max_workers=config.workers) as executor:
            for _, instance_path, seed, result_path in jobs:
                alns = replace(config.alns, seed=seed)
                alns.validate()

                future = executor.submit(
                    _solve_job,
                    solve,
                    instance_path,
                    alns,
                    config.customer_limit,
                    config.risk_limit,
                )
                futures[future] = result_path

            try:
                for future in as_completed(futures):
                    row = future.result()
                    _write_json_atomic(futures[future], row)
            except BaseException:
                for future in futures:
                    future.cancel()

                raise

        rows = [_read_result(path) for _, _, _, path in jobs]

        if config.checkpoint_dir is not None:
            write_results(rows, config.checkpoint_dir)
    except BaseException:
        raise
    else:
        shutil.rmtree(run_dir)

        try:
            run_dir.parent.rmdir()
        except OSError:
            pass

    return rows


def _solve_job(
    solve: Callable,
    instance_path: Path,
    alns: ALNSConfig,
    customer_limit: int,
    risk_limit: int,
) -> dict[str, object]:
    row = solve(instance_path, alns, customer_limit, risk_limit)
    _validate_feasible_row(row, instance_path, alns.seed)

    return dict(row)


def _validate_feasible_row(
    row: dict[str, object], instance_path: Path, seed: int
) -> None:
    if not bool(row["feasible"]):
        raise RuntimeError(f"infeasible benchmark run: {instance_path} seed={seed}")


def _create_run_directory(output_dir: Path | None) -> Path:
    if output_dir is None:
        temporary_root = Path(gettempdir()) / "uav-routing-benchmark"
    else:
        temporary_root = output_dir / ".tmp"

    run_dir = temporary_root / f"run-{uuid4().hex}"
    run_dir.mkdir(parents=True, exist_ok=False)

    return run_dir


def _write_json_atomic(path: Path, row: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(row, indent=2)

    temporary.write_text(payload + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_result(path: Path) -> dict[str, object]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


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
    print(
        f"completed {len(rows)} runs; algorithm={config.algorithm}; "
        f"raw={raw}; aggregate={aggregate}"
    )

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uav-routing-benchmark")

    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--algorithm", choices=("baseline", "contextual"))

    parser.add_argument("--iterations", type=int)
    parser.add_argument("--seeds", type=int, nargs="+")

    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))

    return parser


def _benchmark_config_from_args(args: argparse.Namespace) -> BenchmarkConfig:
    config = _load_config(args.config)
    alns = config.alns

    if args.iterations is not None:
        alns = replace(alns, iterations=args.iterations)

    seeds = tuple(args.seeds) if args.seeds is not None else config.seeds
    algorithm = args.algorithm if args.algorithm is not None else config.algorithm
    bandit = None

    if algorithm == "contextual":
        bandit = config.bandit or ContextualBanditConfig()

    return replace(
        config,
        seeds=seeds,
        alns=alns,
        checkpoint_dir=args.output_dir,
        workers=args.workers,
        algorithm=algorithm,
        bandit=bandit,
    )


def _solve_one(
    path: Path,
    config: ALNSConfig,
    customer_limit: int,
    risk_limit: int,
    *,
    algorithm: str = "baseline",
    bandit: ContextualBanditConfig | None = None,
) -> dict[str, object]:
    instance = parse_instance(path, customer_limit, risk_limit)

    if algorithm == "contextual":
        bandit = bandit or ContextualBanditConfig()
        result = run_contextual_alns(instance, config, bandit)
        payload = result_to_dict(result, instance, config, bandit)
    else:
        result = run_alns(instance, config)
        payload = result_to_dict(result, instance, config)

    row = {key: payload[key] for key in RAW_FIELDS if key not in BANDIT_FIELDS}
    row.update(
        {
            key: getattr(bandit, key) if algorithm == "contextual" else None
            for key in BANDIT_FIELDS
        }
    )

    row["routes"] = [route["customers"] for route in payload["routes"]]

    return row


def _aggregate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}

    for row in rows:
        key = (
            row["instance"],
            row["customers"],
            row["risks"],
            row.get("algorithm", "baseline"),
            row["iterations"],
            row["alpha"],
            row["beta"],
            row.get("context_window"),
            row.get("linucb_exploration"),
            row.get("linucb_regularization"),
        )
        grouped.setdefault(key, []).append(row)

    aggregate: list[dict[str, object]] = []

    for key, group in grouped.items():
        aggregate.append(_aggregate_group(key, group))

    return aggregate


def _aggregate_group(
    key: tuple[object, ...], group: list[dict[str, object]]
) -> dict[str, object]:
    result: dict[str, object] = dict(zip(AGGREGATE_FIELDS[:10], key, strict=True))
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

        for row in rows:
            csv_row = {"algorithm": "baseline", **row}

            if "routes" in csv_row:
                csv_row["routes"] = json.dumps(csv_row["routes"], separators=(",", ":"))

            writer.writerow(csv_row)

    temporary.replace(path)


def _load_config(path: Path) -> BenchmarkConfig:
    values = json.loads(path.read_text(encoding="utf-8"))
    algorithm = values.get("algorithm", "baseline")
    bandit = None

    if "contextual_bandit" in values:
        bandit = ContextualBanditConfig.from_dict(values["contextual_bandit"])
    elif algorithm == "contextual":
        bandit = ContextualBanditConfig()

    config = BenchmarkConfig(
        instance_paths=tuple(Path(value) for value in values["instances"]),
        seeds=tuple(int(value) for value in values["seeds"]),
        alns=ALNSConfig.from_dict(values["alns"]),
        customer_limit=int(values.get("customers", 25)),
        risk_limit=int(values.get("risks", 5)),
        algorithm=algorithm,
        bandit=bandit,
    )
    _validate_benchmark_config(config)

    return config


def _validate_benchmark_config(config: BenchmarkConfig) -> None:
    if config.algorithm not in ("baseline", "contextual"):
        raise ValueError("algorithm must be baseline or contextual")

    if config.bandit is not None:
        if not isinstance(config.bandit, ContextualBanditConfig):
            raise ValueError("bandit must be a ContextualBanditConfig")

        config.bandit.validate()

    if not config.instance_paths:
        raise ValueError("benchmark requires at least one instance")

    if not config.seeds:
        raise ValueError("benchmark requires at least one seed")

    if config.customer_limit <= 0:
        raise ValueError("customer_limit must be positive")

    if not 0 <= config.risk_limit <= 5:
        raise ValueError("risk_limit must be between 0 and 5")

    if config.workers <= 0:
        raise ValueError("workers must be positive")


if __name__ == "__main__":
    raise SystemExit(main())
