"""Behavioral checks for search history and contextual features."""

from dataclasses import replace

import numpy as np
import pytest

from uav_routing.contextual.context import (
    CONTEXT_DIMENSION,
    SearchHistory,
    build_context,
)
from uav_routing.models import SolutionEvaluation


def _evaluation(*, vehicles: int = 2, objective: float = 100.0, risk: float = 0.18):
    return SolutionEvaluation(
        feasible=True,
        vehicle_count=vehicles,
        distance=10.0,
        risk_delay=risk,
        objective=objective,
        score=(vehicles, objective),
        routes=(),
        violations=(),
    )


def _context_kwargs():
    return {
        "iteration": 2,
        "total_iterations": 5,
        "temperature": 10.0,
        "initial_temperature": 100.0,
        "minimum_temperature": 1.0,
        "current": _evaluation(vehicles=3, objective=120.0),
        "best": _evaluation(),
        "max_vehicles": 5,
        "history": SearchHistory(window=4),
    }


def test_empty_history_has_zero_rates_and_counters():
    history = SearchHistory(window=3)

    assert history.acceptance_rate == 0.0
    assert history.improvement_rate == 0.0
    assert history.stagnation == 0
    assert history.total_iterations == 0


def test_history_records_outcomes_and_evicts_oldest_iteration():
    history = SearchHistory(window=2)

    history.record(accepted=False, improved=False, new_best=False)
    assert (history.acceptance_rate, history.improvement_rate) == (0.0, 0.0)
    assert (history.total_iterations, history.stagnation) == (1, 1)

    history.record(accepted=True, improved=False, new_best=False)
    assert (history.acceptance_rate, history.improvement_rate) == (0.5, 0.0)
    assert (history.total_iterations, history.stagnation) == (2, 2)

    history.record(accepted=True, improved=True, new_best=True)
    assert (history.acceptance_rate, history.improvement_rate) == (1.0, 0.5)
    assert (history.total_iterations, history.stagnation) == (3, 0)

    history.record(accepted=False, improved=False, new_best=False)
    assert (history.acceptance_rate, history.improvement_rate) == (0.5, 0.5)
    assert (history.total_iterations, history.stagnation) == (4, 1)


@pytest.mark.parametrize("window", [0, -1, True, False, 1.5, "2"])
def test_history_rejects_invalid_window(window):
    with pytest.raises(ValueError, match="window"):
        SearchHistory(window=window)


def test_context_orders_and_normalizes_all_nine_features():
    arguments = _context_kwargs()
    history = arguments["history"]

    history.record(accepted=False, improved=False, new_best=False)
    history.record(accepted=True, improved=False, new_best=False)
    history.record(accepted=True, improved=True, new_best=True)

    history.record(accepted=False, improved=False, new_best=False)

    arguments["current"] = _evaluation(objective=120.0)
    context = build_context(**arguments)

    assert context.shape == (CONTEXT_DIMENSION,)
    np.testing.assert_allclose(
        context, [1.0, 0.5, 0.5, 0.25, 0.5, 0.25, 0.0, 0.2, 0.18]
    )


def test_context_single_iteration_and_constant_temperature():
    arguments = _context_kwargs()
    arguments.update(iteration=0, total_iterations=1, temperature=2.0)
    arguments.update(initial_temperature=2.0, minimum_temperature=2.0)

    context = build_context(**arguments)

    assert context[1] == 0.0
    assert context[2] == 1.0


@pytest.mark.parametrize("temperature, expected", [(0.1, 0.0), (1000.0, 1.0)])
def test_context_clips_temperature_at_both_ends(temperature, expected):
    arguments = _context_kwargs()
    arguments["temperature"] = temperature

    assert build_context(**arguments)[2] == expected


def test_context_clips_stagnation_to_one():
    arguments = _context_kwargs()
    history = arguments["history"]

    for _ in range(5):
        history.record(accepted=False, improved=False, new_best=False)

    assert build_context(**arguments)[3] == 1.0


def test_context_vehicle_mismatch_zeroes_objective_gap():
    context = build_context(**_context_kwargs())

    assert context[6] == 0.2
    assert context[7] == 0.0


@pytest.mark.parametrize("objective, expected", [(80.0, 0.0), (300.0, 1.0)])
def test_context_clips_objective_gap_at_both_ends(objective, expected):
    arguments = _context_kwargs()
    arguments["current"] = _evaluation(objective=objective)

    assert build_context(**arguments)[7] == expected


def test_context_uses_epsilon_for_zero_best_objective():
    arguments = _context_kwargs()
    arguments["best"] = _evaluation(objective=0.0)
    arguments["current"] = _evaluation(objective=1e-13)

    assert build_context(**arguments)[7] == pytest.approx(0.1)


@pytest.mark.parametrize(
    "field, value",
    [
        ("iteration", True),
        ("iteration", -1),
        ("iteration", 5),
        ("total_iterations", 0),
        ("total_iterations", 1.5),
        ("temperature", 0.0),
        ("temperature", "10"),
        ("initial_temperature", float("inf")),
        ("initial_temperature", 0.5),
        ("minimum_temperature", -1.0),
        ("max_vehicles", False),
        ("max_vehicles", 0),
    ],
)
def test_context_rejects_invalid_scalar_inputs(field, value):
    arguments = _context_kwargs()
    arguments[field] = value

    with pytest.raises(ValueError, match=field):
        build_context(**arguments)


@pytest.mark.parametrize("field", ["objective", "risk_delay"])
def test_context_rejects_nonfinite_evaluation_fields(field):
    arguments = _context_kwargs()
    arguments["current"] = replace(arguments["current"], **{field: float("nan")})

    with pytest.raises(ValueError, match="finite"):
        build_context(**arguments)


def test_context_rejects_nonfinite_best_objective_even_with_vehicle_mismatch():
    arguments = _context_kwargs()
    arguments["best"] = replace(arguments["best"], objective=float("inf"))

    with pytest.raises(ValueError, match="finite"):
        build_context(**arguments)


def test_context_rejects_invalid_vehicle_count():
    arguments = _context_kwargs()
    arguments["current"] = replace(arguments["current"], vehicle_count=True)

    with pytest.raises(ValueError, match="vehicle_count"):
        build_context(**arguments)
