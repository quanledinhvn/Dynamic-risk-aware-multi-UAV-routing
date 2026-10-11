"""Build results.csv and SENSITIVITY_RESULTS.md from finished sensitivity jobs.

Usage (from the repository root):
    phase1/.venv/Scripts/python sensitivity_test/code/analyze.py [--out DIR]

Comparison rule: a solution is better when it is lexicographically smaller on
(unserved, vehicles, objective) for dynamic cases and (vehicles, objective) for
the static case. Every level is compared with the case baseline on the same
(instance, seed) pair.
"""

import argparse
import csv
import json
import math
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import plan  # noqa: E402

ALPHA = 0.05
MIN_RPD = 1.0
MIN_VEHICLES = 0.1
MIN_UNSERVED = 0.1
MIN_RUNTIME = 20.0
DESCRIPTIVE = {"beta"}

CSV_FIELDS = (
    "case",
    "point",
    "param",
    "level",
    "priority",
    "instance",
    "seed",
    "alpha",
    "beta",
    "feasible",
    "vehicles",
    "distance",
    "risk_delay",
    "objective",
    "unserved",
    "unserved_priority",
    "epochs",
    "iterations",
    "runtime_seconds",
    "git_commit",
    "finished_at",
)


def load_rows(root: Path) -> list[dict]:
    rows = []

    for path in sorted((root / "jobs").rglob("*.json")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue

    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    temporary = path.with_suffix(".csv.tmp")

    with open(temporary, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    _replace(temporary, path)


def _replace(source: Path, target: Path) -> None:
    from runner import replace_with_retry

    replace_with_retry(source, target)


def _key(row: dict, dynamic: bool) -> tuple:
    if dynamic:
        return (row.get("unserved", 0), row["vehicles"], row["objective"])

    return (row["vehicles"], row["objective"])


def _ranks(keys: list[tuple]) -> list[float]:
    order = sorted(range(len(keys)), key=lambda index: keys[index])
    ranks = [0.0] * len(keys)
    position = 0

    while position < len(order):
        end = position

        while end + 1 < len(order) and keys[order[end + 1]] == keys[order[position]]:
            end += 1

        average = (position + end) / 2 + 1

        for index in order[position : end + 1]:
            ranks[index] = average

        position = end + 1

    return ranks


def _holm(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)

    for index, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (count - index) * value))
        adjusted[name] = running

    return adjusted


def _overall_p(blocks: list[list[float]], wins: int, losses: int) -> float | None:
    from scipy import stats

    if not blocks:
        return None

    if len(blocks[0]) == 2:
        if wins + losses == 0:
            return 1.0

        return float(stats.binomtest(wins, wins + losses, 0.5).pvalue)

    columns = list(zip(*blocks))

    if all(len(set(block)) == 1 for block in blocks):
        return 1.0

    return float(stats.friedmanchisquare(*columns).pvalue)


def _fmt(value, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"

    return f"{value:.{digits}f}"


def _p_text(value: float | None) -> str:
    if value is None:
        return "—"

    return "<0.001" if value < 0.001 else f"{value:.3f}"


def analyze_case(case: str, rows: list[dict]) -> tuple[list[dict], list[str]]:
    dynamic = plan.CASES[case]["kind"] == "dynamic"
    points = [point for point in plan.all_points() if point.case == case]
    base_id = next(point.point_id for point in points if point.priority == "base")

    by_point: dict[str, dict] = defaultdict(dict)

    for row in rows:
        if row["case"] == case:
            by_point[row["point"]][(row["instance"], row["seed"])] = row

    base = by_point.get(base_id, {})
    params: dict[str, list] = defaultdict(list)

    for point in points:
        if point.priority != "base":
            params[point.param].append(point)

    summaries = []
    lines = []

    for param, param_points in params.items():
        summary, table = _analyze_param(param, param_points, base, by_point, dynamic)
        summaries.append(summary)
        lines.extend(table)

    p_values = {s["param"]: s["p"] for s in summaries if s["p"] is not None and s["param"] not in DESCRIPTIVE}
    adjusted = _holm(p_values)

    full_pairs = len(plan.INSTANCES) * len(plan.SEEDS)

    for summary in summaries:
        summary["p_holm"] = adjusted.get(summary["param"])
        summary["verdict"] = _verdict(summary, dynamic)

        if summary["complete"] and summary["pairs"] < full_pairs:
            summary["verdict"] += f" *(tạm thời, {summary['pairs']}/{full_pairs} cặp)*"

    return summaries, lines


def _analyze_param(param, param_points, base, by_point, dynamic) -> tuple[dict, list[str]]:
    level_rows = [("mặc định", base)] + [
        (point.level, by_point.get(point.point_id, {})) for point in param_points
    ]
    pairs = set(base)

    for _, results in level_rows[1:]:
        pairs &= set(results)

    lines = [
        f"#### `{param}`",
        "",
        _table_header(dynamic),
        _table_rule(dynamic),
    ]

    effects = []
    total_wins = total_losses = 0

    for level, results in level_rows:
        line, effect = _level_line(level, results, base, dynamic)
        lines.append(line)

        if effect is not None:
            effects.append(effect)
            total_wins += effect["wins"]
            total_losses += effect["losses"]

    complete = sorted(pairs)
    blocks = [
        _ranks([_key(results[pair], dynamic) for _, results in level_rows])
        for pair in complete
    ]
    p_value = _overall_p(blocks, total_wins, total_losses) if len(complete) >= 3 else None

    lines += ["", f"Số cặp (instance, seed) đủ mọi mức: {len(complete)}.", ""]

    return {
        "param": param,
        "levels": len(level_rows),
        "pairs": len(complete),
        "p": p_value,
        "effects": effects,
        "complete": all(len(results) == len(base) and results for _, results in level_rows)
        and bool(base),
    }, lines


def _table_header(dynamic: bool) -> str:
    extra = "| unserved | ΔUnserved " if dynamic else ""

    return (
        "| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) "
        + extra
        + "| Thắng/Thua | Runtime (s) | ΔRuntime (%) |"
    )


def _table_rule(dynamic: bool) -> str:
    count = 12 + (2 if dynamic else 0)

    return "|" + "---|" * count


def _level_line(level, results, base, dynamic) -> tuple[str, dict | None]:
    if not results:
        cells = ["—"] * (11 + (2 if dynamic else 0))

        return f"| {level} | " + " | ".join(cells) + " |", None

    values = list(results.values())
    mean = lambda field: st.fmean(float(row.get(field, 0) or 0) for row in values)  # noqa: E731

    shared = [pair for pair in results if pair in base]
    is_base = results is base
    effect = None

    delta_k = delta_obj = delta_unserved = delta_runtime = None
    wins = losses = 0

    if shared and not is_base:
        delta_k = st.fmean(results[p]["vehicles"] - base[p]["vehicles"] for p in shared)
        delta_obj = st.median(
            100 * (results[p]["objective"] - base[p]["objective"]) / base[p]["objective"]
            for p in shared
        )
        delta_runtime = 100 * (
            st.fmean(results[p]["runtime_seconds"] for p in shared)
            / st.fmean(base[p]["runtime_seconds"] for p in shared)
            - 1
        )

        if dynamic:
            delta_unserved = st.fmean(
                results[p].get("unserved", 0) - base[p].get("unserved", 0) for p in shared
            )

        for pair in shared:
            candidate, reference = _key(results[pair], dynamic), _key(base[pair], dynamic)
            wins += candidate < reference
            losses += candidate > reference

        effect = {
            "level": level,
            "delta_k": delta_k,
            "delta_obj": delta_obj,
            "delta_unserved": delta_unserved,
            "delta_runtime": delta_runtime,
            "wins": wins,
            "losses": losses,
        }

    cells = [
        str(len(values)),
        _fmt(mean("vehicles"), 2),
        _fmt(delta_k, 2),
        _fmt(mean("distance"), 1),
        _fmt(mean("risk_delay"), 3),
        _fmt(mean("objective"), 4),
        _fmt(delta_obj, 2),
    ]

    if dynamic:
        cells += [_fmt(mean("unserved"), 2), _fmt(delta_unserved, 2)]

    cells += [
        "—" if is_base else f"{wins}/{losses}",
        _fmt(mean("runtime_seconds"), 1),
        _fmt(delta_runtime, 0),
    ]

    label = f"**{level}**" if is_base else level

    return f"| {label} | " + " | ".join(cells) + " |", effect


def _verdict(summary: dict, dynamic: bool) -> str:
    if not summary["complete"]:
        return "chưa đủ dữ liệu"

    if summary["param"] in DESCRIPTIVE:
        return "mô tả (β đổi định nghĩa objective)"

    effects = summary["effects"]
    practical = any(
        abs(e["delta_obj"] or 0) >= MIN_RPD
        or abs(e["delta_k"] or 0) >= MIN_VEHICLES
        or (dynamic and abs(e["delta_unserved"] or 0) >= MIN_UNSERVED)
        for e in effects
    )
    runtime = any(abs(e["delta_runtime"] or 0) >= MIN_RUNTIME for e in effects)
    significant = summary["p_holm"] is not None and summary["p_holm"] < ALPHA

    if significant and practical:
        return "**NHẠY**"

    if significant:
        return "có ý nghĩa thống kê, hiệu ứng nhỏ"

    if runtime:
        return "không nhạy về chất lượng; nhạy về runtime"

    return "không nhạy"


def _best_level(summary: dict, dynamic: bool) -> str:
    candidates = [("mặc định", 0, 0)] + [
        (e["level"], e["wins"] - e["losses"], e["delta_obj"] or 0) for e in summary["effects"]
    ]
    best = max(candidates, key=lambda item: (item[1], -item[2]))

    return best[0]


def progress_lines(rows: list[dict], root: Path) -> list[str]:
    state = _read_state(root)
    wanted = set(state.get("job_ids", []))
    jobs = [job for job in plan.all_jobs() if not wanted or job.job_id in wanted]
    done = {(row["point"], row["instance"], row["seed"]) for row in rows}

    lines = [
        "| Case | Job xong | % | CPU đã chạy |",
        "|---|---|---|---|",
    ]

    for case, info in plan.CASES.items():
        case_jobs = [job for job in jobs if job.point.case == case]
        finished = [
            job for job in case_jobs if (job.point.point_id, job.instance, job.seed) in done
        ]
        cpu = sum(row["runtime_seconds"] for row in rows if row["case"] == case) / 3600

        if case_jobs:
            percent = 100 * len(finished) / len(case_jobs)
            lines.append(f"| {info['label']} | {len(finished)}/{len(case_jobs)} | {percent:.1f}% | {cpu:.1f} h |")

    total = len(jobs)
    finished_total = sum((job.point.point_id, job.instance, job.seed) in done for job in jobs)
    percent_total = 100 * finished_total / total if total else 100
    lines.append(f"| **Tổng** | **{finished_total}/{total}** | **{percent_total:.1f}%** | |")

    return lines


def _read_state(root: Path) -> dict:
    try:
        return json.loads((root / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_report(rows: list[dict], root: Path) -> str:
    commits = sorted({row.get("git_commit", "")[:7] for row in rows if row.get("git_commit")})
    infeasible = sum(not row.get("feasible", True) for row in rows)

    out = [
        "# Kết quả sensitivity test",
        "",
        f"Sinh tự động bởi `analyze.py` lúc {datetime.now():%Y-%m-%d %H:%M} · commit {', '.join(commits) or '—'} · "
        f"{len(rows)} job · {infeasible} nghiệm không khả thi.",
        "",
        "Kế hoạch: mục 2.2 của [../CLAUDE.md](../CLAUDE.md). Theo dõi tiến độ trực tiếp: "
        "`phase1/.venv/Scripts/python sensitivity_test/code/runner.py status`.",
        "",
        "## 1. Tiến độ",
        "",
        *progress_lines(rows, root),
        "",
        "## 2. Kết luận theo tham số",
        "",
        "| Case | Tham số | Số mức | Cặp đủ | Mức tốt nhất (thắng − thua) | p (Holm) | Kết luận |",
        "|---|---|---|---|---|---|---|",
    ]
    details: list[str] = []

    for case, info in plan.CASES.items():
        summaries, lines = analyze_case(case, rows)
        dynamic = info["kind"] == "dynamic"

        for summary in summaries:
            out.append(
                f"| {case} | `{summary['param']}` | {summary['levels']} | {summary['pairs']} | "
                f"{_best_level(summary, dynamic)} | {_p_text(summary['p_holm'])} | {summary['verdict']} |"
            )

        details += [f"### Case {info['label']}", ""] + lines

    out += [
        "",
        "Quy tắc kết luận:",
        "",
        "- **NHẠY:** kiểm định tổng thể (Friedman trên thứ hạng từ điển; sign test khi chỉ có 2 mức) có "
        f"$p < {ALPHA}$ sau hiệu chỉnh Holm trong cùng case, **và** có ít nhất một mức đạt hiệu ứng thực tế: "
        f"$|\\text{{median}}\\,\\Delta\\text{{Obj}}| \\ge {MIN_RPD:g}\\%$, hoặc $|\\overline{{\\Delta K}}| \\ge {MIN_VEHICLES:g}$, "
        f"hoặc (case động) số khách unserved đổi $\\ge {MIN_UNSERVED:g}$.",
        "- **Có ý nghĩa thống kê, hiệu ứng nhỏ:** $p$ đạt ngưỡng nhưng hiệu ứng dưới các ngưỡng trên.",
        f"- **Không nhạy về chất lượng; nhạy về runtime:** chỉ runtime đổi $\\ge {MIN_RUNTIME:g}\\%$.",
        "- **Mô tả:** $\\beta$ đổi chính định nghĩa của objective nên chỉ đọc bảng đánh đổi, không xếp hạng.",
        "- Thứ tự so sánh: case động (A, C) dùng (unserved, số UAV, objective); case tĩnh (B) dùng (số UAV, objective).",
        "- Với 5 seed × 9 instance = 45 cặp, đây là kết quả **sàng lọc**.",
        "",
        "## 3. Chi tiết theo case",
        "",
        "ΔUAV, ΔObj, ΔUnserved, ΔRuntime: so với mức mặc định trên cùng (instance, seed). Số âm là tốt hơn "
        "(trừ runtime). Thắng/Thua: số cặp mà mức đó tốt hơn / kém hơn mặc định.",
        "",
        *details,
    ]

    return "\n".join(out) + "\n"


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE.parent / "results")
    args = parser.parse_args(argv)

    rows = load_rows(args.out)
    write_csv(rows, args.out / "results.csv")

    report = args.out / "SENSITIVITY_RESULTS.md"
    temporary = report.with_suffix(".md.tmp")
    temporary.write_text(build_report(rows, args.out), encoding="utf-8")
    _replace(temporary, report)


if __name__ == "__main__":
    main()
