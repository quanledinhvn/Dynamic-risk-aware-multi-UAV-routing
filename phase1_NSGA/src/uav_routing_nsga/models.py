"""Immutable domain records for the NSGA-III baseline."""

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np

CustomerId: TypeAlias = int
Route: TypeAlias = tuple[CustomerId, ...]
Objectives: TypeAlias = tuple[float, ...]


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
class Evaluation:
    feasible: bool
    objectives: Objectives
    vehicle_count: int
    distance: float
    risk_delay: float
    max_load: float
    total_lateness: float
    routes: tuple[RouteEvaluation, ...]
    violations: tuple[str, ...]


@dataclass(frozen=True)
class Individual:
    solution: Solution
    evaluation: Evaluation


@dataclass(frozen=True)
class ReferenceAssignment:
    reference_index: int
    distance: float
