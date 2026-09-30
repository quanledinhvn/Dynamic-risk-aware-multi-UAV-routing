"""Scenario JSON format, validation and deterministic generation."""

import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np

from uav_routing.models import Customer, Instance, RiskZone
from uav_routing.parser import InstanceFormatError, parse_instance

from .models import CustomerArrival, DeadlineUpdate, Event, RiskUpdate, Scenario

EVENT_ORDER = {DeadlineUpdate: 0, RiskUpdate: 1, CustomerArrival: 2}
MIN_RISK_RADIUS = 2
MAX_RISK_RADIUS = 10
MIN_EVENT_TIME = 0.1


class ScenarioFormatError(ValueError):
    """Raised when a scenario file or generator request is invalid."""


def load_scenario(path: Path) -> Scenario:
    path = Path(path)

    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScenarioFormatError(f"{path}: invalid JSON: {exc}") from exc

    if not isinstance(values, dict):
        raise ScenarioFormatError(f"{path}: scenario must be a JSON object")

    return scenario_from_dict(values, path.parent)


def save_scenario(scenario: Scenario, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(scenario_to_dict(scenario, path.parent), indent=2)
    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(payload + "\n", encoding="utf-8")
    temporary.replace(path)


def scenario_from_dict(values: dict[str, object], base_dir: Path) -> Scenario:
    try:
        instance = Path(str(values["instance"]))
        static_customers = int(values["static_customers"])
        risk_limit = int(values["risks"])
        seed = int(values["seed"])
        horizon = float(values["horizon"])
        raw_events = values["events"]
    except KeyError as exc:
        raise ScenarioFormatError(f"missing key {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise ScenarioFormatError(f"invalid scalar field: {exc}") from exc

    if not instance.is_absolute():
        instance = (Path(base_dir) / instance).resolve()

    if not isinstance(raw_events, list):
        raise ScenarioFormatError("events must be a list")

    events = tuple(
        _event_from_dict(index, event) for index, event in enumerate(raw_events)
    )
    scenario = Scenario(
        name=str(values.get("name") or instance.stem),
        instance_path=instance,
        static_customers=static_customers,
        risk_limit=risk_limit,
        seed=seed,
        horizon=horizon,
        events=events,
    )

    _validate(scenario)

    return scenario


def scenario_to_dict(scenario: Scenario, base_dir: Path) -> dict[str, object]:
    relative = os.path.relpath(scenario.instance_path, Path(base_dir))

    return {
        "name": scenario.name,
        "instance": Path(relative).as_posix(),
        "static_customers": scenario.static_customers,
        "risks": scenario.risk_limit,
        "seed": scenario.seed,
        "horizon": scenario.horizon,
        "events": [_event_to_dict(event) for event in scenario.events],
    }


def base_instance(scenario: Scenario) -> Instance:
    try:
        return parse_instance(
            scenario.instance_path, scenario.static_customers, scenario.risk_limit
        )
    except (InstanceFormatError, ValueError, OSError) as exc:
        raise ScenarioFormatError(f"cannot load base instance: {exc}") from exc


def generate_scenario(
    instance_path: Path,
    *,
    static_customers: int,
    dynamic_customers: int,
    risk_limit: int = 5,
    risk_events: int = 0,
    deadline_events: int = 0,
    release_fraction: float = 0.6,
    seed: int = 0,
) -> Scenario:
    if not 0 < release_fraction <= 1:
        raise ValueError("release_fraction must be in (0, 1]")

    if static_customers <= 0 or dynamic_customers < 0:
        raise ValueError("static_customers must be positive and dynamic non-negative")

    if risk_events < 0 or deadline_events < 0:
        raise ValueError("event counts must be non-negative")

    instance_path = Path(instance_path).resolve()

    try:
        full = parse_instance(
            instance_path, static_customers + dynamic_customers, risk_limit
        )
    except InstanceFormatError as exc:
        raise ScenarioFormatError(str(exc)) from exc

    rng = np.random.default_rng(seed)
    static = full.customers[:static_customers]
    dynamic = full.customers[static_customers:]
    horizon = float(full.depot.due_date)

    events: list[Event] = []
    events.extend(_arrival_events(dynamic, release_fraction, horizon, rng))
    events.extend(_risk_events(full, risk_events, horizon, rng))
    events.extend(_deadline_events(static, deadline_events, rng))

    scenario = Scenario(
        name=f"{instance_path.stem}-n{static_customers}-d{dynamic_customers}-s{seed}",
        instance_path=instance_path,
        static_customers=static_customers,
        risk_limit=risk_limit,
        seed=seed,
        horizon=horizon,
        events=tuple(sorted(events, key=_event_key)),
    )

    _validate(scenario)

    return scenario


def _arrival_events(
    dynamic: tuple[Customer, ...],
    release_fraction: float,
    horizon: float,
    rng: np.random.Generator,
) -> list[Event]:
    events: list[Event] = []

    for customer in dynamic:
        upper = min(release_fraction * customer.due_date, horizon)
        time = _round_time(float(rng.uniform(0.0, upper)), horizon)
        ready_time = max(float(customer.ready_time), time)

        events.append(CustomerArrival(time, replace(customer, ready_time=ready_time)))

    return events


def _risk_events(
    full: Instance, count: int, horizon: float, rng: np.random.Generator
) -> list[Event]:
    zones = list(full.risk_zones)
    xs = [customer.x for customer in full.customers]
    ys = [customer.y for customer in full.customers]
    events: list[Event] = []

    for index in range(1, count + 1):
        time = _round_time(horizon * index / (count + 1), horizon)

        if zones and float(rng.random()) < 0.5:
            zone_id = zones[int(rng.integers(len(zones)))].id
        else:
            zone_id = max((zone.id for zone in zones), default=0) + 1

        zone = RiskZone(
            zone_id,
            float(rng.integers(int(min(xs)), int(max(xs)) + 1)),
            float(rng.integers(int(min(ys)), int(max(ys)) + 1)),
            float(rng.integers(MIN_RISK_RADIUS, MAX_RISK_RADIUS + 1)),
        )
        zones = [existing for existing in zones if existing.id != zone_id] + [zone]

        events.append(RiskUpdate(time, zone))

    return events


def _deadline_events(
    static: tuple[Customer, ...], count: int, rng: np.random.Generator
) -> list[Event]:
    candidates = [c for c in static if c.due_date - c.ready_time >= 1.0]
    chosen = rng.choice(len(candidates), min(count, len(candidates)), replace=False)
    events: list[Event] = []

    for position in sorted(int(value) for value in chosen):
        customer = candidates[position]
        ready, due = float(customer.ready_time), float(customer.due_date)
        upper = ready if ready > 0 else 0.3 * due
        time = _round_time(float(rng.uniform(0.0, upper)), due)
        theta = float(rng.uniform(0.5, 0.9))
        new_due = min(round(ready + theta * (due - ready), 1), round(due - 0.1, 1))

        events.append(DeadlineUpdate(time, customer.id, max(new_due, ready)))

    return events


def _round_time(value: float, upper: float) -> float:
    return float(min(max(round(value, 1), MIN_EVENT_TIME), upper))


def _event_key(event: Event) -> tuple[float, int, int]:
    if isinstance(event, CustomerArrival):
        identity = event.customer.id
    elif isinstance(event, RiskUpdate):
        identity = event.zone.id
    else:
        identity = event.customer_id

    return (event.time, EVENT_ORDER[type(event)], identity)


def _event_from_dict(index: int, values: object) -> Event:
    if not isinstance(values, dict):
        raise ScenarioFormatError(f"event {index}: must be an object")

    try:
        time = float(values["time"])
        kind = str(values["type"])

        if kind == "customer_arrival":
            return CustomerArrival(time, _customer_from_dict(values["customer"]))

        if kind == "risk_update":
            zone = values["zone"]

            return RiskUpdate(
                time,
                RiskZone(
                    int(zone["id"]),
                    float(zone["x"]),
                    float(zone["y"]),
                    float(zone["radius"]),
                ),
            )

        if kind == "deadline_update":
            return DeadlineUpdate(
                time, int(values["customer_id"]), float(values["due_date"])
            )
    except KeyError as exc:
        raise ScenarioFormatError(f"event {index}: missing key {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise ScenarioFormatError(f"event {index}: invalid value: {exc}") from exc

    raise ScenarioFormatError(f"event {index}: unknown event type {kind!r}")


def _customer_from_dict(values: object) -> Customer:
    if not isinstance(values, dict):
        raise ScenarioFormatError("customer must be an object")

    return Customer(
        int(values["id"]),
        float(values["x"]),
        float(values["y"]),
        float(values["demand"]),
        float(values["ready_time"]),
        float(values["due_date"]),
        float(values["service_time"]),
    )


def _event_to_dict(event: Event) -> dict[str, object]:
    if isinstance(event, CustomerArrival):
        customer = event.customer

        return {
            "time": event.time,
            "type": "customer_arrival",
            "customer": {
                "id": customer.id,
                "x": customer.x,
                "y": customer.y,
                "demand": customer.demand,
                "ready_time": customer.ready_time,
                "due_date": customer.due_date,
                "service_time": customer.service_time,
            },
        }

    if isinstance(event, RiskUpdate):
        zone = event.zone

        return {
            "time": event.time,
            "type": "risk_update",
            "zone": {"id": zone.id, "x": zone.x, "y": zone.y, "radius": zone.radius},
        }

    return {
        "time": event.time,
        "type": "deadline_update",
        "customer_id": event.customer_id,
        "due_date": event.due_date,
    }


def _validate(scenario: Scenario) -> None:
    if scenario.static_customers <= 0:
        raise ScenarioFormatError("static_customers must be positive")

    if not 0 <= scenario.risk_limit <= 5:
        raise ScenarioFormatError("risks must be between 0 and 5")

    if not scenario.horizon > 0:
        raise ScenarioFormatError("horizon must be positive")

    instance = base_instance(scenario)
    known = {customer.id: customer for customer in instance.customers}
    known[instance.depot.id] = instance.depot
    previous_time = 0.0

    for index, event in enumerate(scenario.events):
        if event.time < 0:
            raise ScenarioFormatError(f"event {index}: time must be non-negative")

        if event.time > scenario.horizon:
            raise ScenarioFormatError(f"event {index}: time exceeds horizon")

        if event.time < previous_time:
            raise ScenarioFormatError(f"event {index}: events must be sorted by time")

        previous_time = event.time

        _validate_event(index, event, known)


def _validate_event(index: int, event: Event, known: dict[int, Customer]) -> None:
    if isinstance(event, CustomerArrival):
        customer = event.customer

        if customer.id in known:
            raise ScenarioFormatError(
                f"event {index}: customer id {customer.id} already exists"
            )

        if customer.ready_time < event.time:
            raise ScenarioFormatError(
                f"event {index}: ready_time must not precede the release time"
            )

        if customer.due_date < customer.ready_time:
            raise ScenarioFormatError(
                f"event {index}: due_date must not precede ready_time"
            )

        if customer.demand < 0 or customer.service_time < 0:
            raise ScenarioFormatError(
                f"event {index}: demand and service_time must be non-negative"
            )

        known[customer.id] = customer
    elif isinstance(event, RiskUpdate):
        if event.zone.radius <= 0:
            raise ScenarioFormatError(f"event {index}: radius must be positive")
    else:
        current = known.get(event.customer_id)

        if current is None or event.customer_id == 0:
            raise ScenarioFormatError(
                f"event {index}: unknown customer {event.customer_id}"
            )

        if event.due_date >= current.due_date:
            raise ScenarioFormatError(f"event {index}: deadline_update must tighten")

        if event.due_date < current.ready_time:
            raise ScenarioFormatError(
                f"event {index}: due_date must not precede ready_time"
            )

        known[event.customer_id] = replace(current, due_date=event.due_date)
