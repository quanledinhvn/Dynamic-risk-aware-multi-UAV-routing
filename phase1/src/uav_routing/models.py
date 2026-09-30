"""Immutable domain records used by the routing solver."""

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np

CustomerId: TypeAlias = int
Route: TypeAlias = tuple[CustomerId, ...]


@dataclass(frozen=True)
class Customer:
    id: int
    x: float
    y: float
    demand: float
    ready_time: float
    due_date: float
    service_time: float


@dataclass(frozen=True)
class RiskZone:
    id: int
    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class Instance:
    name: str
    depot: Customer
    customers: tuple[Customer, ...]
    risk_zones: tuple[RiskZone, ...]
    max_vehicles: int
    capacity: float
    distance_matrix: np.ndarray
    risk_priority: np.ndarray


@dataclass(frozen=True)
class Solution:
    routes: tuple[Route, ...]


@dataclass(frozen=True)
class SearchConstraints:
    """Locked route prefixes and the earliest departure of unlaunched routes."""

    locked_prefixes: tuple[Route, ...] = ()
    free_departure: float = 0.0

    def __post_init__(self) -> None:
        locked = [customer for prefix in self.locked_prefixes for customer in prefix]

        if any(not prefix for prefix in self.locked_prefixes):
            raise ValueError("locked prefixes must not be empty")

        if len(locked) != len(set(locked)):
            raise ValueError("locked customers must be unique across prefixes")

        if self.free_departure < 0:
            raise ValueError("free_departure must be non-negative")

    @property
    def locked_route_count(self) -> int:
        return len(self.locked_prefixes)

    def locked_customers(self) -> frozenset[CustomerId]:
        return frozenset(
            customer for prefix in self.locked_prefixes for customer in prefix
        )

    def is_locked(self, customer_id: CustomerId) -> bool:
        return customer_id in self.locked_customers()

    def first_free_position(self, route_index: int) -> int:
        if route_index < self.locked_route_count:
            return len(self.locked_prefixes[route_index])

        return 0


@dataclass(frozen=True)
class StopSchedule:
    customer_id: int
    arrival: float
    service_start: float
    departure: float


@dataclass(frozen=True)
class RouteEvaluation:
    feasible: bool
    distance: float
    load: float
    depot_return: float
    schedule: tuple[StopSchedule, ...]
    violations: tuple[str, ...]


@dataclass(frozen=True)
class SolutionEvaluation:
    feasible: bool
    vehicle_count: int
    distance: float
    risk_delay: float
    objective: float
    score: tuple[int, float]
    routes: tuple[RouteEvaluation, ...]
    violations: tuple[str, ...]
