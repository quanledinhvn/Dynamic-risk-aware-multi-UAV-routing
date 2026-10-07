import csv
import json
from pathlib import Path

import pytest

from uav_routing_nsga.experiment import (
    _benchmark_config_from_args,
    _build_parser,
    aggregate_results,
    load_benchmark_config,
    main,
    run_benchmark,
)

ROOT = Path(__file__).parents[2]


def _write_config(tmp_path: Path, **overrides: object) -> Path:
    values = {
        "instances": ["c101", "r101"],
        "seeds": [0, 1],
        "customer_limit": 25,
        "risk_limits": [1, 5],
        "population_size": 8,
        "generations": 2,
        "divisions": 2,
    }
    values.update(overrides)

    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(values), encoding="utf-8")

    return path


def test_load_benchmark_config_reads_generations_and_seeds(tmp_path):
    path = _write_config(tmp_path, data_dir="data")
    config = load_benchmark_config(path)

    assert config.names == ("c101", "r101")
    assert config.seeds == (0, 1)
    assert config.generations == 2

    assert config.data_dir == (tmp_path / "data").resolve()


def test_cli_overrides_generations_seeds_workers_and_output(tmp_path):
    path = _write_config(tmp_path, data_dir="data")
    output = tmp_path / "raw.csv"
    args = _build_parser().parse_args(
        [
            "--config",
            str(path),
            "--generations",
            "7",
            "--seeds",
            "8",
            "9",
            "--workers",
            "3",
            "--output",
            str(output),
        ]
    )

    config = _benchmark_config_from_args(args)

    assert config.generations == 7
    assert config.seeds == (8, 9)
    assert config.workers == 3

    assert config.output == output


def test_iterations_is_supported_as_generations_alias(tmp_path):
    path = _write_config(tmp_path, generations=9)
    args = _build_parser().parse_args(
        ["--config", str(path), "--iterations", "4"],
    )

    config = _benchmark_config_from_args(args)

    assert config.generations == 4


@pytest.mark.parametrize(
    "overrides",
    [
        {"instances": []},
        {"seeds": []},
        {"customer_limit": 0},
        {"risk_limits": [6]},
        {"population_size": 1},
        {"generations": 0},
        {"divisions": 0},
    ],
)
def test_invalid_benchmark_config_is_rejected(tmp_path, overrides):
    with pytest.raises(ValueError):
        load_benchmark_config(_write_config(tmp_path, **overrides))


def test_main_runs_benchmark_from_config(tmp_path, monkeypatch, capsys):
    path = _write_config(tmp_path, data_dir="data")
    output = tmp_path / "raw.csv"
    captured = {}

    def fake_run_benchmark(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        "uav_routing_nsga.experiment.run_benchmark",
        fake_run_benchmark,
    )

    status = main(["--config", str(path), "--output", str(output)])

    assert status == 0
    assert captured["kwargs"]["generations"] == 2
    assert captured["kwargs"]["workers"] == 1

    assert captured["kwargs"]["output"] == output
    assert "Benchmark completed" in capsys.readouterr().out


def test_aggregate_uses_each_seeds_best_pareto_objectives():
    rows = [
        {
            "instance": "c101",
            "risk_limit": 5,
            "seed": 0,
            "vehicles": 3.0,
            "distance": 20.0,
            "risk_delay": 4.0,
            "max_load": 8.0,
            "total_lateness": 2.0,
        },
        {
            "instance": "c101",
            "risk_limit": 5,
            "seed": 0,
            "vehicles": 4.0,
            "distance": 10.0,
            "risk_delay": 2.0,
            "max_load": 6.0,
            "total_lateness": 1.0,
        },
        {
            "instance": "c101",
            "risk_limit": 5,
            "seed": 1,
            "vehicles": 5.0,
            "distance": 30.0,
            "risk_delay": 6.0,
            "max_load": 10.0,
            "total_lateness": 3.0,
        },
    ]

    aggregate = aggregate_results(rows, 28, 100, 4)[0]

    assert aggregate["runs"] == 2
    assert aggregate["pareto_size_mean"] == 1.5
    assert aggregate["vehicles_mean"] == 4.0

    assert aggregate["distance_mean"] == 20.0
    assert aggregate["distance_best"] == 10.0
    assert aggregate["distance_worst"] == 30.0


@pytest.mark.parametrize("workers", [1, 2])
def test_benchmark_runs_with_configured_worker_count(tmp_path, workers):
    output = tmp_path / "raw.csv"

    run_benchmark(
        data_dir=ROOT / "dataset/solomon_risk",
        names=("c101",),
        seeds=(3,),
        output=output,
        customer_limit=5,
        risk_limits=(0,),
        population_size=4,
        generations=1,
        divisions=1,
        workers=workers,
    )

    rows = output.read_text(encoding="utf-8").splitlines()

    assert rows[0].startswith("instance,risk_limit,seed")
    assert rows[1].startswith("c101,0,3")

    with (tmp_path / "aggregate.csv").open(newline="") as handle:
        aggregate = list(csv.DictReader(handle))

    assert len(aggregate) == 1
    assert aggregate[0]["instance"] == "c101"
    assert aggregate[0]["runs"] == "1"
