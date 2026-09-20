"""Insertion engine and repair neighborhoods."""

from dataclasses import dataclass
import math

from .evaluator import Evaluator
from .models import Instance, Solution


@dataclass(frozen=True)
class Insertion:
    customer_id: int
    route_index: int
    position: int
    delta_k: int
    delta_f: float
    solution: Solution


@dataclass(frozen=True)
class RepairContext:
    instance: Instance
    evaluator: Evaluator
    d_ref: float
    alpha: float
    beta: float

    def evaluate_partial(self, partial: Solution) -> "PartialEvaluation":
        distance = 0.0
        weighted_delay = 0.0
        for route in partial.routes:
            evaluated = self.evaluator.route(route)
            distance += evaluated.distance
            for stop in evaluated.schedule:
                customer = self.evaluator._customers[stop.customer_id]
                index = self.evaluator._matrix_index[stop.customer_id]
                relative_delay = (stop.service_start - customer.ready_time) / max(
                    1.0, customer.due_date - customer.ready_time
                )
                weighted_delay += (
                    float(self.instance.risk_priority[index]) * relative_delay
                )
        total_priority = float(sum(self.instance.risk_priority[1:]))
        risk_delay = weighted_delay / total_priority if total_priority > 0 else 0.0
        objective = self.alpha * distance / self.d_ref + self.beta * risk_delay
        return PartialEvaluation(distance, risk_delay, objective)


@dataclass(frozen=True)
class PartialEvaluation:
    distance: float
    risk_delay: float
    objective: float


def feasible_insertions(
    partial: Solution, customer_id: int, context: RepairContext
) -> tuple[Insertion, ...]:
    known = {customer.id for customer in context.instance.customers}
    assigned = {customer for route in partial.routes for customer in route}
    if customer_id not in known or customer_id in assigned:
        return ()
    base = context.evaluate_partial(partial)
    choices: list[Insertion] = []
    for route_index, route in enumerate(partial.routes):
        for position in range(len(route) + 1):
            candidate = insert_customer(partial, customer_id, route_index, position)
            route_result = context.evaluator.route(candidate.routes[route_index])
            if not route_result.feasible:
                continue
            delta_f = context.evaluate_partial(candidate).objective - base.objective
            choices.append(
                Insertion(
                    customer_id,
                    route_index,
                    position,
                    0,
                    delta_f,
                    candidate,
                )
            )
    if len(partial.routes) < context.instance.max_vehicles:
        route_index = len(partial.routes)
        candidate = Solution(partial.routes + ((customer_id,),))
        if context.evaluator.route((customer_id,)).feasible:
            delta_f = context.evaluate_partial(candidate).objective - base.objective
            choices.append(
                Insertion(customer_id, route_index, 0, 1, delta_f, candidate)
            )
    return tuple(
        sorted(
            choices,
            key=lambda item: (
                item.delta_k,
                item.delta_f,
                item.route_index,
                item.position,
            ),
        )
    )


def best_insertion(
    partial: Solution, customer_id: int, context: RepairContext
) -> Insertion | None:
    choices = feasible_insertions(partial, customer_id, context)
    return choices[0] if choices else None


def insert_customer(
    partial: Solution, customer_id: int, route_index: int, position: int
) -> Solution:
    routes = list(partial.routes)
    route = routes[route_index]
    routes[route_index] = route[:position] + (customer_id,) + route[position:]
    return Solution(tuple(routes))


@dataclass(frozen=True)
class RepairResult:
    success: bool
    solution: Solution | None


class GreedyRepair:
    name = "greedy"

    def apply(
        self,
        partial: Solution,
        removed: tuple[int, ...],
        context: RepairContext,
    ) -> RepairResult:
        if not _valid_removed(partial, removed, context.instance):
            return RepairResult(False, None)
        current = partial
        remaining = list(removed)
        while remaining:
            choices = [
                insertion
                for customer_id in remaining
                for insertion in feasible_insertions(current, customer_id, context)
            ]
            if not choices:
                return RepairResult(False, None)
            choice = min(choices, key=_insertion_key)
            current = choice.solution
            remaining.remove(choice.customer_id)
        return _complete_result(current, context)


class Regret2Repair(GreedyRepair):
    name = "regret2"

    def choose_customer(
        self,
        removed: tuple[int, ...],
        context: RepairContext,
        partial: Solution | None = None,
    ) -> Insertion | None:
        current = partial or Solution(())
        ranked: list[tuple[float, float, int, Insertion]] = []
        for customer_id in removed:
            choices = feasible_insertions(current, customer_id, context)
            if not choices:
                return None
            minimum_delta_k = choices[0].delta_k
            best_level = [
                choice for choice in choices if choice.delta_k == minimum_delta_k
            ]
            best = best_level[0]
            regret = (
                math.inf
                if len(best_level) == 1
                else best_level[1].delta_f - best.delta_f
            )
            ranked.append((regret, -best.delta_f, -customer_id, best))
        return max(ranked, key=lambda item: item[:3])[3] if ranked else None

    def apply(
        self,
        partial: Solution,
        removed: tuple[int, ...],
        context: RepairContext,
    ) -> RepairResult:
        if not _valid_removed(partial, removed, context.instance):
            return RepairResult(False, None)
        current = partial
        remaining = list(removed)
        while remaining:
            choice = self.choose_customer(tuple(remaining), context, current)
            if choice is None:
                return RepairResult(False, None)
            current = choice.solution
            remaining.remove(choice.customer_id)
        return _complete_result(current, context)


class RiskPriorityRepair(GreedyRepair):
    name = "risk_priority"

    def ordered(
        self, removed: tuple[int, ...], instance: Instance
    ) -> tuple[int, ...]:
        customers = {customer.id: customer for customer in instance.customers}
        priorities = {
            customer.id: float(instance.risk_priority[index])
            for index, customer in enumerate(instance.customers, start=1)
        }
        return tuple(
            sorted(
                removed,
                key=lambda customer_id: (
                    -priorities[customer_id],
                    customers[customer_id].due_date,
                    customer_id,
                ),
            )
        )

    def apply(
        self,
        partial: Solution,
        removed: tuple[int, ...],
        context: RepairContext,
    ) -> RepairResult:
        if not _valid_removed(partial, removed, context.instance):
            return RepairResult(False, None)
        current = partial
        for customer_id in self.ordered(removed, context.instance):
            choice = best_insertion(current, customer_id, context)
            if choice is None:
                return RepairResult(False, None)
            current = choice.solution
        return _complete_result(current, context)


def _insertion_key(insertion: Insertion) -> tuple[float, ...]:
    return (
        insertion.delta_k,
        insertion.delta_f,
        insertion.customer_id,
        insertion.route_index,
        insertion.position,
    )


def _valid_removed(
    partial: Solution, removed: tuple[int, ...], instance: Instance
) -> bool:
    known = {customer.id for customer in instance.customers}
    assigned = [customer for route in partial.routes for customer in route]
    return (
        len(removed) == len(set(removed))
        and len(assigned) == len(set(assigned))
        and set(removed).issubset(known)
        and set(assigned).issubset(known)
        and set(removed).isdisjoint(assigned)
    )


def _complete_result(
    solution: Solution, context: RepairContext
) -> RepairResult:
    evaluation = context.evaluator.solution(solution)
    if not evaluation.feasible:
        return RepairResult(False, None)
    return RepairResult(True, solution)
