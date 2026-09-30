# Task 05: Add warm start, constraints and fixed d_ref to run_alns

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 5.1 và 8.4

**Milestone:** M1 — Constraint-aware core

**Depends on:** Tasks 03, 04

**Unlocks:** Task 10

---

**Files:**
- Modify: `phase1/src/uav_routing/alns.py`
- Create: `phase1/tests/dynamic/test_alns_warm_start.py`

**Interfaces:**
- Produces: `run_alns(instance, config, *, initial_solution=None, constraints=None, d_ref=None)`; `ALNSSolver` nhận cùng ba keyword.

- [ ] **Step 1: Write behavioural tests**

```python
def test_default_call_matches_snapshot():
    ...  # tái dùng SNAPSHOT_* của Task 02

def test_initial_solution_is_used_as_starting_point():
    result = run_alns(instance, ALNSConfig(iterations=0, seed=1), initial_solution=warm, d_ref=100.0)

    assert result.initial_solution == warm
    assert result.best_solution == warm
    assert result.d_ref == 100.0

def test_infeasible_initial_solution_is_rejected():
    with pytest.raises(InitialSolutionError):
        run_alns(instance, config, initial_solution=Solution(((1, 1),)), d_ref=10.0)

def test_initial_solution_requires_d_ref():
    with pytest.raises(ValueError):
        run_alns(instance, config, initial_solution=warm)

def test_best_solution_keeps_locked_prefixes_across_search():
    constraints = SearchConstraints(locked_prefixes=((1, 2),), free_departure=20.0)
    result = run_alns(instance, ALNSConfig(iterations=300, seed=3), initial_solution=warm,
                      constraints=constraints, d_ref=d_ref)

    assert result.best_solution.routes[0][:2] == (1, 2)
    assert result.evaluation.feasible

def test_zero_iterations_is_allowed_for_warm_start():
    ...  # ALNSConfig hiện yêu cầu iterations > 0; nới thành >= 0 khi có initial_solution
```

- [ ] **Step 2: Add keyword parameters as scaffolds, verify RED**

Run: `cd phase1 && uv run pytest tests/dynamic/test_alns_warm_start.py -v`

- [ ] **Step 3: Implement**

- `_run_alns`: nếu `initial_solution` là `None`, giữ nguyên `build_initial_solution`; nếu có, yêu cầu `d_ref > 0`, đánh giá bằng `Evaluator(..., constraints)`; nếu không khả thi, `raise InitialSolutionError`.
- `_build_search_resources` tạo `RepairContext(..., constraints=constraints or SearchConstraints())`.
- `_search_step` truyền `constraints` vào `destroy.apply(...)` và dùng `evaluator.solution(candidate, constraints)` trong `_candidate_reward`.
- `_audit_best_solution` dùng `constraints`.
- `ALNSConfig.validate()`: `iterations >= 0`; `run_alns` không có `initial_solution` vẫn yêu cầu `iterations > 0` để hành vi CLI cũ không đổi.
- `SearchResult` giữ nguyên field; `iterations` phản ánh số vòng lặp thực chạy.

- [ ] **Step 4: Verify snapshot, reproducibility and full suite**

Run: `cd phase1 && uv run pytest tests/dynamic tests/test_alns.py tests/test_integration.py tests/test_static_snapshot.py -v && uv run pytest tests -q`

- [ ] **Step 5: Commit**

```bash
git add phase1/src/uav_routing/alns.py phase1/src/uav_routing/config.py phase1/tests/dynamic/test_alns_warm_start.py
git commit -m "feat(alns): accept warm-start solution, search constraints and fixed d_ref"
```
