import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from uav_routing.config import ALNSConfig
from uav_routing.contextual.config import ContextualBanditConfig
from uav_routing.dynamic.config import RollingHorizonConfig
from uav_routing.dynamic.experiment import (
    AGGREGATE_FIELDS,
    RAW_FIELDS,
    DynamicBenchmarkConfig,
    main,
    run_dynamic_benchmark,
    write_dynamic_results,
)

TINY = Path(__file__).parent / "fixtures" / "tiny_scenario.json"
CONFIG = DynamicBenchmarkConfig(
    scenario_paths=(TINY,),
    seeds=(1, 2),
    policies=("greedy_insert", "warm_alns"),
    alns=ALNSConfig(iterations=10, seed=0, q_min=1, q_max=2),
    rolling=RollingHorizonConfig(
        epoch_length=30.0, iterations_epoch0=10, iterations_per_epoch=5
    ),
)
VOLATILE = ("runtime_seconds", "runtime_per_epoch_mean")


def _stable(rows):
    return [{k: v for k, v in row.items() if k not in VOLATILE} for row in rows]


def test_raw_rows_have_one_row_per_scenario_seed_policy():
    rows = run_dynamic_benchmark(CONFIG)

    assert len(rows) == 4
    assert {(row["scenario"], row["seed"], row["policy"]) for row in rows} == {
        ("tiny", 1, "greedy_insert"),
        ("tiny", 1, "warm_alns"),
        ("tiny", 2, "greedy_insert"),
        ("tiny", 2, "warm_alns"),
    }
    assert all(set(RAW_FIELDS) <= set(row) for row in rows)
    assert all(row["feasible"] for row in rows)
    assert all(row["static_customers"] == 2 for row in rows)
    assert all(row["dynamic_customers"] == 1 for row in rows)
    assert all(row["degree_of_dynamism"] == pytest.approx(1 / 3) for row in rows)
    assert all(row["epochs"] == 5 for row in rows)


def test_contextual_policy_records_bandit_hyperparameters():
    config = replace(
        CONFIG,
        seeds=(1,),
        policies=("contextual_warm_alns",),
        bandit=ContextualBanditConfig(
            context_window=7,
            linucb_exploration=0.25,
        ),
    )

    [row] = run_dynamic_benchmark(config)

    assert row["policy"] == "contextual_warm_alns"
    assert row["context_window"] == 7
    assert row["linucb_exploration"] == 0.25

    assert row["feasible"] is True


def test_clairvoyant_is_shared_per_scenario_seed_and_gap_is_filled():
    rows = run_dynamic_benchmark(CONFIG)
    by_seed: dict[int, set[float]] = {}

    for row in rows:
        by_seed.setdefault(row["seed"], set()).add(row["clairvoyant_objective"])

        assert row["clairvoyant_objective"] > 0
        assert row["gap"] == pytest.approx(
            (row["objective"] - row["clairvoyant_objective"])
            / row["clairvoyant_objective"]
        )
        assert row["total_iterations"] <= 10 + 4 * 5

    assert all(len(values) == 1 for values in by_seed.values())


def test_aggregate_groups_by_scenario_policy_trigger_and_epoch_length(tmp_path):
    rows = run_dynamic_benchmark(CONFIG)
    raw, aggregate = write_dynamic_results(rows, tmp_path)

    with aggregate.open(encoding="utf-8") as handle:
        groups = list(csv.DictReader(handle))

    assert raw.name == "raw.csv"
    assert len(groups) == 2
    assert {group["policy"] for group in groups} == {"greedy_insert", "warm_alns"}
    assert all(group["runs"] == "2" for group in groups)
    assert all(set(AGGREGATE_FIELDS) == set(group) for group in groups)
    assert all(float(group["gap_mean"]) == float(group["gap_mean"]) for group in groups)


def test_csv_schema_matches_fields(tmp_path):
    rows = run_dynamic_benchmark(replace(CONFIG, seeds=(1,), policies=("warm_alns",)))
    raw, _ = write_dynamic_results(rows, tmp_path)

    with raw.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        records = list(reader)

    assert tuple(reader.fieldnames) == RAW_FIELDS
    assert len(records) == 1
    assert json.loads(records[0]["routes"])


def test_parallel_and_sequential_produce_same_rows(tmp_path):
    sequential = run_dynamic_benchmark(CONFIG)
    parallel = run_dynamic_benchmark(
        replace(CONFIG, workers=2, checkpoint_dir=tmp_path / "parallel")
    )

    assert _stable(parallel) == _stable(sequential)
    assert (tmp_path / "parallel" / "raw.csv").exists()
    assert not (tmp_path / "parallel" / ".tmp").exists()


def test_infeasible_realized_solution_aborts_benchmark():
    def runner(scenario_path, seed, policy, alns, rolling, budget):
        return {"feasible": False, "scenario": "tiny", "seed": seed, "policy": policy}

    with pytest.raises(RuntimeError, match="infeasible"):
        run_dynamic_benchmark(CONFIG, runner=runner)


def test_config_validation_rejects_empty_inputs():
    for changes in (
        {"scenario_paths": ()},
        {"seeds": ()},
        {"policies": ()},
        {"policies": ("bogus",)},
        {"workers": 0},
    ):
        with pytest.raises(ValueError):
            run_dynamic_benchmark(replace(CONFIG, **changes))


def test_cli_runs_config_file_and_writes_outputs(tmp_path, capsys):
    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        json.dumps(
            {
                "scenarios": [str(TINY)],
                "seeds": [1],
                "policies": ["greedy_insert"],
                "alns": {"iterations": 10, "q_min": 1, "q_max": 2},
                "rolling": {
                    "epoch_length": 50.0,
                    "iterations_epoch0": 10,
                    "iterations_per_epoch": 0,
                },
            }
        ),
        encoding="utf-8",
    )

    code = main(["--config", str(config_path), "--output-dir", str(tmp_path / "out")])
    output = capsys.readouterr().out

    assert code == 0
    assert "completed 1 runs" in output
    assert (tmp_path / "out" / "raw.csv").exists()
    assert (tmp_path / "out" / "aggregate.csv").exists()


def test_cli_scenario_glob_and_overrides(tmp_path, capsys):
    config_path = tmp_path / "benchmark.json"
    config_path.write_text(
        json.dumps(
            {
                "scenarios": [str(TINY.parent / "tiny_*.json")],
                "seeds": [1, 2, 3],
                "policies": ["greedy_insert", "warm_alns"],
                "alns": {"iterations": 10, "q_min": 1, "q_max": 2},
                "rolling": {"epoch_length": 50.0, "iterations_epoch0": 5},
            }
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "--config",
            str(config_path),
            "--seeds",
            "7",
            "--policies",
            "warm_alns",
            "--iterations-per-epoch",
            "1",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 0
    assert "completed 1 runs" in capsys.readouterr().out
