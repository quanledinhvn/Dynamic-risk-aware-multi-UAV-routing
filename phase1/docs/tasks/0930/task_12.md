# Task 12: Add the dynamic benchmark runner, configs, scenarios and README

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 7 và 14

**Milestone:** M4 — Experiments

**Depends on:** Task 10

**Unlocks:** Không có

---

**Files:**
- Create: `phase1/src/uav_routing/dynamic/experiment.py`
- Create: `phase1/configs/dynamic/smoke.json`
- Create: `phase1/configs/dynamic/benchmark_n25_d5.json`, `benchmark_n25_d12.json`, `benchmark_n25_d25.json`
- Create: `dataset/solomon_dynamic/*.json` (sinh bằng script Task 06 cho chín instance × ba $n_{\mathrm{dyn}}$ × 10 seed)
- Create: `phase1/tests/dynamic/test_experiment.py`
- Modify: `phase1/README.md`

**Interfaces:**
- Produces: `DynamicBenchmarkConfig(scenario_paths, seeds, policies, alns, rolling, workers)`, `run_dynamic_benchmark(config) -> list[dict]`, `write_dynamic_results(rows, output_dir)`; `python -m uav_routing.dynamic.experiment --config ... --workers N --output-dir ...`.

- [ ] **Step 1: Write behavioural tests**

```python
def test_raw_rows_have_one_row_per_scenario_seed_policy(): ...
def test_clairvoyant_is_run_once_per_scenario_seed_and_gap_is_filled(): ...
def test_aggregate_groups_by_scenario_policy_and_reports_mean_std_best_worst(): ...
def test_parallel_and_sequential_produce_same_rows(tmp_path): ...
def test_infeasible_realized_solution_aborts_benchmark(): ...
def test_csv_schema_matches_fields(tmp_path): ...
```

- [ ] **Step 2: Scaffold, verify RED**

Run: `cd phase1 && uv run pytest tests/dynamic/test_experiment.py -v`

- [ ] **Step 3: Implement**

- `RAW_FIELDS`: `scenario, instance, static_customers, dynamic_customers, degree_of_dynamism, policy, trigger, epoch_length, seed, epochs, total_iterations, vehicles, distance, risk_delay, objective, unserved, unserved_priority, clairvoyant_objective, gap, runtime_seconds, runtime_per_epoch_mean, feasible, routes`.
- `AGGREGATE_FIELDS`: nhóm theo `scenario, policy, trigger, epoch_length`, thống kê mean/std/best/worst cho `vehicles, distance, risk_delay, objective, unserved, gap, runtime_seconds`.
- Tái dùng cơ chế song song, checkpoint JSON nguyên tử và CSV nguyên tử của `uav_routing.experiment`; tách các hàm dùng chung nếu cần nhưng không đổi hành vi benchmark tĩnh.
- `clairvoyant` chạy một lần cho mỗi cặp kịch bản/seed và được ghép vào mọi chính sách của cặp đó.
- Cấu hình JSON: `scenarios` (glob hoặc danh sách), `seeds`, `policies`, `alns`, `rolling`.

- [ ] **Step 4: Generate scenarios, run smoke, update README**

```bash
cd phase1
uv run python ../dataset/scripts/generate_solomon_dynamic.py \
  --instances c101 c102 c103 r101 r102 r103 rc101 rc102 rc103 \
  --static 25 --dynamic 5 12 25 --seeds 0 1 2 3 4 5 6 7 8 9 \
  --output ../dataset/solomon_dynamic
uv run python -m uav_routing.dynamic.experiment --config configs/dynamic/smoke.json --workers 2 --output-dir results/dynamic-smoke
```

README bổ sung mục “Giai đoạn 2 — Rolling horizon”: mô hình động, quy tắc khóa, định dạng kịch bản, bốn chính sách, lệnh `simulate` và benchmark, metric và cách tái lập.

- [ ] **Step 5: Verify and commit**

Run: `cd phase1 && uv run pytest tests -q`

```bash
git add phase1/src/uav_routing/dynamic/experiment.py phase1/configs/dynamic dataset/solomon_dynamic phase1/tests/dynamic/test_experiment.py phase1/README.md
git commit -m "feat(dynamic): add rolling-horizon benchmark runner, scenarios and docs"
```

Sau task này, gộp `origin/perf/route-local-repair-delta` vào `f/hai` và chạy lại toàn bộ suite trước khi khởi chạy thực nghiệm dài trên SkyPilot.
