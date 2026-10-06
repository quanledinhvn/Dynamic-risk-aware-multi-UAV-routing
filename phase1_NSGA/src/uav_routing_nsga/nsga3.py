"""NSGA-III orchestration for feasible multi-UAV routing."""

from dataclasses import dataclass
import time

import numpy as np

from .dominance import unique_non_dominated
from .encoding import random_individual, solution_to_permutation, decode
from .evaluator import Evaluator
from .models import Individual, Instance
from .reference_directions import reference_directions
from .selection import environmental_selection
from .variation import mutate, order_crossover


@dataclass(frozen=True)
class NSGA3Config:
    population_size: int = 28
    generations: int = 100
    divisions: int = 4
    crossover_probability: float = 0.9
    mutation_probability: float = 0.15
    seed: int = 42

    def validate(self):
        if self.population_size < 2 or self.generations <= 0 or self.divisions <= 0:
            raise ValueError("population_size, generations, and divisions must be positive")
        if not 0 <= self.crossover_probability <= 1 or not 0 <= self.mutation_probability <= 1:
            raise ValueError("variation probabilities must be in [0, 1]")


@dataclass(frozen=True)
class SearchResult:
    population: tuple[Individual, ...]
    pareto_front: tuple[Individual, ...]
    generations: int
    seed: int
    runtime_seconds: float
    reference_direction_count: int


def run_nsga3(instance: Instance, config: NSGA3Config = NSGA3Config()) -> SearchResult:
    started = time.perf_counter()
    config.validate()
    rng = np.random.default_rng(config.seed)
    evaluator = Evaluator(instance)
    directions = reference_directions(5, config.divisions)
    population = tuple(random_individual(instance, evaluator, rng) for _ in range(config.population_size))
    for _ in range(config.generations):
        offspring = []
        while len(offspring) < config.population_size:
            left = _tournament(population, rng)
            right = _tournament(population, rng)
            first = solution_to_permutation(left.solution)
            second = solution_to_permutation(right.solution)
            child = order_crossover(first, second, rng) if float(rng.random()) < config.crossover_probability else first
            child = mutate(child, config.mutation_probability, rng)
            try:
                solution = decode(child, instance, evaluator)
            except ValueError:
                continue
            offspring.append(Individual(solution, evaluator.solution(solution)))
        population = environmental_selection(population + tuple(offspring), config.population_size, directions, rng)
    front = unique_non_dominated(population)
    return SearchResult(population, front, config.generations, config.seed, time.perf_counter() - started, len(directions))


def _tournament(population: tuple[Individual, ...], rng: np.random.Generator) -> Individual:
    first, second = rng.choice(len(population), size=2, replace=False)
    left, right = population[int(first)], population[int(second)]
    from .dominance import dominates
    if dominates(left, right):
        return left
    if dominates(right, left):
        return right
    return left if float(rng.random()) < 0.5 else right
