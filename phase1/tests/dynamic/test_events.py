import numpy as np
import pytest
from helpers import make_instance

from uav_routing.dynamic.events import EventApplicationError, apply_events
from uav_routing.dynamic.models import CustomerArrival, DeadlineUpdate, RiskUpdate
from uav_routing.models import Customer, RiskZone

CUSTOMERS = (
    Customer(1, 3, 4, 1, 0, 100, 0),
    Customer(2, 6, 8, 1, 0, 100, 0),
    Customer(3, 0, 10, 1, 0, 100, 0),
)
INSTANCE = make_instance(CUSTOMERS, max_vehicles=2, priorities=(0.5, 0.0, 0.0))
NEW = Customer(9, 20, 20, 2, 15.0, 90.0, 1)


def test_arrival_appends_customer_and_grows_matrix():
    updated = apply_events(INSTANCE, (CustomerArrival(10.0, NEW),), {})

    assert updated.customers[-1] == NEW
    assert updated.customers[:-1] == INSTANCE.customers
    assert updated.distance_matrix.shape == (5, 5)
    assert updated.distance_matrix[0, 4] == pytest.approx(np.hypot(20, 20))
    assert updated.risk_priority.shape == (5,)


def test_arrival_with_existing_id_is_rejected():
    with pytest.raises(EventApplicationError, match="id"):
        apply_events(INSTANCE, (CustomerArrival(1.0, CUSTOMERS[0]),), {})


def test_risk_update_changes_only_free_customer_priorities():
    zone = RiskUpdate(5.0, RiskZone(9, 3, 4, 10))
    frozen = {1: 0.5}

    updated = apply_events(INSTANCE, (zone,), frozen)

    assert updated.risk_zones == (zone.zone,)
    assert updated.risk_priority[1] == pytest.approx(0.5)
    assert updated.risk_priority[2] == pytest.approx(0.5)
    assert updated.risk_priority[3] == pytest.approx(1 - np.hypot(3, 6) / 10)


def test_risk_update_with_existing_id_replaces_zone():
    first = RiskUpdate(1.0, RiskZone(9, 3, 4, 10))
    second = RiskUpdate(2.0, RiskZone(9, 6, 8, 2))

    updated = apply_events(INSTANCE, (first, second), {})

    assert updated.risk_zones == (second.zone,)
    assert updated.risk_priority[2] == pytest.approx(1.0)


def test_deadline_update_tightens_free_customer():
    updated = apply_events(INSTANCE, (DeadlineUpdate(5.0, 2, 40.0),), {})

    assert updated.customers[1].due_date == 40.0
    assert updated.customers[0] == CUSTOMERS[0]


def test_deadline_update_on_frozen_customer_is_rejected():
    with pytest.raises(EventApplicationError, match="locked"):
        apply_events(INSTANCE, (DeadlineUpdate(5.0, 2, 40.0),), {2: 0.0})


def test_deadline_update_that_loosens_is_rejected():
    with pytest.raises(EventApplicationError, match="tighten"):
        apply_events(INSTANCE, (DeadlineUpdate(5.0, 2, 150.0),), {})


def test_deadline_update_below_ready_time_is_rejected():
    instance = make_instance((Customer(1, 3, 4, 1, 50, 100, 0),))

    with pytest.raises(EventApplicationError, match="ready_time"):
        apply_events(instance, (DeadlineUpdate(5.0, 1, 30.0),), {})


def test_unknown_customer_is_rejected():
    with pytest.raises(EventApplicationError, match="unknown"):
        apply_events(INSTANCE, (DeadlineUpdate(5.0, 42, 40.0),), {})


def test_no_events_returns_equal_instance():
    # priorities are always recomputed from the zones, so use a consistent instance
    instance = apply_events(INSTANCE, (RiskUpdate(1.0, RiskZone(9, 3, 4, 10)),), {})

    updated = apply_events(instance, (), {})

    assert updated.customers == instance.customers
    assert updated.risk_zones == instance.risk_zones
    assert np.array_equal(updated.risk_priority, instance.risk_priority)
    assert np.array_equal(updated.distance_matrix, instance.distance_matrix)


def test_input_instance_is_not_mutated():
    before = INSTANCE.risk_priority.copy()

    apply_events(INSTANCE, (RiskUpdate(1.0, RiskZone(9, 3, 4, 10)),), {})

    assert np.array_equal(INSTANCE.risk_priority, before)
    assert INSTANCE.risk_zones == ()


def test_drop_customers_removes_ids_and_keeps_frozen_priorities():
    from uav_routing.dynamic.events import drop_customers

    instance = apply_events(INSTANCE, (RiskUpdate(1.0, RiskZone(9, 3, 4, 10)),), {})
    frozen = {3: 0.42}

    dropped = drop_customers(instance, (2, 42), frozen)

    assert [customer.id for customer in dropped.customers] == [1, 3]
    assert dropped.distance_matrix.shape == (3, 3)
    assert dropped.risk_priority[1] == pytest.approx(instance.risk_priority[1])
    assert dropped.risk_priority[2] == pytest.approx(0.42)
    assert dropped.risk_zones == instance.risk_zones
