"""Configuration for the rolling-horizon controller."""

import math
from dataclasses import dataclass

POLICIES = ("greedy_insert", "cold_restart", "warm_alns")
TRIGGERS = ("periodic", "event", "hybrid")


@dataclass(frozen=True)
class RollingHorizonConfig:
    policy: str = "warm_alns"
    trigger: str = "periodic"
    epoch_length: float = 60.0
    iterations_epoch0: int = 2_000
    iterations_per_epoch: int = 500
    carry_weights: bool = False
    seed: int = 42

    def validate(self) -> None:
        errors = [message for valid, message in _rules(self) if not valid]

        if errors:
            raise ValueError("; ".join(errors))

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> "RollingHorizonConfig":
        try:
            config = cls(**values)
        except TypeError as exc:
            raise ValueError(f"invalid configuration keys: {exc}") from exc

        config.validate()

        return config


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _rules(config: RollingHorizonConfig) -> tuple[tuple[bool, str], ...]:
    return (
        (config.policy in POLICIES, f"policy must be one of {POLICIES}"),
        (config.trigger in TRIGGERS, f"trigger must be one of {TRIGGERS}"),
        (
            _is_finite_number(config.epoch_length) and config.epoch_length > 0,
            "epoch_length must be a positive finite number",
        ),
        (
            _is_int(config.iterations_epoch0) and config.iterations_epoch0 >= 0,
            "iterations_epoch0 must be a non-negative integer",
        ),
        (
            _is_int(config.iterations_per_epoch) and config.iterations_per_epoch >= 0,
            "iterations_per_epoch must be a non-negative integer",
        ),
        (isinstance(config.carry_weights, bool), "carry_weights must be a boolean"),
        (_is_int(config.seed), "seed must be an integer"),
    )
