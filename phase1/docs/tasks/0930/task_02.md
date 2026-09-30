# Task 02: Add SearchConstraints to the Evaluator without changing static results

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 4.3

**Milestone:** M1 — Constraint-aware core

**Depends on:** Task 01

**Unlocks:** Tasks 03, 04, 08

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Modify: `phase1/src/uav_routing/evaluator.py`
- Create: `phase1/tests/test_static_snapshot.py`
- Create: `phase1/tests/dynamic/test_evaluator_constraints.py`

**Interfaces:**
- Consumes: `SearchConstraints`.
- Produces: `Evaluator.route(route, *, departure=0.0)`, `Evaluator.solution(solution, constraints=None)`, vi phạm mới `"locked_prefix"`.

- [ ] **Step 1: Freeze the static behaviour with a snapshot test before touching the evaluator**

```python
def test_static_alns_snapshot_is_unchanged():
    instance = parse_instance(Path("../dataset/solomon_risk/c101.txt"), 25, 5)
    result = run_alns(instance, ALNSConfig(iterations=200, seed=42))

    assert result.best_solution.routes == SNAPSHOT_ROUTES
    assert result.evaluation.vehicle_count == SNAPSHOT_VEHICLES
    assert result.evaluation.objective == pytest.approx(SNAPSHOT_OBJECTIVE, abs=1e-12)
```

Sinh `SNAPSHOT_*` bằng một lần chạy trên `f/quan` trước khi sửa code và dán giá trị vào test. Test này là hàng rào cho toàn bộ M1.

- [ ] **Step 2: Write behavioural tests for constraints in the evaluator**

```python
def test_free_route_departs_at_free_departure():
    instance = make_instance((Customer(1, 3, 4, 1, 0, 100, 0),), max_vehicles=2)
    evaluator = Evaluator(instance, 1.0, 1.0, 0.0)

    late = evaluator.route((1,), departure=40.0)

    assert late.schedule[0].arrival == pytest.approx(45.0)

def test_free_departure_can_make_route_infeasible_by_depot_deadline():
    instance = make_instance((Customer(1, 3, 4, 1, 0, 100, 0),), max_vehicles=2)
    instance = with_depot_due(instance, 20.0)
    evaluator = Evaluator(instance, 1.0, 1.0, 0.0)
    constraints = SearchConstraints(free_departure=15.0)

    assert not evaluator.solution(Solution(((1,),)), constraints).feasible

def test_locked_route_still_departs_at_zero():
    ...  # tuyến k < L có arrival đầu tiên bằng d_{0i}

def test_changed_prefix_reports_locked_prefix_violation():
    constraints = SearchConstraints(locked_prefixes=((1, 2),))
    evaluation = evaluator.solution(Solution(((2, 1, 3),)), constraints)

    assert "locked_prefix" in evaluation.violations

def test_missing_locked_route_reports_locked_prefix_violation():
    constraints = SearchConstraints(locked_prefixes=((1,), (2,)))
    evaluation = evaluator.solution(Solution(((1, 2),)), constraints)

    assert "locked_prefix" in evaluation.violations

def test_none_constraints_matches_default_evaluation():
    assert evaluator.solution(solution) == evaluator.solution(solution, None)
```

- [ ] **Step 3: Add keyword parameters as scaffolds, verify RED**

Thêm `departure: float = 0.0` vào `route()` và `constraints: SearchConstraints | None = None` vào `solution()` nhưng chưa dùng chúng.

Run: `cd phase1 && uv run pytest tests/dynamic/test_evaluator_constraints.py -v`

Expected: test departure và locked_prefix thất bại tại assertion; test tương đương `None` pass.

- [ ] **Step 4: Implement**

- `_build_route_schedule(route, departure)` khởi tạo `departure` từ tham số thay vì `0.0`.
- Trong `solution()`, với `constraints` khác `None`: tuyến `k < locked_route_count` dùng `departure=0.0`, các tuyến còn lại dùng `constraints.free_departure`; kiểm tra `len(routes) >= locked_route_count` và `routes[k][:len(P_k)] == P_k` với mọi `k`, nếu sai thêm `"locked_prefix"` qua `_append_once`.
- Không đổi công thức $D$, $R$, $F$, score.

- [ ] **Step 5: Verify snapshot and full suite, then commit**

Run: `cd phase1 && uv run pytest tests/test_static_snapshot.py tests/dynamic -v && uv run pytest tests -q`

```bash
git add phase1/src/uav_routing/evaluator.py phase1/tests/test_static_snapshot.py phase1/tests/dynamic
git commit -m "feat(evaluator): enforce locked prefixes and free departure via SearchConstraints"
```
