"""Resumable sensitivity runner with progress, elapsed time and ETA.

Usage (from the repository root):
    phase1/.venv/Scripts/python sensitivity_test/code/runner.py run [--workers 7]
    phase1/.venv/Scripts/python sensitivity_test/code/runner.py status
    phase1/.venv/Scripts/python sensitivity_test/code/runner.py stop

Every finished job is written atomically to results/jobs/<case>/<point>/<instance>-s<seed>.json.
`run` skips jobs that already have a result, so stopping and restarting is safe.
A failed job is retried up to MAX_ATTEMPTS times; failures go to errors.jsonl.
`stop` creates a STOP file: no new job is started and running jobs finish first.
"""

import os

# Keep each worker single-threaded so the CPU budget is respected.
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import argparse
import json
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import plan  # noqa: E402

DEFAULT_ROOT = HERE.parent / "results"
DEFAULT_WORKERS = max(1, int((os.cpu_count() or 2) * 0.6))
MAX_ATTEMPTS = 3
HEARTBEAT_SECONDS = 30
STALE_SECONDS = 120
ANALYZE_EVERY_SECONDS = 1200
DEFAULT_EFFICIENCY = 1.15


# --------------------------------------------------------------------------- #
# Worker side
# --------------------------------------------------------------------------- #


def _init_worker(src: str) -> None:
    sys.path.insert(0, src)
    _lower_priority()


def _lower_priority() -> None:
    if sys.platform != "win32":
        os.nice(10)

        return

    import ctypes

    below_normal = 0x00004000
    kernel32 = ctypes.windll.kernel32
    kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), below_normal)


def run_job(spec: dict) -> dict:
    started = time.perf_counter()

    try:
        row = _solve(spec)
    except Exception:  # noqa: BLE001 - every failure is recorded and retried
        return {"ok": False, "error": traceback.format_exc()}

    row["runtime_seconds"] = time.perf_counter() - started
    row["worker_pid"] = os.getpid()

    return {"ok": True, "row": row}


def _solve(spec: dict) -> dict:
    from uav_routing.config import ALNSConfig
    from uav_routing.contextual.config import ContextualBanditConfig

    alns = ALNSConfig.from_dict({**spec["alns"], "seed": spec["seed"]})
    bandit = ContextualBanditConfig.from_dict(spec["bandit"])

    if spec["kind"] == "static":
        return _solve_static(spec, alns, bandit)

    return _solve_dynamic(spec, alns, bandit)


def _solve_static(spec: dict, alns, bandit) -> dict:
    from uav_routing.contextual.alns import run_contextual_alns
    from uav_routing.parser import parse_instance

    path = plan.DATASET / "solomon_risk" / f"{spec['instance']}.txt"
    instance = parse_instance(path, plan.STATIC_CUSTOMERS, plan.STATIC_RISKS)
    result = run_contextual_alns(instance, alns, bandit)

    return _evaluation_row(result.evaluation, result.best_solution.routes) | {
        "iterations": result.iterations,
    }


def _solve_dynamic(spec: dict, alns, bandit) -> dict:
    from uav_routing.dynamic.config import RollingHorizonConfig
    from uav_routing.dynamic.horizon import run_rolling_horizon
    from uav_routing.dynamic.scenario import load_scenario

    name = plan.DYNAMIC_SCENARIO.format(instance=spec["instance"], seed=spec["seed"])
    scenario = load_scenario(plan.DATASET / "solomon_dynamic" / name)
    rolling = RollingHorizonConfig.from_dict(
        {**spec["rolling"], "policy": spec["policy"], "seed": spec["seed"]}
    )

    active_bandit = bandit if spec["policy"] == "contextual_warm_alns" else None
    result = run_rolling_horizon(scenario, alns, rolling, bandit=active_bandit)

    return _evaluation_row(result.evaluation, result.realized.routes) | {
        "scenario": scenario.name,
        "unserved": len(result.unserved),
        "unserved_priority": float(result.unserved_priority),
        "epochs": len(result.epochs),
        "iterations": result.total_iterations,
    }


def _evaluation_row(evaluation, routes) -> dict:
    return {
        "feasible": bool(evaluation.feasible),
        "vehicles": evaluation.vehicle_count,
        "distance": float(evaluation.distance),
        "risk_delay": float(evaluation.risk_delay),
        "objective": float(evaluation.objective),
        "routes": [list(route) for route in routes],
    }


# --------------------------------------------------------------------------- #
# Bookkeeping shared by run and status
# --------------------------------------------------------------------------- #


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    replace_with_retry(temporary, path)


def replace_with_retry(source: Path, target: Path, attempts: int = 20) -> None:
    """os.replace that tolerates short locks taken by OneDrive or a reader."""
    for attempt in range(1, attempts + 1):
        try:
            source.replace(target)

            return
        except PermissionError:
            if attempt == attempts:
                raise

            time.sleep(0.25 * attempt)


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _error_attempts(root: Path) -> Counter:
    attempts: Counter = Counter()
    path = root / "errors.jsonl"

    if not path.exists():
        return attempts

    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            attempts[json.loads(line)["job_id"]] += 1
        except (json.JSONDecodeError, KeyError):
            continue

    return attempts


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60

    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def _session_seconds(state: dict) -> float:
    total = 0.0

    for session in state.get("sessions", []):
        start = datetime.fromisoformat(session["start"])
        end = datetime.fromisoformat(session.get("end") or session["start"])
        total += (end - start).total_seconds()

    return total


class Progress:
    """Snapshot of finished/failed/pending jobs and the time estimates."""

    def __init__(self, root: Path, jobs: list, workers: int, efficiency: float):
        self.root = root
        self.jobs = jobs
        self.workers = workers
        self.efficiency = efficiency
        self.attempts = _error_attempts(root)

        self.done: dict[str, dict] = {}
        self.cpu_by_case: dict[str, list[float]] = defaultdict(list)

        for job in jobs:
            row = _read_json(job.result_path(root), None)

            if row is not None:
                self.record(job, row)

    def record(self, job, row: dict) -> None:
        self.done[job.job_id] = row
        self.cpu_by_case[job.point.case].append(row["runtime_seconds"] / job.point.factor)

    def failed(self, job) -> bool:
        return job.job_id not in self.done and self.attempts[job.job_id] >= MAX_ATTEMPTS

    def unit_seconds(self, case: str) -> float:
        samples = self.cpu_by_case.get(case)

        if not samples:
            return plan.PRIOR_SECONDS[case]

        return sum(samples) / len(samples)

    def remaining_cpu(self, jobs=None) -> float:
        return sum(
            self.unit_seconds(job.point.case) * job.point.factor
            for job in (jobs or self.jobs)
            if job.job_id not in self.done and not self.failed(job)
        )

    def eta_seconds(self) -> float:
        return self.remaining_cpu() / self.workers * self.efficiency

    def cpu_done(self) -> float:
        return sum(row["runtime_seconds"] for row in self.done.values())

    def summary_line(self, elapsed: float) -> str:
        total = len(self.jobs)
        done = len(self.done)
        failed = sum(self.failed(job) for job in self.jobs)

        percent = 100.0 * done / total if total else 100.0

        return (
            f"Tổng: {done:,} / {total:,} job ({percent:.1f}%) · lỗi {failed} · "
            f"đã chạy {_format_duration(elapsed)} (CPU {_format_duration(self.cpu_done())}) · "
            f"còn lại ≈ {_format_duration(self.eta_seconds())} ({self.workers} worker)"
        )


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #


class Runner:
    def __init__(self, args: argparse.Namespace):
        self.root: Path = args.out
        self.workers: int = args.workers
        self.retry_failed: bool = args.retry_failed

        self.jobs = plan.all_jobs(
            tuple(args.seeds), tuple(args.instances), set(args.only or ())
        )
        self.state_path = self.root / "state.json"
        self.stop_path = self.root / "STOP"

        self.lock = threading.Lock()
        self.in_flight: dict[str, str] = {}
        self.session_attempts: Counter = Counter()
        self.last_analyze = time.time()
        self.analyze_proc: subprocess.Popen | None = None

    # -- state ------------------------------------------------------------- #

    def _start_session(self) -> None:
        state = _read_json(self.state_path, {})
        sessions = state.get("sessions", [])
        sessions.append({"start": datetime.now().isoformat(timespec="seconds"), "end": None})

        self.state = {
            "sessions": sessions,
            "pid": os.getpid(),
            "workers": self.workers,
            "running": True,
            "job_ids": [job.job_id for job in self.jobs],
        }
        self.session_started = time.time()
        self.session_cpu = 0.0

        self._save_state()

    def _save_state(self) -> None:
        with self.lock:
            self.state["sessions"][-1]["end"] = datetime.now().isoformat(timespec="seconds")
            self.state["last_update"] = _now()
            self.state["in_flight"] = dict(self.in_flight)

            self.state["efficiency"] = self._efficiency()
            _write_json_atomic(self.state_path, self.state)

    def _efficiency(self) -> float:
        wall = time.time() - self.session_started

        if self.session_cpu < 600 or wall < 300:
            return DEFAULT_EFFICIENCY

        measured = wall * self.workers / self.session_cpu

        return round(min(2.0, max(1.0, measured)), 3)

    def _heartbeat(self, stop: threading.Event) -> None:
        while not stop.wait(HEARTBEAT_SECONDS):
            self._safe_save_state()

    def _safe_save_state(self) -> None:
        """Never let a bookkeeping failure stop the heartbeat or the run."""
        try:
            self._save_state()
        except Exception as exc:  # noqa: BLE001
            self._log(f"WARN không ghi được state.json: {exc!r}")

    # -- logging ----------------------------------------------------------- #

    def _log(self, message: str) -> None:
        line = f"{_now()} {message}"

        print(line, flush=True)

        with open(self.root / "runner.log", "a", encoding="utf-8") as log:
            log.write(line + "\n")

    def _log_error(self, job, error: str) -> None:
        payload = {"time": _now(), "job_id": job.job_id, "error": error}

        with open(self.root / "errors.jsonl", "a", encoding="utf-8") as errors:
            errors.write(json.dumps(payload) + "\n")

    # -- main loop --------------------------------------------------------- #

    def run(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.stop_path.unlink(missing_ok=True)

        _keep_awake()
        _lower_priority()

        self.progress = Progress(self.root, self.jobs, self.workers, DEFAULT_EFFICIENCY)
        self.commit = _git_commit()

        queue = [job for job in self.jobs if job.job_id not in self.progress.done]

        if not self.retry_failed:
            queue = [job for job in queue if not self.progress.failed(job)]

        self._start_session()
        self._log(f"START {len(queue)} job cần chạy · commit {self.commit[:7]} · {self.workers} worker")

        heartbeat_stop = threading.Event()
        threading.Thread(target=self._heartbeat, args=(heartbeat_stop,), daemon=True).start()

        try:
            self._loop(queue)
        finally:
            heartbeat_stop.set()
            self.state["running"] = False
            self.in_flight.clear()

            self._safe_save_state()
            self._analyze()

    def _loop(self, queue: list) -> None:
        src = str(plan.PHASE1 / "src")
        pending: dict = {}
        stopping = False

        with ProcessPoolExecutor(self.workers, initializer=_init_worker, initargs=(src,)) as pool:
            try:
                while queue or pending:
                    stopping = stopping or self.stop_path.exists()

                    while queue and not stopping and len(pending) < self.workers:
                        job = queue.pop(0)
                        pending[pool.submit(run_job, self._spec(job))] = job

                        with self.lock:
                            self.in_flight[job.job_id] = _now()

                    if not pending:
                        break

                    finished, _ = wait(pending, timeout=HEARTBEAT_SECONDS, return_when=FIRST_COMPLETED)

                    for future in finished:
                        job = pending.pop(future)

                        with self.lock:
                            self.in_flight.pop(job.job_id, None)

                        self._handle(job, future.result(), queue)
            except KeyboardInterrupt:
                self._log("Ctrl+C: dừng nhận job mới; các job đang chạy sẽ bị hủy và chạy lại lần sau")
                pool.shutdown(wait=False, cancel_futures=True)

                raise

        if stopping:
            self._log("STOP: đã dừng theo yêu cầu. Chạy lại lệnh `run` để tiếp tục.")
        else:
            self._log("ALL DONE")

        self._analyze(wait_done=True)

    def _spec(self, job) -> dict:
        alns, rolling, bandit = job.point.configs()
        case = plan.CASES[job.point.case]

        return {
            "kind": case["kind"],
            "policy": case["policy"],
            "instance": job.instance,
            "seed": job.seed,
            "alns": alns,
            "rolling": rolling,
            "bandit": bandit,
        }

    def _handle(self, job, outcome: dict, queue: list) -> None:
        if not outcome["ok"]:
            self._handle_failure(job, outcome["error"], queue)

            return

        point = job.point
        row = {
            "case": point.case,
            "point": point.point_id,
            "param": point.param,
            "level": point.level,
            "priority": point.priority,
            "instance": job.instance,
            "seed": job.seed,
            "alpha": point.configs()[0]["alpha"],
            "beta": point.configs()[0]["beta"],
            **outcome["row"],
            "git_commit": self.commit,
            "finished_at": _now(),
        }

        _write_json_atomic(job.result_path(self.root), row)
        self.progress.record(job, row)
        self.session_cpu += row["runtime_seconds"]

        self.progress.efficiency = self._efficiency()
        self._log(
            f"done {job.job_id} {row['runtime_seconds']:.0f}s · "
            + self.progress.summary_line(_session_seconds(self.state))
        )

        self._safe_save_state()

        if self._point_complete(point):
            self._log(f"POINT DONE {point.point_id}")
            self._analyze()
        elif job.seed < plan.FIRST_WAVE_SEEDS and self._point_complete(point, wave_only=True):
            self._log(f"POINT DONE (seed 0-{plan.FIRST_WAVE_SEEDS - 1}) {point.point_id}")
            self._analyze()
        elif time.time() - self.last_analyze >= ANALYZE_EVERY_SECONDS:
            self._analyze()

    def _handle_failure(self, job, error: str, queue: list) -> None:
        self._log_error(job, error)
        self.session_attempts[job.job_id] += 1
        self.progress.attempts[job.job_id] += 1

        attempts = (
            self.session_attempts[job.job_id]
            if self.retry_failed
            else self.progress.attempts[job.job_id]
        )
        last_line = error.strip().splitlines()[-1] if error.strip() else "unknown error"

        if attempts < MAX_ATTEMPTS:
            queue.append(job)
            self._log(f"ERROR {job.job_id} (lần {attempts}/{MAX_ATTEMPTS}, sẽ thử lại): {last_line}")
        else:
            self._log(f"FAILED {job.job_id} sau {attempts} lần: {last_line}")

    def _point_complete(self, point, wave_only: bool = False) -> bool:
        return all(
            job.job_id in self.progress.done
            for job in self.jobs
            if job.point.point_id == point.point_id
            and (not wave_only or job.seed < plan.FIRST_WAVE_SEEDS)
        )

    def _analyze(self, wait_done: bool = False) -> None:
        script = HERE / "analyze.py"

        if not script.exists():
            return

        # Non-blocking: the main loop must keep feeding workers while analyze runs.
        if self.analyze_proc is not None and self.analyze_proc.poll() is None:
            if not wait_done:
                return

            self.analyze_proc.wait(timeout=600)

        self.last_analyze = time.time()
        flags = 0x4000 if sys.platform == "win32" else 0

        try:
            self.analyze_proc = subprocess.Popen(
                [sys.executable, str(script), "--out", str(self.root)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )

            if wait_done:
                self.analyze_proc.wait(timeout=600)
        except (OSError, subprocess.SubprocessError) as exc:
            self._log(f"analyze.py lỗi: {exc}")


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=plan.REPO, capture_output=True, text=True
        )
    except OSError:
        return "unknown"

    return result.stdout.strip() or "unknown"


def _keep_awake() -> None:
    if sys.platform != "win32":
        return

    import ctypes

    es_continuous, es_system_required = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required)


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #


def status(args: argparse.Namespace) -> None:
    root: Path = args.out
    state = _read_json(root / "state.json", {})

    if state.get("job_ids"):
        wanted = set(state["job_ids"])
        jobs = [job for job in plan.all_jobs() if job.job_id in wanted]
    else:
        jobs = plan.all_jobs()

    workers = state.get("workers", DEFAULT_WORKERS)
    efficiency = state.get("efficiency", DEFAULT_EFFICIENCY)
    progress = Progress(root, jobs, workers, efficiency)

    print(progress.summary_line(_session_seconds(state)))
    print(f"Trạng thái runner: {_runner_state(state, root)} · cập nhật lúc {state.get('last_update', '—')}")
    print()

    in_flight = state.get("in_flight", {}) if state.get("running") else {}
    _print_case_table(jobs, progress, in_flight)
    print()
    _print_point_table(jobs, progress, in_flight, args.all)

    if in_flight:
        print()
        print("Đang chạy:")

        for job_id, since in in_flight.items():
            print(f"  {job_id}  (từ {since})")


def _runner_state(state: dict, root: Path) -> str:
    if not state:
        return "chưa chạy"

    if not state.get("running"):
        return "đã dừng"

    try:
        last = datetime.strptime(state["last_update"], "%Y-%m-%d %H:%M:%S")
    except (KeyError, ValueError):
        return "không rõ"

    age = (datetime.now() - last).total_seconds()

    if age > STALE_SECONDS:
        return f"không phản hồi {int(age)}s (có thể đã bị tắt)"

    suffix = " · đang dừng (STOP)" if (root / "STOP").exists() else ""

    return f"đang chạy (pid {state.get('pid')}){suffix}"


def _label(done: int, total: int, failed: int, running: int) -> str:
    if done == total:
        return "done"

    if running:
        return "running"

    if failed and done + failed == total:
        return "failed"

    return "partial" if done else "pending"


def _print_case_table(jobs: list, progress: Progress, in_flight: dict) -> None:
    print(f"{'Case':<20}{'job':>12}{'%':>8}{'CPU đã chạy':>14}{'còn lại (CPU)':>16}  trạng thái")

    for case, info in plan.CASES.items():
        case_jobs = [job for job in jobs if job.point.case == case]

        if not case_jobs:
            continue

        done = [job for job in case_jobs if job.job_id in progress.done]
        failed = sum(progress.failed(job) for job in case_jobs)
        running = sum(job.job_id in in_flight for job in case_jobs)

        cpu = sum(progress.done[job.job_id]["runtime_seconds"] for job in done)
        remaining = progress.remaining_cpu(case_jobs) if len(done) < len(case_jobs) else 0.0
        percent = 100.0 * len(done) / len(case_jobs)

        print(
            f"{info['label']:<20}{len(done):>5}/{len(case_jobs):<6}{percent:>7.1f}%"
            f"{_format_duration(cpu):>14}{_format_duration(remaining):>16}  "
            f"{_label(len(done), len(case_jobs), failed, running)}"
        )


def _print_point_table(jobs: list, progress: Progress, in_flight: dict, show_all: bool) -> None:
    by_point: dict[str, list] = defaultdict(list)

    for job in jobs:
        by_point[job.point.point_id].append(job)

    print(f"{'Điểm đo':<16}{'case':<6}{'ưu tiên':<9}{'job':>9}{'%':>8}{'CPU':>10}  trạng thái")
    hidden = 0

    for point_id, point_jobs in by_point.items():
        point = point_jobs[0].point
        done = [job for job in point_jobs if job.job_id in progress.done]
        failed = sum(progress.failed(job) for job in point_jobs)

        running = sum(job.job_id in in_flight for job in point_jobs)
        label = _label(len(done), len(point_jobs), failed, running)

        if label == "pending" and not show_all:
            hidden += 1

            continue

        cpu = sum(progress.done[job.job_id]["runtime_seconds"] for job in done)
        percent = 100.0 * len(done) / len(point_jobs)
        failed_note = f" ({failed} lỗi)" if failed else ""

        print(
            f"{point_id:<16}{point.case:<6}{point.priority:<9}"
            f"{len(done):>4}/{len(point_jobs):<4}{percent:>7.0f}%{_format_duration(cpu):>10}  {label}{failed_note}"
        )

    if hidden:
        print(f"... và {hidden} điểm đo đang chờ (thêm --all để xem hết)")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv=None) -> None:
    # Windows consoles default to cp1252, which cannot print Vietnamese text.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("run", "status", "stop"))
    parser.add_argument("--out", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(plan.SEEDS))
    parser.add_argument("--instances", nargs="+", default=list(plan.INSTANCES))

    parser.add_argument("--only", nargs="*", help="point ids or case letters (A/B/C)")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--all", action="store_true", help="status: list pending points too")
    args = parser.parse_args(argv)

    if args.command == "run":
        Runner(args).run()
    elif args.command == "status":
        status(args)
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "STOP").write_text(_now(), encoding="utf-8")
        print("Đã tạo STOP: runner sẽ dừng sau khi các job đang chạy xong.")


if __name__ == "__main__":
    main()
