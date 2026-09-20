# Task 06: Build the lexicographic insertion engine

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M2 — Search neighborhoods

**Depends on:** Task 03

**Unlocks:** Task 07

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/src/uav_routing/repair.py`
- Create: `phase1/tests/test_insertion.py`

**Interfaces:**
- Consumes: partial `Solution`, `Evaluator`, `Instance`, `d_ref`, weights.
- Produces: `Insertion(customer_id, route_index, position, delta_k, delta_f, solution)`; `feasible_insertions(partial: Solution, customer_id: int, context: RepairContext) -> tuple[Insertion, ...]`; `best_insertion(partial: Solution, customer_id: int, context: RepairContext) -> Insertion | None`.

- [ ] **Step 1: Write insertion enumeration and lexicographic-choice tests**

```python
def test_enumerates_all_feasible_existing_and_new_route_positions(context):
    insertions = feasible_insertions(Solution(((1, 2),)), 3, context)
    assert {(x.route_index, x.position) for x in insertions} == {(0, 0), (0, 1), (0, 2), (1, 0)}

def test_existing_route_beats_cheaper_new_route_because_delta_k_is_primary(context):
    chosen = best_insertion(Solution(((1,),)), 2, context)
    assert chosen.delta_k == 0

def test_new_route_is_absent_at_vehicle_limit(context_at_limit):
    assert all(x.delta_k == 0 for x in feasible_insertions(Solution(((1,), (2,))), 3, context_at_limit))
```

- [ ] **Step 2: Add importable insertion-engine stubs, then verify behavioral RED**

```python
@dataclass(frozen=True)
class Insertion:
    customer_id: int
    route_index: int
    position: int
    delta_k: int
    delta_f: float
    solution: Solution

@dataclass(frozen=True)
class RepairContext:
    instance: Instance
    evaluator: Evaluator
    d_ref: float
    alpha: float
    beta: float

def feasible_insertions(partial: Solution, customer_id: int, context: RepairContext) -> tuple[Insertion, ...]:
    raise NotImplementedError("insertion enumeration is not implemented")

def best_insertion(partial: Solution, customer_id: int, context: RepairContext) -> Insertion | None:
    raise NotImplementedError("best insertion is not implemented")
```

Run: `cd phase1 && uv run pytest tests/test_insertion.py -v`

Expected: module imports and tests collect; insertion calls fail at their stubs rather than during import.

- [ ] **Step 3: Implement route-wide reevaluation for every insertion**

```python
base = context.evaluate_partial(partial)
candidate = insert_customer(partial, customer_id, route_index, position)
route_result = context.evaluator.route(candidate.routes[route_index])
if route_result.feasible:
    delta_k = len(candidate.routes) - len(partial.routes)
    delta_f = context.evaluate_partial(candidate).objective - base.objective
    choices.append(Insertion(customer_id, route_index, position, delta_k, delta_f, candidate))
return tuple(sorted(choices, key=lambda x: (x.delta_k, x.delta_f, x.route_index, x.position)))
```

`RepairContext.evaluate_partial` must compute distance and risk-delay numerator only over assigned customers while using the fixed global `d_ref`; it must call `Evaluator.route` for every affected route and must never treat the partial result as a valid complete candidate. Enumerate a new singleton route only if current route count is below `max_vehicles`.

- [ ] **Step 4: Run insertion tests and evaluator regression suite**

Run: `cd phase1 && uv run pytest tests/test_insertion.py tests/test_evaluator.py -v`

Expected: all tests pass, including a case where insertion shifts a downstream customer past its due date and is excluded.

- [ ] **Step 5: Commit insertion engine**

```bash
git add phase1/src/uav_routing/repair.py phase1/tests/test_insertion.py
git commit -m "feat(phase1): add lexicographic insertion engine"
```
