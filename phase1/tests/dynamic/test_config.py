from dataclasses import replace

import pytest

from uav_routing.dynamic.config import RollingHorizonConfig


def test_default_rolling_config_is_valid():
    RollingHorizonConfig().validate()


@pytest.mark.parametrize(
    "changes",
    [
        {"policy": "unknown"},
        {"trigger": "never"},
        {"epoch_length": 0.0},
        {"epoch_length": float("inf")},
        {"iterations_epoch0": -1},
        {"iterations_per_epoch": -1},
        {"iterations_per_epoch": 1.5},
        {"seed": "7"},
    ],
)
def test_invalid_rolling_config_is_rejected(changes):
    config = replace(RollingHorizonConfig(), **changes)

    with pytest.raises(ValueError):
        config.validate()


def test_iterations_per_epoch_zero_is_allowed():
    replace(RollingHorizonConfig(), iterations_per_epoch=0).validate()


def test_from_dict_constructs_and_validates():
    config = RollingHorizonConfig.from_dict({"epoch_length": 30.0})

    assert config.epoch_length == 30.0

    with pytest.raises(ValueError, match="policy"):
        RollingHorizonConfig.from_dict({"policy": "bogus"})

    with pytest.raises(ValueError, match="keys"):
        RollingHorizonConfig.from_dict({"unknown": 1})


@pytest.mark.parametrize("fraction", [0.0, 1.5, -0.1, float("nan")])
def test_invalid_epoch_fraction_is_rejected(fraction):
    with pytest.raises(ValueError, match="epoch_fraction"):
        replace(RollingHorizonConfig(), epoch_fraction=fraction).validate()


def test_epoch_fraction_is_optional_and_accepted():
    replace(RollingHorizonConfig(), epoch_fraction=0.05).validate()
    assert RollingHorizonConfig().epoch_fraction is None
