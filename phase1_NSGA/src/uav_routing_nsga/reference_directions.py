"""Das-Dennis simplex-lattice reference directions."""

from itertools import combinations

import numpy as np


def reference_directions(objective_count: int, divisions: int) -> np.ndarray:
    if objective_count < 2 or divisions <= 0:
        raise ValueError("objective_count must be >= 2 and divisions must be positive")
    rows = []
    for bars in combinations(range(divisions + objective_count - 1), objective_count - 1):
        points = (-1,) + bars + (divisions + objective_count - 1,)
        rows.append([(points[index + 1] - points[index] - 1) / divisions for index in range(objective_count)])
    return np.asarray(rows, dtype=float)
