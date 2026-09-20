"""Parser for Solomon instances extended with a RISK section."""

from pathlib import Path

import numpy as np

from .geometry import compute_risk_priorities, euclidean_distance_matrix
from .models import Customer, Instance, RiskZone


class InstanceFormatError(ValueError):
    """Raised when an input file does not follow the Solomon-RISK format."""


def parse_instance(path: Path, customer_limit: int) -> Instance:
    if customer_limit <= 0:
        raise ValueError("customer_limit must be positive")

    lines = path.read_text(encoding="utf-8").splitlines()
    stripped = [line.strip() for line in lines]
    sections: dict[str, int] = {}
    for heading in ("VEHICLE", "CUSTOMER", "RISK"):
        try:
            sections[heading] = stripped.index(heading)
        except ValueError as exc:
            raise _format_error(path, None, f"missing {heading} section") from exc
    if not sections["VEHICLE"] < sections["CUSTOMER"] < sections["RISK"]:
        raise _format_error(path, None, "sections must appear as VEHICLE, CUSTOMER, RISK")

    name = next((line for line in stripped[: sections["VEHICLE"]] if line), path.stem)
    vehicle_rows = _numeric_rows(
        path,
        lines,
        sections["VEHICLE"] + 1,
        sections["CUSTOMER"],
        width=2,
        section="VEHICLE",
    )
    if len(vehicle_rows) != 1:
        raise _format_error(path, None, "VEHICLE must contain exactly one data row")
    _, vehicle_values = vehicle_rows[0]
    max_vehicles = _integer(vehicle_values[0], path, vehicle_rows[0][0], "vehicle count")
    capacity = vehicle_values[1]
    if max_vehicles <= 0:
        raise _format_error(path, vehicle_rows[0][0], "vehicle count must be positive")
    if capacity <= 0:
        raise _format_error(path, vehicle_rows[0][0], "capacity must be positive")

    customer_rows = _numeric_rows(
        path,
        lines,
        sections["CUSTOMER"] + 1,
        sections["RISK"],
        width=7,
        section="CUSTOMER",
    )
    customers_by_id: dict[int, Customer] = {}
    customer_order: list[Customer] = []
    for line_number, values in customer_rows:
        customer_id = _integer(values[0], path, line_number, "customer id")
        if customer_id in customers_by_id:
            raise _format_error(path, line_number, f"duplicate customer id {customer_id}")
        customer = Customer(customer_id, *values[1:])
        customers_by_id[customer_id] = customer
        customer_order.append(customer)
    if 0 not in customers_by_id:
        raise _format_error(path, None, "missing depot row with id 0")
    depot = customers_by_id[0]
    non_depot = [customer for customer in customer_order if customer.id != 0]
    if len(non_depot) < customer_limit:
        raise _format_error(
            path,
            None,
            f"requested {customer_limit} customers but found {len(non_depot)}",
        )
    customers = tuple(non_depot[:customer_limit])

    risk_rows = _numeric_rows(
        path,
        lines,
        sections["RISK"] + 1,
        len(lines),
        width=4,
        section="RISK",
    )
    risk_zones: list[RiskZone] = []
    risk_ids: set[int] = set()
    for line_number, values in risk_rows:
        zone_id = _integer(values[0], path, line_number, "risk id")
        if zone_id in risk_ids:
            raise _format_error(path, line_number, f"duplicate risk id {zone_id}")
        if values[3] <= 0:
            raise _format_error(path, line_number, "risk radius must be positive")
        risk_ids.add(zone_id)
        risk_zones.append(RiskZone(zone_id, *values[1:]))

    nodes = (depot, *customers)
    priorities = np.concatenate(
        (np.zeros(1, dtype=float), compute_risk_priorities(customers, tuple(risk_zones)))
    )
    return Instance(
        name=name,
        depot=depot,
        customers=customers,
        risk_zones=tuple(risk_zones),
        max_vehicles=max_vehicles,
        capacity=capacity,
        distance_matrix=euclidean_distance_matrix(nodes),
        risk_priority=priorities,
    )


def _numeric_rows(
    path: Path,
    lines: list[str],
    start: int,
    end: int,
    *,
    width: int,
    section: str,
) -> list[tuple[int, tuple[float, ...]]]:
    rows: list[tuple[int, tuple[float, ...]]] = []
    data_started = False
    for index in range(start, end):
        text = lines[index].strip()
        if not text:
            continue
        parts = text.split()
        try:
            values = tuple(float(part) for part in parts)
        except ValueError:
            if data_started:
                raise _format_error(path, index + 1, f"malformed {section} row")
            continue
        data_started = True
        if len(values) != width:
            raise _format_error(
                path,
                index + 1,
                f"malformed {section} row: expected {width} columns, got {len(values)}",
            )
        rows.append((index + 1, values))
    if not rows and section != "RISK":
        raise _format_error(path, None, f"{section} contains no data rows")
    return rows


def _integer(value: float, path: Path, line_number: int, label: str) -> int:
    if not value.is_integer():
        raise _format_error(path, line_number, f"{label} must be an integer")
    return int(value)


def _format_error(path: Path, line_number: int | None, reason: str) -> InstanceFormatError:
    location = f"{path}:{line_number}" if line_number is not None else str(path)
    return InstanceFormatError(f"{location}: {reason}")
