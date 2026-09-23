"""Geometry derived from Solomon-RISK input."""

import math

import numpy as np

from .models import Customer, RiskZone


def euclidean_distance_matrix(nodes: tuple[Customer, ...]) -> np.ndarray:
    xy = np.asarray([(node.x, node.y) for node in nodes], dtype=float)
    delta = xy[:, None, :] - xy[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


def compute_risk_priorities(
    customers: tuple[Customer, ...], zones: tuple[RiskZone, ...]
) -> np.ndarray:
    return np.asarray(
        [
            max(
                (
                    max(0.0, 1.0 - math.hypot(c.x - z.x, c.y - z.y) / z.radius)
                    for z in zones
                ),
                default=0.0,
            )
            for c in customers
        ],
        dtype=float,
    )
