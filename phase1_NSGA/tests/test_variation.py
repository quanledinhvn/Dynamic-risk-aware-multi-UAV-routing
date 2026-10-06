import numpy as np

from uav_routing_nsga.variation import mutate, order_crossover


def test_order_crossover_preserves_permutation():
    child = order_crossover((1, 2, 3, 4, 5), (5, 4, 3, 2, 1), np.random.default_rng(1))
    assert sorted(child) == [1, 2, 3, 4, 5]


def test_mutation_preserves_permutation():
    mutated = mutate((1, 2, 3, 4), 1.0, np.random.default_rng(2))
    assert sorted(mutated) == [1, 2, 3, 4]
