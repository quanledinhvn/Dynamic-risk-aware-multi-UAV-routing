import csv
import json
import os
import statistics
import time
from dataclasses import replace
from pathlib import Path

import pytest

from uav_routing.config import ALNSConfig
from uav_routing.contextual.config import ContextualBanditConfig
from uav_routing.experiment import (
    BenchmarkConfig,
    _benchmark_config_from_args,
    _build_parser,
    _load_config,
    _solve_one,
    main,
    run_benchmark,
    write_results,
)

C101 = Path(__file__).resolve().parents[2] / "dataset/solomon_risk/c101.txt"


@pytest.fixture
def benchmark_file(tmp_path):
    def write(**overrides):
        values = {
            "instances": [str(C101)],
            "seeds": [1, 2],
            "customers": 5,
            "risks": 0,
            "alns": {"iterations": 2},
        }
        values.update(overrides)
        path = tmp_path / "benchmark.json"

        path.write_text(json.dumps(values), encoding="utf-8")

        return path

    return write


def test_missing_algorithm_defaults_to_baseline(benchmark_file):
    config = _load_config(benchmark_file())

    assert config.algorithm == "baseline"
    assert config.bandit is None


def test_contextual_config_loads_all_bandit_values(benchmark_file):
    config = _load_config(
        benchmark_file(
            algorithm="contextual",
            contextual_bandit={
                "context_window": 17,
                "linucb_exploration": 0.25,
                "linucb_regularization": 2.0,
            },
        )
    )

    assert config.algorithm == "contextual"
    assert config.bandit == ContextualBanditConfig(17, 0.25, 2.0)


@pytest.mark.parametrize(
    "file_algorithm,cli_algorithm,expected",
    [
        ("contextual", "baseline", "baseline"),
        ("baseline", "contextual", "contextual"),
        ("contextual", None, "contextual"),
    ],
)
def test_algorithm_cli_overrides_config(
    benchmark_file, file_algorithm, cli_algorithm, expected
):
    path = benchmark_file(algorithm=file_algorithm)
    argv = ["--config", str(path)]

    if cli_algorithm is not None:
        argv.extend(["--algorithm", cli_algorithm])

    config = _benchmark_config_from_args(_build_parser().parse_args(argv))

    assert config.algorithm == expected
    assert config.bandit == (
        ContextualBanditConfig() if expected == "contextual" else None
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"algorithm": "unknown"},
        {"algorithm": None},
        {"contextual_bandit": []},
        {"contextual_bandit": {"unknown": 1}},
        {"contextual_bandit": {"context_window": 0}},
        {"contextual_bandit": {"linucb_exploration": -1}},
        {"contextual_bandit": {"linucb_regularization": 0}},
    ],
)
def test_invalid_algorithm_or_bandit_config_is_rejected(benchmark_file, overrides):
    values = {"algorithm": "contextual", **overrides}

    with pytest.raises(ValueError):
        _load_config(benchmark_file(**values))


@pytest.mark.parametrize("invalid_bandit", [[], {"unknown": 1}, {"context_window": 0}])
@pytest.mark.parametrize("file_algorithm", [None, "baseline", "contextual"])
def test_effective_baseline_ignores_invalid_bandit_block(
    benchmark_file, tmp_path, monkeypatch, invalid_bandit, file_algorithm
):
    values = {"contextual_bandit": invalid_bandit}

    if file_algorithm is not None:
        values["algorithm"] = file_algorithm

    argv = ["--config", str(benchmark_file(**values))]

    if file_algorithm == "contextual":
        argv.extend(["--algorithm", "baseline"])

    def unexpected_solver(*args):
        pytest.fail("baseline invoked contextual solver")

    monkeypatch.setattr("uav_routing.experiment.run_contextual_alns", unexpected_solver)
    config = _benchmark_config_from_args(_build_parser().parse_args(argv))

    assert config.algorithm == "baseline"
    assert config.bandit is None

    rows = run_benchmark(replace(config, checkpoint_dir=None))
    paths = write_results(rows, tmp_path / "output")

    for path in paths:
        with path.open(newline="") as handle:
            csv_rows = list(csv.DictReader(handle))

        for row in csv_rows:
            assert row["algorithm"] == "baseline"
            assert (
                row["context_window"],
                row["linucb_exploration"],
                row["linucb_regularization"],
            ) == ("", "", "")


@pytest.mark.parametrize("workers", [1, 2])
def test_direct_baseline_ignores_invalid_bandit_config(monkeypatch, workers):
    def unexpected_solver(*args):
        pytest.fail("baseline invoked contextual solver")

    monkeypatch.setattr("uav_routing.experiment.run_contextual_alns", unexpected_solver)
    config = BenchmarkConfig(
        (C101,),
        (1,),
        ALNSConfig(iterations=2),
        5,
        0,
        workers=workers,
        bandit=ContextualBanditConfig(context_window=0),
    )

    row = run_benchmark(config)[0]

    assert row["algorithm"] == "baseline"
    assert (
        row["context_window"],
        row["linucb_exploration"],
        row["linucb_regularization"],
    ) == (None, None, None)


@pytest.mark.parametrize("algorithm", ["baseline", "contextual"])
def test_default_solver_dispatches_only_requested_algorithm(monkeypatch, algorithm):
    forbidden = "run_alns" if algorithm == "contextual" else "run_contextual_alns"

    def unexpected_solver(*args):
        pytest.fail(f"{algorithm} benchmark called {forbidden}")

    monkeypatch.setattr(f"uav_routing.experiment.{forbidden}", unexpected_solver)
    config = BenchmarkConfig(
        (C101,), (1,), ALNSConfig(iterations=2), 5, 0, algorithm=algorithm
    )

    rows = run_benchmark(config)

    assert rows[0]["algorithm"] == algorithm
    assert rows[0]["feasible"] is True


@pytest.mark.parametrize("workers", [1, 2])
def test_custom_four_argument_solver_is_preserved_for_contextual_config(workers):
    config = BenchmarkConfig(
        (Path("c101.txt"),),
        (1, 2),
        ALNSConfig(iterations=2),
        workers=workers,
        algorithm="contextual",
        bandit=ContextualBanditConfig(),
    )

    rows = run_benchmark(config, solver=fake_solver)

    assert [row["seed"] for row in rows] == [1, 2]
    assert rows[0]["routes"] == [[1, 2, 3], [4, 5, 6, 7]]


def test_contextual_default_solver_is_picklable_and_preserves_order(tmp_path):
    config = BenchmarkConfig(
        (C101,),
        (2, 1),
        ALNSConfig(iterations=2),
        5,
        0,
        tmp_path,
        2,
        "contextual",
        ContextualBanditConfig(17, 0.25, 2.0),
    )

    rows = run_benchmark(config)

    assert [row["seed"] for row in rows] == [2, 1]
    assert {row["algorithm"] for row in rows} == {"contextual"}

    assert {row["context_window"] for row in rows} == {17}
    assert {row["linucb_exploration"] for row in rows} == {0.25}
    assert {row["linucb_regularization"] for row in rows} == {2.0}

    assert not (tmp_path / ".tmp").exists()


@pytest.mark.parametrize("algorithm", ["baseline", "contextual"])
def test_cli_override_writes_correct_algorithm_and_bandit_csv_values(
    benchmark_file, tmp_path, monkeypatch, capsys, algorithm
):
    other = "contextual" if algorithm == "baseline" else "baseline"
    path = benchmark_file(
        algorithm=other,
        contextual_bandit={
            "context_window": 17,
            "linucb_exploration": 0.25,
            "linucb_regularization": 2.0,
        },
    )

    def unexpected_solver(*args):
        pytest.fail(f"CLI override to {algorithm} invoked {other}")

    forbidden = "run_contextual_alns" if algorithm == "baseline" else "run_alns"
    monkeypatch.setattr(f"uav_routing.experiment.{forbidden}", unexpected_solver)
    output = tmp_path / "results"

    assert (
        main(
            [
                "--config",
                str(path),
                "--algorithm",
                algorithm,
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )

    assert f"algorithm={algorithm}" in capsys.readouterr().out

    for name in ("raw.csv", "aggregate.csv"):
        with (output / name).open(newline="") as handle:
            rows = list(csv.DictReader(handle))

        assert {row["algorithm"] for row in rows} == {algorithm}
        expected = ("17", "0.25", "2.0") if algorithm == "contextual" else ("", "", "")

        for row in rows:
            assert (
                row["context_window"],
                row["linucb_exploration"],
                row["linucb_regularization"],
            ) == expected


def test_baseline_with_supplied_bandit_has_empty_bandit_values():
    config = BenchmarkConfig(
        (C101,),
        (1,),
        ALNSConfig(iterations=2),
        5,
        0,
        bandit=ContextualBanditConfig(17, 0.25, 2.0),
    )

    row = run_benchmark(config)[0]

    assert row["algorithm"] == "baseline"
    assert row["context_window"] is None
    assert row["linucb_exploration"] is None

    assert row["linucb_regularization"] is None


@pytest.mark.parametrize(
    "difference",
    [
        {"instance": "r101"},
        {"customers": 8},
        {"risks": 2},
        {"algorithm": "baseline"},
        {"iterations": 5},
        {"alpha": 0.25, "beta": 0.75},
        {"context_window": 18},
        {"linucb_exploration": 0.75},
        {"linucb_regularization": 3.0},
    ],
)
def test_aggregate_separates_each_experiment_dimension(tmp_path, difference):
    first = fake_solver(Path("c101.txt"), ALNSConfig(iterations=4), 7, 3)
    first.update(
        algorithm="contextual",
        context_window=17,
        linucb_exploration=0.25,
        linucb_regularization=2.0,
    )
    second = {**first, **difference, "seed": 2, "distance": 999.0}

    _, aggregate = write_results([first, second], tmp_path)

    with aggregate.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 2
    assert [row["runs"] for row in rows] == ["1", "1"]
    assert [float(row["distance_mean"]) for row in rows] == [142.0, 999.0]


def test_aggregate_combines_seeds_with_same_contextual_parameters(tmp_path):
    rows = [
        fake_solver(Path("c101.txt"), ALNSConfig(seed=seed), 7, 3) for seed in (1, 2)
    ]

    for row in rows:
        row.update(
            algorithm="contextual",
            context_window=17,
            linucb_exploration=0.25,
            linucb_regularization=2.0,
        )

    _, aggregate = write_results(rows, tmp_path)

    with aggregate.open(newline="") as handle:
        combined = list(csv.DictReader(handle))

    assert len(combined) == 1
    assert combined[0]["runs"] == "2"
    assert combined[0]["context_window"] == "17"

    assert float(combined[0]["distance_mean"]) == 101.5


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
    ]
    assert read_header(aggregate) == [
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
    assert row["algorithm"] == "baseline"
    assert (
        row["context_window"],
        row["linucb_exploration"],
        row["linucb_regularization"],
    ) == ("", "", "")


def test_solve_one_keeps_only_customer_lists_in_raw_routes(monkeypatch):
    payload = {
        "algorithm": "baseline",
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
    monkeypatch.setattr("uav_routing.experiment.result_to_dict", lambda *args: payload)

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
