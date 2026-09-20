from dataclasses import replace

import pytest

from uav_routing.config import ALNSConfig
from uav_routing.models import Solution


def test_default_config_is_valid():
    ALNSConfig().validate()


@pytest.mark.parametrize(
    "changes",
    [
        {"iterations": 0},
        {"segment_length": 0},
        {"q_min": 0},
        {"q_min": 6, "q_max": 5},
        {"alpha": -0.1, "beta": 1.1},
        {"alpha": 0.4, "beta": 0.5},
        {"initial_temperature": 0.0},
        {"minimum_temperature": 0.0},
        {"cooling_rate": 1.01},
        {"minimum_weight": 0.0},
        {"reaction_factor": 1.1},
        {"removal_determinism": 0.0},
        {
            "related_distance_weight": 0.0,
            "related_time_weight": 0.0,
            "related_demand_weight": 0.0,
            "related_risk_weight": 0.0,
        },
        {"reward_best": -1.0},
    ],
)
def test_invalid_config_is_rejected(changes):
    config = replace(ALNSConfig(), **changes)

    with pytest.raises(ValueError):
        config.validate()


@pytest.mark.parametrize(
    "changes",
    [
        {"iterations": 1.5},
        {"q_min": True},
        {"q_max": 2.5},
        {"segment_length": 10.5},
        {"seed": False},
        {"iterations": "10"},
    ],
)
def test_count_fields_require_integers(changes):
    with pytest.raises(ValueError):
        replace(ALNSConfig(), **changes).validate()


@pytest.mark.parametrize(
    "changes",
    [
        {"alpha": float("nan")},
        {"beta": float("inf")},
        {"initial_temperature": float("inf")},
        {"minimum_weight": float("nan")},
        {"related_risk_weight": float("inf")},
        {"reward_best": float("nan")},
        {"cooling_rate": True},
        {"alpha": "0.5"},
    ],
)
def test_real_parameters_must_be_finite_numbers(changes):
    with pytest.raises(ValueError):
        replace(ALNSConfig(), **changes).validate()


def test_solution_routes_are_immutable():
    solution = Solution(routes=((1, 2),))

    with pytest.raises(TypeError):
        solution.routes[0][0] = 9


def test_from_dict_constructs_and_validates():
    assert ALNSConfig.from_dict({"iterations": 50}).iterations == 50

    with pytest.raises(ValueError, match="iterations"):
        ALNSConfig.from_dict({"iterations": 0})


def test_from_dict_rejects_unknown_keys_as_value_error():
    with pytest.raises(ValueError, match="invalid configuration keys"):
        ALNSConfig.from_dict({"unknown": 1})
