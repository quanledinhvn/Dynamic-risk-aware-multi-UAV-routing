# Task 03: Make destroy operators respect locked customers

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 4.2 và 8.4

**Milestone:** M1 — Constraint-aware core

**Depends on:** Task 02

**Unlocks:** Task 05

---

**Files:**
- Modify: `phase1/src/uav_routing/destroy.py`
- Create: `phase1/tests/dynamic/test_destroy_constraints.py`

**Interfaces:**
- Consumes: `SearchConstraints`.
- Produces: mọi `DestroyOperator.apply(..., constraints=None)`; `remove_customers(solution, selected, constraints=None)`.

- [ ] **Step 1: Write behavioural tests over all five operators**

```python
OPERATORS = (RandomRemoval(), WorstRemoval(), RelatedRemoval(), RouteRemoval(), RiskPriorityRemoval())

@pytest.mark.parametrize("operator", OPERATORS, ids=lambda op: op.name)
def test_destroy_never_removes_locked_customers(operator):
    solution = Solution(((1, 2, 3), (4, 5)))
    constraints = SearchConstraints(locked_prefixes=((1, 2), (4,)))

    for seed in range(20):
        result = operator.apply(solution, instance, evaluator, np.random.default_rng(seed), 3, constraints)

        assert set(result.removed).isdisjoint({1, 2, 4})
        assert result.partial.routes[0][:2] == (1, 2)
        assert result.partial.routes[1][:1] == (4,)

def test_route_removal_keeps_locked_prefix_and_route_index():
    ...  # chọn tuyến 0, removed == (3,), routes[0] == (1, 2)

def test_destroy_with_only_locked_customers_removes_nothing():
    ...  # partial == solution, removed == ()

def test_empty_free_route_is_dropped_but_locked_routes_keep_indices():
    solution = Solution(((1,), (7, 8), (9,)))
    constraints = SearchConstraints(locked_prefixes=((1,),))
    result = remove_customers(solution, (7, 8), constraints)

    assert result.partial.routes == ((1,), (9,))

@pytest.mark.parametrize("operator", OPERATORS, ids=lambda op: op.name)
def test_destroy_without_constraints_is_unchanged(operator):
    ...  # apply(..., None) trùng apply(...) cũ với cùng seed
```

- [ ] **Step 2: Add the keyword parameter to every operator as a scaffold, verify RED**

Run: `cd phase1 && uv run pytest tests/dynamic/test_destroy_constraints.py -v`

Expected: test khóa thất bại tại assertion; test tương đương `None` pass.

- [ ] **Step 3: Implement**

- Thêm `_free(solution, constraints)` trả các khách hàng không bị khóa theo thứ tự tuyến; mọi operator dùng nó thay `_served` khi `constraints` khác `None`.
- `WorstRemoval` chỉ tính đóng góp cho khách hàng tự do; `RelatedRemoval` chọn hạt giống và ứng viên trong tập tự do; `RiskPriorityRemoval` xếp hạng tập tự do.
- `RouteRemoval` tháo `route[first_free_position(k):]`; nếu tập tự do của tuyến rỗng, chọn tuyến khác có phần tự do; nếu không có, trả `removed=()`.
- `remove_customers` giữ tuyến `k < locked_route_count` kể cả khi phần tự do trống, chỉ xóa tuyến tự do rỗng.

Nhánh `constraints is None` phải giữ nguyên thứ tự lời gọi `rng` để snapshot tĩnh không đổi.

- [ ] **Step 4: Verify**

Run: `cd phase1 && uv run pytest tests/dynamic tests/test_destroy.py tests/test_static_snapshot.py -v && uv run pytest tests -q`

- [ ] **Step 5: Commit**

```bash
git add phase1/src/uav_routing/destroy.py phase1/tests/dynamic/test_destroy_constraints.py
git commit -m "feat(destroy): skip locked customers and preserve locked route indices"
```
