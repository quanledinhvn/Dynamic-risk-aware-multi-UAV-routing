"""Configurable solution preferences for ALNS search decisions."""

from .models import SolutionEvaluation


def preference_key(
    evaluation: SolutionEvaluation,
    policy: str,
    risk_threshold: float,
) -> tuple[float, ...]:
    """Return the ordered preference key for one evaluated solution."""
    if policy == "lexicographic":
        return float(evaluation.vehicle_count), float(evaluation.objective)

    if policy != "emergency_gate":
        raise ValueError(f"unknown score policy: {policy}")

    if evaluation.risk_delay > risk_threshold:
        return (
            1.0,
            float(evaluation.risk_delay),
            float(evaluation.vehicle_count),
            float(evaluation.objective),
        )

    return (
        0.0,
        float(evaluation.vehicle_count),
        float(evaluation.objective),
        float(evaluation.risk_delay),
    )


def is_better(
    candidate: SolutionEvaluation,
    reference: SolutionEvaluation,
    policy: str,
    risk_threshold: float,
) -> bool:
    """Return whether candidate is preferred to reference by the policy."""
    candidate_key = preference_key(candidate, policy, risk_threshold)
    reference_key = preference_key(reference, policy, risk_threshold)

    return candidate_key < reference_key


def annealing_delta(
    candidate: SolutionEvaluation,
    current: SolutionEvaluation,
    policy: str,
    risk_threshold: float,
) -> float | None:
    """Return a non-negative SA delta, or None for a forbidden worsening."""
    candidate_key = preference_key(candidate, policy, risk_threshold)
    current_key = preference_key(current, policy, risk_threshold)

    if candidate_key <= current_key:
        return 0.0

    if policy == "lexicographic":
        if candidate.vehicle_count > current.vehicle_count:
            return None

        return max(0.0, candidate.objective - current.objective)

    candidate_unsafe = candidate.risk_delay > risk_threshold
    current_unsafe = current.risk_delay > risk_threshold

    if candidate_unsafe and not current_unsafe:
        return None

    if candidate_unsafe and current_unsafe:
        return _unsafe_delta(candidate, current)

    if candidate.vehicle_count > current.vehicle_count:
        return None

    return max(0.0, candidate.objective - current.objective)


def _unsafe_delta(
    candidate: SolutionEvaluation,
    current: SolutionEvaluation,
) -> float | None:
    if candidate.risk_delay > current.risk_delay:
        return candidate.risk_delay - current.risk_delay

    if candidate.vehicle_count > current.vehicle_count:
        return None

    return max(0.0, candidate.objective - current.objective)
