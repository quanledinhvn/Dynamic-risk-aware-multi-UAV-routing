# Task 03: Make Evaluator the single feasibility and objective oracle

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M1 — Deterministic problem core

**Depends on:** Task 02

**Unlocks:** Tasks 04, 05 và 06

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/src/uav_routing/evaluator.py`
- Create: `phase1/tests/test_evaluator.py`

**Interfaces:**
- Consumes: `Instance`, `Solution`, `RouteEvaluation`, `SolutionEvaluation`.
- Produces: `Evaluator(instance, d_ref, alpha, beta)`, `Evaluator.route(route)`, `Evaluator.solution(solution)`, `lexicographically_better(left, right) -> bool`.

- [ ] **Step 1: Write tests covering schedule, every hard constraint and objective**

```python
def test_route_schedule_includes_wait_service_and_return(tiny_instance):
    result = make_evaluator(tiny_instance).route((1, 2))
    assert [(s.arrival, s.service_start, s.departure) for s in result.schedule] == pytest.approx([
        (5.0, 10.0, 12.0), (15.0, 15.0, 17.0)
    ])
    assert result.depot_return == pytest.approx(21.0)

@pytest.mark.parametrize("route, violation", [
    ((1, 2), "capacity"), ((3,), "customer_due_date"), ((4,), "depot_due_date")
])
def test_route_rejects_each_hard_constraint(instance_for_violation, route, violation):
    result = make_evaluator(instance_for_violation).route(route)
    assert not result.feasible
    assert violation in result.violations

@pytest.mark.parametrize("routes, violation", [
    (((1,),), "missing_customers"),
    (((1, 2), (2, 3)), "duplicate_customers"),
    (((1,), (2,), (3,)), "vehicle_limit"),
])
def test_solution_checks_completeness_and_vehicle_limit(instance3, routes, violation):
    result = make_evaluator(instance3).solution(Solution(routes))
    assert not result.feasible
    assert violation in result.violations

def test_zero_priority_has_zero_risk_delay(zero_priority_instance):
    result = Evaluator(zero_priority_instance, d_ref=10, alpha=.5, beta=.5).solution(Solution(((1,),)))
    assert result.risk_delay == 0.0
    assert math.isfinite(result.objective)

def test_lexicographic_score_prefers_vehicle_count_before_objective():
    assert lexicographically_better((2, 100.0), (3, 0.0))
    assert lexicographically_better((2, 0.9), (2, 1.0))
```

- [ ] **Step 2: Add an importable evaluator stub, then verify behavioral RED**

```python
class Evaluator:
    def __init__(self, instance: Instance, d_ref: float, alpha: float, beta: float):
        self.instance = instance

    def route(self, route: Route) -> RouteEvaluation:
        raise NotImplementedError("route evaluation is not implemented")

    def solution(self, solution: Solution) -> SolutionEvaluation:
        raise NotImplementedError("solution evaluation is not implemented")

def lexicographically_better(left: tuple[int, float], right: tuple[int, float]) -> bool:
    raise NotImplementedError("score comparison is not implemented")
```

Run: `cd phase1 && python -m pytest tests/test_evaluator.py -v`

Expected: module imports and tests collect; tests fail only when evaluator behavior is invoked.

- [ ] **Step 3: Implement one-pass route scheduling and solution aggregation**

```python
arrival = departure + distance(previous_id, customer_id)
service_start = max(arrival, customer.ready_time)
departure = service_start + customer.service_time
q_i = (service_start - customer.ready_time) / max(1.0, customer.due_date - customer.ready_time)
risk_delay = weighted_delay / total_priority if total_priority > 0 else 0.0
objective = alpha * distance / d_ref + beta * risk_delay
score = (len(solution.routes), objective)
```

Reject `d_ref <= 0`, invalid weights, empty routes, unknown customer ids, repeated or missing customers, excessive route count, capacity violation, customer service start after due date, and depot return after depot due date. Store stable violation codes shown in tests. Build a private `customer_id -> matrix_index` map once in `Evaluator.__init__` so customer ids need not be contiguous.

- [ ] **Step 4: Run evaluator tests and prior tests**

Run: `cd phase1 && python -m pytest tests/test_evaluator.py tests/test_parser.py tests/test_geometry.py tests/test_config.py -v`

Expected: all tests pass; risk delay assertions also verify `0 <= result.risk_delay <= 1` for feasible fixtures.

- [ ] **Step 5: Commit the oracle**

```bash
git add phase1/src/uav_routing/evaluator.py phase1/tests/test_evaluator.py
git commit -m "feat(phase1): add route and solution evaluator"
```
