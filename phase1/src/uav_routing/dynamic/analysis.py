"""Paired statistical analysis of dynamic benchmark results.

Rows come from the ``raw.csv`` written by ``uav_routing.dynamic.experiment``.
Policies are compared pairwise on the same (scenario, seed) with a lexicographic
win rule (unserved, vehicles, objective) and a two-sided Wilcoxon signed-rank
test on the objective, Holm-adjusted across the comparisons of one block.
"""

import argparse
import csv
import json
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from scipy.stats import wilcoxon

NUMERIC_FIELDS = (
    "objective",
    "distance",
    "risk_delay",
    "gap",
    "clairvoyant_objective",
    "runtime_seconds",
    "runtime_per_epoch_mean",
    "degree_of_dynamism",
    "epoch_length",
)
INTEGER_FIELDS = (
    "vehicles",
    "unserved",
    "seed",
    "epochs",
    "total_iterations",
    "static_customers",
    "dynamic_customers",
)
JSON_FIELDS = ("unserved_ids", "routes")


@dataclass(frozen=True)
class PolicySummary:
    policy: str
    runs: int
    objective_mean: float
    objective_std: float
    vehicles_mean: float
    unserved_mean: float
    served_all_share: float
    gap_all_served_mean: float
    runtime_mean: float


@dataclass(frozen=True)
class PairedComparison:
    reference: str
    other: str
    pairs: int
    wins: int
    losses: int
    ties: int
    mean_objective_diff: float
    median_objective_diff: float
    wilcoxon_p: float
    holm_p: float


def load_rows(path: Path) -> list[dict[str, object]]:
    path = Path(path)

    if path.is_dir():
        path = path / "raw.csv"

    with path.open(encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]

    return [_convert(row) for row in rows]


def relabel(rows: list[dict[str, object]], label: str) -> list[dict[str, object]]:
    return [{**row, "policy": label} for row in rows]


def summarize_policies(rows: list[dict[str, object]]) -> list[PolicySummary]:
    summaries: list[PolicySummary] = []

    for policy in _policies(rows):
        group = [row for row in rows if row["policy"] == policy]
        objectives = [float(row["objective"]) for row in group]
        served = [row for row in group if int(row["unserved"]) == 0]
        gaps = [float(row["gap"]) for row in served if math.isfinite(float(row["gap"]))]

        summaries.append(
            PolicySummary(
                policy=policy,
                runs=len(group),
                objective_mean=statistics.fmean(objectives),
                objective_std=statistics.stdev(objectives) if len(group) > 1 else 0.0,
                vehicles_mean=statistics.fmean(float(row["vehicles"]) for row in group),
                unserved_mean=statistics.fmean(float(row["unserved"]) for row in group),
                served_all_share=len(served) / len(group),
                gap_all_served_mean=statistics.fmean(gaps) if gaps else math.nan,
                runtime_mean=statistics.fmean(
                    float(row["runtime_seconds"]) for row in group
                ),
            )
        )

    return summaries


def paired_comparisons(
    rows: list[dict[str, object]], reference: str
) -> list[PairedComparison]:
    by_pair = _by_pair(rows)
    others = [policy for policy in _policies(rows) if policy != reference]
    partial: list[tuple[str, int, int, int, int, list[float]]] = []

    for other in others:
        pairs = [
            (cell[reference], cell[other])
            for cell in by_pair.values()
            if reference in cell and other in cell
        ]
        wins = sum(_rank(left) < _rank(right) for left, right in pairs)
        losses = sum(_rank(left) > _rank(right) for left, right in pairs)
        diffs = [
            float(right["objective"]) - float(left["objective"])
            for left, right in pairs
        ]

        partial.append(
            (other, len(pairs), wins, losses, len(pairs) - wins - losses, diffs)
        )

    raw_p = [_wilcoxon(diffs) for *_, diffs in partial]
    adjusted = holm_adjust(raw_p)

    return [
        PairedComparison(
            reference=reference,
            other=other,
            pairs=pairs,
            wins=wins,
            losses=losses,
            ties=ties,
            mean_objective_diff=statistics.fmean(diffs) if diffs else math.nan,
            median_objective_diff=statistics.median(diffs) if diffs else math.nan,
            wilcoxon_p=p_value,
            holm_p=holm,
        )
        for (other, pairs, wins, losses, ties, diffs), p_value, holm in zip(
            partial, raw_p, adjusted, strict=True
        )
    ]


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    valid = [(p, index) for index, p in enumerate(p_values) if not math.isnan(p)]
    adjusted = [math.nan] * len(p_values)
    count = len(valid)
    running = 0.0

    for rank, (p, index) in enumerate(sorted(valid)):
        running = max(running, (count - rank) * p)
        adjusted[index] = min(1.0, running)

    return adjusted


def markdown_report(rows: list[dict[str, object]], reference: str, title: str) -> str:
    lines = [f"## {title}", ""]
    lines.append(
        "| policy | runs | F mean | F std | UAVs | unserved | served-all % "
        "| gap % (all-served) | runtime s |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for summary in summarize_policies(rows):
        lines.append(
            f"| {summary.policy} | {summary.runs} | {summary.objective_mean:.4f} "
            f"| {summary.objective_std:.4f} | {summary.vehicles_mean:.2f} "
            f"| {summary.unserved_mean:.2f} | {100 * summary.served_all_share:.1f} "
            f"| {_percent(summary.gap_all_served_mean)} | {summary.runtime_mean:.1f} |"
        )

    lines.append("")
    lines.append(
        f"Paired comparison of `{reference}` against each other policy on the same "
        "scenario and seed. Wins use the lexicographic order (unserved, UAVs, F); "
        "ΔF is other minus reference, so positive favours the reference. "
        "Wilcoxon is the two-sided signed-rank test on F; Holm adjusts across "
        "the comparisons in this block."
    )
    lines.append("")
    lines.append(
        "| reference vs | pairs | wins | losses | ties | mean ΔF | median ΔF "
        "| Wilcoxon p | Holm p |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for comparison in paired_comparisons(rows, reference):
        lines.append(
            f"| {comparison.other} | {comparison.pairs} | {comparison.wins} "
            f"| {comparison.losses} | {comparison.ties} "
            f"| {comparison.mean_objective_diff:+.4f} "
            f"| {comparison.median_objective_diff:+.4f} "
            f"| {_p_text(comparison.wilcoxon_p)} | {_p_text(comparison.holm_p)} |"
        )

    lines.append("")

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if bool(args.results) == bool(args.grid):
        parser.error("use exactly one of --results or --grid")

    try:
        sections = _results_sections(args) if args.results else _grid_section(args)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))

    text = "\n".join(sections)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uav-routing-dynamic-analysis")

    parser.add_argument("--results", type=Path, nargs="+")
    parser.add_argument("--grid", nargs="+", metavar="LABEL=DIR")
    parser.add_argument("--reference", default="warm_alns")
    parser.add_argument("--policy", default="warm_alns")
    parser.add_argument("--title")
    parser.add_argument("--output", type=Path)

    return parser


def _results_sections(args: argparse.Namespace) -> list[str]:
    return [
        markdown_report(load_rows(folder), args.reference, folder.name)
        for folder in args.results
    ]


def _grid_section(args: argparse.Namespace) -> list[str]:
    rows: list[dict[str, object]] = []

    for item in args.grid:
        label, _, folder = item.partition("=")

        if not label or not folder:
            raise ValueError(f"grid entries must look like LABEL=DIR, got {item!r}")

        loaded = [
            row for row in load_rows(Path(folder)) if row["policy"] == args.policy
        ]
        rows.extend(relabel(loaded, label))

    return [markdown_report(rows, args.reference, args.title or "Grid")]


def _convert(row: dict[str, object]) -> dict[str, object]:
    for field in NUMERIC_FIELDS:
        if field in row and row[field] not in ("", None):
            row[field] = float(row[field])

    for field in INTEGER_FIELDS:
        if field in row and row[field] not in ("", None):
            row[field] = int(float(row[field]))

    for field in JSON_FIELDS:
        if isinstance(row.get(field), str):
            row[field] = json.loads(row[field])

    if isinstance(row.get("feasible"), str):
        row["feasible"] = row["feasible"].strip().lower() == "true"

    return row


def _policies(rows: list[dict[str, object]]) -> list[str]:
    return list(dict.fromkeys(str(row["policy"]) for row in rows))


def _by_pair(rows: list[dict[str, object]]) -> dict[tuple[object, object], dict]:
    cells: dict[tuple[object, object], dict[str, dict[str, object]]] = {}

    for row in rows:
        cells.setdefault((row["scenario"], row["seed"]), {})[str(row["policy"])] = row

    return cells


def _rank(row: dict[str, object]) -> tuple[int, int, float]:
    return (
        int(row["unserved"]),
        int(row["vehicles"]),
        round(float(row["objective"]), 9),
    )


def _wilcoxon(diffs: list[float]) -> float:
    if len(diffs) < 2 or all(diff == 0.0 for diff in diffs):
        return math.nan

    try:
        return float(wilcoxon(diffs, alternative="two-sided").pvalue)
    except ValueError:
        return math.nan


def _percent(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{100 * value:.2f}"


def _p_text(value: float) -> str:
    if math.isnan(value):
        return "n/a"

    return f"{value:.2e}" if value < 1e-3 else f"{value:.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
