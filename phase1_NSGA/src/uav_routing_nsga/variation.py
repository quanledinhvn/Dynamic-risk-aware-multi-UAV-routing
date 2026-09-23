"""Permutation crossover and mutation operators."""

import numpy as np


def order_crossover(left: tuple[int, ...], right: tuple[int, ...], rng: np.random.Generator) -> tuple[int, ...]:
    if len(left) != len(right):
        raise ValueError("parents must have equal length")
    size = len(left)
    start, end = sorted((int(rng.integers(size)), int(rng.integers(size))))
    if start == end:
        end = min(size, start + 1)
    child = [None] * size
    child[start:end] = left[start:end]
    remaining = [value for value in right if value not in child]
    cursor = end % size
    for value in remaining:
        while child[cursor] is not None:
            cursor = (cursor + 1) % size
        child[cursor] = value
    return tuple(int(value) for value in child)


def mutate(permutation: tuple[int, ...], probability: float, rng: np.random.Generator) -> tuple[int, ...]:
    result = list(permutation)
    if float(rng.random()) >= probability or len(result) < 2:
        return tuple(result)
    first, second = sorted((int(rng.integers(len(result))), int(rng.integers(len(result)))))
    if first == second:
        second = (first + 1) % len(result)
    result[first], result[second] = result[second], result[first]
    return tuple(result)
