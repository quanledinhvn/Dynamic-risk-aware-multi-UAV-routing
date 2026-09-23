"""Strict parser for Solomon instances with a RISK section."""

from pathlib import Path

import numpy as np

from .geometry import compute_risk_priorities, euclidean_distance_matrix
from .models import Customer, Instance, RiskZone


class InstanceFormatError(ValueError):
    pass


def parse_instance(path: Path, customer_limit: int, risk_limit: int = 5) -> Instance:
    if customer_limit <= 0:
        raise ValueError("customer_limit must be positive")

    lines = path.read_text(encoding="utf-8").splitlines()
    stripped = [line.strip() for line in lines]
    sections = {}

    for heading in ("VEHICLE", "CUSTOMER", "RISK"):
        if heading not in stripped:
            raise _error(path, None, f"missing {heading} section")
        sections[heading] = stripped.index(heading)

    if not sections["VEHICLE"] < sections["CUSTOMER"] < sections["RISK"]:
        raise _error(path, None, "sections must appear as VEHICLE, CUSTOMER, RISK")

    vehicle_rows = _numeric_rows(path, lines, sections["VEHICLE"] + 1, sections["CUSTOMER"], 2, "VEHICLE")
    if len(vehicle_rows) != 1:
        raise _error(path, None, "VEHICLE must contain exactly one data row")
    vehicle_values = vehicle_rows[0][1]
    max_vehicles = _integer(vehicle_values[0], path, vehicle_rows[0][0], "vehicle count")
    capacity = vehicle_values[1]

    customer_rows = _numeric_rows(path, lines, sections["CUSTOMER"] + 1, sections["RISK"], 7, "CUSTOMER")
    records = {}
    order = []
    for line_number, values in customer_rows:
        customer_id = _integer(values[0], path, line_number, "customer id")
        if customer_id in records:
            raise _error(path, line_number, f"duplicate customer id {customer_id}")
        records[customer_id] = Customer(customer_id, *values[1:])
        order.append(records[customer_id])

    if 0 not in records:
        raise _error(path, None, "missing depot row with id 0")
    customers = tuple(customer for customer in order if customer.id != 0)[:customer_limit]
    if len(customers) < customer_limit:
        raise _error(path, None, f"requested {customer_limit} customers but found {len(customers)}")

    risk_rows = _numeric_rows(path, lines, sections["RISK"] + 1, len(lines), 4, "RISK")
    zones = []
    for line_number, values in risk_rows[:risk_limit]:
        zone_id = _integer(values[0], path, line_number, "risk id")
        if values[3] <= 0:
            raise _error(path, line_number, "risk radius must be positive")
        zones.append(RiskZone(zone_id, *values[1:]))
    if len(zones) < risk_limit:
        raise _error(path, None, f"requested {risk_limit} risk zones but found {len(zones)}")

    depot = records[0]
    nodes = (depot, *customers)
    priorities = np.concatenate(([0.0], compute_risk_priorities(customers, tuple(zones))))
    return Instance(
        path.stem,
        depot,
        customers,
        tuple(zones),
        max_vehicles,
        capacity,
        euclidean_distance_matrix(nodes),
        priorities,
    )


def _numeric_rows(path, lines, start, end, width, section):
    rows = []
    started = False
    for index in range(start, end):
        text = lines[index].strip()
        if not text:
            continue
        try:
            values = tuple(float(part) for part in text.split())
        except ValueError:
            if started:
                raise _error(path, index + 1, f"malformed {section} row")
            continue
        started = True
        if len(values) != width:
            raise _error(path, index + 1, f"malformed {section} row: expected {width} columns, got {len(values)}")
        rows.append((index + 1, values))
    if not rows and section != "RISK":
        raise _error(path, None, f"{section} contains no data rows")
    return rows


def _integer(value, path, line_number, label):
    if not value.is_integer():
        raise _error(path, line_number, f"{label} must be an integer")
    return int(value)


def _error(path, line_number, reason):
    location = f"{path}:{line_number}" if line_number is not None else str(path)
    return InstanceFormatError(f"{location}: {reason}")
