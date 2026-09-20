"""Geometric quantities derived from an instance."""

import math

import numpy as np

from .models import Customer, RiskZone


def euclidean_distance_matrix(nodes: tuple[Customer, ...]) -> np.ndarray:
    if not nodes:
        return np.empty((0, 0), dtype=float)
    xy = np.asarray([(node.x, node.y) for node in nodes], dtype=float)
    delta = xy[:, None, :] - xy[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


def compute_risk_priorities(
    customers: tuple[Customer, ...], zones: tuple[RiskZone, ...]
) -> np.ndarray:
    priorities = np.zeros(len(customers), dtype=float)
    for index, customer in enumerate(customers):
        priorities[index] = max(
            (
                max(
                    0.0,
                    1.0
                    - math.hypot(customer.x - zone.x, customer.y - zone.y)
                    / zone.radius,
                )
                for zone in zones
            ),
            default=0.0,
        )
    return priorities
