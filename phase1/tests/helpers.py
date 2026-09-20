from dataclasses import replace

import numpy as np

from uav_routing.geometry import euclidean_distance_matrix
from uav_routing.models import Customer, Instance, RiskZone


def make_instance(
    customers: tuple[Customer, ...],
    *,
    depot: Customer | None = None,
    max_vehicles: int = 2,
    capacity: float = 100,
    priorities: tuple[float, ...] | None = None,
    name: str = "TEST",
) -> Instance:
    depot = depot or Customer(0, 0, 0, 0, 0, 100, 0)
    nodes = (depot, *customers)
    customer_priorities = priorities or tuple(0.0 for _ in customers)
    return Instance(
        name=name,
        depot=depot,
        customers=customers,
        risk_zones=(),
        max_vehicles=max_vehicles,
        capacity=capacity,
        distance_matrix=euclidean_distance_matrix(nodes),
        risk_priority=np.asarray((0.0, *customer_priorities)),
    )


def with_depot_due(instance: Instance, due_date: float) -> Instance:
    depot = replace(instance.depot, due_date=due_date)
    return replace(
        instance,
        depot=depot,
        distance_matrix=euclidean_distance_matrix((depot, *instance.customers)),
    )
