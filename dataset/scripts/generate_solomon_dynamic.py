#!/usr/bin/env python3
"""Generate dynamic scenarios from Solomon-RISK instances.

Run from ``phase1`` so that ``uav_routing`` is importable::

    uv run python ../dataset/scripts/generate_solomon_dynamic.py \
        --instances c101 r101 rc101 --static 25 --dynamic 5 12 25 \
        --seeds 0 1 2 --output ../dataset/solomon_dynamic
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from uav_routing.dynamic.scenario import generate_scenario, save_scenario

DEFAULT_INSTANCES = (
    "c101",
    "c102",
    "c103",
    "r101",
    "r102",
    "r103",
    "rc101",
    "rc102",
    "rc103",
)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    written = 0

    for name in args.instances:
        instance_path = args.source / f"{name}.txt"

        for dynamic in args.dynamic:
            for seed in args.seeds:
                scenario = generate_scenario(
                    instance_path,
                    static_customers=args.static,
                    dynamic_customers=dynamic,
                    risk_limit=args.risks,
                    risk_events=args.risk_events,
                    deadline_events=args.deadline_events,
                    release_fraction=args.release_fraction,
                    seed=seed,
                )
                target = args.output / f"{scenario.name}.json"

                save_scenario(scenario, target)
                written += 1

    print(f"wrote {written} scenarios to {args.output}", file=sys.stderr)

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])

    parser.add_argument("--instances", nargs="+", default=list(DEFAULT_INSTANCES))
    parser.add_argument("--source", type=Path, default=Path("../dataset/solomon_risk"))
    parser.add_argument(
        "--output", type=Path, default=Path("../dataset/solomon_dynamic")
    )
    parser.add_argument("--static", type=int, default=25)
    parser.add_argument("--dynamic", type=int, nargs="+", default=[5, 12, 25])
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    parser.add_argument("--risks", type=int, default=5)
    parser.add_argument("--risk-events", type=int, default=2)
    parser.add_argument("--deadline-events", type=int, default=2)
    parser.add_argument("--release-fraction", type=float, default=0.6)

    return parser


if __name__ == "__main__":
    raise SystemExit(main())
