"""Destroy neighborhoods for adaptive large neighborhood search."""

from dataclasses import dataclass
from itertools import combinations
from typing import Collection, Protocol

import numpy as np

from .evaluator import Evaluator
from .models import Customer, Instance, SearchConstraints, Solution


@dataclass(frozen=True)
class DestroyResult:
    partial: Solution
    removed: tuple[int, ...]


@dataclass(frozen=True)
class RelatednessWeights:
    distance: float
    time_window: float
    demand: float
    risk: float


class DestroyOperator(Protocol):
    name: str

    def apply(
        self,
        solution: Solution,
        instance: Instance,
        evaluator: Evaluator,
        rng: np.random.Generator,
        q: int,
        constraints: SearchConstraints | None = None,
    ) -> DestroyResult: ...


def relatedness(
    instance: Instance,
    left_id: int,
    right_id: int,
    weights: RelatednessWeights,
) -> float:
    customers = {customer.id: customer for customer in instance.customers}

    if left_id not in customers or right_id not in customers:
        raise ValueError("relatedness requires known customer ids")

    indices = {
        customer.id: index for index, customer in enumerate(instance.customers, start=1)
    }
    maxima = _relatedness_maxima(instance, indices)
    differences = _customer_differences(
        instance,
        customers[left_id],
        customers[right_id],
        indices,
    )

    return sum(
        weight * _normalized(value, maximum)
        for weight, value, maximum in zip(
            (
                weights.distance,
                weights.time_window,
                weights.demand,
                weights.risk,
            ),
            differences,
            maxima,
            strict=True,
        )
    )


def _relatedness_maxima(
    instance: Instance, indices: dict[int, int]
) -> tuple[float, float, float, float]:
    pairs = tuple(combinations(instance.customers, 2))

    max_distance = max(
        (
            float(instance.distance_matrix[indices[a.id], indices[b.id]])
            for a, b in pairs
        ),
        default=0.0,
    )
    max_time = max(
        (
            abs(a.ready_time - b.ready_time) + abs(a.due_date - b.due_date)
            for a, b in pairs
        ),
        default=0.0,
    )
    max_demand = max((abs(a.demand - b.demand) for a, b in pairs), default=0.0)
    max_risk = max(
        (
            abs(
                float(instance.risk_priority[indices[a.id]])
                - float(instance.risk_priority[indices[b.id]])
            )
            for a, b in pairs
        ),
        default=0.0,
    )

    return max_distance, max_time, max_demand, max_risk


def _customer_differences(
    instance: Instance,
    left: Customer,
    right: Customer,
    indices: dict[int, int],
) -> tuple[float, float, float, float]:
    distance = float(instance.distance_matrix[indices[left.id], indices[right.id]])
    time = abs(left.ready_time - right.ready_time) + abs(left.due_date - right.due_date)
    demand = abs(left.demand - right.demand)
    risk = abs(
        float(instance.risk_priority[indices[left.id]])
        - float(instance.risk_priority[indices[right.id]])
    )

    return distance, time, demand, risk


class RandomRemoval:
    name = "random"

    def apply(
        self, solution, instance, evaluator, rng, q, constraints=None
    ) -> DestroyResult:
        served = _free(solution, constraints)
        count = min(max(int(q), 0), len(served))

        if count == 0:
            return DestroyResult(solution, ())

        selected = tuple(
            int(value) for value in rng.choice(served, count, replace=False)
        )

        return remove_customers(solution, selected, constraints)


class WorstRemoval(RandomRemoval):
    name = "worst"

    def __init__(self, determinism: float = 6.0):
        if determinism <= 0:
            raise ValueError("determinism must be positive")

        self.determinism = determinism

    def apply(
        self, solution, instance, evaluator, rng, q, constraints=None
    ) -> DestroyResult:
        free = set(_free(solution, constraints))
        count = min(max(int(q), 0), len(free))
        current = solution
        selected: list[int] = []

        for _ in range(count):
            ranked = _ranked_contributions(current, evaluator, free, constraints)
            index = _powered_index(rng, len(ranked), self.determinism)
            chosen = ranked[index][1]

            selected.append(chosen)
            free.discard(chosen)
            current = remove_customers(current, (chosen,), constraints).partial

        return DestroyResult(current, tuple(selected))


def _ranked_contributions(
    solution: Solution,
    evaluator: Evaluator,
    free: set[int],
    constraints: SearchConstraints | None,
) -> list[tuple[float, int]]:
    contributions: list[tuple[float, int]] = []

    for route_index, route in enumerate(solution.routes):
        before = _route_cost(evaluator, route, route_index, constraints)

        for customer_id in route:
            if customer_id not in free:
                continue

            reduced = tuple(cid for cid in route if cid != customer_id)
            contribution = before - _route_cost(
                evaluator, reduced, route_index, constraints
            )
            contributions.append((contribution, customer_id))

    return sorted(contributions, key=lambda item: (-item[0], item[1]))


class RelatedRemoval(RandomRemoval):
    name = "related"

    def __init__(
        self,
        weights: RelatednessWeights | None = None,
        determinism: float = 6.0,
    ):
        if determinism <= 0:
            raise ValueError("determinism must be positive")

        self.weights = weights or RelatednessWeights(1.0, 1.0, 1.0, 1.0)
        self.determinism = determinism

    def apply(
        self, solution, instance, evaluator, rng, q, constraints=None
    ) -> DestroyResult:
        served = _free(solution, constraints)
        count = min(max(int(q), 0), len(served))

        if count == 0:
            return DestroyResult(solution, ())

        selected = [int(rng.choice(served))]

        while len(selected) < count:
            reference = int(rng.choice(selected))
            candidates = [cid for cid in served if cid not in selected]
            ranked = sorted(
                candidates,
                key=lambda cid: (
                    relatedness(instance, reference, cid, self.weights),
                    cid,
                ),
            )
            index = _powered_index(rng, len(ranked), self.determinism)
            selected.append(ranked[index])

        return remove_customers(solution, tuple(selected), constraints)


class RouteRemoval(RandomRemoval):
    name = "route"

    def apply(
        self, solution, instance, evaluator, rng, q, constraints=None
    ) -> DestroyResult:
        candidates = [
            route_index
            for route_index, route in enumerate(solution.routes)
            if len(route) > _first_free_position(constraints, route_index)
        ]

        if not candidates:
            return DestroyResult(solution, ())

        route_index = int(rng.choice(candidates))
        start = _first_free_position(constraints, route_index)
        selected = solution.routes[route_index][start:]

        return remove_customers(solution, selected, constraints)


class RiskPriorityRemoval(RandomRemoval):
    name = "risk_priority"

    def __init__(self, determinism: float = 6.0):
        if determinism <= 0:
            raise ValueError("determinism must be positive")

        self.determinism = determinism

    def apply(
        self, solution, instance, evaluator, rng, q, constraints=None
    ) -> DestroyResult:
        served = _free(solution, constraints)
        count = min(max(int(q), 0), len(served))
        priorities = {
            customer.id: float(instance.risk_priority[index])
            for index, customer in enumerate(instance.customers, start=1)
        }
        remaining = list(served)
        selected: list[int] = []

        for _ in range(count):
            ranked = sorted(remaining, key=lambda cid: (-priorities[cid], cid))
            index = _powered_index(rng, len(ranked), self.determinism)
            chosen = ranked[index]
            selected.append(chosen)
            remaining.remove(chosen)

        return remove_customers(solution, tuple(selected), constraints)


def remove_customers(
    solution: Solution,
    selected: Collection[int],
    constraints: SearchConstraints | None = None,
) -> DestroyResult:
    selected_tuple = tuple(selected)
    selected_set = set(selected_tuple)
    locked_count = 0

    if constraints is not None:
        if not selected_set.isdisjoint(constraints.locked_customers()):
            raise ValueError("cannot remove locked customers")

        locked_count = constraints.locked_route_count

    routes = tuple(
        tuple(customer for customer in route if customer not in selected_set)
        for route in solution.routes
    )
    kept = tuple(
        route
        for route_index, route in enumerate(routes)
        if route or route_index < locked_count
    )

    return DestroyResult(Solution(kept), selected_tuple)


def _served(solution: Solution) -> tuple[int, ...]:
    return tuple(customer for route in solution.routes for customer in route)


def _free(solution: Solution, constraints: SearchConstraints | None) -> tuple[int, ...]:
    if constraints is None:
        return _served(solution)

    locked = constraints.locked_customers()

    return tuple(
        customer
        for route in solution.routes
        for customer in route
        if customer not in locked
    )


def _first_free_position(
    constraints: SearchConstraints | None, route_index: int
) -> int:
    return 0 if constraints is None else constraints.first_free_position(route_index)


def _normalized(value: float, maximum: float) -> float:
    return value / maximum if maximum > 0 else 0.0


def _powered_index(rng: np.random.Generator, length: int, determinism: float) -> int:
    if length <= 0:
        raise ValueError("cannot select from an empty ranking")

    return min(int(float(rng.random()) ** determinism * length), length - 1)


def _route_cost(
    evaluator: Evaluator,
    route: tuple[int, ...],
    route_index: int = 0,
    constraints: SearchConstraints | None = None,
) -> float:
    if not route:
        return 0.0

    if constraints is None:
        return evaluator.solution(Solution((route,))).objective

    departure = (
        0.0
        if route_index < constraints.locked_route_count
        else constraints.free_departure
    )

    return evaluator.solution(
        Solution((route,)), SearchConstraints(free_departure=departure)
    ).objective
