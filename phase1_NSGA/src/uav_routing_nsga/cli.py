"""Command line interface for one NSGA-III run."""

import argparse
import json
from pathlib import Path

from .nsga3 import NSGA3Config, run_nsga3
from .parser import parse_instance


def main():
    parser = argparse.ArgumentParser(description="Run NSGA-III for risk-aware multi-UAV routing")
    parser.add_argument("instance", type=Path)
    parser.add_argument("--customers", type=int, default=25)
    parser.add_argument("--risk-zones", type=int, default=5)
    parser.add_argument("--population", type=int, default=28)
    parser.add_argument("--generations", type=int, default=100)
    parser.add_argument("--divisions", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    instance = parse_instance(args.instance, args.customers, args.risk_zones)
    result = run_nsga3(instance, NSGA3Config(args.population, args.generations, args.divisions, seed=args.seed))
    payload = {
        "instance": instance.name,
        "seed": result.seed,
        "generations": result.generations,
        "runtime_seconds": result.runtime_seconds,
        "reference_direction_count": result.reference_direction_count,
        "pareto_front": [
            {"objectives": item.evaluation.objectives, "routes": item.solution.routes}
            for item in result.pareto_front
        ],
    }
    text = json.dumps(payload, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
