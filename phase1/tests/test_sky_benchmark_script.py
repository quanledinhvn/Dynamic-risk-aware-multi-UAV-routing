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
    isolated_root = tmp_path / "repo"
    (isolated_root / "scripts").mkdir(parents=True)
    (isolated_root / "infra/skypilot").mkdir(parents=True)
    (isolated_root / "phase1/configs").mkdir(parents=True)

    shutil.copy2(SCRIPT, isolated_root / "scripts/sky_benchmark.sh")
    shutil.copy2(
        ROOT / "infra/skypilot/benchmark.yaml",
        isolated_root / "infra/skypilot/benchmark.yaml",
    )
    shutil.copy2(
        DEFAULT_CONFIG,
        isolated_root / "phase1/configs/benchmark_p1_c25_r1.json",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    log_path = tmp_path / "commands.jsonl"
    cwd_log_path = tmp_path / "working-directories.jsonl"
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

with Path(os.environ["FAKE_CWD_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps([name, os.getcwd()]) + "\\n")

if name == "aws" and sys.argv[1:4] == [
    "sts",
    "get-caller-identity",
    "--query",
]:
    print(os.environ.get("FAKE_AWS_ACCOUNT_ID", "123456789012"))

    raise SystemExit(0)

selected = os.environ.get("FAKE_FAIL_SUBCOMMAND")
actual = sys.argv[1] if name == "sky" and len(sys.argv) > 1 else name
state_action = os.environ.get("FAKE_STATE_ACTION")
if actual == "logs" and "--follow" in sys.argv and state_action:
    state_path = Path(os.environ["FAKE_STATE_PATH"])
    if state_action == "remove":
        state_path.unlink(missing_ok=True)
    elif state_action == "malform":
        state_path.write_text("run_id=../../bad\\nremote_output=/tmp/bad\\n")
if os.environ.get("FAKE_TERM_SUBCOMMAND") == actual:
    os.kill(os.getppid(), signal.SIGTERM)
raise SystemExit(23 if selected == actual else 0)
"""
    for name in ("aws", "sky", "rsync", "date"):
        _write_executable(bin_dir / name, fake)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["FAKE_COMMAND_LOG"] = str(log_path)
    env["FAKE_CWD_LOG"] = str(cwd_log_path)
    env["TEST_REPO_ROOT"] = str(isolated_root)
    env["FAKE_STATE_PATH"] = str(
        isolated_root / ".sky-benchmark/uav-benchmark.state"
    )

    return env, log_path


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    root = Path(env.get("TEST_REPO_ROOT", ROOT))
    script = root / "scripts/sky_benchmark.sh"

    return subprocess.run(
        [str(script), *args],
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


def _repo(env: dict[str, str]) -> Path:
    return Path(env["TEST_REPO_ROOT"])


def _working_directories(env: dict[str, str]) -> list[list[str]]:
    path = Path(env["FAKE_CWD_LOG"])
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_fake_tools_uses_isolated_repository(fake_tools, tmp_path: Path) -> None:
    env, _ = fake_tools
    isolated_root = Path(env["TEST_REPO_ROOT"])

    assert isolated_root.is_relative_to(tmp_path)
    assert isolated_root != ROOT


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


@pytest.mark.parametrize(
    "region",
    ["-bad", "ap southeast 1", "ap-southeast", "ap-southeast-1;bad"],
)
def test_invalid_region_is_rejected_before_sky(fake_tools, region: str) -> None:
    env, log_path = fake_tools
    result = _run("check", "--region", region, env=env)

    assert result.returncode != 0
    assert "region" in result.stderr
    assert _commands(log_path) == []


def test_config_outside_repository_is_rejected_before_sky(
    fake_tools, tmp_path: Path
) -> None:
    env, log_path = fake_tools
    external = tmp_path / "benchmark.json"
    shutil.copyfile(
        _repo(env) / "phase1/configs/benchmark_p1_c25_r1.json",
        external,
    )

    result = _run("check", "--config", str(external), env=env)

    assert result.returncode != 0
    assert "repository" in result.stderr
    assert _commands(log_path) == []


@pytest.fixture
def cluster_state(fake_tools) -> Path:
    env, _ = fake_tools
    path = _repo(env) / ".sky-benchmark/uav-benchmark.state"
    yield path


@pytest.mark.parametrize("account_id", ["", "abc", "123", "1234567890123"])
def test_launch_rejects_invalid_aws_account_id_before_sky_launch(
    fake_tools, account_id: str
) -> None:
    env, log_path = fake_tools
    env["FAKE_AWS_ACCOUNT_ID"] = account_id

    result = _run("launch", env=env)

    assert result.returncode != 0
    assert "AWS account ID" in result.stderr
    assert not any(
        command[0:2] == ["sky", "launch"]
        for command in _commands(log_path)
    )


def test_launch_passes_s3_identity_and_records_it_in_state(
    fake_tools, cluster_state: Path
) -> None:
    env, log_path = fake_tools
    result = _run("launch", env=env)

    assert result.returncode == 0
    assert _commands(log_path) == [
        ["sky", "check", "aws"],
        [
            "aws",
            "sts",
            "get-caller-identity",
            "--query",
            "Account",
            "--output",
            "text",
        ],
        [
            "sky",
            "launch",
            "--yes",
            "--detach-run",
            "--cluster",
            "uav-benchmark",
            "--region",
            "ap-southeast-1",
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
            "--env",
            "BENCHMARK_S3_BUCKET=sky-uav-benchmark-123456789012-ap-southeast-1",
            "--env",
            "BENCHMARK_RUN_ID=20260922T120000Z",
            str(_repo(env) / "infra/skypilot/benchmark.yaml"),
        ],
    ]
    assert cluster_state.read_text(encoding="utf-8") == (
        "run_id=20260922T120000Z\n"
        "remote_output=phase1/results/sky/20260922T120000Z\n"
        "s3_bucket=sky-uav-benchmark-123456789012-ap-southeast-1\n"
        "s3_prefix=runs/20260922T120000Z\n"
    )


def test_launch_runs_sky_from_repository_root(
    fake_tools, cluster_state: Path
) -> None:
    env, _ = fake_tools
    result = _run("launch", env=env)

    assert result.returncode == 0
    assert ["sky", str(_repo(env))] in _working_directories(env)


def test_launch_accepts_region_override(fake_tools, cluster_state: Path) -> None:
    env, log_path = fake_tools
    result = _run("launch", "--region", "ap-southeast-2", env=env)

    assert result.returncode == 0
    launch = next(
        command
        for command in _commands(log_path)
        if command[0:2] == ["sky", "launch"]
    )

    assert launch[launch.index("--region") + 1] == "ap-southeast-2"


def test_launch_preserves_config_path_with_spaces(
    fake_tools, cluster_state: Path
) -> None:
    env, log_path = fake_tools
    config = _repo(env) / "phase1/configs/benchmark spaced.json"
    shutil.copyfile(
        _repo(env) / "phase1/configs/benchmark_p1_c25_r1.json",
        config,
    )

    try:
        result = _run("launch", "--config", str(config), env=env)
    finally:
        config.unlink(missing_ok=True)

    assert result.returncode == 0
    launch = next(
        command
        for command in _commands(log_path)
        if command[0:2] == ["sky", "launch"]
    )

    assert "BENCHMARK_CONFIG=phase1/configs/benchmark spaced.json" in launch


def test_spot_is_opt_in(fake_tools, cluster_state: Path) -> None:
    env, log_path = fake_tools
    assert _run("launch", env=env).returncode == 0
    launch = next(
        command
        for command in _commands(log_path)
        if command[0:2] == ["sky", "launch"]
    )

    assert "--use-spot" not in launch

    log_path.unlink()

    assert _run("launch", "--spot", env=env).returncode == 0
    launch = next(
        command
        for command in _commands(log_path)
        if command[0:2] == ["sky", "launch"]
    )

    assert "--use-spot" in launch


def _write_s3_state(path: Path) -> None:
    path.parent.mkdir(exist_ok=True)

    path.write_text(
        "run_id=20260922T120000Z\n"
        "remote_output=phase1/results/sky/20260922T120000Z\n"
        "s3_bucket=sky-uav-benchmark-123456789012-ap-southeast-1\n"
        "s3_prefix=runs/20260922T120000Z\n",
        encoding="utf-8",
    )


def test_download_uses_s3_after_cluster_is_gone(
    fake_tools, cluster_state: Path
) -> None:
    env, log_path = fake_tools
    _write_s3_state(cluster_state)

    result = _run("download", env=env)

    assert result.returncode == 0
    assert _commands(log_path) == [[
        "aws",
        "s3",
        "sync",
        "s3://sky-uav-benchmark-123456789012-ap-southeast-1/runs/20260922T120000Z/",
        str(_repo(env) / "phase1/results/sky/20260922T120000Z") + "/",
    ]]


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
            str(_repo(env) / "phase1/results/sky/20260922T120000Z") + "/",
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


@pytest.mark.parametrize(
    "state",
    [
        "run_id=20260922T120000Z\nremote_output=phase1/results/sky/20260922T120000Z\ns3_bucket=Bad_Bucket\ns3_prefix=runs/20260922T120000Z\n",
        "run_id=20260922T120000Z\nremote_output=phase1/results/sky/20260922T120000Z\ns3_bucket=sky-uav-benchmark-123456789012-ap-southeast-1\ns3_prefix=runs/../../bad\n",
        "run_id=20260922T120000Z\nrun_id=20260922T120000Z\nremote_output=phase1/results/sky/20260922T120000Z\n",
        "run_id=20260922T120000Z\nremote_output=phase1/results/sky/20260922T120000Z\nunknown=value\n",
    ],
)
def test_download_rejects_unsafe_s3_state(
    fake_tools, cluster_state: Path, state: str
) -> None:
    env, log_path = fake_tools
    cluster_state.parent.mkdir(exist_ok=True)

    cluster_state.write_text(state, encoding="utf-8")
    result = _run("download", env=env)

    assert result.returncode != 0
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


def test_run_stops_before_provision_when_preflight_fails(
    fake_tools, cluster_state: Path
) -> None:
    env, log_path = fake_tools
    env["FAKE_FAIL_SUBCOMMAND"] = "check"

    result = _run("run", env=env)

    assert result.returncode != 0
    assert _commands(log_path) == [["sky", "check", "aws"]]


@pytest.mark.parametrize("state_action", ["remove", "malform"])
def test_run_rejects_invalid_state_before_rsync_and_cleans_up(
    fake_tools, cluster_state: Path, state_action: str
) -> None:
    env, log_path = fake_tools
    env["FAKE_STATE_ACTION"] = state_action

    result = _run("run", env=env)
    commands = _commands(log_path)

    assert result.returncode != 0
    assert not any(command[0] == "rsync" for command in commands)
    assert ["sky", "logs", "uav-benchmark", "--no-follow"] in commands
    assert commands[-1] == ["sky", "down", "--yes", "uav-benchmark"]


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
