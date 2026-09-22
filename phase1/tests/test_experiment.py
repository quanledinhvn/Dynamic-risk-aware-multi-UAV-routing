import csv
import statistics
from dataclasses import replace
from pathlib import Path

from uav_routing.config import ALNSConfig
from uav_routing.experiment import BenchmarkConfig, run_benchmark, write_results


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
    }


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
