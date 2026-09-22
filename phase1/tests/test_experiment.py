import csv
import json
import os
import statistics
import time
from dataclasses import replace
from pathlib import Path

from uav_routing.config import ALNSConfig
from uav_routing.experiment import (
    BenchmarkConfig,
    _build_parser,
    _solve_one,
    run_benchmark,
    write_results,
)


def fake_solver(path, config, customer_limit, risk_limit):
    offset = 0 if Path(path).stem == "c101" else 1

    return {
        "instance": Path(path).stem,
        "customers": customer_limit,
        "risks": risk_limit,
        "seed": config.seed,
        "iterations": config.iterations,
        "alpha": config.alpha,
        "beta": config.beta,
        "vehicles": 2 + offset,
        "distance": 100.0 + config.seed + offset,
        "risk_delay": 0.1 + offset / 10,
        "objective": 0.5 + config.seed / 100,
        "runtime_seconds": 1.0,
        "feasible": True,
        "routes": [[1, 2, 3], [4, 5, 6, 7]],
    }


def process_solver(path, config, customer_limit, risk_limit):
    row = fake_solver(path, config, customer_limit, risk_limit)
    row["process_id"] = os.getpid()

    return row


def delayed_solver(path, config, customer_limit, risk_limit):
    if config.seed == 1:
        time.sleep(0.1)

    return fake_solver(path, config, customer_limit, risk_limit)


def partially_infeasible_solver(path, config, customer_limit, risk_limit):
    row = fake_solver(path, config, customer_limit, risk_limit)

    if config.seed == 2:
        time.sleep(0.1)
        row["feasible"] = False

    return row


def test_benchmark_runs_cartesian_product_in_stable_order():
    config = BenchmarkConfig(
        instance_paths=(Path("c101.txt"), Path("r101.txt")),
        seeds=(1, 2, 3),
        alns=replace(ALNSConfig(), iterations=4),
        customer_limit=7,
        risk_limit=3,
    )

    rows = run_benchmark(config, solver=fake_solver)

    assert len(rows) == 6
    assert {row["risks"] for row in rows} == {3}
    assert [(row["instance"], row["seed"]) for row in rows] == [
        ("c101", 1),
        ("c101", 2),
        ("c101", 3),
        ("r101", 1),
        ("r101", 2),
        ("r101", 3),
    ]


def test_parallel_benchmark_runs_in_child_processes():
    config = BenchmarkConfig(
        instance_paths=(Path("c101.txt"),),
        seeds=(1, 2),
        alns=replace(ALNSConfig(), iterations=4),
        customer_limit=7,
        risk_limit=3,
        workers=2,
    )

    rows = run_benchmark(config, solver=process_solver)

    assert {row["process_id"] for row in rows}.isdisjoint({os.getpid()})


def test_parallel_benchmark_preserves_stable_order(tmp_path):
    config = BenchmarkConfig(
        instance_paths=(Path("c101.txt"), Path("r101.txt")),
        seeds=(1, 2),
        alns=replace(ALNSConfig(), iterations=4),
        checkpoint_dir=tmp_path,
        workers=2,
    )

    rows = run_benchmark(config, solver=delayed_solver)

    assert [(row["instance"], row["seed"]) for row in rows] == [
        ("c101", 1),
        ("c101", 2),
        ("r101", 1),
        ("r101", 2),
    ]


def test_parallel_benchmark_removes_temporary_directory_after_success(tmp_path):
    config = BenchmarkConfig(
        instance_paths=(Path("c101.txt"),),
        seeds=(1,),
        alns=replace(ALNSConfig(), iterations=4),
        checkpoint_dir=tmp_path,
        workers=2,
    )

    run_benchmark(config, solver=fake_solver)

    assert not (tmp_path / ".tmp").exists()


def test_parallel_benchmark_retains_completed_jobs_after_failure(tmp_path):
    config = BenchmarkConfig(
        instance_paths=(Path("c101.txt"),),
        seeds=(1, 2),
        alns=replace(ALNSConfig(), iterations=4),
        checkpoint_dir=tmp_path,
        workers=2,
    )

    try:
        run_benchmark(config, solver=partially_infeasible_solver)
    except RuntimeError as exc:
        assert "infeasible" in str(exc)
    else:
        raise AssertionError("parallel benchmark accepted an infeasible row")

    assert list((tmp_path / ".tmp").glob("run-*/*.json"))
    assert not (tmp_path / "raw.csv").exists()


def test_parallel_benchmark_rejects_unpicklable_solver():
    config = BenchmarkConfig(
        instance_paths=(Path("c101.txt"),),
        seeds=(1,),
        alns=replace(ALNSConfig(), iterations=4),
        workers=2,
    )

    def unpicklable_solver(*args):
        return fake_solver(*args)

    try:
        run_benchmark(config, solver=unpicklable_solver)
    except ValueError as exc:
        assert "picklable" in str(exc)
    else:
        raise AssertionError("parallel benchmark accepted an unpicklable solver")


def test_cli_defaults_to_one_worker():
    args = _build_parser().parse_args(["--config", "benchmark.json"])

    assert args.workers == 1


def read_header(path):
    with path.open(newline="") as handle:
        return next(csv.reader(handle))


def test_raw_and_aggregate_csv_have_stable_schema(tmp_path):
    config = BenchmarkConfig(
        (Path("c101.txt"),), (1, 2), replace(ALNSConfig(), iterations=4), 7
    )

    rows = run_benchmark(config, solver=fake_solver)
    raw, aggregate = write_results(rows, tmp_path)

    assert read_header(raw) == [
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
        "routes",
    ]
    assert read_header(aggregate) == [
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
    ]


def test_raw_csv_serializes_routes_as_json(tmp_path):
    config = BenchmarkConfig(
        (Path("c101.txt"),), (1,), replace(ALNSConfig(), iterations=4), 7
    )

    rows = run_benchmark(config, solver=fake_solver)
    raw, _ = write_results(rows, tmp_path)

    with raw.open(newline="") as handle:
        row = next(csv.DictReader(handle))

    assert json.loads(row["routes"]) == [[1, 2, 3], [4, 5, 6, 7]]


def test_solve_one_keeps_only_customer_lists_in_raw_routes(monkeypatch):
    payload = {
        "instance": "C101",
        "customers": 3,
        "risks": 1,
        "seed": 7,
        "iterations": 4,
        "alpha": 0.5,
        "beta": 0.5,
        "vehicles": 2,
        "distance": 10.0,
        "risk_delay": 0.1,
        "objective": 0.2,
        "runtime_seconds": 1.0,
        "feasible": True,
        "operators": [],
        "routes": [
            {"route_index": 1, "customers": [1, 3], "schedule": []},
            {"route_index": 2, "customers": [2], "schedule": []},
        ],
    }

    monkeypatch.setattr("uav_routing.experiment.parse_instance", lambda *args: object())
    monkeypatch.setattr("uav_routing.experiment.run_alns", lambda *args: object())
    monkeypatch.setattr(
        "uav_routing.experiment.result_to_dict", lambda *args: payload
    )

    row = _solve_one(Path("c101.txt"), replace(ALNSConfig(), seed=7), 3, 1)

    assert row["routes"] == [[1, 3], [2]]


def test_aggregate_values_use_sample_standard_deviation(tmp_path):
    config = BenchmarkConfig(
        (Path("c101.txt"),), (1, 2, 3), replace(ALNSConfig(), iterations=4), 7
    )

    rows = run_benchmark(config, solver=fake_solver)
    _, aggregate = write_results(rows, tmp_path)

    with aggregate.open(newline="") as handle:
        row = next(csv.DictReader(handle))

    assert float(row["distance_mean"]) == statistics.fmean([101, 102, 103])
    assert float(row["distance_std"]) == statistics.stdev([101, 102, 103])
    assert float(row["distance_best"]) == 101
    assert float(row["distance_worst"]) == 103


def test_infeasible_run_aborts_benchmark():
    def infeasible(path, config, customer_limit, risk_limit):
        row = fake_solver(path, config, customer_limit, risk_limit)
        row["feasible"] = False

        return row

    config = BenchmarkConfig((Path("c101.txt"),), (1,), ALNSConfig(), 7)

    try:
        run_benchmark(config, solver=infeasible)
    except RuntimeError as exc:
        assert "infeasible" in str(exc)
    else:
        raise AssertionError("infeasible benchmark row was accepted")


def test_benchmark_accepts_zero_risk_zones():
    config = BenchmarkConfig(
        instance_paths=(Path("c101.txt"),),
        seeds=(1,),
        alns=ALNSConfig(),
        customer_limit=7,
        risk_limit=0,
    )

    rows = run_benchmark(config, solver=fake_solver)

    assert rows[0]["risks"] == 0


def test_benchmark_rejects_risk_count_outside_zero_to_five():
    config = BenchmarkConfig(
        instance_paths=(Path("c101.txt"),),
        seeds=(1,),
        alns=ALNSConfig(),
        customer_limit=7,
        risk_limit=6,
    )

    try:
        run_benchmark(config, solver=fake_solver)
    except ValueError as exc:
        assert "risk_limit" in str(exc)
    else:
        raise AssertionError("invalid risk_limit was accepted")


def test_benchmark_rejects_nonpositive_worker_count():
    config = BenchmarkConfig(
        instance_paths=(Path("c101.txt"),),
        seeds=(1,),
        alns=ALNSConfig(),
        customer_limit=7,
        workers=0,
    )

    try:
        run_benchmark(config, solver=fake_solver)
    except ValueError as exc:
        assert "workers" in str(exc)
    else:
        raise AssertionError("nonpositive worker count was accepted")
