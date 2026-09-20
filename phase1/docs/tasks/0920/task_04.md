# Task 04: Build the deterministic greedy initial solution

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M1 — Deterministic problem core

**Depends on:** Task 03

**Unlocks:** Task 09

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/src/uav_routing/initial.py`
- Create: `phase1/tests/test_initial.py`

**Interfaces:**
- Consumes: `Instance`; `Evaluator.route()` for insertion feasibility.
- Produces: `build_initial_solution(instance, alpha, beta) -> tuple[Solution, float]`; raises `InitialSolutionError` when construction is impossible.

- [ ] **Step 1: Write ordering, tie-break and infeasibility tests**

```python
def test_initial_customer_order_is_due_risk_id(instance):
    assert ordered_customer_ids(instance) == (2, 3, 1)

def test_initial_solution_is_deterministic_complete_and_feasible(c101_25):
    first, d_ref_1 = build_initial_solution(c101_25, .5, .5)
    second, d_ref_2 = build_initial_solution(c101_25, .5, .5)
    assert first == second
    assert d_ref_1 == d_ref_2
    assert Evaluator(c101_25, d_ref_1, .5, .5).solution(first).feasible

def test_initial_solution_raises_when_vehicle_limit_is_insufficient(impossible_instance):
    with pytest.raises(InitialSolutionError, match="customer 2"):
        build_initial_solution(impossible_instance, .5, .5)
```

- [ ] **Step 2: Add an importable initial-solution stub, then verify behavioral RED**

```python
class InitialSolutionError(RuntimeError):
    pass

def ordered_customer_ids(instance: Instance) -> tuple[int, ...]:
    raise NotImplementedError("initial ordering is not implemented")

def build_initial_solution(instance: Instance, alpha: float, beta: float) -> tuple[Solution, float]:
    raise NotImplementedError("initial construction is not implemented")
```

Run: `cd phase1 && uv run pytest tests/test_initial.py -v`

Expected: module imports and tests collect; ordering and construction calls fail at their stubs.

- [ ] **Step 3: Implement deterministic cheapest-distance insertion**

```python
ordered = sorted(instance.customers, key=lambda c: (c.due_date, -priority[c.id], c.id))
choices.append((distance_delta, route_index, insert_position, candidate_route))
best = min(choices, key=lambda item: item[:3])
```

For each customer, enumerate positions `0..len(route)` in existing routes, keep only routes accepted by `Evaluator.route`, and choose minimum `(distance_delta, route_index, insert_position)`. If none works, test singleton route and append it only while below `max_vehicles`; otherwise raise `InitialSolutionError`. After all insertions, compute route distance sum directly, require it to be positive, assign it to `d_ref`, then run a fresh `Evaluator(instance, d_ref, alpha, beta).solution(solution)` and reject any non-feasible construction.

- [ ] **Step 4: Verify determinism on C101 and full unit suite**

Run: `cd phase1 && uv run pytest tests/test_initial.py -v && uv run pytest tests -q`

Expected: all tests pass; repeated C101 construction has identical routes and `d_ref`.

- [ ] **Step 5: Commit initial construction**

```bash
git add phase1/src/uav_routing/initial.py phase1/tests/test_initial.py
git commit -m "feat(phase1): construct deterministic initial solution"
```
