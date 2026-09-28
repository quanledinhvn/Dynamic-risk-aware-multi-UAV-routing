import pytest
from helpers import make_instance

from uav_routing.evaluator import Evaluator
from uav_routing.models import Customer, Solution
from uav_routing.repair import RepairContext, best_insertion, feasible_insertions


def make_context(max_vehicles=2):
    instance = make_instance(
        (
            Customer(1, 1, 0, 1, 0, 100, 0),
            Customer(2, 2, 0, 1, 0, 100, 0),
            Customer(3, 3, 0, 1, 0, 100, 0),
        ),
        max_vehicles=max_vehicles,
        priorities=(0.1, 0.2, 0.9),
    )

    return RepairContext(
        instance=instance,
        evaluator=Evaluator(instance, 10, 0.5, 0.5),
        d_ref=10,
        alpha=0.5,
        beta=0.5,
    )


class CountingEvaluator(Evaluator):
    def __init__(self, instance, d_ref, alpha, beta):
        super().__init__(instance, d_ref, alpha, beta)
        self.solution_calls = 0

    def solution(self, solution):
        self.solution_calls += 1

        return super().solution(solution)


def test_enumerates_all_feasible_existing_and_new_route_positions():
    insertions = feasible_insertions(Solution(((1, 2),)), 3, make_context())

    assert {(item.route_index, item.position) for item in insertions} == {
        (0, 0),
        (0, 1),
        (0, 2),
        (1, 0),
    }


def test_existing_route_beats_cheaper_new_route_because_delta_k_is_primary():
    chosen = best_insertion(Solution(((1,),)), 2, make_context())

    assert chosen is not None
    assert chosen.delta_k == 0


def test_new_route_is_absent_at_vehicle_limit():
    choices = feasible_insertions(Solution(((1,), (2,))), 3, make_context(2))

    assert choices
    assert all(item.delta_k == 0 for item in choices)


def test_insertion_that_breaks_downstream_due_date_is_excluded():
    instance = make_instance(
        (
            Customer(1, 1, 0, 1, 0, 100, 0),
            Customer(2, 2, 0, 1, 0, 4, 0),
            Customer(3, 20, 0, 1, 0, 100, 0),
        ),
        max_vehicles=1,
    )
    context = RepairContext(
        instance,
        Evaluator(instance, 40, 0.5, 0.5),
        40,
        0.5,
        0.5,
    )

    choices = feasible_insertions(Solution(((1, 2),)), 3, context)

    assert (0, 1) not in {(item.route_index, item.position) for item in choices}


def test_unknown_customer_has_no_feasible_insertion():
    assert feasible_insertions(Solution(((1,),)), 99, make_context()) == ()
    assert best_insertion(Solution(((1,),)), 99, make_context()) is None


def test_choices_are_sorted_by_lexicographic_cost_and_stable_ties():
    choices = feasible_insertions(Solution(((1,),)), 2, make_context())
    keys = [
        (item.delta_k, item.delta_f, item.route_index, item.position)
        for item in choices
    ]

    assert keys == sorted(keys)
    assert choices[0] == best_insertion(Solution(((1,),)), 2, make_context())


@pytest.mark.parametrize("position", (0, 1, 2))
def test_existing_route_delta_matches_full_solution_oracle(position):
    context = make_context()
    partial = Solution(((1, 2),))

    choice = next(
        item
        for item in feasible_insertions(partial, 3, context)
        if item.route_index == 0 and item.position == position
    )
    expected = (
        context.evaluator.solution(choice.solution).objective
        - context.evaluator.solution(partial).objective
    )

    assert choice.delta_f == pytest.approx(expected)


def test_new_route_delta_matches_full_solution_oracle():
    instance = make_instance(
        (
            Customer(1, 1, 0, 1, 0, 100, 0),
            Customer(3, 3, 0, 1, 0, 100, 0),
        ),
        max_vehicles=2,
        capacity=1,
        priorities=(0.1, 0.9),
    )
    context = RepairContext(
        instance,
        Evaluator(instance, 10, 0.5, 0.5),
        10,
        0.5,
        0.5,
    )
    partial = Solution(((1,),))

    choices = feasible_insertions(partial, 3, context)
    choice = next(item for item in choices if item.delta_k == 1)

    assert all(item.delta_k == 1 for item in choices)
    assert choice.delta_f == pytest.approx(
        context.evaluator.solution(choice.solution).objective
        - context.evaluator.solution(partial).objective
    )


def test_feasible_insertions_does_not_evaluate_full_solutions():
    base_context = make_context()
    evaluator = CountingEvaluator(base_context.instance, 10, 0.5, 0.5)
    context = RepairContext(base_context.instance, evaluator, 10, 0.5, 0.5)

    choices = feasible_insertions(Solution(((1, 2),)), 3, context)

    assert choices
    assert evaluator.solution_calls == 0
