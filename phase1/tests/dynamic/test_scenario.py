import json
from pathlib import Path

import pytest

from uav_routing.dynamic.models import CustomerArrival, DeadlineUpdate, RiskUpdate
from uav_routing.dynamic.scenario import (
    ScenarioFormatError,
    base_instance,
    generate_scenario,
    load_scenario,
    save_scenario,
)
from uav_routing.parser import parse_instance

FIXTURES = Path(__file__).parent / "fixtures"
TINY = FIXTURES / "tiny_scenario.json"
C101 = Path(__file__).resolve().parents[3] / "dataset" / "solomon_risk" / "c101.txt"


def _tiny_payload() -> dict:
    return json.loads(TINY.read_text(encoding="utf-8"))


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "scenario.json"
    payload["instance"] = str(FIXTURES.parent.parent / "fixtures" / "tiny_valid.txt")
    path.write_text(json.dumps(payload), encoding="utf-8")

    return path


def test_load_tiny_scenario_parses_all_event_types():
    scenario = load_scenario(TINY)

    assert scenario.name == "tiny"
    assert scenario.static_customers == 2
    assert scenario.risk_limit == 1
    assert scenario.horizon == 100.0
    assert scenario.instance_path.is_file()
    assert [type(event) for event in scenario.events] == [
        DeadlineUpdate,
        CustomerArrival,
        RiskUpdate,
    ]
    assert scenario.events[1].customer.id == 3
    assert scenario.events[2].zone.radius == 5


def test_base_instance_matches_phase1_parser():
    scenario = load_scenario(TINY)
    expected = parse_instance(scenario.instance_path, 2, 1)
    instance = base_instance(scenario)

    assert instance.customers == expected.customers
    assert instance.risk_zones == expected.risk_zones
    assert instance.max_vehicles == expected.max_vehicles


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda p: p["events"].reverse(), "sorted"),
        (lambda p: p["events"][0].update(time=-1.0), "time"),
        (lambda p: p["events"][2].update(time=1000.0), "horizon"),
        (lambda p: p["events"][1]["customer"].update(id=1), "id"),
        (lambda p: p["events"][1]["customer"].update(ready_time=5.0), "ready_time"),
        (lambda p: p["events"][0].update(due_date=90.0), "tighten"),
        (lambda p: p["events"][0].update(customer_id=99), "unknown"),
        (lambda p: p["events"][2]["zone"].update(radius=0), "radius"),
        (lambda p: p["events"][0].update(type="teleport"), "type"),
        (lambda p: p.pop("horizon"), "horizon"),
    ],
)
def test_invalid_scenarios_are_rejected(tmp_path, mutate, message):
    payload = _tiny_payload()
    mutate(payload)

    with pytest.raises(ScenarioFormatError, match=message):
        load_scenario(_write(tmp_path, payload))


def test_save_then_load_round_trips(tmp_path):
    scenario = load_scenario(TINY)
    target = tmp_path / "nested" / "copy.json"

    save_scenario(scenario, target)
    reloaded = load_scenario(target)

    assert reloaded == scenario
    assert not Path(json.loads(target.read_text())["instance"]).is_absolute()


def test_generate_is_deterministic_for_same_seed():
    kwargs = dict(
        static_customers=25,
        dynamic_customers=5,
        risk_limit=5,
        risk_events=2,
        deadline_events=2,
        release_fraction=0.6,
        seed=7,
    )

    assert generate_scenario(C101, **kwargs) == generate_scenario(C101, **kwargs)
    assert generate_scenario(C101, **kwargs) != generate_scenario(
        C101, **{**kwargs, "seed": 8}
    )


def test_generate_uses_next_solomon_rows_as_dynamic_customers():
    scenario = generate_scenario(
        C101, static_customers=25, dynamic_customers=5, risk_limit=5, seed=1
    )
    arrivals = [
        event for event in scenario.events if isinstance(event, CustomerArrival)
    ]

    assert sorted(event.customer.id for event in arrivals) == [26, 27, 28, 29, 30]
    assert all(event.customer.ready_time >= event.time for event in arrivals)
    assert all(0 < event.time <= scenario.horizon for event in arrivals)
    assert scenario.name == "c101-n25-d5-s1"
    assert scenario.static_customers == 25


def test_generate_produces_valid_risk_and_deadline_events(tmp_path):
    scenario = generate_scenario(
        C101,
        static_customers=25,
        dynamic_customers=3,
        risk_limit=5,
        risk_events=3,
        deadline_events=2,
        seed=3,
    )
    kinds = [type(event) for event in scenario.events]

    assert kinds.count(RiskUpdate) == 3
    assert kinds.count(DeadlineUpdate) == 2
    assert [event.time for event in scenario.events] == sorted(
        event.time for event in scenario.events
    )

    target = tmp_path / "generated.json"
    save_scenario(scenario, target)

    assert load_scenario(target) == scenario


def test_generate_rejects_when_solomon_has_too_few_rows():
    with pytest.raises(ScenarioFormatError, match="customers"):
        generate_scenario(C101, static_customers=90, dynamic_customers=20, seed=0)


def test_generate_rejects_bad_release_fraction():
    with pytest.raises(ValueError, match="release_fraction"):
        generate_scenario(
            C101, static_customers=5, dynamic_customers=1, release_fraction=1.5
        )
