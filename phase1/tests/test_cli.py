import json
import subprocess
import sys
from pathlib import Path

import pytest

from uav_routing.alns import run_alns
from uav_routing.cli import result_to_dict
from uav_routing.config import ALNSConfig
from uav_routing.contextual.alns import run_contextual_alns
from uav_routing.contextual.config import ContextualBanditConfig
from uav_routing.parser import parse_instance

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
        "algorithm",
        "instance",
        "customers",
        "risks",
        "seed",
        "iterations",
        "score_policy",
        "risk_threshold",
        "vehicles",
        "distance",
        "risk_delay",
        "objective",
        "runtime_seconds",
        "feasible",
        "operators",
        "contextual_bandit",
        "pair_selection_stats",
        "routes",
    } <= data.keys()
    assert data["algorithm"] == "baseline"
    assert data["contextual_bandit"] is None
    assert data["score_policy"] == "lexicographic"
    assert data["risk_threshold"] == 0.2

    assert data["operators"]
    assert data["pair_selection_stats"] == []
    assert data["risks"] == 0

    assert sum(len(route["schedule"]) for route in data["routes"]) == 25
    assert all(
        {"customer_id", "arrival", "service_start", "departure"} <= stop.keys()
        for route in data["routes"]
        for stop in route["schedule"]
    )

    assert json.loads(completed.stdout) == data
    assert "ALNS Started" in completed.stderr
    assert "ALNS Completed" in completed.stderr

    assert not output.with_suffix(".json.tmp").exists()


def test_explicit_baseline_keeps_roulette_schema():
    completed = run_cli(
        "solve",
        "--algorithm",
        "baseline",
        "--instance",
        str(C101),
        "--customers",
        "25",
        "--risks",
        "0",
        "--iterations",
        "2",
    )

    assert completed.returncode == 0, completed.stderr

    data = json.loads(completed.stdout)

    assert data["algorithm"] == "baseline"
    assert data["contextual_bandit"] is None
    assert data["operators"]

    assert data["pair_selection_stats"] == []


def test_contextual_solve_uses_pair_stats_and_shared_route_schema(tmp_path):
    output = tmp_path / "contextual.json"
    completed = run_cli(
        "solve",
        "--algorithm",
        "contextual",
        "--instance",
        str(C101),
        "--customers",
        "25",
        "--risks",
        "0",
        "--iterations",
        "2",
        "--seed",
        "42",
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr

    data = json.loads(completed.stdout)

    assert json.loads(output.read_text()) == data
    assert data["algorithm"] == "contextual"
    assert data["contextual_bandit"] == {
        "context_window": 100,
        "linucb_exploration": 0.5,
        "linucb_regularization": 1.0,
        "include_temperature": True,
        "short_route_warm_start": False,
    }

    assert data["operators"] == []
    assert len(data["pair_selection_stats"]) == 15
    assert sum(stat["total_uses"] for stat in data["pair_selection_stats"]) == 2

    assert all(
        {
            "destroy_name",
            "repair_name",
            "total_uses",
            "total_raw_reward",
            "average_raw_reward",
        }
        == stat.keys()
        for stat in data["pair_selection_stats"]
    )
    assert sum(len(route["schedule"]) for route in data["routes"]) == 25

    assert "ALNS Started" in completed.stderr
    assert "ALNS Completed" in completed.stderr
    assert not output.with_suffix(".json.tmp").exists()


def test_contextual_result_requires_explicit_bandit_config_for_serialization():
    instance = parse_instance(C101, 5, 0)
    config = ALNSConfig(iterations=1)
    bandit = ContextualBanditConfig(17, 0.25, 2.0)
    result = run_contextual_alns(instance, config, bandit)

    with pytest.raises(ValueError, match="bandit_config"):
        result_to_dict(result, instance, config)

    payload = result_to_dict(result, instance, config, bandit)

    assert payload["contextual_bandit"] == {
        "context_window": 17,
        "linucb_exploration": 0.25,
        "linucb_regularization": 2.0,
        "include_temperature": True,
        "short_route_warm_start": False,
    }


def test_contextual_cli_enables_short_route_warm_start():
    completed = run_cli(
        "solve",
        "--algorithm",
        "contextual",
        "--instance",
        str(C101),
        "--customers",
        "100",
        "--iterations",
        "1",
        "--short-route-warm-start",
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["contextual_bandit"]["short_route_warm_start"]


def test_baseline_result_keeps_three_argument_serialization():
    instance = parse_instance(C101, 5, 0)
    config = ALNSConfig(iterations=1)
    result = run_alns(instance, config)

    payload = result_to_dict(result, instance, config)

    assert payload["algorithm"] == "baseline"
    assert payload["contextual_bandit"] is None


def test_cli_rejects_unknown_algorithm():
    completed = run_cli("solve", "--algorithm", "unknown", "--instance", str(C101))

    assert completed.returncode == 2
    assert "invalid choice" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_weights_that_do_not_sum_to_one():
    completed = run_cli(
        "solve", "--instance", str(C101), "--alpha", ".7", "--beta", ".7"
    )

    assert completed.returncode == 2
    assert "sum to 1" in completed.stderr


def test_cli_accepts_emergency_gate_score_policy():
    completed = run_cli(
        "solve",
        "--instance",
        str(C101),
        "--customers",
        "25",
        "--iterations",
        "1",
        "--score-policy",
        "emergency_gate",
        "--risk-threshold",
        "0.25",
    )

    assert completed.returncode == 0, completed.stderr

    data = json.loads(completed.stdout)

    assert data["score_policy"] == "emergency_gate"
    assert data["risk_threshold"] == 0.25


def test_cli_reports_input_errors_without_traceback(tmp_path):
    completed = run_cli("solve", "--instance", str(tmp_path / "missing.txt"))

    assert completed.returncode == 2
    assert "Traceback" not in completed.stderr


def test_cli_rejects_risk_count_outside_zero_to_five():
    completed = run_cli("solve", "--instance", str(C101), "--risks", "6")

    assert completed.returncode == 2
    assert "risks" in completed.stderr
