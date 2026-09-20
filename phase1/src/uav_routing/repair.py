"""Insertion engine and repair neighborhoods."""

from dataclasses import dataclass

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
