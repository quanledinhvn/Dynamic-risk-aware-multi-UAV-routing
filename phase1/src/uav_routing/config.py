"""Configuration for the ALNS search."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ALNSConfig:
    iterations: int = 10_000
    seed: int = 42
    alpha: float = 0.5
    beta: float = 0.5
    q_min: int = 2
    q_max: int = 5
    segment_length: int = 100
    reaction_factor: float = 0.2
    initial_temperature: float = 0.05
    cooling_rate: float = 0.9995
    minimum_temperature: float = 1e-6
    minimum_weight: float = 0.1
    removal_determinism: float = 6.0
    related_distance_weight: float = 1.0
    related_time_weight: float = 1.0
    related_demand_weight: float = 1.0
    related_risk_weight: float = 1.0
    reward_best: float = 20.0
    reward_improve: float = 10.0
    reward_accepted: float = 2.0

    def validate(self) -> None:
        related = (
            self.related_distance_weight,
            self.related_time_weight,
            self.related_demand_weight,
            self.related_risk_weight,
        )
        rules = (
            (self.iterations > 0, "iterations must be positive"),
            (self.segment_length > 0, "segment_length must be positive"),
            (0 < self.q_min <= self.q_max, "require 0 < q_min <= q_max"),
            (
                self.alpha >= 0 and self.beta >= 0,
                "alpha and beta must be non-negative",
            ),
            (
                math.isclose(self.alpha + self.beta, 1.0, abs_tol=1e-9),
                "alpha and beta must sum to 1",
            ),
            (
                self.initial_temperature > 0 and self.minimum_temperature > 0,
                "temperatures must be positive",
            ),
            (0 < self.cooling_rate <= 1, "cooling_rate must be in (0, 1]"),
            (
                0 <= self.reaction_factor <= 1,
                "reaction_factor must be in [0, 1]",
            ),
            (self.minimum_weight > 0, "minimum_weight must be positive"),
            (
                self.removal_determinism > 0,
                "removal_determinism must be positive",
            ),
            (
                all(weight >= 0 for weight in related) and sum(related) > 0,
                "relatedness weights must be non-negative and not all zero",
            ),
            (
                min(self.reward_best, self.reward_improve, self.reward_accepted) >= 0,
                "operator rewards must be non-negative",
            ),
        )
        errors = [message for valid, message in rules if not valid]
        if errors:
            raise ValueError("; ".join(errors))

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> "ALNSConfig":
        try:
            config = cls(**values)
        except TypeError as exc:
            raise ValueError(f"invalid configuration keys: {exc}") from exc
        config.validate()
        return config
