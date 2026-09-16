#!/usr/bin/env python3
"""Generate one standalone HTML visualization per Solomon testcase."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path


DATASET_DIR = Path(__file__).resolve().parent.parent / "solomon"
RISK_DATASET_DIR = Path(__file__).resolve().parent.parent / "solomon_risk"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "solomon_visualize"
DATA_LINE = re.compile(
    r"^\s*(\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+"
    r"-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+"
    r"-?\d+(?:\.\d+)?\s*$"
)
RISK_LINE = re.compile(
    r"^\s*(\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+"
    r"(-?\d+(?:\.\d+)?)\s*$"
)


def read_case(path: Path) -> tuple[str, list[dict[str, int | float]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    name = lines[0].strip()
    points: list[dict[str, int | float]] = []

    for line in lines:
        match = DATA_LINE.match(line)
        if not match:
            continue
        customer_id, raw_x, raw_y = match.groups()
        x, y = float(raw_x), float(raw_y)
        points.append(
            {
                "id": int(customer_id),
                "x": int(x) if x.is_integer() else x,
                "y": int(y) if y.is_integer() else y,
            }
        )

    if not points or points[0]["id"] != 0:
        raise ValueError(f"No depot/customer data found in {path}")
    return name, points


def read_risks(path: Path) -> list[dict[str, int | float]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    risk_header_index = next(
        (index for index, line in enumerate(lines) if line.strip() == "RISK"), None
    )
    if risk_header_index is None:
        raise ValueError(f"No risk data found in {path}")

    risks: list[dict[str, int | float]] = []
    for line in lines[risk_header_index + 1 :]:
        match = RISK_LINE.match(line)
        if not match:
            continue
        risk_id, raw_x, raw_y, raw_radius = match.groups()
        x, y, radius = float(raw_x), float(raw_y), float(raw_radius)
        risks.append(
            {
                "id": int(risk_id),
                "x": int(x) if x.is_integer() else x,
                "y": int(y) if y.is_integer() else y,
                "radius": int(radius) if radius.is_integer() else radius,
            }
        )

    if not risks:
        raise ValueError(f"No risk rows found in {path}")
    return risks


def case_page(
    name: str,
    points: list[dict[str, int | float]],
    risks: list[dict[str, int | float]],
    previous_file: str,
    next_file: str,
) -> str:
    safe_name = html.escape(name)
    payload = json.dumps(
        {"name": name, "points": points, "risks": risks},
        separators=(",", ":"),
        ensure_ascii=False,
    ).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Biểu đồ tọa độ customer cho Solomon testcase {safe_name}">
  <title>{safe_name} · Solomon Visualizer</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="app-shell">
    <header class="topbar">
      <div>
        <a class="eyebrow" href="index.html">Solomon Visualizer</a>
        <h1>{safe_name}</h1>
        <p class="subtitle">Phân bố customer theo tọa độ X–Y</p>
      </div>
      <nav class="case-nav" aria-label="Chuyển testcase">
        <a href="{previous_file}" aria-label="Testcase trước">←</a>
        <a href="index.html" aria-label="Danh sách testcase">Tất cả</a>
        <a href="{next_file}" aria-label="Testcase sau">→</a>
      </nav>
    </header>

    <section class="visualizer" aria-labelledby="chart-title">
      <div class="toolbar">
        <div>
          <h2 id="chart-title">Bản đồ customer</h2>
          <p id="point-summary">25 customer + depot</p>
        </div>
        <div class="toolbar-controls">
          <div class="picker-group">
            <span class="picker-label">Customer</span>
            <div class="count-picker" role="group" aria-label="Số customer hiển thị">
              <button type="button" data-count="25" aria-pressed="true">25</button>
              <button type="button" data-count="100" aria-pressed="false">100</button>
            </div>
          </div>
          <div class="picker-group">
            <span class="picker-label">Risk</span>
            <div class="count-picker risk-picker" role="group" aria-label="Số risk hiển thị">
              <button type="button" data-risk-count="0" aria-pressed="true">0</button>
              <button type="button" data-risk-count="1" aria-pressed="false">1</button>
              <button type="button" data-risk-count="5" aria-pressed="false">5</button>
            </div>
          </div>
        </div>
      </div>

      <div class="chart-wrap">
        <svg id="customer-chart" role="img" aria-labelledby="chart-title chart-description"></svg>
        <p id="chart-description" class="sr-only">
          Biểu đồ tọa độ các customer và vùng risk. Depot được ký hiệu bằng hình thoi màu cam;
          tâm risk được ký hiệu bằng hình tam giác có số thứ tự.
        </p>
      </div>

      <div class="legend" aria-label="Chú giải">
        <span><i class="legend-dot customer-dot"></i>Customer</span>
        <span><i class="legend-dot depot-dot"></i>Depot (0)</span>
        <span><i class="legend-risk"></i>Risk và vùng ảnh hưởng</span>
        <span class="hint">Rê chuột vào một điểm để xem tọa độ</span>
      </div>
    </section>
  </main>

  <script>window.SOLOMON_CASE={payload};</script>
  <script src="viewer.js"></script>
</body>
</html>
"""


def index_page(cases: list[tuple[str, str]]) -> str:
    cards = "\n".join(
        f'        <a class="case-card" href="{filename}"><strong>{html.escape(name)}</strong><span>Mở biểu đồ →</span></a>'
        for name, filename in cases
    )
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Danh sách biểu đồ tọa độ Solomon VRPTW">
  <title>Solomon Visualizer</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="app-shell index-shell">
    <header class="index-header">
      <p class="eyebrow">Solomon VRPTW</p>
      <h1>Customer maps</h1>
      <p>Chọn một testcase để xem phân bố 25 hoặc 100 customer trên hệ trục X–Y.</p>
    </header>
    <section class="case-grid" aria-label="Danh sách testcase">
{cards}
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    source_files = sorted(DATASET_DIR.glob("*.txt"))
    parsed = [
        (path, *read_case(path), read_risks(RISK_DATASET_DIR / path.name))
        for path in source_files
    ]
    cases = [(name, f"{path.stem}.html") for path, name, _, _ in parsed]

    for index, (path, name, points, risks) in enumerate(parsed):
        previous_file = f"{parsed[index - 1][0].stem}.html"
        next_file = f"{parsed[(index + 1) % len(parsed)][0].stem}.html"
        (OUTPUT_DIR / f"{path.stem}.html").write_text(
            case_page(name, points, risks, previous_file, next_file), encoding="utf-8"
        )

    (OUTPUT_DIR / "index.html").write_text(index_page(cases), encoding="utf-8")
    print(f"Generated {len(parsed)} testcase pages in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
