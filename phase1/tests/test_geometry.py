import numpy as np
import pytest

from uav_routing.geometry import compute_risk_priorities, euclidean_distance_matrix
from uav_routing.models import Customer, RiskZone


def make_customers(points):
    return tuple(Customer(i + 1, x, y, 0, 0, 100, 0) for i, (x, y) in enumerate(points))


def test_euclidean_distance_matrix_is_symmetric_with_zero_diagonal():
    nodes = make_customers([(0, 0), (3, 4), (3, 0)])
    result = euclidean_distance_matrix(nodes)
    np.testing.assert_allclose(result, [[0, 5, 3], [5, 0, 4], [3, 4, 0]])
    assert np.array_equal(result, result.T)


def test_risk_priority_at_center_inside_boundary_and_outside():
    customers = make_customers([(0, 0), (3, 0), (5, 0), (6, 0)])
    zones = (RiskZone(1, 0, 0, 5),)
    assert compute_risk_priorities(customers, zones) == pytest.approx(
        [1.0, 0.4, 0.0, 0.0]
    )


def test_overlapping_zones_use_maximum_influence():
    customer = make_customers([(2, 0)])
    zones = (RiskZone(1, 0, 0, 4), RiskZone(2, 3, 0, 2))
    assert compute_risk_priorities(customer, zones)[0] == pytest.approx(0.5)


def test_no_zones_produces_zero_priorities():
    assert compute_risk_priorities(make_customers([(1, 2)]), ()) == pytest.approx([0])
