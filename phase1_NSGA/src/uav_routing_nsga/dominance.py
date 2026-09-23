"""Dominance and fast non-dominated sorting for minimization objectives."""

from .models import Individual


def dominates(left: Individual, right: Individual) -> bool:
    a, b = left.evaluation.objectives, right.evaluation.objectives
    return all(x <= y for x, y in zip(a, b, strict=True)) and any(x < y for x, y in zip(a, b, strict=True))


def non_dominated_sort(population: tuple[Individual, ...] | list[Individual]) -> tuple[tuple[Individual, ...], ...]:
    items = tuple(population)
    dominated = [set() for _ in items]
    counts = [0] * len(items)
    first = []
    for i, left in enumerate(items):
        for j, right in enumerate(items):
            if i == j:
                continue
            if dominates(left, right):
                dominated[i].add(j)
            elif dominates(right, left):
                counts[i] += 1
        if counts[i] == 0:
            first.append(i)
    fronts = []
    current = first
    while current:
        fronts.append(tuple(items[index] for index in current))
        next_front = []
        for index in current:
            for other in dominated[index]:
                counts[other] -= 1
                if counts[other] == 0:
                    next_front.append(other)
        current = next_front
    return tuple(fronts)


def unique_non_dominated(population):
    result = []
    seen = set()
    for individual in non_dominated_sort(tuple(population))[0] if population else ():
        key = individual.solution
        if key not in seen:
            seen.add(key)
            result.append(individual)
    return tuple(result)
