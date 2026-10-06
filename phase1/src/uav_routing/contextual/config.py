"""Configuration for contextual bandit operator selection."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ContextualBanditConfig:
    context_window: int = 100
    linucb_exploration: float = 0.5
    linucb_regularization: float = 1.0

    include_temperature: bool = True
    short_route_warm_start: bool = False

    def validate(self) -> None:
        if (
            isinstance(self.context_window, bool)
            or not isinstance(self.context_window, int)
            or self.context_window <= 0
        ):
            raise ValueError("context_window must be a positive integer")

        if (
            isinstance(self.linucb_exploration, bool)
            or not isinstance(self.linucb_exploration, (int, float))
            or not math.isfinite(self.linucb_exploration)
            or self.linucb_exploration < 0
        ):
            raise ValueError("linucb_exploration must be a finite non-negative number")

        if (
            isinstance(self.linucb_regularization, bool)
            or not isinstance(self.linucb_regularization, (int, float))
            or not math.isfinite(self.linucb_regularization)
            or self.linucb_regularization <= 0
        ):
            raise ValueError("linucb_regularization must be a finite positive number")

        if not isinstance(self.include_temperature, bool):
            raise ValueError("include_temperature must be a boolean")

        if not isinstance(self.short_route_warm_start, bool):
            raise ValueError("short_route_warm_start must be a boolean")

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> "ContextualBanditConfig":
        try:
            config = cls(**values)
        except TypeError as exc:
            raise ValueError(f"invalid configuration keys: {exc}") from exc

        config.validate()

        return config
