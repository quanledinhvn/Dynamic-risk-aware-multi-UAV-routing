"""Locked route prefixes derived from the executed schedule.

A customer is locked once its UAV has strictly departed toward it. The UAV
leaves the depot as late as possible for the first customer, so a route whose
first customer opens far in the future stays free until that latest departure.
"""

from uav_routing.evaluator import Evaluator
from uav_routing.models import Route, RouteEvaluation, SearchConstraints, Solution


def route_prefixes(
    solution: Solution,
    evaluator: Evaluator,
    time: float,
    previous: SearchConstraints | None,
) -> tuple[Route, ...]:
    if time < 0:
        raise ValueError("time must be non-negative")

    evaluation = evaluator.solution(solution, previous)
    prefixes: list[Route] = []

    for index, (route, result) in enumerate(
        zip(solution.routes, evaluation.routes, strict=True)
    ):
        departure = _route_departure(previous, index)
        length = _locked_length(route, result, departure, time, evaluator)

        if previous is not None and index < previous.locked_route_count:
            length = max(length, len(previous.locked_prefixes[index]))

        prefixes.append(route[:length])

    return tuple(prefixes)


def lock_solution(
    solution: Solution,
    evaluator: Evaluator,
    time: float,
    previous: SearchConstraints | None,
) -> tuple[Solution, SearchConstraints]:
    prefixes = route_prefixes(solution, evaluator, time, previous)
    locked = [index for index, prefix in enumerate(prefixes) if prefix]
    free = [index for index, prefix in enumerate(prefixes) if not prefix]

    reordered = Solution(tuple(solution.routes[index] for index in locked + free))
    constraints = SearchConstraints(
        locked_prefixes=tuple(prefixes[index] for index in locked),
        free_departure=float(time),
    )

    return reordered, constraints


def _route_departure(previous: SearchConstraints | None, index: int) -> float:
    if previous is None or index < previous.locked_route_count:
        return 0.0

    return previous.free_departure


def _locked_length(
    route: Route,
    result: RouteEvaluation,
    departure: float,
    time: float,
    evaluator: Evaluator,
) -> int:
    if not route:
        return 0

    if not _latest_depot_departure(route[0], departure, evaluator) < time:
        return 0

    length = 1

    for stop in result.schedule[:-1]:
        if not stop.departure < time:
            break

        length += 1

    return length


def _latest_depot_departure(
    customer_id: int, departure: float, evaluator: Evaluator
) -> float:
    instance = evaluator.instance
    position = next(
        index
        for index, customer in enumerate(instance.customers, start=1)
        if customer.id == customer_id
    )
    ready_time = instance.customers[position - 1].ready_time
    travel = float(instance.distance_matrix[0, position])

    return max(departure, ready_time - travel)
