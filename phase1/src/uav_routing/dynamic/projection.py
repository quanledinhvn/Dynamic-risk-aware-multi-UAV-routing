"""Projection of the previous plan onto a new instance and pool triage.

``project`` keeps every locked prefix, drops customers that left the instance,
ejects free customers until each route is feasible again and returns the pool
of customers that still need a place. ``triage`` inserts that pool greedily in
risk-priority order and reports the customers that fit nowhere.
"""

from uav_routing.evaluator import Evaluator
from uav_routing.models import Instance, Route, SearchConstraints, Solution
from uav_routing.repair import RepairContext, RiskPriorityRepair, best_insertion


def project(
    solution: Solution,
    instance: Instance,
    evaluator: Evaluator,
    constraints: SearchConstraints,
) -> tuple[Solution, tuple[int, ...]]:
    known = {customer.id: customer for customer in instance.customers}
    routes: list[Route] = []

    for index, route in enumerate(solution.routes):
        kept = tuple(customer for customer in route if customer in known)
        kept = _eject_until_feasible(kept, index, instance, evaluator, constraints)

        if kept or index < constraints.locked_route_count:
            routes.append(kept)

    served = {customer for route in routes for customer in route}
    pool = tuple(sorted(customer for customer in known if customer not in served))

    return Solution(tuple(routes)), pool


def triage(
    partial: Solution,
    pool: tuple[int, ...],
    context: RepairContext,
) -> tuple[Solution, tuple[int, ...]]:
    current = partial
    rejected: list[int] = []

    for customer_id in RiskPriorityRepair().ordered(pool, context.instance):
        choice = best_insertion(current, customer_id, context)

        if choice is None:
            rejected.append(customer_id)
        else:
            current = choice.solution

    return current, tuple(rejected)


def lost_customers(
    instance: Instance, rejected: tuple[int, ...], time: float
) -> tuple[int, ...]:
    latest_launch = {
        customer.id: customer.due_date - float(instance.distance_matrix[0, index])
        for index, customer in enumerate(instance.customers, start=1)
    }

    return tuple(
        sorted(
            customer_id
            for customer_id in rejected
            if customer_id in latest_launch and time > latest_launch[customer_id]
        )
    )


def _eject_until_feasible(
    route: Route,
    index: int,
    instance: Instance,
    evaluator: Evaluator,
    constraints: SearchConstraints,
) -> Route:
    customers = {customer.id: customer for customer in instance.customers}
    departure = (
        0.0 if index < constraints.locked_route_count else (constraints.free_departure)
    )
    first_free = constraints.first_free_position(index)

    while route and first_free < len(route):
        result = evaluator.route(route, departure=departure)

        if result.feasible:
            break

        position = _violating_position(route, result, first_free, customers)
        route = route[:position] + route[position + 1 :]

    return route


def _violating_position(route, result, first_free, customers) -> int:
    for position in range(first_free, len(route)):
        stop = result.schedule[position]

        if stop.service_start > customers[route[position]].due_date:
            return position

    return len(route) - 1
