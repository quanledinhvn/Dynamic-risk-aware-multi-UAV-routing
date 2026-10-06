"""Summarize paired equal-time ejection experiments without pooling objectives."""

import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def score(row):
    return int(row["vehicles"]), float(row["objective"])


def compare(rows, candidate, baseline):
    base = {
        (row["instance"], row["seed"]): row for row in rows if row["policy"] == baseline
    }
    pairs = [
        (row, base[(row["instance"], row["seed"])])
        for row in rows
        if row["policy"] == candidate and (row["instance"], row["seed"]) in base
    ]
    wins = sum(score(a) < score(b) for a, b in pairs)
    losses = sum(score(a) > score(b) for a, b in pairs)
    decisive = wins + losses

    p_value = (
        min(
            1.0,
            2
            * sum(math.comb(decisive, k) for k in range(min(wins, losses) + 1))
            / 2**decisive,
        )
        if decisive
        else 1.0
    )
    equal_k = [
        float(a["objective"]) - float(b["objective"])
        for a, b in pairs
        if int(a["vehicles"]) == int(b["vehicles"])
    ]

    return dict(
        candidate=candidate,
        baseline=baseline,
        pairs=len(pairs),
        wins=wins,
        losses=losses,
        ties=len(pairs) - decisive,
        sign_test_p=p_value,
        mean_delta_k=statistics.mean(
            int(a["vehicles"]) - int(b["vehicles"]) for a, b in pairs
        ),
        equal_k_pairs=len(equal_k),
        equal_k_mean_delta_f=statistics.mean(equal_k) if equal_k else None,
    )


def summarize(rows):
    policies = sorted({row["policy"] for row in rows})
    groups = []

    for instance in sorted({row["instance"] for row in rows}) + ["ALL"]:
        for policy in policies:
            selected = [
                row
                for row in rows
                if row["policy"] == policy
                and (instance == "ALL" or row["instance"] == instance)
            ]

            if not selected:
                continue

            groups.append(
                dict(
                    instance=instance,
                    policy=policy,
                    runs=len(selected),
                    mean_k=statistics.mean(int(row["vehicles"]) for row in selected),
                    mean_runtime=statistics.mean(
                        float(row["runtime"]) for row in selected
                    ),
                    max_runtime=max(float(row["runtime"]) for row in selected),
                    mean_iterations=statistics.mean(
                        int(row["iterations"]) for row in selected
                    ),
                    unchanged_rate=sum(int(row["unchanged"]) for row in selected)
                    / max(1, sum(int(row["iterations"]) for row in selected)),
                    attempts=sum(int(row["attempts"]) for row in selected),
                    repair_success=sum(int(row["repair_success"]) for row in selected),
                    chain_success=sum(int(row["chain_success"]) for row in selected),
                    all_feasible=all(row["feasible"] == "True" for row in selected),
                )
            )

    comparisons = [
        compare(rows, candidate, baseline)
        for candidate, baseline in (
            ("beam", "guided"),
            ("ejection", "guided"),
            ("risk_ejection", "guided"),
            ("ejection", "beam"),
            ("risk_ejection", "ejection"),
        )
        if candidate in policies and baseline in policies
    ]

    return dict(groups=groups, comparisons=comparisons)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    with args.input.open(newline="", encoding="utf-8") as handle:
        result = summarize(list(csv.DictReader(handle)))

    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["comparisons"], indent=2))


if __name__ == "__main__":
    main()
