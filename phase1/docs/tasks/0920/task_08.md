# Task 08: Implement roulette selection and segmented adaptive weights

> **Master plan:** [ALNS Baseline Phase 1 Implementation Plan](../../2026-09-20-alns-baseline-implementation-plan.md)
> **Design spec:** [Thiết kế ALNS baseline cho Pha 1](../../2026-09-19-alns-baseline-design.md)

**Milestone:** M3 — Adaptive search

**Depends on:** Task 01

**Unlocks:** Task 09

**Execution rule:** Hoàn thành tuần tự từng checkbox, chạy đúng lệnh verification và chỉ commit khi toàn bộ bước kiểm tra của task vượt qua.

---

**Files:**
- Create: `phase1/src/uav_routing/adaptive.py`
- Create: `phase1/tests/test_adaptive.py`

**Interfaces:**
- Consumes: named operator sequences and shared `Generator`.
- Produces: `AdaptivePool`, `select(rng)`, `record(name, reward)`, `update_segment()` and serializable `OperatorStats`.

- [ ] **Step 1: Write deterministic selection and update-formula tests**

```python
def test_roulette_uses_normalized_positive_weights():
    pool = AdaptivePool(("a", "b"), initial_weight=1.0, reaction_factor=.2, minimum_weight=.1)
    assert pool.probabilities() == pytest.approx((.5, .5))

def test_segment_update_uses_average_reward_and_resets_counters():
    pool = AdaptivePool(("a",), initial_weight=1.0, reaction_factor=.2, minimum_weight=.1)
    pool.record("a", 20)
    pool.record("a", 0)
    pool.update_segment()
    assert pool.weight("a") == pytest.approx(.8 * 1 + .2 * 10)
    assert pool.segment_count("a") == 0
    assert pool.segment_score("a") == 0

def test_unused_operator_keeps_weight_and_floor_is_enforced():
    pool = AdaptivePool(("a", "b"), 1.0, 1.0, .1)
    pool.record("a", 0)
    pool.update_segment()
    assert pool.weight("a") == .1
    assert pool.weight("b") == 1.0
```

- [ ] **Step 2: Add an importable adaptive-pool stub, then verify behavioral RED**

```python
@dataclass(frozen=True)
class OperatorStats:
    name: str
    weight: float
    total_uses: int
    segment_uses: int
    segment_score: float

class AdaptivePool:
    def __init__(self, names, initial_weight, reaction_factor, minimum_weight):
        self.names = tuple(names)

    def probabilities(self) -> tuple[float, ...]:
        raise NotImplementedError("operator probabilities are not implemented")

    def select(self, rng: np.random.Generator) -> str:
        raise NotImplementedError("roulette selection is not implemented")

    def record(self, name: str, reward: float) -> None:
        raise NotImplementedError("reward recording is not implemented")

    def update_segment(self) -> None:
        raise NotImplementedError("weight update is not implemented")

    def weight(self, name: str) -> float:
        raise NotImplementedError("weight lookup is not implemented")

    def segment_count(self, name: str) -> int:
        raise NotImplementedError("segment count is not implemented")

    def segment_score(self, name: str) -> float:
        raise NotImplementedError("segment score is not implemented")

    def snapshot(self) -> tuple[OperatorStats, ...]:
        raise NotImplementedError("statistics snapshot is not implemented")
```

Run: `cd phase1 && uv run pytest tests/test_adaptive.py -v`

Expected: module imports and tests collect; calls fail at the specific unimplemented adaptive behavior.

- [ ] **Step 3: Implement cumulative-probability selection and updates**

```python
probabilities = weights / weights.sum()
index = int(rng.choice(len(self.names), p=probabilities))
new_weight = (1.0 - rho) * old_weight + rho * (score / count)
self.weights[index] = max(minimum_weight, new_weight)
```

Track both all-run selection count and per-segment count/score. Reject duplicate names, empty pools, non-positive starting/floor weights, and unknown names. `snapshot()` returns name, final weight, total uses, segment uses and segment score in stable input order.

- [ ] **Step 4: Run adaptive tests over a fixed seeded draw sequence**

Run: `cd phase1 && uv run pytest tests/test_adaptive.py -v`

Expected: exact selected-name sequence for seed 42 matches the committed test fixture.

- [ ] **Step 5: Commit adaptive mechanism**

```bash
git add phase1/src/uav_routing/adaptive.py phase1/tests/test_adaptive.py
git commit -m "feat(phase1): add adaptive operator weighting"
```
