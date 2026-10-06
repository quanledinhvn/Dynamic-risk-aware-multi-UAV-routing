import pytest

from uav_routing.models import SearchConstraints


def test_constraints_default_is_unconstrained():
    constraints = SearchConstraints()

    assert constraints.locked_route_count == 0
    assert constraints.locked_customers() == frozenset()
    assert constraints.first_free_position(3) == 0
    assert constraints.free_departure == 0.0


def test_constraints_expose_locked_customers_and_positions():
    constraints = SearchConstraints(locked_prefixes=((1, 2), (5,)), free_departure=30.0)

    assert constraints.locked_route_count == 2
    assert constraints.locked_customers() == frozenset({1, 2, 5})
    assert constraints.is_locked(2)
    assert not constraints.is_locked(9)
    assert constraints.first_free_position(0) == 2
    assert constraints.first_free_position(1) == 1
    assert constraints.first_free_position(2) == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"locked_prefixes": ((1,), (1,))},
        {"locked_prefixes": ((1, 1),)},
        {"locked_prefixes": ((),)},
        {"free_departure": -1.0},
    ],
)
def test_constraints_reject_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        SearchConstraints(**kwargs)


def test_constraints_are_hashable_and_comparable():
    left = SearchConstraints(((1,),), 5.0)
    right = SearchConstraints(((1,),), 5.0)

    assert left == right
    assert hash(left) == hash(right)
