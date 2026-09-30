"""Pure application of revealed events to an immutable Instance."""

from dataclasses import replace

import numpy as np

from uav_routing.geometry import compute_risk_priorities, euclidean_distance_matrix
from uav_routing.models import Customer, Instance, RiskZone

from .models import CustomerArrival, DeadlineUpdate, Event, RiskUpdate


class EventApplicationError(ValueError):
    """Raised when an event cannot be applied to the current instance."""


def apply_events(
    instance: Instance,
    events: tuple[Event, ...],
    frozen_priority: dict[int, float],
) -> Instance:
    customers = list(instance.customers)
    zones = list(instance.risk_zones)

    for event in events:
        if isinstance(event, CustomerArrival):
            _apply_arrival(customers, instance.depot, event.customer)
        elif isinstance(event, RiskUpdate):
            _apply_risk(zones, event.zone)
        elif isinstance(event, DeadlineUpdate):
            _apply_deadline(customers, event, frozen_priority)
        else:
            raise EventApplicationError(f"unsupported event {event!r}")

    return _rebuild(instance, tuple(customers), tuple(zones), frozen_priority)


def _apply_arrival(
    customers: list[Customer], depot: Customer, customer: Customer
) -> None:
    existing = {depot.id, *(known.id for known in customers)}

    if customer.id in existing:
        raise EventApplicationError(
            f"customer_arrival: customer id {customer.id} already exists"
        )

    customers.append(customer)


def _apply_risk(zones: list[RiskZone], zone: RiskZone) -> None:
    if zone.radius <= 0:
        raise EventApplicationError(
            f"risk_update: zone {zone.id} radius must be positive"
        )

    for index, existing in enumerate(zones):
        if existing.id == zone.id:
            zones[index] = zone

            return

    zones.append(zone)


def _apply_deadline(
    customers: list[Customer],
    event: DeadlineUpdate,
    frozen_priority: dict[int, float],
) -> None:
    index = next(
        (i for i, customer in enumerate(customers) if customer.id == event.customer_id),
        None,
    )

    if index is None:
        raise EventApplicationError(
            f"deadline_update: unknown customer {event.customer_id}"
        )

    if event.customer_id in frozen_priority:
        raise EventApplicationError(
            f"deadline_update: customer {event.customer_id} is locked"
        )

    current = customers[index]

    if event.due_date >= current.due_date:
        raise EventApplicationError(
            f"deadline_update: customer {event.customer_id} must tighten its due date"
        )

    if event.due_date < current.ready_time:
        raise EventApplicationError(
            f"deadline_update: customer {event.customer_id} due date below ready_time"
        )

    customers[index] = replace(current, due_date=event.due_date)


def _rebuild(
    instance: Instance,
    customers: tuple[Customer, ...],
    zones: tuple[RiskZone, ...],
    frozen_priority: dict[int, float],
) -> Instance:
    nodes = (instance.depot, *customers)
    priorities = np.concatenate(
        (np.zeros(1, dtype=float), compute_risk_priorities(customers, zones))
    )

    for index, customer in enumerate(customers, start=1):
        if customer.id in frozen_priority:
            priorities[index] = float(frozen_priority[customer.id])

    return replace(
        instance,
        customers=customers,
        risk_zones=zones,
        distance_matrix=euclidean_distance_matrix(nodes),
        risk_priority=priorities,
    )
