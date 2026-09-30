# Task 09: Project the previous plan and triage the unassigned pool

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 8.1 đến 8.3

**Milestone:** M2 — Dynamic model

**Depends on:** Tasks 04, 07, 08

**Unlocks:** Task 10

---

**Files:**
- Create: `phase1/src/uav_routing/dynamic/projection.py`
- Create: `phase1/tests/dynamic/test_projection.py`

**Interfaces:**
- Consumes: `Evaluator`, `RepairContext`, `RiskPriorityRepair`, `best_insertion`, `SearchConstraints`.
- Produces: `project(solution, instance, evaluator, constraints) -> tuple[Solution, tuple[int, ...]]`, `triage(partial, pool, context) -> tuple[Solution, tuple[int, ...]]`, `lost_customers(instance, rejected, time) -> tuple[int, ...]`.

- [ ] **Step 1: Write behavioural tests**

```python
def test_project_collects_new_customers_into_pool():
    # instance có thêm khách hàng 9 chưa nằm trong solution
    projected, pool = project(solution, instance, evaluator, constraints)

    assert 9 in pool
    assert projected.routes == solution.routes

def test_project_removes_free_customers_until_route_feasible_after_deadline_tightening():
    # deadline của 3 bị siết làm tuyến (1, 2, 3) trễ; 1 bị khóa
    projected, pool = project(Solution(((1, 2, 3),)), tightened, evaluator, locks_1)

    assert pool == (3,)
    assert evaluator.solution(projected, locks_1).violations == ("missing_customers",)

def test_project_never_removes_locked_customers_even_if_late(): ...
def test_project_drops_empty_free_routes_and_keeps_locked_indices(): ...
def test_project_is_noop_without_changes(): ...

def test_triage_inserts_in_priority_then_due_date_order(): ...

def test_triage_reports_uninsertable_customers_without_failing():
    inserted, rejected = triage(partial, (4, 5), context)

    assert rejected == (5,)
    assert context.evaluator.solution(inserted, context.constraints).violations == ("missing_customers",)

def test_triage_result_keeps_locked_prefixes(): ...

def test_lost_customers_are_those_past_latest_launch():
    # lost khi t > l_i - d_{0i}
    ...
```

- [ ] **Step 2: Scaffold, verify RED**

Run: `cd phase1 && uv run pytest tests/dynamic/test_projection.py -v`

- [ ] **Step 3: Implement**

- `project`: loại khách hàng không còn trong `instance`; với tuyến `k`, lặp: đánh giá tuyến với departure phù hợp; nếu vi phạm `customer_due_date` hoặc `depot_due_date`, tháo khách hàng tự do có `due_date` nhỏ nhất (tie-break `id`) rồi lặp lại; đưa vào `pool`. Xóa tuyến tự do rỗng. `pool` gồm khách hàng bị tháo và khách hàng mới, sắp theo `id`.
- `triage`: dùng `RiskPriorityRepair.ordered` để sắp `pool`, chèn từng khách hàng bằng `best_insertion`; không có vị trí thì ghi vào `rejected` và tiếp tục. Không dùng `RepairResult` thất bại vì hành vi cần là chèn được bao nhiêu thì chèn.
- `lost_customers`: `rejected` có $t > l_i - d_{0i}$.

- [ ] **Step 4: Verify**

Run: `cd phase1 && uv run pytest tests/dynamic -v && uv run pytest tests -q`

- [ ] **Step 5: Commit**

```bash
git add phase1/src/uav_routing/dynamic/projection.py phase1/tests/dynamic/test_projection.py
git commit -m "feat(dynamic): project previous plan onto new instance and triage pool"
```
