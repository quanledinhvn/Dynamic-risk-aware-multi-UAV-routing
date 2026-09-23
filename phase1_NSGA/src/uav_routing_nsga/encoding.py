"""Permutation encoding, deterministic decoding, and initial population."""

import numpy as np

from .evaluator import Evaluator
from .models import Individual, Instance, Solution


def solution_to_permutation(solution: Solution) -> tuple[int, ...]:
    return tuple(customer_id for route in solution.routes for customer_id in route)


def decode(permutation: tuple[int, ...], instance: Instance, evaluator: Evaluator) -> Solution:
    routes = []
    for customer_id in permutation:
        choices = []
        for route_index, route in enumerate(routes):
            for position in range(len(route) + 1):
                candidate = route[:position] + (customer_id,) + route[position:]
                result = evaluator.route(candidate)
                if result.feasible:
                    choices.append((result.distance, route_index, position, candidate))
        if len(routes) < instance.max_vehicles and evaluator.route((customer_id,)).feasible:
            choices.append((evaluator.route((customer_id,)).distance, len(routes), 0, (customer_id,)))
        if not choices:
            raise ValueError(f"cannot decode customer {customer_id} into a feasible route")
        _, route_index, _, selected = min(choices, key=lambda item: item[:3])
        if route_index == len(routes):
            routes.append(selected)
        else:
            routes[route_index] = selected
    return Solution(tuple(routes))


def random_individual(instance: Instance, evaluator: Evaluator, rng: np.random.Generator) -> Individual:
    ids = np.asarray([customer.id for customer in instance.customers], dtype=int)
    for _ in range(100):
        rng.shuffle(ids)
        try:
            solution = decode(tuple(int(value) for value in ids), instance, evaluator)
        except ValueError:
            continue
        evaluation = evaluator.solution(solution)
        if evaluation.feasible:
            return Individual(solution, evaluation)
    ordered = tuple(customer.id for customer in sorted(instance.customers, key=lambda customer: (customer.due_date, customer.id)))
    solution = decode(ordered, instance, evaluator)
    return Individual(solution, evaluator.solution(solution))
