from dataclasses import replace
from pathlib import Path

import pytest

from uav_routing.alns import run_alns
from uav_routing.config import ALNSConfig
from uav_routing.dynamic.config import RollingHorizonConfig
from uav_routing.dynamic.horizon import (
    epoch_seed,
    next_decision_time,
    run_rolling_horizon,
)
from uav_routing.dynamic.models import (
    CustomerArrival,
    DeadlineUpdate,
    RiskUpdate,
    Scenario,
)
from uav_routing.dynamic.scenario import base_instance, load_scenario
from uav_routing.models import Customer, RiskZone

FIXTURES = Path(__file__).parent / "fixtures"
TINY = load_scenario(FIXTURES / "tiny_scenario.json")
EMPTY = Scenario(
    name="empty",
    instance_path=TINY.instance_path,
    static_customers=3,
    risk_limit=1,
    seed=0,
    horizon=100.0,
    events=(),
)
ALNS = ALNSConfig(iterations=50, seed=0, q_min=1, q_max=2)
CONFIG = RollingHorizonConfig(
    policy="warm_alns",
    trigger="periodic",
    epoch_length=30.0,
    iterations_epoch0=50,
    iterations_per_epoch=20,
    seed=5,
)


def _served(solution) -> list[int]:
    return sorted(c for route in solution.routes for c in route)


def test_epoch_seed_is_deterministic_and_distinct():
    assert epoch_seed(5, 1) == epoch_seed(5, 1)
    assert epoch_seed(5, 1) != epoch_seed(5, 2)
    assert epoch_seed(5, 1) != epoch_seed(6, 1)


def test_next_decision_time_by_trigger():
    events = TINY.events  # 5, 10, 30

    assert next_decision_time(0.0, CONFIG, events, 100.0) == 30.0
    assert next_decision_time(90.0, CONFIG, events, 100.0) == 100.0
    assert next_decision_time(0.0, replace(CONFIG, trigger="event"), events, 100.0) == (
        5.0
    )
    assert next_decision_time(30.0, replace(CONFIG, trigger="event"), (), 100.0) == (
        100.0
    )
    assert next_decision_time(
        0.0, replace(CONFIG, trigger="hybrid"), events, 100.0
    ) == (5.0)
    assert next_decision_time(
        10.0, replace(CONFIG, trigger="hybrid"), events[2:], 100.0
    ) == (30.0)


def test_empty_scenario_with_zero_epoch_iterations_reproduces_static_solution():
    result = run_rolling_horizon(EMPTY, ALNS, replace(CONFIG, iterations_per_epoch=0))
    static = run_alns(
        base_instance(EMPTY), replace(ALNS, iterations=50, seed=epoch_seed(5, 0))
    )

    assert result.realized == static.best_solution
    assert result.d_ref == static.d_ref
    assert result.evaluation.objective == pytest.approx(static.evaluation.objective)
    assert result.unserved == ()
    assert result.total_iterations == 50


def test_periodic_trigger_produces_expected_epochs():
    result = run_rolling_horizon(TINY, ALNS, CONFIG)

    assert [record.time for record in result.epochs] == [0.0, 30.0, 60.0, 90.0, 100.0]
    assert [record.index for record in result.epochs] == [0, 1, 2, 3, 4]
    assert result.total_iterations == 50 + 4 * 20
    assert sum(record.iterations for record in result.epochs) == result.total_iterations


def test_event_trigger_visits_event_times_and_horizon():
    result = run_rolling_horizon(TINY, ALNS, replace(CONFIG, trigger="event"))

    assert [record.time for record in result.epochs] == [0.0, 5.0, 10.0, 30.0, 100.0]


def test_events_are_revealed_only_at_or_before_epoch_time():
    result = run_rolling_horizon(TINY, ALNS, CONFIG)
    previous = 0.0

    for record in result.epochs[1:]:
        assert all(previous < event.time <= record.time for event in record.revealed)
        previous = record.time

    revealed = [event for record in result.epochs for event in record.revealed]

    assert revealed == list(TINY.events)


def test_locked_prefix_of_each_epoch_is_prefix_of_next():
    result = run_rolling_horizon(TINY, ALNS, CONFIG)

    for earlier, later in zip(result.epochs, result.epochs[1:]):
        assert later.locked_customers >= earlier.locked_customers

    assert result.epochs[-1].locked_customers == len(_served(result.realized))


def test_realized_solution_is_feasible_and_serves_arrivals():
    result = run_rolling_horizon(TINY, ALNS, CONFIG)

    assert result.evaluation.feasible
    assert _served(result.realized) == [1, 2, 3]
    assert result.unserved == ()
    assert result.unserved_priority == 0.0
    assert result.policy == "warm_alns"
    assert result.scenario == "tiny"
    assert result.runtime_seconds >= 0.0


@pytest.mark.parametrize("policy", ["greedy_insert", "cold_restart", "warm_alns"])
def test_same_seed_reproduces_simulation_result(policy):
    config = replace(CONFIG, policy=policy)

    left = run_rolling_horizon(TINY, ALNS, config)
    right = run_rolling_horizon(TINY, ALNS, config)

    assert left.realized == right.realized
    assert left.evaluation == right.evaluation
    assert [record.solution for record in left.epochs] == [
        record.solution for record in right.epochs
    ]


def test_rejected_customers_are_retried_then_lost():
    # customer 9 is far away with a window that closes before any UAV can reach it
    hopeless = Customer(9, 90, 90, 1, 20.0, 25.0, 0)
    scenario = replace(
        EMPTY,
        events=(CustomerArrival(15.0, hopeless),),
    )

    result = run_rolling_horizon(scenario, ALNS, replace(CONFIG, epoch_length=5.0))

    assert result.unserved == (9,)
    assert 9 not in _served(result.realized)
    assert result.evaluation.feasible
    assert any(9 in record.rejected for record in result.epochs)
    assert all(9 not in record.rejected for record in result.epochs if record.time > 30)


def test_frozen_priorities_survive_later_risk_updates():
    # zone 1 at (3, 4) radius 5 gives customer 1 priority 1.0 at t = 0;
    # a huge zone appearing later must not change it once it is locked
    scenario = replace(
        EMPTY,
        events=(RiskUpdate(60.0, RiskZone(1, 100, 100, 1)),),
    )

    result = run_rolling_horizon(scenario, ALNS, CONFIG)
    locked_before = result.epochs[2].locked_customers

    assert locked_before >= 1
    assert result.final_instance.risk_priority[1] == pytest.approx(1.0)


def test_deadline_update_on_locked_customer_is_skipped_not_raised():
    scenario = replace(
        EMPTY,
        events=(DeadlineUpdate(90.0, 1, 30.0),),
    )

    result = run_rolling_horizon(scenario, ALNS, CONFIG)

    assert result.evaluation.feasible
    assert _served(result.realized) == [1, 2, 3]


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        run_rolling_horizon(TINY, ALNS, replace(CONFIG, policy="bogus"))


def test_custom_solver_is_used_for_every_epoch_after_zero():
    calls = []

    def solver(instance, initial, constraints, d_ref, alns, iterations, seed):
        from uav_routing.dynamic.policies import evaluate_only

        calls.append((iterations, seed))

        return evaluate_only(instance, initial, constraints, d_ref, alns, seed)

    result = run_rolling_horizon(TINY, ALNS, CONFIG, solver=solver)

    assert len(calls) == 4
    assert [iterations for iterations, _ in calls] == [20, 20, 20, 20]
    assert len({seed for _, seed in calls}) == 4
    assert result.total_iterations == 50
