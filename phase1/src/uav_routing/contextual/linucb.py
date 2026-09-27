"""Disjoint LinUCB state and operator-arm selection."""

import math
from dataclasses import dataclass
from numbers import Real
from typing import Hashable

import numpy as np


@dataclass(frozen=True)
class LinUCBArmState:
    matrix: np.ndarray
    reward_vector: np.ndarray


class DisjointLinUCB:
    def __init__(
        self,
        arms: tuple[Hashable, ...],
        dimension: int,
        exploration: float,
        regularization: float,
        rng: np.random.Generator,
    ) -> None:
        if not arms or len(set(arms)) != len(arms):
            raise ValueError("arms must be nonempty and unique")

        if (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension <= 0
        ):
            raise ValueError("dimension must be a positive integer")

        if (
            isinstance(exploration, bool)
            or not isinstance(exploration, Real)
            or not math.isfinite(exploration)
            or exploration < 0
        ):
            raise ValueError("exploration must be finite and non-negative")

        if (
            isinstance(regularization, bool)
            or not isinstance(regularization, Real)
            or not math.isfinite(regularization)
            or regularization <= 0
        ):
            raise ValueError("regularization must be finite and positive")

        self._arms = tuple(arms)
        self._dimension = dimension
        self._exploration = exploration
        self._rng = rng
        self._states = {
            arm: LinUCBArmState(
                matrix=regularization * np.eye(dimension, dtype=float),
                reward_vector=np.zeros(dimension, dtype=float),
            )
            for arm in arms
        }

    def _validate_context(self, context: np.ndarray) -> None:
        if not isinstance(context, np.ndarray) or context.shape != (self._dimension,):
            raise ValueError("context must be a one-dimensional NumPy array")

        if not np.isrealobj(context) or not np.issubdtype(context.dtype, np.number):
            raise ValueError("context must contain only finite numbers")

        if not np.all(np.isfinite(context)):
            raise ValueError("context must contain only finite numbers")

    def select(self, context: np.ndarray) -> Hashable:
        self._validate_context(context)

        scores = []

        for arm in self._arms:
            state = self._states[arm]
            coefficients = np.linalg.solve(state.matrix, state.reward_vector)
            inverse_context = np.linalg.solve(state.matrix, context)

            mean = float(context @ coefficients)
            uncertainty = math.sqrt(float(context @ inverse_context))
            scores.append(mean + self._exploration * uncertainty)

        best_score = max(scores)
        tied_indices = np.flatnonzero(np.isclose(scores, best_score))
        selected_index = int(self._rng.choice(tied_indices))

        return self._arms[selected_index]

    def update(self, arm: Hashable, context: np.ndarray, reward: float) -> None:
        if arm not in self._states:
            raise ValueError("unknown arm")

        self._validate_context(context)

        if (
            isinstance(reward, bool)
            or not isinstance(reward, Real)
            or not math.isfinite(reward)
        ):
            raise ValueError("reward must be finite")

        state = self._states[arm]
        state.matrix[...] += np.outer(context, context)
        state.reward_vector[...] += reward * context

    def state(self, arm: Hashable) -> LinUCBArmState:
        if arm not in self._states:
            raise ValueError("unknown arm")

        current = self._states[arm]

        return LinUCBArmState(
            matrix=current.matrix.copy(),
            reward_vector=current.reward_vector.copy(),
        )
