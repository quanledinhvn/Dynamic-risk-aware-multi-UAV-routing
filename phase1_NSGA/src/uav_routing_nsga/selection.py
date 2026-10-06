"""NSGA-III environmental selection."""

import numpy as np

from .dominance import non_dominated_sort
from .models import Individual
from .normalization import associate, normalize_objectives


def environmental_selection(population, size: int, directions: np.ndarray, rng: np.random.Generator) -> tuple[Individual, ...]:
    fronts = non_dominated_sort(tuple(population))
    selected = []
    last = ()
    for front in fronts:
        if len(selected) + len(front) <= size:
            selected.extend(front)
        else:
            last = front
            break
    if len(selected) == size:
        return tuple(selected)
    if not last:
        return tuple(selected)
    combined = tuple(selected) + tuple(last)
    normalized = normalize_objectives(combined)
    assignments = associate(normalized, directions)
    niche_counts = np.zeros(len(directions), dtype=int)
    for index in range(len(selected)):
        niche_counts[assignments[index].reference_index] += 1
    candidates = list(range(len(selected), len(combined)))
    while len(selected) < size and candidates:
        available = sorted({assignments[index].reference_index for index in candidates}, key=lambda ref: (niche_counts[ref], ref))
        reference = available[0]
        niche = [index for index in candidates if assignments[index].reference_index == reference]
        if niche_counts[reference] == 0:
            chosen = min(niche, key=lambda index: (assignments[index].distance, index))
        else:
            chosen = int(rng.choice(niche))
        selected.append(combined[chosen])
        candidates.remove(chosen)
        niche_counts[reference] += 1
    return tuple(selected)
