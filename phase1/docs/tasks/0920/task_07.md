# Task 07: Implement Greedy, Regret-2 and Risk-Priority repair

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M2 — Search neighborhoods

**Depends on:** Task 06

**Unlocks:** Task 09

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Modify: `phase1/src/uav_routing/repair.py`
- Create: `phase1/tests/test_repair.py`

**Interfaces:**
- Consumes: Task 6 insertion engine.
- Produces: `RepairResult(success: bool, solution: Solution | None)` and `GreedyRepair`, `Regret2Repair`, `RiskPriorityRepair` with `name` and `apply(partial, removed, context) -> RepairResult`.

- [ ] **Step 1: Write success, ordering, infinite-regret and atomic-failure tests**

```python
@pytest.mark.parametrize("repair", [GreedyRepair(), Regret2Repair(), RiskPriorityRepair()])
def test_repair_restores_complete_feasible_solution(repair, destroyed, context):
    result = repair.apply(destroyed.partial, destroyed.removed, context)
    assert result.success
    assert context.evaluator.solution(result.solution).feasible

def test_regret2_prioritizes_customer_with_one_best_delta_k_position(context):
    assert Regret2Repair().choose_customer((2, 3), context).customer_id == 3

def test_risk_priority_order_is_priority_due_id(instance):
    assert RiskPriorityRepair().ordered((3, 1, 2), instance) == (2, 3, 1)

def test_failed_repair_is_atomic(partial, context):
    before = partial
    result = GreedyRepair().apply(partial, (99,), context)
    assert result == RepairResult(False, None)
    assert partial == before
```

- [ ] **Step 2: Add importable repair-operator stubs, then verify behavioral RED**

```python
@dataclass(frozen=True)
class RepairResult:
    success: bool
    solution: Solution | None

class GreedyRepair:
    name = "greedy"
    def apply(self, partial, removed, context) -> RepairResult:
        raise NotImplementedError("greedy repair is not implemented")

class Regret2Repair(GreedyRepair):
    name = "regret2"

    def choose_customer(self, removed, context):
        raise NotImplementedError("regret-2 choice is not implemented")

class RiskPriorityRepair(GreedyRepair):
    name = "risk_priority"

    def ordered(self, removed, instance) -> tuple[int, ...]:
        raise NotImplementedError("risk-priority ordering is not implemented")
```

Run: `cd phase1 && uv run pytest tests/test_repair.py -v`

Expected: imports and test collection succeed; operator behavior fails at the shared stub.

- [ ] **Step 3: Implement the three customer-selection policies**

```python
# Greedy: global best pair
choice = min(all_insertions, key=insertion_key)

# Regret-2: compare only insertions at the customer's minimum delta_k
regret = math.inf if len(best_level) == 1 else best_level[1].delta_f - best_level[0].delta_f
customer_choice = max(per_customer, key=lambda x: (x.regret, -x.best.delta_f, -x.customer_id))

# Risk priority: fixed customer order, best insertion for each
ordered = sorted(removed, key=lambda cid: (-priority[cid], customer[cid].due_date, cid))
```

After every insertion, recompute choices against the updated partial solution. If any remaining customer has no feasible insertion when selected, return `RepairResult(False, None)`. On success, call the complete `Evaluator.solution`; return failure if it is not feasible or complete.

- [ ] **Step 4: Run repair and destroy integration tests**

Run: `cd phase1 && uv run pytest tests/test_repair.py tests/test_insertion.py tests/test_destroy.py -v`

Expected: every destroy/repair pair restores the customer set on the small fixture whenever repair reports success.

- [ ] **Step 5: Commit repair neighborhoods**

```bash
git add phase1/src/uav_routing/repair.py phase1/tests/test_repair.py
git commit -m "feat(phase1): add ALNS repair operators"
```
