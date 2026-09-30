from dataclasses import replace

from helpers import make_instance

from uav_routing.dynamic.events import apply_events
from uav_routing.dynamic.models import CustomerArrival, DeadlineUpdate
from uav_routing.dynamic.projection import lost_customers, project, triage
from uav_routing.evaluator import Evaluator
from uav_routing.models import Customer, SearchConstraints, Solution
from uav_routing.repair import RepairContext

# depot (0,0); 1 (3,4) leave 7; 2 (6,8) leave 14; 3 (0,10) arrive ~20.3
CUSTOMERS = (
    Customer(1, 3, 4, 1, 0, 200, 2),
    Customer(2, 6, 8, 1, 0, 200, 2),
    Customer(3, 0, 10, 1, 0, 200, 0),
    Customer(4, 3, 0, 1, 0, 200, 0),
    Customer(5, 10, 0, 1, 0, 200, 0),
)
INSTANCE = make_instance(
    CUSTOMERS,
    depot=Customer(0, 0, 0, 0, 0, 500, 0),
    max_vehicles=2,
    priorities=(0.1, 0.2, 0.9, 0.4, 0.5),
)
NEW = Customer(9, 20, 20, 1, 30.0, 120.0, 0)


def _evaluator(instance):
    return Evaluator(instance, 100.0, 0.5, 0.5)


def _context(instance, constraints):
    return RepairContext(instance, _evaluator(instance), 100.0, 0.5, 0.5, constraints)


def test_project_collects_new_customers_into_pool():
    updated = apply_events(INSTANCE, (CustomerArrival(10.0, NEW),), {})
    solution = Solution(((1, 2, 3), (4, 5)))
    constraints = SearchConstraints(locked_prefixes=((1,),), free_departure=10.0)

    projected, pool = project(solution, updated, _evaluator(updated), constraints)

    assert projected == solution
    assert pool == (9,)


def test_project_removes_free_customers_until_route_feasible():
    tightened = apply_events(
        INSTANCE, (DeadlineUpdate(5.0, 3, 15.0), DeadlineUpdate(5.0, 2, 13.0)), {}
    )
    solution = Solution(((1, 2, 3), (4, 5)))
    constraints = SearchConstraints(locked_prefixes=((1,),), free_departure=5.0)

    projected, pool = project(solution, tightened, _evaluator(tightened), constraints)

    # customer 2 is served at 12 <= 13, but 3 cannot make 15 behind it
    assert projected.routes == ((1, 2), (4, 5))
    assert pool == (3,)
    assert _evaluator(tightened).solution(projected, constraints).violations == (
        "missing_customers",
    )


def test_project_removes_the_violating_customer_first():
    tightened = apply_events(INSTANCE, (DeadlineUpdate(5.0, 2, 8.0),), {})
    solution = Solution(((1, 2, 3), (4, 5)))
    constraints = SearchConstraints(locked_prefixes=((1,),), free_departure=5.0)

    projected, pool = project(solution, tightened, _evaluator(tightened), constraints)

    assert projected.routes == ((1, 3), (4, 5))
    assert pool == (2,)


def test_project_never_removes_locked_customers_even_if_late():
    late = replace(
        INSTANCE,
        customers=(replace(CUSTOMERS[0], due_date=1.0),) + CUSTOMERS[1:],
    )
    solution = Solution(((1, 2), (4, 5)))
    constraints = SearchConstraints(locked_prefixes=((1,),), free_departure=5.0)

    projected, pool = project(solution, late, _evaluator(late), constraints)

    assert projected.routes[0][:1] == (1,)
    assert 1 not in pool


def test_project_drops_customers_missing_from_instance():
    shrunk = replace(INSTANCE, customers=CUSTOMERS[:3])
    solution = Solution(((1, 2), (4, 5), (3,)))
    constraints = SearchConstraints(locked_prefixes=((1,),), free_departure=5.0)

    projected, pool = project(solution, shrunk, _evaluator(shrunk), constraints)

    assert projected.routes == ((1, 2), (3,))
    assert pool == ()


def test_project_drops_empty_free_routes_and_keeps_locked_indices():
    tightened = apply_events(INSTANCE, (DeadlineUpdate(5.0, 4, 1.0),), {})
    solution = Solution(((1, 2, 3), (4,), (5,)))
    constraints = SearchConstraints(locked_prefixes=((1,),), free_departure=5.0)

    projected, pool = project(solution, tightened, _evaluator(tightened), constraints)

    assert projected.routes == ((1, 2, 3), (5,))
    assert pool == (4,)


def test_project_is_noop_without_changes():
    solution = Solution(((1, 2, 3), (4, 5)))
    constraints = SearchConstraints(locked_prefixes=((1,),), free_departure=5.0)

    projected, pool = project(solution, INSTANCE, _evaluator(INSTANCE), constraints)

    assert projected == solution
    assert pool == ()


def test_triage_inserts_by_priority_then_due_date():
    constraints = SearchConstraints(locked_prefixes=((1,),), free_departure=5.0)
    context = _context(INSTANCE, constraints)

    inserted, rejected = triage(Solution(((1,),)), (2, 3, 4, 5), context)

    assert rejected == ()
    assert inserted.routes[0][:1] == (1,)
    assert sorted(c for route in inserted.routes for c in route) == [1, 2, 3, 4, 5]
    assert context.evaluator.solution(inserted, constraints).feasible


def test_triage_reports_uninsertable_customers_without_failing():
    tightened = apply_events(INSTANCE, (DeadlineUpdate(5.0, 5, 6.0),), {})
    constraints = SearchConstraints(locked_prefixes=((1,),), free_departure=8.0)
    context = _context(tightened, constraints)

    inserted, rejected = triage(Solution(((1,),)), (4, 5), context)

    assert rejected == (5,)
    assert sorted(c for route in inserted.routes for c in route) == [1, 4]
    assert context.evaluator.solution(inserted, constraints).violations == (
        "missing_customers",
    )


def test_triage_with_empty_pool_returns_partial():
    context = _context(INSTANCE, SearchConstraints())

    assert triage(Solution(((1,),)), (), context) == (Solution(((1,),)), ())


def test_lost_customers_are_those_past_latest_launch():
    # customer 5 is 10 away with due date 200: lost once time > 190
    assert lost_customers(INSTANCE, (5, 4), 189.0) == ()
    assert lost_customers(INSTANCE, (5, 4), 191.0) == (5,)
    assert lost_customers(INSTANCE, (5, 4), 500.0) == (4, 5)


def test_lost_customers_ignores_unknown_ids():
    assert lost_customers(INSTANCE, (42,), 1e9) == ()
