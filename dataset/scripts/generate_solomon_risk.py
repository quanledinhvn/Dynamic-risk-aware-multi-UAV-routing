#!/usr/bin/env python3
"""Create Solomon instances with five deterministic, offset risk zones appended."""

from __future__ import annotations

import argparse
import hashlib
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path


MIN_RISK_RADIUS = 2
MAX_RISK_RADIUS = 10
RISK_COUNT = 5
FIRST_VIEW_CUSTOMER_COUNT = 25
CUSTOMER_ROW = re.compile(
    r"^\s*(\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)"
    r"\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?"
    r"\s+\d+(?:\.\d+)?\s*$"
)


@dataclass(frozen=True)
class Point:
    customer_id: int
    x: float
    y: float


def parse_customers(text: str) -> list[Point]:
    customers = [
        Point(int(match.group(1)), float(match.group(2)), float(match.group(3)))
        for line in text.splitlines()
        if (match := CUSTOMER_ROW.match(line))
    ]
    if not customers or customers[0].customer_id != 0:
        raise ValueError("could not find depot row (customer 0)")
    if len(customers) < 6:
        raise ValueError("not enough customer rows to place five risk zones")
    return customers


def distance(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def seed_for(filename: str, base_seed: int) -> int:
    digest = hashlib.sha256(f"{base_seed}:{filename}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def offset_center(
    host: Point,
    depot: Point,
    radius: int,
    customers: list[Point],
    rng: random.Random,
) -> Point:
    """Move a risk center away from its covered customer without covering the depot."""
    offset = radius / 2
    for _ in range(360):
        angle = rng.uniform(0, math.tau)
        center = Point(
            host.customer_id,
            round(host.x + math.cos(angle) * offset),
            round(host.y + math.sin(angle) * offset),
        )
        if distance(center, depot) <= radius:
            continue
        if any(distance(center, customer) < 1e-9 for customer in customers):
            continue
        return center

    raise ValueError(f"could not offset risk center from customer {host.customer_id}")


def choose_risks(customers: list[Point], rng: random.Random) -> list[tuple[Point, int]]:
    depot = customers[0]
    remaining = customers[1:].copy()
    # Draw unique radii per instance. Keep both parities so the generated set
    # always contains odd values as well as even ones.
    while True:
        radii = rng.sample(range(MIN_RISK_RADIUS, MAX_RISK_RADIUS + 1), RISK_COUNT)
        if any(radius % 2 for radius in radii) and any(radius % 2 == 0 for radius in radii):
            break
    selected: list[tuple[Point, int]] = []

    for risk_index, radius in enumerate(radii):
        candidates = (
            customers[1 : FIRST_VIEW_CUSTOMER_COUNT + 1]
            if risk_index == 0
            else remaining
        )
        eligible = [point for point in candidates if distance(point, depot) > radius]
        if not eligible:
            customer_scope = (
                f"the first {FIRST_VIEW_CUSTOMER_COUNT} customers"
                if risk_index == 0
                else "the customer set"
            )
            raise ValueError(
                f"no location in {customer_scope} can host risk radius {radius}"
            )

        if risk_index == 0:
            # Risk 1 is visible with the default 25-customer view and covers its
            # host customer even though the risk center is offset from it.
            host = rng.choice(eligible)
        else:
            # Spread centers across the customer region. A tiny seeded tie-breaker
            # prevents every instance with the same coordinates from looking alike.
            host = max(
                eligible,
                key=lambda candidate: (
                    min(distance(candidate, chosen) for chosen, _ in selected)
                    + rng.random() * 1e-6
                ),
            )

        center = offset_center(host, depot, radius, customers, rng)
        selected.append((center, radius))
        remaining.remove(host)

    return selected


def format_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else format(value, "g")


def append_risks(source: Path, destination: Path, base_seed: int) -> None:
    raw = source.read_bytes()
    text = raw.decode("utf-8")
    customers = parse_customers(text)
    risks = choose_risks(customers, random.Random(seed_for(source.name, base_seed)))

    newline = "\r\n" if b"\r\n" in raw else "\n"
    rows = [
        "RISK",
        "RISK NO.   XCOORD.   YCOORD. RADIUS",
        "",
        *[
            f"{risk_no:5d}      {format_number(point.x):<11}"
            f"{format_number(point.y):<8}{radius}"
            for risk_no, (point, radius) in enumerate(risks, start=1)
        ],
    ]
    separator = b"" if raw.endswith((b"\n", b"\r")) else newline.encode()
    addition = separator + newline.encode() + newline.join(rows).encode() + newline.encode()

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw + addition)

    # Fail immediately if a future edit breaks any generation guarantee.
    radii = [radius for _, radius in risks]
    assert len(risks) == RISK_COUNT
    assert len(set(radii)) == RISK_COUNT
    assert all(MIN_RISK_RADIUS <= radius <= MAX_RISK_RADIUS for radius in radii)
    assert any(radius % 2 for radius in radii)
    assert any(radius % 2 == 0 for radius in radii)
    assert len({point.customer_id for point, _ in risks}) == RISK_COUNT
    assert all(distance(point, customers[0]) > radius for point, radius in risks)
    assert all(
        all(distance(center, customer) > 1e-9 for customer in customers)
        for center, _ in risks
    )
    first_risk_center, first_risk_radius = risks[0]
    assert any(
        distance(first_risk_center, customer) <= first_risk_radius
        for customer in customers[1 : FIRST_VIEW_CUSTOMER_COUNT + 1]
    )


def main() -> None:
    dataset_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=dataset_dir / "solomon")
    parser.add_argument("--output", type=Path, default=dataset_dir / "solomon_risk")
    parser.add_argument("--seed", type=int, default=20260916)
    args = parser.parse_args()

    files = sorted(args.source.glob("*.txt"))
    if not files:
        raise SystemExit(f"no .txt files found in {args.source}")

    for source in files:
        append_risks(source, args.output / source.name, args.seed)

    print(f"Generated {len(files)} files in {args.output}")


if __name__ == "__main__":
    main()
