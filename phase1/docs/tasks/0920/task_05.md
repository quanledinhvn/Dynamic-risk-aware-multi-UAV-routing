# Task 05: Implement five destroy operators with a common contract

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M2 — Search neighborhoods

**Depends on:** Task 03

**Unlocks:** Task 09

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/src/uav_routing/destroy.py`
- Create: `phase1/tests/test_destroy.py`

**Interfaces:**
- Consumes: current feasible `Solution`, `Instance`, `Evaluator`, one shared `Generator`.
- Produces: `DestroyResult(partial: Solution, removed: tuple[int, ...])` and classes `RandomRemoval`, `WorstRemoval`, `RelatedRemoval`, `RouteRemoval`, `RiskPriorityRemoval`, each implementing `DestroyOperator.apply(solution, instance, evaluator, rng, q) -> DestroyResult`.

- [ ] **Step 1: Write invariant and operator-specific tests**

```python
@pytest.mark.parametrize("operator", all_destroy_operators())
def test_destroy_partitions_customer_set(operator, solution, context):
    result = operator.apply(solution, **context, q=2)
    remaining = [c for route in result.partial.routes for c in route]
    original = [c for route in solution.routes for c in route]
    assert sorted(remaining + list(result.removed)) == sorted(original)
    assert len(remaining) == len(set(remaining))
    assert all(result.partial.routes)

def test_random_removal_is_seed_reproducible(solution, context):
    a = RandomRemoval().apply(solution, **context_with_seed(context, 7), q=2)
    b = RandomRemoval().apply(solution, **context_with_seed(context, 7), q=2)
    assert a == b

def test_route_removal_ignores_q_max_and_removes_whole_route(solution, context):
    result = RouteRemoval().apply(solution, **context, q=2)
    assert tuple(result.removed) in solution.routes

def test_relatedness_combines_four_normalized_terms(instance):
    weights = RelatednessWeights(distance=1, time_window=1, demand=1, risk=1)
    assert relatedness(instance, 1, 2, weights) == pytest.approx(known_value)
```

- [ ] **Step 2: Add importable destroy-operator stubs, then verify behavioral RED**

```python
@dataclass(frozen=True)
class DestroyResult:
    partial: Solution
    removed: tuple[int, ...]

@dataclass(frozen=True)
class RelatednessWeights:
    distance: float
    time_window: float
    demand: float
    risk: float

def relatedness(instance, left_id, right_id, weights) -> float:
    raise NotImplementedError("relatedness is not implemented")

class RandomRemoval:
    name = "random"
    def apply(self, solution, instance, evaluator, rng, q) -> DestroyResult:
        raise NotImplementedError("random removal is not implemented")

class WorstRemoval(RandomRemoval):
    name = "worst"

class RelatedRemoval(RandomRemoval):
    name = "related"

class RouteRemoval(RandomRemoval):
    name = "route"

class RiskPriorityRemoval(RandomRemoval):
    name = "risk_priority"
```

Run: `cd phase1 && python -m pytest tests/test_destroy.py -v`

Expected: module imports and tests collect; relatedness and operator calls fail at their `NotImplementedError` stubs.

- [ ] **Step 3: Implement shared removal plus exact selection policies**

```python
def remove_customers(solution: Solution, selected: Collection[int]) -> DestroyResult:
    selected_set = set(selected)
    routes = tuple(tuple(c for c in route if c not in selected_set) for route in solution.routes)
    return DestroyResult(tuple(route for route in routes if route), tuple(selected))
```

Use `rng.choice` for random seeds and route selection. WorstRemoval ranks marginal route-objective decrease, then samples index `floor(U^p * remaining_count)` with configurable `p=6`. RelatedRemoval normalizes each term by the maximum non-zero pairwise value and repeatedly selects from similarity rank using the same powered index. RiskPriorityRemoval ranks descending priority and samples within that ranking with powered index. Clamp normal destroy count to `min(q, served_customer_count)`; RouteRemoval always removes the selected full route. Never mutate the input solution.

- [ ] **Step 4: Run invariant tests across seeds and the full suite**

Run: `cd phase1 && python -m pytest tests/test_destroy.py -v && python -m pytest tests -q`

Expected: all operators pass partition invariants for seeds 0–19.

- [ ] **Step 5: Commit destroy neighborhoods**

```bash
git add phase1/src/uav_routing/destroy.py phase1/tests/test_destroy.py
git commit -m "feat(phase1): add ALNS destroy operators"
```
