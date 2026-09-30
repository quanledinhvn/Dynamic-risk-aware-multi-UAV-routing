"""Immutable records for scenarios, events and simulation results."""

from dataclasses import dataclass
from pathlib import Path

from uav_routing.models import (
    Customer,
    Instance,
    RiskZone,
    SearchConstraints,
    Solution,
    SolutionEvaluation,
)


@dataclass(frozen=True)
class CustomerArrival:
    time: float
    customer: Customer


@dataclass(frozen=True)
class RiskUpdate:
    time: float
    zone: RiskZone


@dataclass(frozen=True)
class DeadlineUpdate:
    time: float
    customer_id: int
    due_date: float


Event = CustomerArrival | RiskUpdate | DeadlineUpdate


@dataclass(frozen=True)
class Scenario:
    name: str
    instance_path: Path
    static_customers: int
    risk_limit: int
    seed: int
    horizon: float
    events: tuple[Event, ...]


@dataclass(frozen=True)
class LockState:
    time: float
    constraints: SearchConstraints
    frozen_priority: dict[int, float]


@dataclass(frozen=True)
class EpochRecord:
    index: int
    time: float
    revealed: tuple[Event, ...]
    locked_customers: int
    rejected: tuple[int, ...]
    solution: Solution
    evaluation: SolutionEvaluation
    iterations: int
    runtime_seconds: float


@dataclass(frozen=True)
class SimulationResult:
    scenario: str
    policy: str
    seed: int
    d_ref: float
    final_instance: Instance
    realized: Solution
    evaluation: SolutionEvaluation
    unserved: tuple[int, ...]
    unserved_priority: float
    epochs: tuple[EpochRecord, ...]
    total_iterations: int
    runtime_seconds: float
