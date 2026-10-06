"""Recent search outcomes and features for contextual operator selection."""

import math
from collections import deque
from numbers import Real

import numpy as np

from uav_routing.models import SolutionEvaluation

CONTEXT_DIMENSION = 9


class SearchHistory:
    def __init__(self, window: int) -> None:
        if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
            raise ValueError("window must be a positive integer")

        self.window = window
        self._accepted: deque[bool] = deque(maxlen=window)
        self._improved: deque[bool] = deque(maxlen=window)

        self._stagnation = 0
        self._total_iterations = 0

    @property
    def stagnation(self) -> int:
        return self._stagnation

    @property
    def total_iterations(self) -> int:
        return self._total_iterations

    @property
    def acceptance_rate(self) -> float:
        if not self._accepted:
            return 0.0

        return sum(self._accepted) / len(self._accepted)

    @property
    def improvement_rate(self) -> float:
        if not self._improved:
            return 0.0

        return sum(self._improved) / len(self._improved)

    def record(self, *, accepted: bool, improved: bool, new_best: bool) -> None:
        self._accepted.append(accepted)
        self._improved.append(improved)
        self._total_iterations += 1

        self._stagnation = 0 if new_best else self._stagnation + 1


def build_context(
    *,
    iteration: int,
    total_iterations: int,
    temperature: float,
    initial_temperature: float,
    minimum_temperature: float,
    current: SolutionEvaluation,
    best: SolutionEvaluation,
    max_vehicles: int,
    history: SearchHistory,
) -> np.ndarray:
    for name, value in (
        ("iteration", iteration),
        ("total_iterations", total_iterations),
        ("max_vehicles", max_vehicles),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")

    if total_iterations <= 0:
        raise ValueError("total_iterations must be positive")

    if not 0 <= iteration < total_iterations:
        raise ValueError("iteration must be within the search range")

    if max_vehicles <= 0:
        raise ValueError("max_vehicles must be positive")

    for name, value in (
        ("temperature", temperature),
        ("initial_temperature", initial_temperature),
        ("minimum_temperature", minimum_temperature),
    ):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{name} must be a finite positive number")

        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a finite positive number")

    if initial_temperature < minimum_temperature:
        raise ValueError("initial_temperature must be at least minimum_temperature")

    for name, evaluation in (("current", current), ("best", best)):
        vehicles = evaluation.vehicle_count
        if isinstance(vehicles, bool) or not isinstance(vehicles, int) or vehicles < 0:
            raise ValueError(f"{name}.vehicle_count must be a non-negative integer")

        for field in ("objective", "risk_delay"):
            value = getattr(evaluation, field)
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name}.{field} must be finite")

    progress = iteration / max(1, total_iterations - 1)

    if initial_temperature == minimum_temperature:
        normalized_temperature = 1.0
    else:
        log_range = math.log(initial_temperature) - math.log(minimum_temperature)

        if log_range == 0.0:
            relative_initial = (
                initial_temperature - minimum_temperature
            ) / minimum_temperature
            relative_temperature = max(
                0.0, (temperature - minimum_temperature) / minimum_temperature
            )
            log_range = math.log1p(relative_initial)
            log_temperature = math.log1p(relative_temperature)
        else:
            log_temperature = math.log(temperature) - math.log(minimum_temperature)

        normalized_temperature = float(np.clip(log_temperature / log_range, 0.0, 1.0))

    stagnation = min(1.0, history.stagnation / history.window)
    vehicle_gap = max(0, current.vehicle_count - best.vehicle_count) / max(
        1, max_vehicles
    )

    if current.vehicle_count == best.vehicle_count:
        objective_delta = max(0.0, current.objective - best.objective)
        objective_gap = min(1.0, objective_delta / max(abs(best.objective), 1e-12))
    else:
        objective_gap = 0.0

    context = np.array(
        [
            1.0,
            progress,
            normalized_temperature,
            stagnation,
            history.acceptance_rate,
            history.improvement_rate,
            vehicle_gap,
            objective_gap,
            current.risk_delay,
        ],
        dtype=float,
    )

    if context.shape != (CONTEXT_DIMENSION,) or not np.all(np.isfinite(context)):
        raise ValueError("context must have nine finite features")

    return context
