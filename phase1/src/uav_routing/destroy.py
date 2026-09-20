"""Destroy neighborhoods for adaptive large neighborhood search."""

from dataclasses import dataclass
from itertools import combinations
from typing import Collection, Protocol

import numpy as np

from .evaluator import Evaluator
from .models import Customer, Instance, Solution


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

    def apply(self, solution, instance, evaluator, rng, q) -> DestroyResult:
        served = _served(solution)
        count = min(max(int(q), 0), len(served))

        if count == 0:
            return DestroyResult(solution, ())

        selected = tuple(
            int(value) for value in rng.choice(served, count, replace=False)
        )

        return remove_customers(solution, selected)


class WorstRemoval(RandomRemoval):
    name = "worst"

    def __init__(self, determinism: float = 6.0):
        if determinism <= 0:
            raise ValueError("determinism must be positive")

        self.determinism = determinism

    def apply(self, solution, instance, evaluator, rng, q) -> DestroyResult:
        count = min(max(int(q), 0), len(_served(solution)))
        current = solution
        selected: list[int] = []

        for _ in range(count):
            contributions: list[tuple[float, int]] = []

            for route in current.routes:
                before = _route_cost(evaluator, route)

                for customer_id in route:
                    reduced = tuple(cid for cid in route if cid != customer_id)
                    contribution = before - _route_cost(evaluator, reduced)
                    contributions.append((contribution, customer_id))

            ranked = sorted(contributions, key=lambda item: (-item[0], item[1]))
            index = _powered_index(rng, len(ranked), self.determinism)
            chosen = ranked[index][1]
            selected.append(chosen)
            current = remove_customers(current, (chosen,)).partial

        return DestroyResult(current, tuple(selected))


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

    def apply(self, solution, instance, evaluator, rng, q) -> DestroyResult:
        served = _served(solution)
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

        return remove_customers(solution, tuple(selected))


class RouteRemoval(RandomRemoval):
    name = "route"

    def apply(self, solution, instance, evaluator, rng, q) -> DestroyResult:
        if not solution.routes:
            return DestroyResult(solution, ())

        route_index = int(rng.choice(len(solution.routes)))
        selected = solution.routes[route_index]

        return remove_customers(solution, selected)


class RiskPriorityRemoval(RandomRemoval):
    name = "risk_priority"

    def __init__(self, determinism: float = 6.0):
        if determinism <= 0:
            raise ValueError("determinism must be positive")

        self.determinism = determinism

    def apply(self, solution, instance, evaluator, rng, q) -> DestroyResult:
        served = _served(solution)
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

        return remove_customers(solution, tuple(selected))


def remove_customers(solution: Solution, selected: Collection[int]) -> DestroyResult:
    selected_tuple = tuple(selected)
    selected_set = set(selected_tuple)
    routes = tuple(
        tuple(customer for customer in route if customer not in selected_set)
        for route in solution.routes
    )

    return DestroyResult(
        Solution(tuple(route for route in routes if route)), selected_tuple
    )


def _served(solution: Solution) -> tuple[int, ...]:
    return tuple(customer for route in solution.routes for customer in route)


def _normalized(value: float, maximum: float) -> float:
    return value / maximum if maximum > 0 else 0.0


def _powered_index(rng: np.random.Generator, length: int, determinism: float) -> int:
    if length <= 0:
        raise ValueError("cannot select from an empty ranking")

    return min(int(float(rng.random()) ** determinism * length), length - 1)


def _route_cost(evaluator: Evaluator, route: tuple[int, ...]) -> float:
    if not route:
        return 0.0

    return evaluator.solution(Solution((route,))).objective
