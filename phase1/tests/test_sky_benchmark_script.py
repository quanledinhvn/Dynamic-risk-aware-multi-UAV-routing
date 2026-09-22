import json
import os
import shutil

# isort: split
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "sky_benchmark.sh"
DEFAULT_CONFIG = ROOT / "phase1/configs/benchmark_p1_c25_r1.json"


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def fake_tools(tmp_path: Path) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    log_path = tmp_path / "commands.jsonl"
    fake = """#!/usr/bin/env python3
import json
import os
import signal
import sys
from pathlib import Path

name = Path(sys.argv[0]).name
if name == "date":
    print("20260922T120000Z")
    raise SystemExit(0)

with Path(os.environ["FAKE_COMMAND_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps([name, *sys.argv[1:]]) + "\\n")

selected = os.environ.get("FAKE_FAIL_SUBCOMMAND")
actual = sys.argv[1] if name == "sky" and len(sys.argv) > 1 else name
if os.environ.get("FAKE_TERM_SUBCOMMAND") == actual:
    os.kill(os.getppid(), signal.SIGTERM)
raise SystemExit(23 if selected == actual else 0)
"""
    for name in ("sky", "rsync", "date"):
        _write_executable(bin_dir / name, fake)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["FAKE_COMMAND_LOG"] = str(log_path)

    return env, log_path


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd="/tmp",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _commands(log_path: Path) -> list[list[str]]:
    if not log_path.exists():
        return []

    return [json.loads(line) for line in log_path.read_text().splitlines()]


def test_check_fails_when_sky_is_missing(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PATH"] = "/usr/bin:/bin"

    result = _run("check", env=env)

    assert result.returncode != 0
    assert "SkyPilot" in result.stderr


def test_missing_config_is_rejected_before_sky(fake_tools) -> None:
    env, log_path = fake_tools
    result = _run("check", "--config", "phase1/configs/missing.json", env=env)

    assert result.returncode != 0
    assert "không tồn tại" in result.stderr
    assert _commands(log_path) == []


@pytest.mark.parametrize("workers", ["0", "-1", "abc", "1.5"])
def test_invalid_workers_are_rejected_before_sky(fake_tools, workers: str) -> None:
    env, log_path = fake_tools
    result = _run("check", "--workers", workers, env=env)

    assert result.returncode != 0
    assert "workers" in result.stderr
    assert _commands(log_path) == []


@pytest.mark.parametrize("cluster", ["-bad", "bad name", "bad/name", "bad;name"])
def test_invalid_cluster_is_rejected_before_sky(fake_tools, cluster: str) -> None:
    env, log_path = fake_tools
    result = _run("check", "--cluster", cluster, env=env)

    assert result.returncode != 0
    assert "cluster" in result.stderr
    assert _commands(log_path) == []


def test_config_outside_repository_is_rejected_before_sky(
    fake_tools, tmp_path: Path
) -> None:
    env, log_path = fake_tools
    external = tmp_path / "benchmark.json"
    shutil.copyfile(DEFAULT_CONFIG, external)

    result = _run("check", "--config", str(external), env=env)

    assert result.returncode != 0
    assert "repository" in result.stderr
    assert _commands(log_path) == []


@pytest.fixture
def cluster_state() -> Path:
    path = ROOT / ".sky-benchmark/uav-benchmark.state"
    path.unlink(missing_ok=True)

    yield path

    path.unlink(missing_ok=True)


def test_launch_passes_defaults_and_records_state_after_success(
    fake_tools, cluster_state: Path
) -> None:
    env, log_path = fake_tools
    result = _run("launch", env=env)

    assert result.returncode == 0
    assert _commands(log_path) == [
        ["sky", "check", "aws"],
        [
            "sky",
            "launch",
            "--yes",
            "--detach-run",
            "--cluster",
            "uav-benchmark",
            "--instance-type",
            "c7a.2xlarge",
            "--idle-minutes-to-autostop",
            "15",
            "--down",
            "--wait-for",
            "jobs",
            "--env",
            "BENCHMARK_CONFIG=phase1/configs/benchmark_p1_c25_r1.json",
            "--env",
            "BENCHMARK_WORKERS=8",
            "--env",
            "BENCHMARK_OUTPUT_DIR=phase1/results/sky/20260922T120000Z",
            str(ROOT / "infra/skypilot/benchmark.yaml"),
        ],
    ]
    assert cluster_state.read_text(encoding="utf-8") == (
        "run_id=20260922T120000Z\n"
        "remote_output=phase1/results/sky/20260922T120000Z\n"
    )


def test_launch_preserves_config_path_with_spaces(
    fake_tools, cluster_state: Path
) -> None:
    env, log_path = fake_tools
    config = ROOT / "phase1/configs/benchmark spaced.json"
    shutil.copyfile(DEFAULT_CONFIG, config)

    try:
        result = _run("launch", "--config", str(config), env=env)
    finally:
        config.unlink(missing_ok=True)

    assert result.returncode == 0
    launch = _commands(log_path)[1]
    assert "BENCHMARK_CONFIG=phase1/configs/benchmark spaced.json" in launch


def test_spot_is_opt_in(fake_tools, cluster_state: Path) -> None:
    env, log_path = fake_tools
    assert _run("launch", env=env).returncode == 0
    assert "--use-spot" not in _commands(log_path)[1]

    log_path.unlink()

    assert _run("launch", "--spot", env=env).returncode == 0
    assert "--use-spot" in _commands(log_path)[1]


def test_download_uses_validated_state_paths(
    fake_tools, cluster_state: Path
) -> None:
    env, log_path = fake_tools
    cluster_state.parent.mkdir(exist_ok=True)
    cluster_state.write_text(
        "run_id=20260922T120000Z\n"
        "remote_output=phase1/results/sky/20260922T120000Z\n",
        encoding="utf-8",
    )

    result = _run("download", env=env)

    assert result.returncode == 0
    assert _commands(log_path) == [
        [
            "rsync",
            "-az",
            "--",
            "uav-benchmark:~/sky_workdir/phase1/results/sky/20260922T120000Z/",
            str(ROOT / "phase1/results/sky/20260922T120000Z") + "/",
        ]
    ]


@pytest.mark.parametrize(
    "state",
    ["", "broken", "run_id=../../bad\nremote_output=/tmp/bad\n"],
)
def test_download_rejects_missing_or_malformed_state(
    fake_tools, cluster_state: Path, state: str
) -> None:
    env, log_path = fake_tools
    if state:
        cluster_state.parent.mkdir(exist_ok=True)
        cluster_state.write_text(state, encoding="utf-8")

    result = _run("download", env=env)

    assert result.returncode != 0
    assert "state" in result.stderr
    assert _commands(log_path) == []


def test_down_targets_only_the_validated_cluster(fake_tools) -> None:
    env, log_path = fake_tools
    result = _run("down", "--cluster", "research-01", env=env)

    assert result.returncode == 0
    assert _commands(log_path) == [["sky", "down", "--yes", "research-01"]]


def _subcommands(commands: list[list[str]]) -> list[str]:
    return [
        command[1] if command[0] == "sky" else command[0]
        for command in commands
    ]


def test_run_orders_launch_logs_download_and_down(
    fake_tools, cluster_state: Path
) -> None:
    env, log_path = fake_tools
    result = _run("run", env=env)

    assert result.returncode == 0
    assert _subcommands(_commands(log_path)) == [
        "check",
        "launch",
        "logs",
        "rsync",
        "down",
    ]


@pytest.mark.parametrize("failing_command", ["launch", "logs", "rsync"])
def test_run_cleans_up_after_failure(
    fake_tools, cluster_state: Path, failing_command: str
) -> None:
    env, log_path = fake_tools
    env["FAKE_FAIL_SUBCOMMAND"] = failing_command

    result = _run("run", env=env)
    commands = _commands(log_path)

    assert result.returncode != 0
    assert ["sky", "logs", "uav-benchmark", "--no-follow"] in commands
    assert commands[-1] == ["sky", "down", "--yes", "uav-benchmark"]


def test_keep_cluster_on_failure_skips_down_and_prints_cleanup_command(
    fake_tools, cluster_state: Path
) -> None:
    env, log_path = fake_tools
    env["FAKE_FAIL_SUBCOMMAND"] = "logs"

    result = _run("run", "--keep-cluster-on-failure", env=env)

    assert result.returncode != 0
    assert not any(command[1:2] == ["down"] for command in _commands(log_path))
    assert (
        "scripts/sky_benchmark.sh down --cluster uav-benchmark"
        in result.stderr
    )


def test_term_after_launch_uses_failure_cleanup_policy(
    fake_tools, cluster_state: Path
) -> None:
    env, log_path = fake_tools
    env["FAKE_TERM_SUBCOMMAND"] = "logs"

    result = _run("run", env=env)

    assert result.returncode != 0
    assert _commands(log_path)[-1] == [
        "sky",
        "down",
        "--yes",
        "uav-benchmark",
    ]
