# Task 11: Add the simulate CLI and JSON output

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 5.2

**Milestone:** M4 — Experiments

**Depends on:** Task 10

**Unlocks:** Không có

---

**Files:**
- Create: `phase1/src/uav_routing/dynamic/cli.py`
- Create: `phase1/tests/dynamic/test_cli.py`

**Interfaces:**
- Produces: `python -m uav_routing.dynamic.cli simulate --scenario <json> --policy warm_alns --epoch-length 60 --iterations-epoch0 2000 --iterations-per-epoch 500 --seed 42 [--alpha --beta --trigger --output]`; `simulation_to_dict(result, config, alns) -> dict`.

- [ ] **Step 1: Write CLI smoke tests using the tiny scenario fixture**

```python
def test_simulate_prints_json_with_expected_keys(capsys): ...
def test_simulate_writes_output_atomically(tmp_path): ...
def test_invalid_policy_exits_with_argparse_error(): ...
def test_missing_scenario_file_reports_path(): ...
def test_output_epochs_include_revealed_events_and_locked_count(): ...
```

- [ ] **Step 2: Scaffold `main`, `simulation_to_dict`, verify RED**

Run: `cd phase1 && uv run pytest tests/dynamic/test_cli.py -v`

- [ ] **Step 3: Implement**

JSON gồm:

- `scenario`, `policy`, `seed`, `trigger`, `epoch_length`, `iterations_epoch0`, `iterations_per_epoch`, `total_iterations`, `alpha`, `beta`, `d_ref`;
- `vehicles`, `distance`, `risk_delay`, `objective`, `feasible`, `unserved`, `unserved_priority`, `runtime_seconds`;
- `epochs`: mỗi phần tử có `index`, `time`, `revealed` (số sự kiện theo loại), `locked_customers`, `rejected`, `vehicles`, `objective`, `iterations`, `runtime_seconds`;
- `routes` với lịch phục vụ, tái dùng `_route_to_dict` của `uav_routing.cli`.

Xử lý lỗi qua `parser.error` như CLI Pha 1, thêm `ScenarioFormatError` và `EventApplicationError`. Ghi file nguyên tử bằng `_write_json_atomic`.

- [ ] **Step 4: Verify**

Run: `cd phase1 && uv run pytest tests/dynamic -v && uv run python -m uav_routing.dynamic.cli simulate --scenario tests/dynamic/fixtures/tiny_scenario.json --policy warm_alns --iterations-epoch0 20 --iterations-per-epoch 5 --seed 1`

- [ ] **Step 5: Commit**

```bash
git add phase1/src/uav_routing/dynamic/cli.py phase1/tests/dynamic/test_cli.py
git commit -m "feat(dynamic): add simulate CLI with epoch history JSON"
```
