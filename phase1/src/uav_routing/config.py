"""Configuration for the ALNS search."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ALNSConfig:
    iterations: int = 10_000
    seed: int = 42
    alpha: float = 0.5
    beta: float = 0.5
    score_policy: str = "lexicographic"
    risk_threshold: float = 0.2
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
        type_errors = _type_errors(self)

        if type_errors:
            raise ValueError("; ".join(type_errors))

        errors = [message for valid, message in _validation_rules(self) if not valid]

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


def _type_errors(config: ALNSConfig) -> list[str]:
    integer_fields = {
        "iterations": config.iterations,
        "seed": config.seed,
        "q_min": config.q_min,
        "q_max": config.q_max,
        "segment_length": config.segment_length,
    }
    real_fields = {
        "alpha": config.alpha,
        "beta": config.beta,
        "risk_threshold": config.risk_threshold,
        "reaction_factor": config.reaction_factor,
        "initial_temperature": config.initial_temperature,
        "cooling_rate": config.cooling_rate,
        "minimum_temperature": config.minimum_temperature,
        "minimum_weight": config.minimum_weight,
        "removal_determinism": config.removal_determinism,
        "related_distance_weight": config.related_distance_weight,
        "related_time_weight": config.related_time_weight,
        "related_demand_weight": config.related_demand_weight,
        "related_risk_weight": config.related_risk_weight,
        "reward_best": config.reward_best,
        "reward_improve": config.reward_improve,
        "reward_accepted": config.reward_accepted,
    }

    errors = [
        f"{name} must be an integer"
        for name, value in integer_fields.items()
        if isinstance(value, bool) or not isinstance(value, int)
    ]

    if not isinstance(config.score_policy, str):
        errors.append("score_policy must be a string")
    
    errors.extend(
        f"{name} must be a finite number"
        for name, value in real_fields.items()
        if isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    )

    return errors


def _validation_rules(config: ALNSConfig) -> tuple[tuple[bool, str], ...]:
    related = (
        config.related_distance_weight,
        config.related_time_weight,
        config.related_demand_weight,
        config.related_risk_weight,
    )

    return (
        (config.iterations > 0, "iterations must be positive"),
        (config.segment_length > 0, "segment_length must be positive"),
        (0 < config.q_min <= config.q_max, "require 0 < q_min <= q_max"),
        (
            config.score_policy in {"lexicographic", "emergency_gate"},
            "score_policy must be lexicographic or emergency_gate",
        ),
        (
            0 <= config.risk_threshold <= 1,
            "risk_threshold must be in [0, 1]",
        ),
        (
            config.alpha >= 0 and config.beta >= 0,
            "alpha and beta must be non-negative",
        ),
        (
            math.isclose(config.alpha + config.beta, 1.0, abs_tol=1e-9),
            "alpha and beta must sum to 1",
        ),
        (
            config.initial_temperature > 0 and config.minimum_temperature > 0,
            "temperatures must be positive",
        ),
        (0 < config.cooling_rate <= 1, "cooling_rate must be in (0, 1]"),
        (
            0 <= config.reaction_factor <= 1,
            "reaction_factor must be in [0, 1]",
        ),
        (config.minimum_weight > 0, "minimum_weight must be positive"),
        (
            config.removal_determinism > 0,
            "removal_determinism must be positive",
        ),
        (
            all(weight >= 0 for weight in related) and sum(related) > 0,
            "relatedness weights must be non-negative and not all zero",
        ),
        (
            min(config.reward_best, config.reward_improve, config.reward_accepted) >= 0,
            "operator rewards must be non-negative",
        ),
    )
