"""Sensitivity plan: 3 cases, one-at-a-time measurement points, jobs.

Case A: rolling horizon with warm ALNS (roulette) on Solomon-Dynamic n88-d12.
Case B: static contextual ALNS (LinUCB) on Solomon-RISK, 100 customers, 5 risks.
Case C: rolling horizon with contextual warm ALNS on Solomon-Dynamic n88-d12.

See sensitivity_test/CLAUDE.md section 2.2 for the rationale of every level.
"""

from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PHASE1 = REPO / "phase1"
DATASET = REPO / "dataset"

INSTANCES = (
    "c101",
    "c102",
    "c103",
    "r101",
    "r102",
    "r103",
    "rc101",
    "rc102",
    "rc103",
)
SEEDS = (0, 1, 2, 3, 4)

DYNAMIC_SCENARIO = "{instance}-n88-d12-s{seed}.json"
STATIC_CUSTOMERS = 100
STATIC_RISKS = 5

PRIORITY_ORDER = {"base": 0, "high": 1, "medium": 2}
CASE_ORDER = {"C": 0, "B": 1, "A": 2}

# Seconds per job at the default configuration (100 customers), measured by the
# smoke test on master 1d15fce with 3 concurrent low-priority workers.
PRIOR_SECONDS = {"A": 400.0, "B": 83.0, "C": 374.0}

# Seeds below this value run first for every point (screening wave), the rest after.
FIRST_WAVE_SEEDS = 3

ALNS_DYNAMIC = {
    "iterations": 1000,
    "seed": 0,
    "alpha": 0.5,
    "beta": 0.5,
    "score_policy": "lexicographic",
    "risk_threshold": 0.2,
    "q_min": 2,
    "q_max": 5,
    "segment_length": 100,
    "reaction_factor": 0.2,
    "initial_temperature": 0.05,
    "cooling_rate": 0.9995,
    "minimum_temperature": 0.000001,
    "minimum_weight": 0.1,
    "removal_determinism": 6.0,
    "related_distance_weight": 1.0,
    "related_time_weight": 1.0,
    "related_demand_weight": 1.0,
    "related_risk_weight": 1.0,
    "reward_best": 20.0,
    "reward_improve": 10.0,
    "reward_accepted": 2.0,
}
ALNS_STATIC = {**ALNS_DYNAMIC, "iterations": 1000, "cooling_rate": 0.9954}
ROLLING = {
    "trigger": "periodic",
    "epoch_length": 60.0,
    "epoch_fraction": 0.05,
    "iterations_epoch0": 2000,
    "iterations_per_epoch": 500,
    "carry_weights": False,
    "seed": 0,
}
BANDIT = {
    "context_window": 100,
    "linucb_exploration": 0.5,
    "linucb_regularization": 1.0,
    "include_temperature": True,
    "short_route_warm_start": False,
}

CASES = {
    "A": {"label": "A. RH (warm_alns)", "kind": "dynamic", "policy": "warm_alns"},
    "B": {"label": "B. CTX (static)", "kind": "static", "policy": "contextual"},
    "C": {
        "label": "C. RH + CTX",
        "kind": "dynamic",
        "policy": "contextual_warm_alns",
    },
}


@dataclass(frozen=True)
class Point:
    point_id: str
    case: str
    param: str
    level: str
    priority: str
    factor: float
    alns: dict = field(default_factory=dict)
    rolling: dict = field(default_factory=dict)
    bandit: dict = field(default_factory=dict)

    def configs(self) -> tuple[dict, dict, dict]:
        base_alns = ALNS_STATIC if CASES[self.case]["kind"] == "static" else ALNS_DYNAMIC

        return (
            {**base_alns, **self.alns},
            {**ROLLING, **self.rolling},
            {**BANDIT, **self.bandit},
        )


@dataclass(frozen=True)
class Job:
    point: Point
    instance: str
    seed: int

    @property
    def job_id(self) -> str:
        return f"{self.point.point_id}/{self.instance}-s{self.seed}"

    def result_path(self, root: Path) -> Path:
        return root / "jobs" / self.point.case / self.point.point_id / (
            f"{self.instance}-s{self.seed}.json"
        )

    @property
    def expected_seconds(self) -> float:
        return PRIOR_SECONDS[self.point.case] * self.point.factor


def _beta(beta: float) -> dict:
    return {"alpha": round(1.0 - beta, 10), "beta": beta}


def _points_rolling(case: str) -> list[Point]:
    points = []

    for level, factor in (("0.025", 1.78), ("0.1", 0.62), ("0.2", 0.43)):
        points.append(
            Point(f"{case}_ef_{level}", case, "epoch_fraction", level, "high", factor,
                  rolling={"epoch_fraction": float(level)})
        )

    for level, factor in (("100", 0.43), ("250", 0.64), ("1000", 1.77)):
        points.append(
            Point(f"{case}_ipe_{level}", case, "iterations_per_epoch", level, "high",
                  factor, rolling={"iterations_per_epoch": int(level)})
        )

    return points


def _points_shared(case: str) -> list[Point]:
    points = []

    for level in ("0.0", "0.25", "0.75", "1.0"):
        points.append(
            Point(f"{case}_beta_{level}", case, "beta", level, "medium", 1.0,
                  alns=_beta(float(level)))
        )

    for (q_min, q_max), factor in (((5, 10), 2.2), ((10, 20), 6.3)):
        points.append(
            Point(f"{case}_q_{q_min}-{q_max}", case, "q_min-q_max", f"{q_min}-{q_max}",
                  "medium", factor, alns={"q_min": q_min, "q_max": q_max})
        )

    return points


def _points_a() -> list[Point]:
    points = [Point("A0_base", "A", "base", "default", "base", 1.0)]
    points += _points_rolling("A")

    for level, factor in (("event", 1.27), ("hybrid", 1.64)):
        points.append(
            Point(f"A_trig_{level}", "A", "trigger", level, "high", factor,
                  rolling={"trigger": level})
        )

    for level, factor in (("500", 0.88), ("1000", 0.92), ("4000", 1.16)):
        points.append(
            Point(f"A_ie0_{level}", "A", "iterations_epoch0", level, "medium", factor,
                  rolling={"iterations_epoch0": int(level)})
        )

    return points + _points_shared("A")


def _points_b() -> list[Point]:
    points = [Point("B0_base", "B", "base", "default", "base", 1.0)]

    for level in ("0.0", "0.1", "1.0", "2.0"):
        points.append(
            Point(f"B_explo_{level}", "B", "linucb_exploration", level, "high", 1.0,
                  bandit={"linucb_exploration": float(level)})
        )

    for level in ("25", "50", "200"):
        points.append(
            Point(f"B_win_{level}", "B", "context_window", level, "high", 1.0,
                  bandit={"context_window": int(level)})
        )

    # Scale cooling so the final temperature matches the 1000-iteration default.
    for level, cooling, factor in (("500", 0.99079, 0.5), ("2000", 0.99770, 2.0)):
        points.append(
            Point(f"B_iter_{level}", "B", "iterations", level, "high", factor,
                  alns={"iterations": int(level), "cooling_rate": cooling})
        )

    for level in ("0.1", "10.0"):
        points.append(
            Point(f"B_reg_{level}", "B", "linucb_regularization", level, "medium", 1.0,
                  bandit={"linucb_regularization": float(level)})
        )

    points.append(
        Point("B_temp_off", "B", "include_temperature", "false", "medium", 1.0,
              bandit={"include_temperature": False})
    )

    return points + _points_shared("B")


def _points_c() -> list[Point]:
    points = [Point("C0_base", "C", "base", "default", "base", 1.0)]

    for level in ("0.0", "2.0"):
        points.append(
            Point(f"C_explo_{level}", "C", "linucb_exploration", level, "high", 1.0,
                  bandit={"linucb_exploration": float(level)})
        )

    points += _points_rolling("C")

    for level in ("25", "200"):
        points.append(
            Point(f"C_win_{level}", "C", "context_window", level, "medium", 1.0,
                  bandit={"context_window": int(level)})
        )

    return points + _points_shared("C")


def all_points() -> list[Point]:
    points = _points_a() + _points_b() + _points_c()

    return sorted(
        points,
        key=lambda p: (
            PRIORITY_ORDER[p.priority],
            CASE_ORDER[p.case] if p.priority != "base" else 0,
            p.factor,
            p.point_id,
        ),
    )


def all_jobs(
    seeds: tuple[int, ...] = SEEDS,
    instances: tuple[str, ...] = INSTANCES,
    only: set[str] | None = None,
) -> list[Job]:
    jobs = [
        Job(point, instance, seed)
        for point in all_points()
        if not only or point.point_id in only or point.case in only
        for seed in seeds
        for instance in instances
    ]

    # Stable sort: the first seeds of every point finish before the later wave.
    return sorted(jobs, key=lambda job: job.seed >= FIRST_WAVE_SEEDS)


if __name__ == "__main__":
    points = all_points()
    jobs = all_jobs()
    cpu_hours = sum(job.expected_seconds for job in jobs) / 3600

    for case in CASES:
        count = sum(point.case == case for point in points)
        print(f"case {case}: {count} points")

    print(f"total: {len(points)} points, {len(jobs)} jobs, ~{cpu_hours:.1f} CPU-hours")
