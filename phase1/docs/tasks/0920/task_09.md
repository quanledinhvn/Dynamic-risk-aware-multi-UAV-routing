# Task 09: Implement acceptance, cooling and the ALNS loop

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M3 — Adaptive search

**Depends on:** Tasks 04, 05, 07, 08

**Unlocks:** Task 10

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/src/uav_routing/alns.py`
- Create: `phase1/tests/test_alns.py`

**Interfaces:**
- Consumes: Tasks 4, 5, 7 and 8 plus `ALNSConfig`.
- Produces: `accept_candidate(current, candidate, temperature, rng) -> Acceptance`; `run_alns(instance, config) -> SearchResult`.

- [ ] **Step 1: Write acceptance branch, cooling, reward and orchestration tests**

```python
def test_fewer_vehicles_is_always_accepted(rng):
    assert accept_score((2, 99), (3, 0), temperature=.01, rng=rng).accepted

def test_more_vehicles_is_always_rejected(rng):
    assert not accept_score((3, 0), (2, 99), temperature=100, rng=rng).accepted

def test_equal_vehicle_improvement_is_accepted(rng):
    assert accept_score((2, .9), (2, 1.0), temperature=.01, rng=rng).kind == "improve"

def test_worse_equal_vehicle_candidate_uses_sa_probability(stub_rng):
    result = accept_score((2, 1.1), (2, 1.0), temperature=.5, rng=stub_rng(value=.1))
    assert result.probability == pytest.approx(math.exp(-.1 / .5))
    assert result.accepted

def test_temperature_respects_floor():
    assert cool_temperature(.01, .5, .008) == .008
```

- [ ] **Step 2: Add importable ALNS function stubs, then verify behavioral RED**

```python
@dataclass(frozen=True)
class Acceptance:
    accepted: bool
    kind: str
    probability: float

@dataclass(frozen=True)
class SearchResult:
    best_solution: Solution
    evaluation: SolutionEvaluation

def accept_score(candidate, current, temperature, rng) -> Acceptance:
    raise NotImplementedError("acceptance is not implemented")

def cool_temperature(temperature: float, cooling_rate: float, minimum: float) -> float:
    raise NotImplementedError("cooling is not implemented")

def run_alns(instance: Instance, config: ALNSConfig) -> SearchResult:
    raise NotImplementedError("ALNS loop is not implemented")
```

Run: `cd phase1 && python -m pytest tests/test_alns.py -v`

Expected: module imports and tests collect; acceptance, cooling and search tests fail at the invoked stub.

- [ ] **Step 3: Implement the exact iteration state machine**

```python
rng = np.random.default_rng(config.seed)
current, d_ref = build_initial_solution(instance, config.alpha, config.beta)
best = current
for iteration in range(config.iterations):
    q = int(rng.integers(config.q_min, config.q_max + 1))
    destroy_op = destroy_pool.select(rng)
    repair_op = repair_pool.select(rng)
    partial = destroy_op.apply(current, instance, evaluator, rng, q)
    repaired = repair_op.apply(partial.partial, partial.removed, repair_context)
    # failed or infeasible repair: reward 0 and keep current
    # successful candidate: acceptance, best update, reward classification
    if (iteration + 1) % config.segment_length == 0:
        destroy_pool.update_segment()
        repair_pool.update_segment()
    temperature = max(config.minimum_temperature, temperature * config.cooling_rate)
```

Reward precedence is best-so-far `20`, current improvement `10`, accepted worse `2`, otherwise `0`; the same reward goes to the selected destroy and repair. A candidate with equal score is accepted but receives `0`. Copy-on-write immutable solutions ensure rejection and repair failure cannot mutate `current`. At exit, reevaluate `best` through a fresh `Evaluator` and raise `SearchInvariantError` if infeasible.

- [ ] **Step 4: Run ALNS unit tests and a 20-iteration small-instance test**

Run: `cd phase1 && python -m pytest tests/test_alns.py -v && python -m pytest tests -q`

Expected: all tests pass; final best score is no worse than the initial score.

- [ ] **Step 5: Commit the search loop**

```bash
git add phase1/src/uav_routing/alns.py phase1/tests/test_alns.py
git commit -m "feat(phase1): implement adaptive large neighborhood search"
```
