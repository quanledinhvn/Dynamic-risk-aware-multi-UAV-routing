# Task 10: Implement the rolling-horizon controller and the four policies

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 5 đến 9

**Milestone:** M3 — Controller

**Depends on:** Tasks 05, 09

**Unlocks:** Tasks 11 và 12

---

**Files:**
- Create: `phase1/src/uav_routing/dynamic/policies.py`
- Create: `phase1/src/uav_routing/dynamic/horizon.py`
- Create: `phase1/tests/dynamic/test_policies.py`
- Create: `phase1/tests/dynamic/test_horizon.py`

**Interfaces:**
- Consumes: mọi module Task 05 đến 09.
- Produces: `EpochSolver` protocol; `greedy_insert`, `cold_restart`, `warm_alns`, `solve_clairvoyant(scenario, alns, total_iterations, seed) -> SearchResult`; `run_rolling_horizon(scenario, alns, config, solver=None) -> SimulationResult`; `next_decision_time(time, config, events)`.

- [ ] **Step 1: Write behavioural tests for policies**

```python
def test_greedy_insert_returns_initial_without_search(): ...
def test_warm_alns_starts_from_initial_and_keeps_locks(): ...
def test_cold_restart_rebuilds_free_part_but_keeps_locked_prefixes(): ...
def test_clairvoyant_solves_final_instance_with_total_budget(): ...
```

- [ ] **Step 2: Write behavioural tests for the controller**

```python
def test_empty_scenario_with_zero_epoch_iterations_reproduces_static_solution():
    result = run_rolling_horizon(empty_scenario, alns, replace(config, iterations_per_epoch=0))
    static = run_alns(base_instance(empty_scenario), replace(alns, iterations=config.iterations_epoch0))

    assert result.realized == static.best_solution
    assert result.evaluation.objective == pytest.approx(static.evaluation.objective)

def test_locked_prefix_of_each_epoch_is_prefix_of_next():
    for earlier, later in zip(result.epochs, result.epochs[1:]):
        for k, prefix in enumerate(locks_of(earlier)):
            assert later.solution.routes[k][:len(prefix)] == prefix

def test_events_are_revealed_only_at_or_before_epoch_time(): ...
def test_periodic_trigger_produces_ceil_horizon_over_delta_epochs(): ...
def test_event_trigger_skips_quiet_periods(): ...
def test_same_seed_reproduces_simulation_result(): ...
def test_rejected_customers_are_retried_then_lost(): ...
def test_realized_solution_is_fully_locked_and_feasible(): ...
def test_total_iterations_is_accounted(): ...
def test_frozen_priorities_survive_later_risk_updates(): ...
```

- [ ] **Step 3: Scaffold both modules, verify RED**

Run: `cd phase1 && uv run pytest tests/dynamic/test_policies.py tests/dynamic/test_horizon.py -v`

- [ ] **Step 4: Implement**

- `horizon.py` theo giả mã mục 6: epoch 0 chạy `run_alns` tĩnh với `iterations_epoch0`, lấy `d_ref`; vòng lặp: `next_decision_time`, tiết lộ sự kiện, `locked_prefixes` + `reorder_locked_first`, cập nhật `frozen_priority` cho khách hàng mới khóa, `apply_events`, `project`, thêm `rejected` epoch trước vào `pool` trừ `lost`, `triage`, gọi `solver`, ghi `EpochRecord`.
- Seed mỗi epoch dẫn xuất xác định: `rng_seed = config.seed * 1_000_003 + epoch_index` hoặc qua `np.random.SeedSequence(config.seed).spawn`.
- Instance của epoch loại khách hàng `rejected` để `Evaluator` giữ hard feasibility; `realized` cuối cùng được đánh giá trên instance đầy đủ trừ `unserved`.
- `policies.py`: `warm_alns` gọi `run_alns(instance, replace(alns, iterations=iterations, seed=rng_seed), initial_solution=initial, constraints=constraints, d_ref=d_ref)`; `cold_restart` tháo toàn bộ phần tự do rồi chèn lại bằng `triage` trước khi gọi `warm_alns`; `greedy_insert` trả `initial` với `iterations = 0`; `solve_clairvoyant` áp dụng mọi sự kiện lên $I_0$ (không đóng băng) và chạy `run_alns` với `iterations = iterations_epoch0 + m \cdot iterations_per_epoch`.
- `SimulationResult.runtime_seconds` là tổng runtime các epoch; `epochs` là tuple bất biến.

- [ ] **Step 5: Verify and commit**

Run: `cd phase1 && uv run pytest tests/dynamic -v && uv run pytest tests -q`

```bash
git add phase1/src/uav_routing/dynamic/policies.py phase1/src/uav_routing/dynamic/horizon.py phase1/tests/dynamic
git commit -m "feat(dynamic): add rolling-horizon controller and re-optimization policies"
```
