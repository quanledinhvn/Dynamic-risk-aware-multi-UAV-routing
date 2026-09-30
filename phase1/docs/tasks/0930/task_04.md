# Task 04: Make insertion and repair respect locked prefixes and free departure

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 4.3 và 8.4

**Milestone:** M1 — Constraint-aware core

**Depends on:** Task 02

**Unlocks:** Tasks 05 và 09

---

**Files:**
- Modify: `phase1/src/uav_routing/repair.py`
- Create: `phase1/tests/dynamic/test_repair_constraints.py`

**Interfaces:**
- Consumes: `SearchConstraints`, `Evaluator.route(..., departure=)`, `Evaluator.solution(..., constraints)`.
- Produces: `RepairContext.constraints` (mặc định `SearchConstraints()`); `feasible_insertions`, `best_insertion` và ba repair tôn trọng ràng buộc.

- [x] **Step 1: Write behavioural tests**

```python
def test_insertions_skip_positions_inside_locked_prefix():
    context = make_context(constraints=SearchConstraints(locked_prefixes=((1, 2),)))
    partial = Solution(((1, 2, 3),))

    positions = {(ins.route_index, ins.position) for ins in feasible_insertions(partial, 4, context)}

    assert all(position >= 2 for route_index, position in positions if route_index == 0)

def test_new_route_uses_free_departure():
    context = make_context(constraints=SearchConstraints(free_departure=90.0))
    # khách hàng 4 có due date 50 → tuyến mới không khả thi vì khởi hành lúc 90
    assert all(ins.delta_k == 0 for ins in feasible_insertions(Solution(()), 4, context))

def test_existing_free_route_evaluated_with_free_departure():
    ...  # tuyến k >= L có lịch dịch theo free_departure khi tính delta_f

def test_partial_evaluation_uses_constraints():
    ...  # RepairContext.evaluate_partial gọi evaluator.solution(partial, constraints)

@pytest.mark.parametrize("repair", (GreedyRepair(), Regret2Repair(), RiskPriorityRepair()))
def test_repair_result_keeps_locked_prefixes(repair):
    result = repair.apply(Solution(((1, 2), (5,))), (3, 6), context_with_locks)

    assert result.success
    assert result.solution.routes[0][:2] == (1, 2)
    assert result.solution.routes[1][:1] == (5,)

def test_repair_without_constraints_is_unchanged():
    ...  # RepairContext mặc định cho cùng nghiệm như trước
```

- [x] **Step 2: Add `constraints` to `RepairContext` with default, verify RED**

Run: `cd phase1 && uv run pytest tests/dynamic/test_repair_constraints.py -v`

- [x] **Step 3: Implement**

- `RepairContext.evaluate_partial` truyền `self.constraints` vào `evaluator.solution`.
- `_existing_route_insertions`: bắt đầu `position` từ `constraints.first_free_position(route_index)`; đánh giá `route_result` với `departure = 0.0` nếu `route_index < locked_route_count`, ngược lại `constraints.free_departure`.
- `_new_route_insertion`: đánh giá singleton với `departure = constraints.free_departure`.
- `_complete_result` đánh giá bằng `constraints` để `locked_prefix` được kiểm tra.
- `_valid_removed` thêm điều kiện `set(removed)` không giao với `locked_customers()`.

Không đổi thứ tự sắp xếp `_insertion_key` để hành vi tĩnh giữ nguyên.

- [x] **Step 4: Verify**

Run: `cd phase1 && uv run pytest tests/dynamic tests/test_repair.py tests/test_insertion.py tests/test_static_snapshot.py -v && uv run pytest tests -q`

- [x] **Step 5: Commit**

```bash
git add phase1/src/uav_routing/repair.py phase1/tests/dynamic/test_repair_constraints.py
git commit -m "feat(repair): respect locked prefixes and free departure in insertion"
```
