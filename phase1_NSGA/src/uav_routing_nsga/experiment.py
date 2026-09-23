"""Small reproducible benchmark runner for raw Pareto summaries."""

import csv
from pathlib import Path

from .nsga3 import NSGA3Config, run_nsga3
from .parser import parse_instance


def run_benchmark(
    data_dir: Path,
    names: tuple[str, ...],
    seeds: tuple[int, ...],
    output: Path,
    customer_limit: int = 25,
    risk_limit: int = 5,
    population_size: int = 28,
    generations: int = 100,
    divisions: int = 4,
    risk_limits: tuple[int, ...] | None = None,
) -> None:
    selected_risk_limits = risk_limits or (risk_limit,)
    rows = []
    for risk_count in selected_risk_limits:
        for name in names:
            instance = parse_instance(data_dir / f"{name}.txt", customer_limit, risk_count)
            for seed in seeds:
                result = run_nsga3(
                    instance,
                    NSGA3Config(
                        population_size=population_size,
                        generations=generations,
                        divisions=divisions,
                        seed=seed,
                    ),
                )
                rows.extend(
                    {
                        "instance": name,
                        "risk_limit": risk_count,
                        "seed": seed,
                        "pareto_index": index,
                        "vehicles": item.evaluation.objectives[0],
                        "distance": item.evaluation.objectives[1],
                        "risk_delay": item.evaluation.objectives[2],
                        "max_load": item.evaluation.objectives[3],
                        "total_lateness": item.evaluation.objectives[4],
                        "runtime_seconds": result.runtime_seconds,
                    }
                    for index, item in enumerate(result.pareto_front)
                )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = (
            "instance",
            "risk_limit",
            "seed",
            "pareto_index",
            "vehicles",
            "distance",
            "risk_delay",
            "max_load",
            "total_lateness",
            "runtime_seconds",
        )
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
