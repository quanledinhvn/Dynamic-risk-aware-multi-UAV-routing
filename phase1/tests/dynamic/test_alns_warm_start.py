import pytest
from helpers import make_instance

from uav_routing.alns import ALNSSolver, run_alns
from uav_routing.config import ALNSConfig
from uav_routing.dynamic.policies import contextual_warm_alns
from uav_routing.evaluator import Evaluator, lexicographically_better
from uav_routing.initial import InitialSolutionError, build_initial_solution
from uav_routing.models import Customer, SearchConstraints, Solution

CUSTOMERS = (
    Customer(1, 3, 4, 1, 0, 200, 0),
    Customer(2, 6, 8, 1, 0, 200, 0),
    Customer(3, 0, 10, 1, 0, 200, 0),
    Customer(4, 3, 0, 1, 0, 80, 0),
    Customer(5, 10, 0, 1, 0, 200, 0),
    Customer(6, 12, 5, 1, 0, 200, 0),
    Customer(7, -5, 5, 1, 0, 200, 0),
)
INSTANCE = make_instance(
    CUSTOMERS,
    depot=Customer(0, 0, 0, 0, 0, 500, 0),
    max_vehicles=3,
    priorities=(1.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.0),
)
WARM, D_REF = build_initial_solution(INSTANCE, 0.5, 0.5)
CONFIG = ALNSConfig(iterations=150, seed=3, q_min=1, q_max=3)


def test_initial_solution_is_used_as_starting_point():
    result = run_alns(
        INSTANCE, ALNSConfig(iterations=1, seed=1), initial_solution=WARM, d_ref=100.0
    )

    assert result.initial_solution == WARM
    assert result.d_ref == 100.0
    assert result.iterations == 1
    assert result.evaluation.feasible


def test_initial_solution_requires_d_ref():
    with pytest.raises(ValueError, match="d_ref"):
        run_alns(INSTANCE, CONFIG, initial_solution=WARM)


def test_non_positive_d_ref_is_rejected():
    with pytest.raises(ValueError, match="d_ref"):
        run_alns(INSTANCE, CONFIG, initial_solution=WARM, d_ref=0.0)


def test_infeasible_initial_solution_is_rejected():
    with pytest.raises(InitialSolutionError):
        run_alns(INSTANCE, CONFIG, initial_solution=Solution(((1, 1),)), d_ref=10.0)


def test_initial_solution_violating_constraints_is_rejected():
    constraints = SearchConstraints(locked_prefixes=((7,),))

    with pytest.raises(InitialSolutionError, match="locked_prefix"):
        run_alns(
            INSTANCE,
            CONFIG,
            initial_solution=WARM,
            constraints=constraints,
            d_ref=D_REF,
        )


def test_best_solution_keeps_locked_prefixes_across_search():
    prefix = WARM.routes[0][:1]
    constraints = SearchConstraints(locked_prefixes=(prefix,), free_departure=5.0)

    result = run_alns(
        INSTANCE, CONFIG, initial_solution=WARM, constraints=constraints, d_ref=D_REF
    )

    assert result.best_solution.routes[0][:1] == prefix
    assert result.final_current.routes[0][:1] == prefix
    assert result.evaluation.feasible
    assert sum(stats.total_uses for stats in result.operator_stats) == 2 * 150


def test_search_never_returns_worse_than_initial():
    result = run_alns(INSTANCE, CONFIG, initial_solution=WARM, d_ref=D_REF)
    initial_score = Evaluator(INSTANCE, D_REF, 0.5, 0.5).solution(WARM).score

    assert not lexicographically_better(initial_score, result.evaluation.score)


def test_warm_start_is_reproducible():
    kwargs = {"initial_solution": WARM, "d_ref": D_REF}

    left = run_alns(INSTANCE, CONFIG, **kwargs)
    right = ALNSSolver(INSTANCE, CONFIG, **kwargs).run()

    assert left.best_solution == right.best_solution
    assert left.operator_stats == right.operator_stats


def test_d_ref_override_without_initial_solution_is_used():
    result = run_alns(INSTANCE, ALNSConfig(iterations=1, seed=1), d_ref=1234.5)

    assert result.d_ref == 1234.5


def test_contextual_warm_alns_uses_epoch_start_and_locked_prefix():
    prefix = WARM.routes[0][:1]
    constraints = SearchConstraints(locked_prefixes=(prefix,), free_departure=5.0)

    result = contextual_warm_alns(
        INSTANCE,
        WARM,
        constraints,
        D_REF,
        CONFIG,
        20,
        17,
    )

    assert result.initial_solution == WARM
    assert result.best_solution.routes[0][:1] == prefix
    assert result.iterations == 20

    assert result.seed == 17
    assert result.evaluation.feasible
