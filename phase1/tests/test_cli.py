import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
C101 = ROOT.parent / "dataset/solomon_risk/c101.txt"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "uav_routing.cli", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_solve_writes_required_json_fields(tmp_path):
    output = tmp_path / "result.json"
    completed = run_cli(
        "solve",
        "--instance",
        str(C101),
        "--customers",
        "25",
        "--risks",
        "0",
        "--iterations",
        "5",
        "--seed",
        "42",
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr

    data = json.loads(output.read_text())

    assert {
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
        "operators",
        "routes",
    } <= data.keys()
    assert data["risks"] == 0
    assert sum(len(route["schedule"]) for route in data["routes"]) == 25
    assert all(
        {"customer_id", "arrival", "service_start", "departure"} <= stop.keys()
        for route in data["routes"]
        for stop in route["schedule"]
    )


def test_cli_rejects_weights_that_do_not_sum_to_one():
    completed = run_cli(
        "solve", "--instance", str(C101), "--alpha", ".7", "--beta", ".7"
    )

    assert completed.returncode == 2
    assert "sum to 1" in completed.stderr


def test_cli_reports_input_errors_without_traceback(tmp_path):
    completed = run_cli("solve", "--instance", str(tmp_path / "missing.txt"))

    assert completed.returncode == 2
    assert "Traceback" not in completed.stderr


def test_cli_rejects_risk_count_outside_zero_to_five():
    completed = run_cli("solve", "--instance", str(C101), "--risks", "6")

    assert completed.returncode == 2
    assert "risks" in completed.stderr
