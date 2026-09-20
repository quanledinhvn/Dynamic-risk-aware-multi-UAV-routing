"""Deterministic greedy construction for the initial ALNS solution."""

from .evaluator import Evaluator
from .models import Instance, Solution


class InitialSolutionError(RuntimeError):
    """Raised when no complete feasible initial solution can be built."""


def ordered_customer_ids(instance: Instance) -> tuple[int, ...]:
    priorities = {
        customer.id: float(instance.risk_priority[index])
        for index, customer in enumerate(instance.customers, start=1)
    }
    ordered = sorted(
        instance.customers,
        key=lambda customer: (
            customer.due_date,
            -priorities[customer.id],
            customer.id,
        ),
    )

    return tuple(customer.id for customer in ordered)


def build_initial_solution(
    instance: Instance, alpha: float, beta: float
) -> tuple[Solution, float]:
    route_evaluator = Evaluator(instance, d_ref=1.0, alpha=1.0, beta=0.0)
    routes: list[tuple[int, ...]] = []

    for customer_id in ordered_customer_ids(instance):
        _insert_customer_or_raise(
            routes,
            customer_id,
            instance.max_vehicles,
            route_evaluator,
        )

    solution = Solution(tuple(routes))
    d_ref = sum(route_evaluator.route(route).distance for route in solution.routes)

    if d_ref <= 0:
        raise InitialSolutionError(
            "initial solution has non-positive reference distance"
        )

    evaluation = Evaluator(instance, d_ref, alpha, beta).solution(solution)

    if not evaluation.feasible:
        raise InitialSolutionError(
            "constructed initial solution is infeasible: "
            + ", ".join(evaluation.violations)
        )

    return solution, d_ref


def _insert_customer_or_raise(
    routes: list[tuple[int, ...]],
    customer_id: int,
    max_vehicles: int,
    evaluator: Evaluator,
) -> None:
    choice = _best_existing_route_insertion(routes, customer_id, evaluator)

    if choice is not None:
        route_index, candidate = choice
        routes[route_index] = candidate

        return

    singleton = (customer_id,)

    if len(routes) < max_vehicles and evaluator.route(singleton).feasible:
        routes.append(singleton)

        return

    raise InitialSolutionError(
        f"cannot build a feasible initial solution for customer {customer_id}"
    )


def _best_existing_route_insertion(
    routes: list[tuple[int, ...]],
    customer_id: int,
    evaluator: Evaluator,
) -> tuple[int, tuple[int, ...]] | None:
    choices: list[tuple[float, int, int, tuple[int, ...]]] = []

    for route_index, route in enumerate(routes):
        base_distance = evaluator.route(route).distance

        for position in range(len(route) + 1):
            candidate = route[:position] + (customer_id,) + route[position:]
            evaluated = evaluator.route(candidate)

            if evaluated.feasible:
                choices.append(
                    (
                        evaluated.distance - base_distance,
                        route_index,
                        position,
                        candidate,
                    )
                )

    if not choices:
        return None

    _, route_index, _, candidate = min(choices, key=lambda item: item[:3])

    return route_index, candidate
