import pytest
from helpers import make_instance

from uav_routing.dynamic.locking import lock_solution, route_prefixes
from uav_routing.evaluator import Evaluator
from uav_routing.models import Customer, SearchConstraints, Solution

# depot (0,0); route (1, 2, 3): arrive 1 at 5, leave 7, arrive 2 at 12, leave 14,
# arrive 3 at 14 + sqrt(40) ~ 20.32
CUSTOMERS = (
    Customer(1, 3, 4, 1, 0, 200, 2),
    Customer(2, 6, 8, 1, 0, 200, 2),
    Customer(3, 0, 10, 1, 0, 200, 0),
    Customer(4, 3, 0, 1, 50, 200, 0),
    Customer(5, -3, -4, 1, 0, 200, 0),
    Customer(7, 0, -5, 1, 500, 600, 0),
    Customer(8, 5, 0, 1, 500, 600, 0),
    Customer(9, 10, 0, 1, 500, 600, 0),
)
INSTANCE = make_instance(
    CUSTOMERS, depot=Customer(0, 0, 0, 0, 0, 1000, 0), max_vehicles=5
)
EVALUATOR = Evaluator(INSTANCE, 1.0, 1.0, 0.0)
ROUTE = Solution(((1, 2, 3),))


@pytest.mark.parametrize(
    "time,expected",
    [
        (0.0, ()),
        (0.5, (1,)),
        (6.0, (1,)),
        (7.0, (1,)),
        (7.5, (1, 2)),
        (13.0, (1, 2)),
        (14.0, (1, 2)),
        (14.5, (1, 2, 3)),
        (1e9, (1, 2, 3)),
    ],
)
def test_prefix_follows_strict_departure_rule(time, expected):
    assert route_prefixes(ROUTE, EVALUATOR, time, None) == (expected,)

    solution, constraints = lock_solution(ROUTE, EVALUATOR, time, None)

    assert solution == ROUTE
    assert constraints.locked_prefixes == ((expected,) if expected else ())
    assert constraints.free_departure == time


def test_first_customer_uses_latest_depot_departure():
    # customer 4 opens at 50 and is 3 away, so the UAV leaves the depot at 47
    solution = Solution(((4,),))

    assert route_prefixes(solution, EVALUATOR, 46.0, None) == ((),)
    assert route_prefixes(solution, EVALUATOR, 47.5, None) == ((4,),)


def test_free_routes_use_previous_free_departure():
    previous = SearchConstraints(free_departure=20.0)
    solution = Solution(((1,), (4,)))

    assert route_prefixes(solution, EVALUATOR, 25.0, previous) == ((1,), ())
    assert route_prefixes(solution, EVALUATOR, 19.0, previous) == ((), ())


def test_previous_locks_are_never_shortened():
    previous = SearchConstraints(locked_prefixes=((1, 2),))

    assert route_prefixes(ROUTE, EVALUATOR, 6.0, previous) == ((1, 2),)


def test_previous_locked_routes_are_scheduled_from_zero():
    previous = SearchConstraints(locked_prefixes=((1,),), free_departure=50.0)

    assert route_prefixes(ROUTE, EVALUATOR, 8.0, previous) == ((1, 2),)


def test_reorder_moves_locked_routes_first_preserving_relative_order():
    solution = Solution(((7,), (1, 2), (8, 9), (5,)))

    reordered, constraints = lock_solution(solution, EVALUATOR, 3.0, None)

    assert reordered.routes == ((1, 2), (5,), (7,), (8, 9))
    assert constraints.locked_prefixes == ((1,), (5,))
    assert constraints.free_departure == 3.0


def test_lock_solution_keeps_previously_locked_routes_in_front():
    previous = SearchConstraints(locked_prefixes=((5,),), free_departure=1.0)
    solution = Solution(((5,), (7,), (1, 2)))

    reordered, constraints = lock_solution(solution, EVALUATOR, 3.0, previous)

    assert reordered.routes == ((5,), (1, 2), (7,))
    assert constraints.locked_prefixes == ((5,), (1,))


def test_lock_solution_rejects_negative_time():
    with pytest.raises(ValueError):
        lock_solution(ROUTE, EVALUATOR, -1.0, None)
