from pathlib import Path

import pytest

from uav_routing_nsga.evaluator import Evaluator
from uav_routing_nsga.parser import InstanceFormatError, parse_instance
from uav_routing_nsga.models import Solution


ROOT = Path(__file__).parents[2]


def test_parse_real_risk_instance():
    instance = parse_instance(ROOT / "dataset/solomon_risk/c101.txt", 25)
    assert len(instance.customers) == 25
    assert instance.distance_matrix.shape == (26, 26)
    assert len(instance.risk_zones) == 5


def test_zero_priority_is_finite():
    instance = parse_instance(ROOT / "dataset/solomon_risk/c101.txt", 25)
    instance = type(instance)(instance.name, instance.depot, instance.customers, (), instance.max_vehicles, instance.capacity, instance.distance_matrix, instance.risk_priority * 0)
    route = Solution(tuple((customer.id,) for customer in instance.customers))
    evaluation = Evaluator(instance).solution(route)
    assert evaluation.risk_delay == 0.0


def test_missing_section_reports_path():
    path = ROOT / "phase1_NSGA/tests/_malformed.txt"
    path.write_text("C101\n", encoding="utf-8")
    try:
        with pytest.raises(InstanceFormatError, match="_malformed.txt"):
            parse_instance(path, 1)
    finally:
        path.unlink()
