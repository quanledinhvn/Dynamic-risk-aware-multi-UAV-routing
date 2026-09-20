"""Roulette selection and segmented adaptive operator weights."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class OperatorStats:
    name: str
    weight: float
    total_uses: int
    segment_uses: int
    segment_score: float


class AdaptivePool:
    def __init__(self, names, initial_weight, reaction_factor, minimum_weight):
        self.names = tuple(names)

        if not self.names:
            raise ValueError("operator pool must not be empty")

        if len(self.names) != len(set(self.names)):
            raise ValueError("operator names must be unique")

        if initial_weight <= 0:
            raise ValueError("initial_weight must be positive")

        if not 0 <= reaction_factor <= 1:
            raise ValueError("reaction_factor must be in [0, 1]")

        if minimum_weight <= 0:
            raise ValueError("minimum_weight must be positive")

        self.reaction_factor = float(reaction_factor)
        self.minimum_weight = float(minimum_weight)
        self._weights = np.full(len(self.names), float(initial_weight), dtype=float)
        self._total_uses = np.zeros(len(self.names), dtype=int)
        self._segment_uses = np.zeros(len(self.names), dtype=int)
        self._segment_scores = np.zeros(len(self.names), dtype=float)
        self._indices = {name: index for index, name in enumerate(self.names)}

    def probabilities(self) -> tuple[float, ...]:
        probabilities = self._weights / self._weights.sum()

        return tuple(float(value) for value in probabilities)

    def select(self, rng: np.random.Generator) -> str:
        index = int(rng.choice(len(self.names), p=self.probabilities()))

        return self.names[index]

    def record(self, name: str, reward: float) -> None:
        index = self._index(name)

        if reward < 0:
            raise ValueError("reward must be non-negative")

        self._total_uses[index] += 1
        self._segment_uses[index] += 1
        self._segment_scores[index] += reward

    def update_segment(self) -> None:
        for index in range(len(self.names)):
            count = int(self._segment_uses[index])

            if count:
                average = float(self._segment_scores[index]) / count
                updated = (1.0 - self.reaction_factor) * self._weights[
                    index
                ] + self.reaction_factor * average
                self._weights[index] = max(self.minimum_weight, updated)

        self._segment_uses.fill(0)
        self._segment_scores.fill(0.0)

    def weight(self, name: str) -> float:
        return float(self._weights[self._index(name)])

    def segment_count(self, name: str) -> int:
        return int(self._segment_uses[self._index(name)])

    def segment_score(self, name: str) -> float:
        return float(self._segment_scores[self._index(name)])

    def snapshot(self) -> tuple[OperatorStats, ...]:
        return tuple(
            OperatorStats(
                name=name,
                weight=float(self._weights[index]),
                total_uses=int(self._total_uses[index]),
                segment_uses=int(self._segment_uses[index]),
                segment_score=float(self._segment_scores[index]),
            )
            for index, name in enumerate(self.names)
        )

    def _index(self, name: str) -> int:
        try:
            return self._indices[name]
        except KeyError as exc:
            raise KeyError(f"unknown operator {name!r}") from exc
