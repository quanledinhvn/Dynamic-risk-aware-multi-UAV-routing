import numpy as np

from uav_routing_nsga.dominance import dominates, non_dominated_sort
from uav_routing_nsga.models import Evaluation, Individual, Solution
from uav_routing_nsga.normalization import associate, normalize_objectives
from uav_routing_nsga.reference_directions import reference_directions


def individual(values):
    evaluation = Evaluation(True, tuple(values), 1, 0, 0, 0, 0, (), ())
    return Individual(Solution(((1,),)), evaluation)


def test_dominance_and_fronts():
    first = individual((1, 2, 3))
    second = individual((2, 3, 4))
    third = individual((1, 4, 2))
    assert dominates(first, second)
    assert not dominates(first, third)
    assert len(non_dominated_sort((first, second, third))) == 2


def test_reference_directions_and_association():
    directions = reference_directions(3, 2)
    assert directions.shape == (6, 3)
    assert np.allclose(directions.sum(axis=1), 1.0)
    normalized = normalize_objectives((individual((0, 0, 0)), individual((1, 2, 3))))
    assigned = associate(normalized, directions)
    assert len(assigned) == 2
