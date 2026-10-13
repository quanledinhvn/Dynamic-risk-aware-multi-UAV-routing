#!/usr/bin/env python3
# ruff: noqa: E501
"""Why contextual ALNS trails roulette inside the rolling horizon.

Two diagnostics, both deterministic given the seeds:

1. ``epoch0``: the static 2000-iteration epoch-0 solve on every 100-customer base
   instance (95/88/75 static customers, seeds 0-2) under both selectors.
2. ``traces``: full rolling-horizon runs with the two selectors swapped only
   inside the re-planning epochs (identical roulette epoch 0), recording the
   per-epoch objective and how concentrated each selector's operator choice is.

Run from ``phase1``::

    uv run python scripts/diagnose_bandit.py --output results/analysis
"""

from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import statistics as st
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "dataset" / "solomon_dynamic"
INSTANCES = ("c101", "c102", "c103", "r101", "r102", "r103", "rc101", "rc102", "rc103")
LEVELS = ((95, 5), (88, 12), (75, 25))
EPOCH0_ITERATIONS = 2000
EPOCH_ITERATIONS = 400


def _class(instance: str) -> str:
    return "RC" if instance.startswith("rc") else instance[0].upper()


def epoch0_job(args):
    name, seed = args
    from uav_routing.alns import run_alns
    from uav_routing.config import ALNSConfig
    from uav_routing.contextual.alns import run_contextual_alns
    from uav_routing.contextual.config import ContextualBanditConfig
    from uav_routing.dynamic.horizon import epoch_seed
    from uav_routing.dynamic.scenario import base_instance, load_scenario

    instance = base_instance(load_scenario(SCENARIOS / name))
    config = ALNSConfig(iterations=EPOCH0_ITERATIONS, seed=epoch_seed(seed, 0))
    roulette = run_alns(instance, config).evaluation
    contextual = run_contextual_alns(
        instance, config, ContextualBanditConfig()
    ).evaluation

    return {
        "scenario": name.removesuffix(".json"),
        "class": _class(name),
        "seed": seed,
        "roulette_K": roulette.vehicle_count,
        "roulette_F": roulette.objective,
        "roulette_D": roulette.distance,
        "roulette_R": roulette.risk_delay,
        "contextual_K": contextual.vehicle_count,
        "contextual_F": contextual.objective,
        "contextual_D": contextual.distance,
        "contextual_R": contextual.risk_delay,
    }


def trace_job(name):
    from uav_routing.alns import SearchResult, run_alns
    from uav_routing.config import ALNSConfig
    from uav_routing.contextual.alns import run_contextual_alns
    from uav_routing.contextual.config import ContextualBanditConfig
    from uav_routing.dynamic.config import RollingHorizonConfig
    from uav_routing.dynamic.horizon import run_rolling_horizon
    from uav_routing.dynamic.scenario import load_scenario

    scenario = load_scenario(SCENARIOS / name)
    alns = ALNSConfig(iterations=10_000, seed=0)
    rolling = RollingHorizonConfig(
        epoch_fraction=0.05,
        iterations_epoch0=EPOCH0_ITERATIONS,
        iterations_per_epoch=EPOCH_ITERATIONS,
        seed=0,
    )
    trace = {"roulette": [], "contextual": []}

    def roulette(instance, initial, constraints, d_ref, cfg, iterations, seed):
        result = run_alns(
            instance,
            replace(cfg, iterations=iterations, seed=seed),
            initial_solution=initial,
            constraints=constraints,
            d_ref=d_ref,
        )
        uses = {
            s.name: s.total_uses
            for s in result.operator_stats
            if s.name.startswith("destroy")
        }
        trace["roulette"].append(
            (
                result.evaluation.objective,
                result.initial_solution == result.best_solution,
                max(uses.values()) / sum(uses.values()),
            )
        )

        return result

    def contextual(instance, initial, constraints, d_ref, cfg, iterations, seed):
        result = run_contextual_alns(
            instance,
            replace(cfg, iterations=iterations, seed=seed),
            ContextualBanditConfig(),
            initial_solution=initial,
            constraints=constraints,
            d_ref=d_ref,
        )
        by_destroy: dict[str, int] = {}

        for stat in result.pair_selection_stats:
            by_destroy[stat.destroy_name] = (
                by_destroy.get(stat.destroy_name, 0) + stat.total_uses
            )

        trace["contextual"].append(
            (
                result.evaluation.objective,
                result.initial_solution == result.best_solution,
                max(by_destroy.values()) / sum(by_destroy.values()),
            )
        )

        return SearchResult(
            result.initial_solution,
            result.final_current,
            result.best_solution,
            result.d_ref,
            result.evaluation,
            result.iterations,
            result.seed,
            result.runtime_seconds,
            (),
        )

    final_r = run_rolling_horizon(scenario, alns, rolling, solver=roulette)
    final_c = run_rolling_horizon(scenario, alns, rolling, solver=contextual)

    return {
        "scenario": name.removesuffix(".json"),
        "roulette_F": final_r.evaluation.objective,
        "contextual_F": final_c.evaluation.objective,
        "roulette_improving_epochs": sum(not x[1] for x in trace["roulette"]),
        "contextual_improving_epochs": sum(not x[1] for x in trace["contextual"]),
        "epochs": len(trace["roulette"]),
        "roulette_max_destroy_share": st.mean(x[2] for x in trace["roulette"]),
        "contextual_max_destroy_share": st.mean(x[2] for x in trace["contextual"]),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def epoch0_report(rows: list[dict]) -> str:
    n = len(rows)
    lines = [
        "## Epoch 0: static 2000-iteration solve, roulette vs contextual",
        "",
        f"{n} instance x seed pairs (9 instances x {{95, 88, 75}} static customers x seeds 0-2), same seed for both selectors.",
        "",
        "| selector | mean K | mean F | mean D | mean R |",
        "|---|---:|---:|---:|---:|",
    ]

    for label in ("roulette", "contextual"):
        lines.append(
            f"| {label} | {st.mean(r[f'{label}_K'] for r in rows):.2f} | {st.mean(r[f'{label}_F'] for r in rows):.4f} "
            f"| {st.mean(r[f'{label}_D'] for r in rows):.1f} | {st.mean(r[f'{label}_R'] for r in rows):.4f} |"
        )

    lex_c = sum(
        (r["contextual_K"], round(r["contextual_F"], 9))
        < (r["roulette_K"], round(r["roulette_F"], 9))
        for r in rows
    )
    lex_r = sum(
        (r["contextual_K"], round(r["contextual_F"], 9))
        > (r["roulette_K"], round(r["roulette_F"], 9))
        for r in rows
    )
    f_c = sum(r["contextual_F"] < r["roulette_F"] - 1e-9 for r in rows)
    f_r = sum(r["contextual_F"] > r["roulette_F"] + 1e-9 for r in rows)
    lines += [
        "",
        f"Lexicographic (K, F): contextual better {lex_c}, roulette better {lex_r}, tie {n - lex_c - lex_r}.  ",
        f"F only: contextual better {f_c}, roulette better {f_r}, tie {n - f_c - f_r}.  ",
        f"K: contextual fewer {sum(r['contextual_K'] < r['roulette_K'] for r in rows)}, more {sum(r['contextual_K'] > r['roulette_K'] for r in rows)}, equal {sum(r['contextual_K'] == r['roulette_K'] for r in rows)}.",
        "",
        "| class | n | F roulette | F contextual | K roulette | K contextual | R roulette | R contextual |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for cls in ("C", "R", "RC"):
        g = [r for r in rows if r["class"] == cls]
        lines.append(
            f"| {cls} | {len(g)} | {st.mean(r['roulette_F'] for r in g):.4f} | {st.mean(r['contextual_F'] for r in g):.4f} "
            f"| {st.mean(r['roulette_K'] for r in g):.2f} | {st.mean(r['contextual_K'] for r in g):.2f} "
            f"| {st.mean(r['roulette_R'] for r in g):.3f} | {st.mean(r['contextual_R'] for r in g):.3f} |"
        )

    return "\n".join(lines) + "\n"


def traces_report(rows: list[dict]) -> str:
    lines = [
        "## Re-planning epochs only: identical roulette epoch 0, selectors swapped afterwards",
        "",
        f"{len(rows)} scenarios (95+5, seeds 0-1), {EPOCH_ITERATIONS} iterations per epoch. "
        "Max destroy share is the largest share any destroy operator received, averaged over epochs; uniform is 20%.",
        "",
        "| scenario | F roulette | F contextual | improving epochs r/c | epochs | max destroy share r/c |",
        "|---|---:|---:|---|---:|---|",
    ]

    for r in rows:
        lines.append(
            f"| {r['scenario']} | {r['roulette_F']:.4f} | {r['contextual_F']:.4f} | {r['roulette_improving_epochs']}/{r['contextual_improving_epochs']} "
            f"| {r['epochs']} | {100 * r['roulette_max_destroy_share']:.0f}%/{100 * r['contextual_max_destroy_share']:.0f}% |"
        )

    deltas = [r["contextual_F"] - r["roulette_F"] for r in rows]
    lines += [
        "",
        f"Mean F(contextual) - F(roulette) = {st.mean(deltas):+.4f}; contextual better in {sum(d < 0 for d in deltas)}/{len(rows)}.",
    ]

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("results/analysis"))
    parser.add_argument("--workers", type=int, default=14)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    epoch0_jobs = [
        (f"{i}-n{s}-d{d}-s0.json", seed)
        for i in INSTANCES
        for s, d in LEVELS
        for seed in (0, 1, 2)
    ]
    trace_jobs = [
        f"{i}-n95-d5-s{s}.json"
        for i in ("c101", "r101", "rc101", "c102", "r102", "rc102")
        for s in (0, 1)
    ]

    with mp.get_context("fork").Pool(args.workers) as pool:
        epoch0_rows = pool.map(epoch0_job, epoch0_jobs)
        trace_rows = pool.map(trace_job, trace_jobs)

    write_csv(args.output / "bandit_epoch0.csv", epoch0_rows)
    write_csv(args.output / "bandit_epoch_traces.csv", trace_rows)
    (args.output / "bandit_diagnosis.md").write_text(
        "# Contextual bandit diagnosis\n\n"
        + epoch0_report(epoch0_rows)
        + "\n"
        + traces_report(trace_rows),
        encoding="utf-8",
    )
    print((args.output / "bandit_diagnosis.md").read_text(encoding="utf-8"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
