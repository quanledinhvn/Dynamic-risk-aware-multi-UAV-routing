"""Contextual selection and raw statistics for destroy--repair pairs."""

import math
from dataclasses import dataclass
from numbers import Real

import numpy as np

from .config import ContextualBanditConfig
from .context import CONTEXT_DIMENSION
from .linucb import DisjointLinUCB

OperatorPair = tuple[str, str]


@dataclass(frozen=True)
class PairSelectionStats:
    destroy_name: str
    repair_name: str
    total_uses: int
    total_raw_reward: float
    average_raw_reward: float


class OperatorPairSelector:
    def __init__(
        self,
        destroy_names: tuple[str, ...],
        repair_names: tuple[str, ...],
        config: ContextualBanditConfig,
        maximum_raw_reward: float,
        rng: np.random.Generator,
    ) -> None:
        for label, names in (
            ("destroy_names", destroy_names),
            ("repair_names", repair_names),
        ):
            if not names or any(
                not isinstance(name, str) or not name.strip() for name in names
            ):
                raise ValueError(f"{label} must contain nonblank names")

            if len(set(names)) != len(names):
                raise ValueError(f"{label} must contain unique names")

        if (
            isinstance(maximum_raw_reward, bool)
            or not isinstance(maximum_raw_reward, Real)
            or not math.isfinite(maximum_raw_reward)
            or maximum_raw_reward <= 0
        ):
            raise ValueError("maximum_raw_reward must be finite and positive")

        config.validate()

        self._arms = tuple(
            (destroy_name, repair_name)
            for destroy_name in destroy_names
            for repair_name in repair_names
        )

        self._bandit = DisjointLinUCB(
            self._arms,
            CONTEXT_DIMENSION,
            config.linucb_exploration,
            config.linucb_regularization,
            rng,
        )
        self._maximum_raw_reward = maximum_raw_reward
        self._uses = {arm: 0 for arm in self._arms}
        self._raw_totals = {arm: 0.0 for arm in self._arms}

    @property
    def arms(self) -> tuple[OperatorPair, ...]:
        return self._arms

    def select(self, context: np.ndarray) -> OperatorPair:
        return self._bandit.select(context)

    def record(
        self,
        arm: OperatorPair,
        context: np.ndarray,
        raw_reward: float,
    ) -> None:
        if arm not in self._uses:
            raise ValueError("unknown arm")

        if (
            isinstance(raw_reward, bool)
            or not isinstance(raw_reward, Real)
            or not math.isfinite(raw_reward)
            or raw_reward < 0
        ):
            raise ValueError("raw_reward must be finite and non-negative")

        next_total = self._raw_totals[arm] + raw_reward

        if not math.isfinite(next_total):
            raise ValueError("raw_reward would produce a nonfinite total")

        normalized_reward = raw_reward / self._maximum_raw_reward
        self._bandit.update(arm, context, normalized_reward)

        self._uses[arm] += 1
        self._raw_totals[arm] = next_total

    def snapshot(self) -> tuple[PairSelectionStats, ...]:
        return tuple(
            PairSelectionStats(
                destroy_name=arm[0],
                repair_name=arm[1],
                total_uses=self._uses[arm],
                total_raw_reward=self._raw_totals[arm],
                average_raw_reward=(
                    self._raw_totals[arm] / self._uses[arm]
                    if self._uses[arm]
                    else 0.0
                ),
            )
            for arm in self._arms
        )
