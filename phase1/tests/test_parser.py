from pathlib import Path

import numpy as np
import pytest

from uav_routing.parser import InstanceFormatError, parse_instance


FIXTURES = Path(__file__).parent / "fixtures"


def valid_text_without_depot():
    return """TINY
VEHICLE
NUMBER CAPACITY
2 10
CUSTOMER
HEADER
1 3 4 2 0 50 1
2 6 8 3 0 60 1
RISK
HEADER
1 3 4 5
"""


def valid_text_with_zone_radius(radius):
    return f"""TINY
VEHICLE
NUMBER CAPACITY
2 10
CUSTOMER
HEADER
0 0 0 0 0 100 0
1 3 4 2 0 50 1
2 6 8 3 0 60 1
RISK
HEADER
1 3 4 {radius}
"""


def test_parse_limits_customers_and_builds_derived_arrays():
    instance = parse_instance(FIXTURES / "tiny_valid.txt", customer_limit=2)
    assert instance.name == "TINY"
    assert instance.max_vehicles == 2
    assert instance.capacity == 10
    assert [c.id for c in instance.customers] == [1, 2]
    assert instance.distance_matrix.shape == (3, 3)
    assert instance.risk_priority.shape == (3,)
    assert instance.risk_priority == pytest.approx([0.0, 1.0, 0.0])
    assert np.array_equal(instance.distance_matrix, instance.distance_matrix.T)


@pytest.mark.parametrize(
    "content, message",
    [
        ("BROKEN", "VEHICLE"),
        (valid_text_without_depot(), "depot"),
        (valid_text_with_zone_radius(0), "radius"),
    ],
)
def test_malformed_input_reports_path_and_reason(tmp_path, content, message):
    path = tmp_path / "bad.txt"
    path.write_text(content)
    with pytest.raises(InstanceFormatError, match=message) as error:
        parse_instance(path, customer_limit=2)
    assert str(path) in str(error.value)


@pytest.mark.parametrize("limit", [0, -1])
def test_customer_limit_must_be_positive(limit):
    with pytest.raises(ValueError, match="customer_limit"):
        parse_instance(FIXTURES / "tiny_valid.txt", customer_limit=limit)


def test_rejects_insufficient_customers():
    with pytest.raises(InstanceFormatError, match="requested 4"):
        parse_instance(FIXTURES / "tiny_valid.txt", customer_limit=4)


def test_rejects_duplicate_customer_ids(tmp_path):
    content = (FIXTURES / "tiny_valid.txt").read_text().replace(
        "2 6 8 3 0 60 1", "1 6 8 3 0 60 1"
    )
    path = tmp_path / "duplicate.txt"
    path.write_text(content)
    with pytest.raises(InstanceFormatError, match="duplicate"):
        parse_instance(path, customer_limit=2)
