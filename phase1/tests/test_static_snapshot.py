"""Guard: default run_alns must reproduce the Phase 1 result exactly."""

from pathlib import Path

import pytest

from uav_routing.alns import run_alns
from uav_routing.config import ALNSConfig
from uav_routing.parser import parse_instance

INSTANCE = Path(__file__).resolve().parents[2] / "dataset" / "solomon_risk" / "c101.txt"

SNAPSHOT_ROUTES = (
    (5, 3, 7, 8, 10, 11, 9, 6, 4, 2, 1),
    (20, 24, 25, 15, 23, 22, 21),
    (13, 17, 18, 19, 16, 14, 12),
)
SNAPSHOT_VEHICLES = 3
SNAPSHOT_DISTANCE = 239.33378170687155
SNAPSHOT_RISK_DELAY = 0.03580718239498451
SNAPSHOT_OBJECTIVE = 0.6417742578974153
SNAPSHOT_D_REF = 191.8136197786562
SNAPSHOT_USES = {
    "destroy:random": 30,
    "destroy:worst": 42,
    "destroy:related": 37,
    "destroy:route": 48,
    "destroy:risk_priority": 43,
    "repair:greedy": 71,
    "repair:regret2": 66,
    "repair:risk_priority": 63,
}


def test_static_alns_snapshot_is_unchanged():
    instance = parse_instance(INSTANCE, 25, 5)
    result = run_alns(instance, ALNSConfig(iterations=200, seed=42))

    assert result.best_solution.routes == SNAPSHOT_ROUTES
    assert result.evaluation.vehicle_count == SNAPSHOT_VEHICLES
    assert result.d_ref == pytest.approx(SNAPSHOT_D_REF, abs=1e-12)
    assert result.evaluation.distance == pytest.approx(SNAPSHOT_DISTANCE, abs=1e-12)
    assert result.evaluation.risk_delay == pytest.approx(SNAPSHOT_RISK_DELAY, abs=1e-12)
    assert result.evaluation.objective == pytest.approx(SNAPSHOT_OBJECTIVE, abs=1e-12)
    assert {stats.name: stats.total_uses for stats in result.operator_stats} == (
        SNAPSHOT_USES
    )
