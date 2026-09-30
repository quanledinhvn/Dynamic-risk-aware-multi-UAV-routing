import json
from pathlib import Path

import pytest

from uav_routing.dynamic.cli import main

TINY = Path(__file__).parent / "fixtures" / "tiny_scenario.json"
BASE_ARGS = [
    "simulate",
    "--scenario",
    str(TINY),
    "--policy",
    "warm_alns",
    "--epoch-length",
    "30",
    "--iterations-epoch0",
    "20",
    "--iterations-per-epoch",
    "5",
    "--seed",
    "1",
]


def _run(capsys, extra=()):
    code = main([*BASE_ARGS, *extra])
    captured = capsys.readouterr()

    return code, json.loads(captured.out), captured.err


def test_simulate_prints_json_with_expected_keys(capsys):
    code, payload, err = _run(capsys)

    assert code == 0
    assert "Simulation Started" in err
    assert "Simulation Completed" in err
    assert payload["scenario"] == "tiny"
    assert payload["policy"] == "warm_alns"
    assert payload["trigger"] == "periodic"
    assert payload["epoch_length"] == 30.0
    assert payload["seed"] == 1
    assert payload["iterations_epoch0"] == 20
    assert payload["iterations_per_epoch"] == 5
    assert payload["total_iterations"] == 20 + 4 * 5
    assert payload["alpha"] == 0.5
    assert payload["d_ref"] > 0
    assert payload["feasible"] is True
    assert payload["vehicles"] >= 1
    assert payload["unserved"] == []
    assert payload["unserved_priority"] == 0.0
    assert payload["runtime_seconds"] >= 0.0
    assert set(payload) >= {
        "distance",
        "risk_delay",
        "objective",
        "epochs",
        "routes",
        "static_customers",
        "dynamic_customers",
        "events",
    }


def test_output_epochs_include_revealed_events_and_locked_count(capsys):
    _, payload, _ = _run(capsys)
    epochs = payload["epochs"]

    assert [epoch["time"] for epoch in epochs] == [0.0, 30.0, 60.0, 90.0, 100.0]
    assert [epoch["index"] for epoch in epochs] == [0, 1, 2, 3, 4]
    assert epochs[1]["revealed"] == {
        "customer_arrival": 1,
        "risk_update": 1,
        "deadline_update": 1,
    }
    assert epochs[0]["locked_customers"] == 0
    assert epochs[-1]["locked_customers"] == 3
    assert all(epoch["iterations"] == 5 for epoch in epochs[1:])
    assert all("objective" in epoch and "vehicles" in epoch for epoch in epochs)
    assert all(epoch["rejected"] == [] for epoch in epochs)


def test_routes_include_schedule(capsys):
    _, payload, _ = _run(capsys)

    served = sorted(c for route in payload["routes"] for c in route["customers"])

    assert served == [1, 2, 3]
    assert all(
        {"arrival", "service_start", "departure", "customer_id"} <= set(stop)
        for route in payload["routes"]
        for stop in route["schedule"]
    )


def test_simulate_writes_output_atomically(tmp_path, capsys):
    target = tmp_path / "nested" / "result.json"

    code, payload, _ = _run(capsys, ["--output", str(target)])

    assert code == 0
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert not target.with_suffix(".json.tmp").exists()


def test_invalid_policy_exits_with_argparse_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main([*BASE_ARGS[:4], "--policy", "bogus"])

    assert exc.value.code == 2


def test_missing_scenario_file_reports_path(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["simulate", "--scenario", "/nowhere/missing.json"])

    assert exc.value.code == 2
    assert "missing.json" in capsys.readouterr().err


def test_invalid_scenario_content_is_reported(tmp_path, capsys):
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main(["simulate", "--scenario", str(broken)])

    assert exc.value.code == 2
    assert "invalid JSON" in capsys.readouterr().err


def test_same_seed_is_reproducible_through_cli(capsys):
    _, left, _ = _run(capsys)
    _, right, _ = _run(capsys)

    left.pop("runtime_seconds")
    right.pop("runtime_seconds")
    for epoch in [*left["epochs"], *right["epochs"]]:
        epoch.pop("runtime_seconds")

    assert left == right
