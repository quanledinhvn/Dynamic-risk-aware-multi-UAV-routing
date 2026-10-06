import pytest

from uav_routing.models import SolutionEvaluation
from uav_routing.scoring import annealing_delta, is_better, preference_key


def _evaluation(
    vehicles: int,
    risk: float,
    objective: float,
) -> SolutionEvaluation:
    return SolutionEvaluation(
        feasible=True,
        vehicle_count=vehicles,
        distance=100.0,
        risk_delay=risk,
        objective=objective,
        score=(vehicles, objective),
        routes=(),
        violations=(),
    )


def test_lexicographic_policy_preserves_existing_order():
    fewer_uavs = _evaluation(2, 0.9, 99.0)
    lower_objective = _evaluation(3, 0.1, 0.1)

    assert is_better(fewer_uavs, lower_objective, "lexicographic", 0.2)
    assert preference_key(fewer_uavs, "lexicographic", 0.2) == (2.0, 99.0)


def test_emergency_gate_prioritizes_risk_while_both_solutions_are_unsafe():
    lower_risk = _evaluation(3, 0.25, 2.0)
    fewer_uavs = _evaluation(2, 0.35, 1.0)

    assert is_better(lower_risk, fewer_uavs, "emergency_gate", 0.2)


def test_emergency_gate_prioritizes_uavs_after_both_solutions_are_safe():
    fewer_uavs = _evaluation(2, 0.19, 2.0)
    lower_risk = _evaluation(3, 0.10, 1.0)

    assert is_better(fewer_uavs, lower_risk, "emergency_gate", 0.2)


def test_emergency_gate_always_prefers_safe_solution_to_unsafe_solution():
    safe = _evaluation(4, 0.20, 3.0)
    unsafe = _evaluation(2, 0.21, 1.0)

    assert is_better(safe, unsafe, "emergency_gate", 0.2)


def test_emergency_gate_anneals_risk_worsening_only_inside_unsafe_region():
    current = _evaluation(2, 0.30, 1.0)
    candidate = _evaluation(2, 0.35, 0.8)

    assert annealing_delta(candidate, current, "emergency_gate", 0.2) == pytest.approx(
        0.05
    )


def test_emergency_gate_forbids_crossing_from_safe_to_unsafe():
    current = _evaluation(3, 0.20, 2.0)
    candidate = _evaluation(2, 0.21, 1.0)

    assert annealing_delta(candidate, current, "emergency_gate", 0.2) is None


def test_preference_policy_rejects_unknown_name():
    evaluation = _evaluation(2, 0.1, 1.0)

    with pytest.raises(ValueError, match="score policy"):
        preference_key(evaluation, "unknown", 0.2)
