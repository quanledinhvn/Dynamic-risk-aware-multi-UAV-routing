"""Behavioral checks for contextual bandit configuration."""

from dataclasses import FrozenInstanceError, replace

import pytest

from uav_routing.contextual import ContextualBanditConfig


def test_defaults_are_valid_and_immutable():
    config = ContextualBanditConfig()

    assert config.context_window == 100
    assert config.linucb_exploration == 0.5
    assert config.linucb_regularization == 1.0
    assert config.include_temperature is True

    assert config.validate() is None

    with pytest.raises(FrozenInstanceError):
        config.context_window = 5


def test_from_dict_constructs_and_validates():
    config = ContextualBanditConfig.from_dict(
        {
            "context_window": 5,
            "linucb_exploration": 0.0,
            "linucb_regularization": 2.0,
        }
    )

    assert config == ContextualBanditConfig(5, 0.0, 2.0)

    with pytest.raises(ValueError, match="context_window"):
        ContextualBanditConfig.from_dict({"context_window": 0})


def test_from_dict_rejects_unknown_keys_as_value_error():
    with pytest.raises(ValueError, match="invalid configuration keys"):
        ContextualBanditConfig.from_dict({"unknown": 1})


@pytest.mark.parametrize("value", [True, False, 1.5, "5", 0, -1])
def test_context_window_requires_positive_integer(value):
    with pytest.raises(ValueError, match="context_window"):
        replace(ContextualBanditConfig(), context_window=value).validate()


@pytest.mark.parametrize(
    "value",
    [True, False, "0.5", float("nan"), float("inf"), float("-inf"), -0.1],
)
def test_exploration_requires_finite_nonnegative_number(value):
    with pytest.raises(ValueError, match="linucb_exploration"):
        replace(ContextualBanditConfig(), linucb_exploration=value).validate()


@pytest.mark.parametrize(
    "value",
    [True, False, "1.0", float("nan"), float("inf"), float("-inf"), 0.0, -0.1],
)
def test_regularization_requires_finite_positive_number(value):
    with pytest.raises(ValueError, match="linucb_regularization"):
        replace(ContextualBanditConfig(), linucb_regularization=value).validate()


@pytest.mark.parametrize("value", [0, 1, None, "false"])
def test_include_temperature_requires_boolean(value):
    with pytest.raises(ValueError, match="include_temperature"):
        replace(ContextualBanditConfig(), include_temperature=value).validate()


@pytest.mark.parametrize("value", [0, 1, None, "true"])
def test_short_route_warm_start_requires_boolean(value):
    with pytest.raises(ValueError, match="short_route_warm_start"):
        replace(ContextualBanditConfig(), short_route_warm_start=value).validate()
