# Task 10: Lock reproducibility and end-to-end search invariants

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M3 — Adaptive search

**Depends on:** Task 09

**Unlocks:** Tasks 11 và 12

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/tests/test_integration.py`
- Modify: `phase1/src/uav_routing/alns.py`

**Interfaces:**
- Consumes: `parse_instance`, `run_alns`.
- Produces: regression coverage for same-seed reproducibility, different-seed validity, failed-repair isolation and C101 smoke search.

- [ ] **Step 1: Write end-to-end reproducibility tests**

```python
def comparable(result):
    return result.best_solution, result.evaluation, result.operator_stats

def test_same_seed_produces_identical_search_result(c101_25):
    config = replace(ALNSConfig(), iterations=50, seed=123)
    first = run_alns(c101_25, config)
    second = run_alns(c101_25, config)
    assert comparable(first) == comparable(second)

def test_final_solution_is_complete_and_independently_feasible(c101_25):
    result = run_alns(c101_25, replace(ALNSConfig(), iterations=50))
    checked = Evaluator(c101_25, result.d_ref, .5, .5).solution(result.best_solution)
    assert checked.feasible
    assert sorted(flatten(result.best_solution.routes)) == [c.id for c in c101_25.customers]

def test_failed_repair_does_not_change_current_solution(solver_with_failing_repair):
    result = solver_with_failing_repair.run(iterations=1)
    assert result.final_current == result.initial_solution
```

- [ ] **Step 2: Run integration tests before adjustment**

Run: `cd phase1 && uv run pytest tests/test_integration.py -v`

Expected: tests reveal any untracked RNG source, runtime field in equality, mutable state leak or missing final audit.

- [ ] **Step 3: Make reproducible fields explicit**

```python
@dataclass(frozen=True)
class SearchResult:
    initial_solution: Solution
    final_current: Solution
    best_solution: Solution
    d_ref: float
    evaluation: SolutionEvaluation
    iterations: int
    seed: int
    runtime_seconds: float
    operator_stats: tuple[OperatorStats, ...]
```

Exclude only `runtime_seconds` from reproducibility comparison. Search code must not call `random`, `np.random.*` global functions, wall-clock time for decisions, or unordered set/dict iteration for tie-breaking. Sort every equal-cost choice by customer id, route index and position.

- [ ] **Step 4: Run the full suite twice**

Run: `cd phase1 && uv run pytest tests -q && uv run pytest tests -q`

Expected: both runs pass with identical test counts; the same-seed test compares routes, metrics and operator statistics exactly.

- [ ] **Step 5: Commit reproducibility guarantees**

```bash
git add phase1/src/uav_routing/alns.py phase1/tests/test_integration.py
git commit -m "test(phase1): lock ALNS reproducibility invariants"
```
