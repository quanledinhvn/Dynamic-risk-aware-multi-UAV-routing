import csv
import math

import pytest

from uav_routing.dynamic.analysis import (
    holm_adjust,
    load_rows,
    main,
    markdown_report,
    paired_comparisons,
    relabel,
    summarize_policies,
)
from uav_routing.dynamic.experiment import RAW_FIELDS


def _row(policy, scenario, seed, objective, vehicles=3, unserved=0, gap=0.1):
    row = dict.fromkeys(RAW_FIELDS, 0)
    row.update(
        scenario=scenario,
        instance="c101.txt",
        policy=policy,
        seed=seed,
        objective=objective,
        vehicles=vehicles,
        unserved=unserved,
        unserved_ids=[],
        gap=gap,
        clairvoyant_objective=0.5,
        runtime_seconds=1.0,
        runtime_per_epoch_mean=0.1,
        distance=100.0,
        risk_delay=0.1,
        degree_of_dynamism=0.2,
        epoch_length=60.0,
        epochs=5,
        total_iterations=100,
        static_customers=25,
        dynamic_customers=5,
        trigger="periodic",
        budget=100,
        feasible=True,
        routes=[[1, 2]],
    )

    return row


def _rows():
    rows = []

    for seed in range(8):
        scenario = f"s{seed % 2}"
        rows.append(_row("warm", scenario, seed, 0.50 + 0.001 * seed))
        rows.append(_row("greedy", scenario, seed, 0.60 + 0.001 * seed, vehicles=4))
        rows.append(
            _row(
                "cold",
                scenario,
                seed,
                0.50 + 0.001 * seed,
                unserved=1 if seed == 0 else 0,
                gap=0.3,
            )
        )

    return rows


def test_summarize_policies_reports_means_and_served_share():
    summaries = {s.policy: s for s in summarize_policies(_rows())}

    assert set(summaries) == {"warm", "greedy", "cold"}
    assert summaries["warm"].runs == 8
    assert summaries["warm"].objective_mean == pytest.approx(0.5035)
    assert summaries["greedy"].vehicles_mean == pytest.approx(4.0)
    assert summaries["cold"].unserved_mean == pytest.approx(1 / 8)
    assert summaries["cold"].served_all_share == pytest.approx(7 / 8)
    assert summaries["cold"].gap_all_served_mean == pytest.approx(0.3)
    assert summaries["warm"].runtime_mean == pytest.approx(1.0)


def test_paired_comparisons_count_lexicographic_wins():
    comparisons = {c.other: c for c in paired_comparisons(_rows(), "warm")}

    assert set(comparisons) == {"greedy", "cold"}
    greedy = comparisons["greedy"]

    assert greedy.pairs == 8
    assert (greedy.wins, greedy.losses, greedy.ties) == (8, 0, 0)
    assert greedy.mean_objective_diff == pytest.approx(0.1)
    assert greedy.median_objective_diff == pytest.approx(0.1)
    assert greedy.wilcoxon_p < 0.05

    cold = comparisons["cold"]

    # identical objectives, but one pair where cold leaves a customer unserved
    assert (cold.wins, cold.losses, cold.ties) == (1, 0, 7)
    assert cold.mean_objective_diff == pytest.approx(0.0)
    assert math.isnan(cold.wilcoxon_p)


def test_holm_adjustment_is_monotone_and_bounded():
    adjusted = holm_adjust([0.01, 0.04, 0.03])

    assert adjusted == pytest.approx([0.03, 0.06, 0.06])
    assert holm_adjust([float("nan"), 0.02]) == pytest.approx(
        [float("nan"), 0.02], nan_ok=True
    )
    assert holm_adjust([]) == []


def test_paired_comparisons_apply_holm_across_others():
    comparisons = {c.other: c for c in paired_comparisons(_rows(), "warm")}

    assert comparisons["greedy"].holm_p >= comparisons["greedy"].wilcoxon_p
    assert comparisons["greedy"].holm_p <= 1.0


def test_relabel_replaces_policy_without_mutating_input():
    rows = _rows()
    relabelled = relabel(rows, "cfg")

    assert {row["policy"] for row in relabelled} == {"cfg"}
    assert {row["policy"] for row in rows} == {"warm", "greedy", "cold"}
    assert len(relabelled) == len(rows)


def test_markdown_report_lists_policies_and_comparisons():
    report = markdown_report(_rows(), "warm", "Test block")

    assert report.startswith("## Test block")
    assert "| warm |" in report
    assert "| greedy |" in report
    assert "Wilcoxon" in report


def test_load_rows_converts_numeric_fields(tmp_path):
    path = tmp_path / "raw.csv"

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_FIELDS, extrasaction="ignore")
        writer.writeheader()

        for row in _rows():
            writer.writerow({**row, "unserved_ids": "[]", "routes": "[[1,2]]"})

    rows = load_rows(path)

    assert len(rows) == 24
    assert isinstance(rows[0]["objective"], float)
    assert isinstance(rows[0]["vehicles"], int)
    assert isinstance(rows[0]["seed"], int)
    assert rows[0]["policy"] == "warm"


def test_main_writes_markdown_for_result_dirs_and_grids(tmp_path):
    for name in ("alpha", "beta"):
        folder = tmp_path / name
        folder.mkdir()

        with (folder / "raw.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=RAW_FIELDS, extrasaction="ignore"
            )
            writer.writeheader()

            for row in _rows():
                writer.writerow({**row, "unserved_ids": "[]", "routes": "[]"})

    output = tmp_path / "report.md"
    code = main(
        [
            "--results",
            str(tmp_path / "alpha"),
            str(tmp_path / "beta"),
            "--reference",
            "warm",
            "--output",
            str(output),
        ]
    )

    assert code == 0
    text = output.read_text(encoding="utf-8")

    assert "## alpha" in text and "## beta" in text

    grid_output = tmp_path / "grid.md"
    code = main(
        [
            "--grid",
            f"base={tmp_path / 'alpha'}",
            f"other={tmp_path / 'beta'}",
            "--reference",
            "base",
            "--policy",
            "warm",
            "--output",
            str(grid_output),
        ]
    )

    assert code == 0
    assert "| base |" in grid_output.read_text(encoding="utf-8")
    assert "| other |" in grid_output.read_text(encoding="utf-8")
