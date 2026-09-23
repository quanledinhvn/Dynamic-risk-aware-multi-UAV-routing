"""Objective normalization and reference-direction association."""

import numpy as np

from .models import Individual, ReferenceAssignment


def normalize_objectives(individuals: tuple[Individual, ...] | list[Individual]) -> np.ndarray:
    values = np.asarray([item.evaluation.objectives for item in individuals], dtype=float)
    if len(values) == 0:
        return np.empty((0, 0), dtype=float)
    ideal = values.min(axis=0)
    nadir = values.max(axis=0)
    scale = np.where(nadir > ideal, nadir - ideal, 1.0)
    return (values - ideal) / scale


def associate(normalized: np.ndarray, directions: np.ndarray) -> tuple[ReferenceAssignment, ...]:
    if len(normalized) == 0:
        return ()
    direction_norm = np.sum(directions * directions, axis=1)
    projections = normalized @ directions.T / np.where(direction_norm > 0, direction_norm, 1.0)
    projected = projections[:, :, None] * directions[None, :, :]
    distances = np.linalg.norm(normalized[:, None, :] - projected, axis=2)
    indices = np.argmin(distances, axis=1)
    return tuple(ReferenceAssignment(int(index), float(distances[row, index])) for row, index in enumerate(indices))
