# Task 08: Derive locked prefixes from the executed schedule

> **Master plan:** [Rolling Horizon Phase 2 Implementation Plan](../../2026-09-30-rolling-horizon-implementation-plan.md)
> **Design spec:** [Thiết kế Rolling Horizon cho Pha 2](../../2026-09-30-rolling-horizon-design.md), mục 4.1 và 4.2

**Milestone:** M2 — Dynamic model

**Depends on:** Task 02

**Unlocks:** Task 09

---

**Files:**
- Create: `phase1/src/uav_routing/dynamic/locking.py`
- Create: `phase1/tests/dynamic/test_locking.py`

**Interfaces:**
- Consumes: `Evaluator.solution(solution, constraints)`, `StopSchedule`.
- Produces: `locked_prefixes(solution, instance, evaluator, time, previous) -> SearchConstraints`, `reorder_locked_first(solution, constraints) -> tuple[Solution, SearchConstraints]`.

- [ ] **Step 1: Write behavioural tests on a hand-computed schedule**

Instance: depot $(0,0)$, khách hàng 1 tại $(3,4)$ service 2, khách hàng 2 tại $(6,8)$ service 2, khách hàng 3 tại $(0,10)$, ready time đều $0$. Tuyến $(1,2,3)$ có `departure` tại depot $0$, đến 1 lúc $5$, rời lúc $7$, đến 2 lúc $12$, rời lúc $14$.

```python
@pytest.mark.parametrize("time,expected", [
    (0.0, ()),          # chưa khởi hành: không khóa
    (0.5, (1,)),        # đang bay tới 1
    (6.0, (1,)),        # đang phục vụ 1
    (7.0, (1, 2)),      # vừa rời 1, đã cam kết 2
    (13.0, (1, 2)),
    (14.0, (1, 2, 3)),
    (1e9, (1, 2, 3)),   # toàn tuyến
])
def test_prefix_follows_departure_rule(time, expected):
    constraints = locked_prefixes(Solution(((1, 2, 3),)), instance, evaluator, time, None)

    assert constraints.locked_prefixes == ((expected,) if expected else ())
    assert constraints.free_departure == time

def test_free_routes_evaluated_with_previous_free_departure():
    ...  # tuyến mở ở epoch trước với free_departure=20 chưa khởi hành lúc t=25 → vẫn tự do

def test_previous_locks_are_never_shortened(): ...

def test_reorder_moves_locked_routes_first_preserving_relative_order():
    solution = Solution(((7,), (1, 2), (8, 9), (5,)))
    constraints = locked_prefixes(solution, instance, evaluator, t, None)  # khóa (1,) và (5,)
    reordered, constraints = reorder_locked_first(solution, constraints)

    assert reordered.routes[:2] == ((1, 2), (5,))
    assert constraints.locked_prefixes == ((1,), (5,))
```

- [ ] **Step 2: Scaffold, verify RED**

Run: `cd phase1 && uv run pytest tests/dynamic/test_locking.py -v`

- [ ] **Step 3: Implement**

- Đánh giá `solution` bằng `previous` (ràng buộc của epoch trước, để tuyến tự do có `departure` đúng); với mỗi tuyến, quét `schedule`: khách hàng $i$ bị khóa khi departure của điểm trước nó (depot: departure của tuyến) $\leq t$.
- Tiền tố mới không ngắn hơn tiền tố trong `previous`.
- `reorder_locked_first` đặt các tuyến có tiền tố khác rỗng lên đầu theo thứ tự xuất hiện, tuyến tự do theo sau; trả `SearchConstraints(locked_prefixes, free_departure=t)`.

- [ ] **Step 4: Verify**

Run: `cd phase1 && uv run pytest tests/dynamic -v && uv run pytest tests -q`

- [ ] **Step 5: Commit**

```bash
git add phase1/src/uav_routing/dynamic/locking.py phase1/tests/dynamic/test_locking.py
git commit -m "feat(dynamic): derive locked prefixes from executed schedule"
```
